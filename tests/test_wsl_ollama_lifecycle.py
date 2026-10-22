"""
tests/test_wsl_ollama_lifecycle.py - Autonomous Ollama & WSL Lifecycle Tests
=============================================================================

Tests:
1. is_ollama_reachable detection (mocked + active socket validation).
2. list_installed_models parser.
3. warmup_models non-blocking / safe payload execution.
4. run_startup_diagnostics integrity and reporting.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.ollama_lifecycle import (
    is_ollama_reachable,
    list_installed_models,
    warmup_models,
    warmup_functiongemma,
    initialize_local_brain_lifecycle,
)
from app.diagnostics import run_startup_diagnostics


def test_is_ollama_reachable_mocked_true():
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_url.return_value.__enter__.return_value = mock_resp
        assert is_ollama_reachable("http://127.0.0.1:11434") is True


def test_is_ollama_reachable_mocked_false():
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert is_ollama_reachable("http://127.0.0.1:11434") is False


def test_list_installed_models_parser():
    mock_payload = b'{"models": [{"name": "smollm2:135m"}, {"model": "functiongemma:latest"}]}'
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_url.return_value.__enter__.return_value = mock_resp
        models = list_installed_models()
        assert "smollm2:135m" in models
        assert "functiongemma:latest" in models


def test_warmup_models_execution():
    with patch("app.ollama_lifecycle.list_installed_models", return_value=["smollm2:135m", "functiongemma:latest"]), \
         patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_url.return_value.__enter__.return_value = mock_resp
        res = warmup_models(["smollm2:135m", "functiongemma:latest"])
        assert isinstance(res, dict)
        assert res.get("smollm2:135m") is True


@pytest.mark.asyncio
async def test_initialize_local_brain_lifecycle_offline():
    with patch("app.ollama_lifecycle.is_ollama_reachable", return_value=False), \
         patch("app.ollama_lifecycle.ensure_ollama_running", return_value=False):
        status = await initialize_local_brain_lifecycle(auto_start=False)
        assert status["ollama_running"] is False
        assert status["active_mode"] == "deterministic_fallback"


def test_startup_diagnostics_structure():
    diag = run_startup_diagnostics()
    assert "system" in diag
    assert "dependencies" in diag
    assert "windows_apis" in diag
    assert "ollama_wsl" in diag
    assert "vision" in diag
    assert diag["system"] == "JARVIS OS"
