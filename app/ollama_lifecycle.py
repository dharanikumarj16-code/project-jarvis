"""
app/ollama_lifecycle.py - Autonomous Service Management for Ollama and FunctionGemma
===================================================================================

Ensures:
1. Automatic detection of whether Ollama is running on localhost.
2. Background startup of the Ollama service via Windows native or WSL if missing.
3. Verification that FunctionGemma is installed and available, with automated pull capability.
4. Single-instance model initialization, reuse, and warmup.
5. Graceful fallback to deterministic NLP router if Ollama or FunctionGemma is unavailable.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional

from app.config import config

logger = logging.getLogger("jarvis.ollama_lifecycle")

DEFAULT_OLLAMA_HOST = getattr(config, "ollama_host", "http://127.0.0.1:11434")
DEFAULT_MODEL = getattr(config, "local_brain_model", "functiongemma:latest")
DEFAULT_REASONING_MODEL = getattr(config, "reasoning_model", "smollm2:135m")


def is_ollama_reachable(host: str = DEFAULT_OLLAMA_HOST, timeout: float = 1.5) -> bool:
    """Check whether the Ollama API responds on the configured host."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_ollama_service() -> bool:
    """Launch the Ollama daemon via native Windows executable or WSL (avoiding duplicate instances)."""
    # Check if already running and reachable
    if is_ollama_reachable():
        logger.info("Ollama is already running and reachable.")
        return True

    logger.info("Attempting to automatically start Ollama service...")

    creation_flags = 0
    if os.name == "nt":
        # Detach process so it continues running independently of this Python process
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000  # CREATE_NO_WINDOW

    # 1. Try native Windows 'ollama.exe'
    ollama_path = shutil.which("ollama")
    if ollama_path:
        try:
            logger.info(f"Starting native Ollama via '{ollama_path} serve'...")
            subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            return True
        except Exception as e:
            logger.warning(f"Native Ollama start failed: {e}")

    # 2. Try WSL 'wsl bash -c "OLLAMA_HOST=0.0.0.0:11434 nohup ollama serve ..."'
    wsl_path = shutil.which("wsl")
    if wsl_path:
        try:
            logger.info("Starting Ollama inside WSL with OLLAMA_HOST=0.0.0.0:11434...")
            cmd = [
                wsl_path,
                "bash",
                "-c",
                "OLLAMA_HOST=0.0.0.0:11434 nohup /usr/local/bin/ollama serve > /tmp/ollama.log 2>&1 &"
            ]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            return True
        except Exception as e:
            logger.warning(f"WSL Ollama start failed: {e}")

    return False


async def ensure_ollama_running(host: str = DEFAULT_OLLAMA_HOST, wait_timeout: float = 8.0) -> bool:
    """Verify Ollama is reachable, starting it automatically if needed."""
    if is_ollama_reachable(host):
        return True

    started = start_ollama_service()
    if not started:
        return False

    # Poll until ready or timeout
    start_time = time.monotonic()
    while time.monotonic() - start_time < wait_timeout:
        await asyncio.sleep(0.5)
        if is_ollama_reachable(host):
            logger.info("Ollama service successfully started and reachable.")
            return True

    logger.warning("Timed out waiting for Ollama service to become ready.")
    return False


def list_installed_models(host: str = DEFAULT_OLLAMA_HOST) -> List[str]:
    """Retrieve list of currently installed models in Ollama."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            return [m.get("model") or m.get("name", "") for m in models]
    except Exception as e:
        logger.debug(f"Failed to query model list: {e}")
        return []


def pull_model_if_missing(model_name: str = DEFAULT_MODEL, host: str = DEFAULT_OLLAMA_HOST) -> bool:
    """Pull the target model via Ollama HTTP API if it is not present."""
    models = list_installed_models(host)
    model_lower = model_name.lower()
    base_name = model_lower.split(":")[0]

    for m in models:
        m_l = m.lower()
        if m_l == model_lower or m_l.startswith(base_name):
            logger.info(f"Target model '{model_name}' is already installed ({m}).")
            return True

    logger.info(f"Model '{model_name}' not found locally. Initiating automated pull...")
    url = f"{host.rstrip('/')}/api/pull"
    payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180.0) as resp:
            if resp.status == 200:
                logger.info(f"Successfully pulled model '{model_name}'.")
                return True
    except Exception as e:
        logger.warning(f"Could not pull model '{model_name}': {e}")

    return False


def warmup_models(models: List[str], host: str = DEFAULT_OLLAMA_HOST, timeout: float = 12.0) -> Dict[str, bool]:
    """Preload models into RAM to avoid cold-start latency on user queries."""
    results: Dict[str, bool] = {}
    installed = list_installed_models(host)

    for model in models:
        matched = None
        m_lower = model.lower()
        for inst in installed:
            if inst.lower() == m_lower or inst.lower().startswith(m_lower.split(":")[0]):
                matched = inst
                break

        if not matched:
            results[model] = False
            continue

        url = f"{host.rstrip('/')}/api/chat"
        payload = json.dumps({
            "model": matched,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(f"Model '{matched}' preloaded and resident in RAM ({elapsed_ms:.1f}ms).")
                results[matched] = (resp.status == 200)
        except Exception as e:
            logger.debug(f"Preload ping for '{matched}' skipped: {e}")
            results[matched] = False

    return results


def warmup_functiongemma(model_name: str = DEFAULT_MODEL, host: str = DEFAULT_OLLAMA_HOST) -> bool:
    """Initialize and warm up FunctionGemma with a lightweight dummy query."""
    res = warmup_models([model_name], host=host)
    return any(res.values())


async def initialize_local_brain_lifecycle(
    host: str = DEFAULT_OLLAMA_HOST,
    model_name: str = DEFAULT_MODEL,
    auto_start: bool = True,
    auto_pull: bool = True,
    additional_models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Autonomous bootstrap sequence for local LLM routing with WSL and multi-model support."""
    status: Dict[str, Any] = {
        "ollama_running": False,
        "model_available": False,
        "warmed_up": False,
        "active_mode": "deterministic_fallback",
        "model_name": model_name,
        "host": host,
        "installed_models": [],
        "preloaded_models": {},
    }

    # 1. Check or start Ollama
    if auto_start:
        status["ollama_running"] = await ensure_ollama_running(host)
    else:
        status["ollama_running"] = is_ollama_reachable(host)

    if not status["ollama_running"]:
        logger.info("Ollama is not running. Operating in 100% deterministic NLP fallback mode.")
        return status

    # List all installed models
    status["installed_models"] = list_installed_models(host)

    # 2. Check or pull target model
    if auto_pull:
        status["model_available"] = pull_model_if_missing(model_name, host)
    else:
        status["model_available"] = any(model_name.lower() in m.lower() for m in status["installed_models"])

    if not status["model_available"]:
        logger.info(f"Model '{model_name}' not available. Operating in deterministic NLP fallback mode.")
        return status

    # 3. Preload and warm up models
    to_preload = [model_name]
    if additional_models:
        to_preload.extend(additional_models)

    status["preloaded_models"] = warmup_models(to_preload, host)
    status["warmed_up"] = any(status["preloaded_models"].values())
    status["active_mode"] = "gemma_slm"
    return status
