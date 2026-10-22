"""
scripts/pull_models.py - Model Provisioning & Cache Manager
===========================================================

Autonomous model pulling and validation for JARVIS:
1. Verifies connectivity to WSL / native Ollama service on 127.0.0.1:11434.
2. Checks and pulls open-source SLMs: 'jarvis:latest' (1.5B) and 'functiongemma:latest' (268M).
3. Preloads models into memory for low-latency inference.
4. Downloads Faster-Whisper ASR models for offline voice recognition.
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.error

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODELS = ["jarvis:latest", "functiongemma:latest"]

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[90m"
RESET = "\033[0m"


def is_service_ready(host: str = DEFAULT_HOST) -> bool:
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_installed_models(host: str = DEFAULT_HOST) -> list:
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("model") or m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def pull_ollama_model(model_name: str, host: str = DEFAULT_HOST) -> bool:
    print(f"  {CYAN}⬇ Pulling model:{RESET} {BOLD}{model_name}{RESET} ...")
    url = f"{host.rstrip('/')}/api/pull"
    payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=300.0) as resp:
            if resp.status == 200:
                elapsed = time.perf_counter() - t0
                print(f"  {GREEN}✔ Installed:{RESET} {BOLD}{model_name}{RESET} ({elapsed:.1f}s)")
                return True
    except Exception as e:
        print(f"  {RED}✘ Failed to pull {model_name}:{RESET} {e}")
    return False


def warmup_ollama_model(model_name: str, host: str = DEFAULT_HOST) -> bool:
    print(f"  {CYAN}⚡ Preloading into memory:{RESET} {BOLD}{model_name}{RESET} ...")
    url = f"{host.rstrip('/')}/api/chat"
    payload = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=45.0) as resp:
            if resp.status == 200:
                elapsed = time.perf_counter() - t0
                print(f"  {GREEN}✔ Model warm in RAM:{RESET} {BOLD}{model_name}{RESET} ({elapsed:.2f}s)")
                return True
    except Exception as e:
        print(f"  {YELLOW}⚠ Warmup ping skipped/timeout:{RESET} {e}")
    return False


def setup_voice_model():
    print(f"\n{BOLD}[2/3] Checking Faster-Whisper Voice Models...{RESET}")
    try:
        from faster_whisper import WhisperModel
        print(f"  {CYAN}⬇ Loading faster-whisper (tiny.en)...{RESET}")
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        WhisperModel("tiny.en", device="cpu", compute_type="int8", download_root=model_path)
        print(f"  {GREEN}✔ Voice model ready in cache:{RESET} {model_path}")
        return True
    except Exception as e:
        print(f"  {YELLOW}⚠ Voice model download skipped:{RESET} {e}")
        return False


def setup_minilm_model():
    print(f"\n{BOLD}[3/3] Checking MiniLM Semantic NLP Model (fastembed)...{RESET}")
    try:
        from fastembed import TextEmbedding
        print(f"  {CYAN}⬇ Initializing all-MiniLM-L6-v2 ONNX cache...{RESET}")
        m = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        list(m.embed(["JARVIS mini-NLP verification"]))
        print(f"  {GREEN}✔ MiniLM model ready and cached in ONNX runtime.{RESET}")
        return True
    except Exception as e:
        print(f"  {YELLOW}⚠ MiniLM model download skipped:{RESET} {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pull & configure AI models for JARVIS")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Ollama server host URL")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="List of Ollama models to pull")
    parser.add_argument("--skip-voice", action="store_true", help="Skip downloading whisper voice models")
    parser.add_argument("--warmup", action="store_true", default=True, help="Preload models into memory")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}             J A R V I S   M O D E L   P R O V I S I O N E R           {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    print(f"{BOLD}[1/2] Connecting to Ollama service ({args.host})...{RESET}")
    if not is_service_ready(args.host):
        print(f"  {RED}✘ Ollama is not reachable at {args.host}!{RESET}")
        print(f"  {YELLOW}Hint: Start Ollama in WSL with: 'ollama serve'{RESET}")
        print(f"  {YELLOW}      or run 'launch_jarvis.ps1' which handles startup automatically.{RESET}\n")
    else:
        installed = get_installed_models(args.host)
        print(f"  {GREEN}✔ Ollama service online.{RESET} Installed models: {BOLD}{', '.join(installed) if installed else 'None'}{RESET}\n")

        for m in args.models:
            if any(m.lower() == inst.lower() for inst in installed):
                print(f"  {GREEN}✔ Model already present:{RESET} {BOLD}{m}{RESET}")
            else:
                pull_ollama_model(m, host=args.host)

            if args.warmup:
                warmup_ollama_model(m, host=args.host)

    if not args.skip_voice:
        setup_voice_model()

    setup_minilm_model()

    print(f"\n{GREEN}{BOLD}✔ All model provisioning steps complete.{RESET}\n")


if __name__ == "__main__":
    main()
