# ⚡ JARVIS OS — Next-Gen Windows AI & Native OS Automation

[![CI Pipeline](https://github.com/dharanikumarj16-code/project-jarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/dharanikumarj16-code/project-jarvis/actions)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%2B%20WSL2-0078D6.svg)](https://learn.microsoft.com/en-us/windows/wsl/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

**JARVIS OS** is a high-performance Windows automation agent and AI system operator. Built with an accessibility-first, deterministic architecture, it executes computer operations through native Windows APIs (Win32, COM, UIAutomation, DirectInput) with zero unnecessary LLM calls, sub-millisecond routing latency, and hybrid SLM inference via Ollama in WSL.

---

## 🏛️ Architecture: Multi-Layer Execution Pipeline

```
User Voice / Text Intent
          │
          ▼
┌────────────────────────────────────────────────────────┐
│  Layer 1: Fast-Path NLP Router (<0.1ms Direct)        │
│  • Maps 45+ verbs (apps, audio, power, windowing)      │
│  • Contextual coreference resolution ("it", "that")    │
│  • Bypasses LLMs entirely for deterministic tasks      │
└─────────────────────────┬──────────────────────────────┘
                          │ complex / ambiguous
                          ▼
┌────────────────────────────────────────────────────────┐
│  Layer 2: Mini-NLP Semantic Retrieval (fastembed ONNX) │
│  • all-MiniLM-L6-v2 ONNX embeddings (<2ms)             │
│  • Dense exemplar vector matching & top-k ranking      │
└─────────────────────────┬──────────────────────────────┘
                          │ parametric reasoning
                          ▼
┌────────────────────────────────────────────────────────┐
│  Layer 3: Local Dual-SLM Brain (WSL Ollama)            │
│  • Reasoning & Task Planning : smollm2:135m            │
│  • Tool & Function Calling   : functiongemma:latest    │
│  • Single-instance preloaded RAM residency             │
└─────────────────────────┬──────────────────────────────┘
                          │ multi-step planning / web
                          ▼
┌────────────────────────────────────────────────────────┐
│  Layer 4: Cloud LLM Fallback (PydanticAI Gateway)      │
│  • Gemini 2.5 Pro / Flash, Groq, DeepSeek              │
│  • Dynamic tool injection & category filtering         │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (One-Click)

### Option 1: Double-Click Launcher
Double-click **`start_jarvis.bat`** from Windows Explorer.  
It automatically binds to the Python virtual environment, verifies the WSL Ollama service, and launches JARVIS.

### Option 2: PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File .\launch_jarvis.ps1
```

---

## 📦 Setup & Installation (From Source)

### 1. Clone the Repository
```bash
git clone https://github.com/dharanikumarj16-code/project-jarvis.git
cd project-jarvis
```

### 2. Set Up Virtual Environment & Dependencies
We recommend using **`uv`** for blazingly fast installation, or standard `pip`:

```bash
# Using uv (Recommended)
uv venv .venv
uv pip install -r requirements.txt

# Or using standard pip
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Pull & Cache Open-Source AI Models
Run the automated model provisioner to verify WSL Ollama and download required open-source models:

```bash
.\.venv\Scripts\python scripts/pull_models.py
```
This script automatically:
* Connects to Ollama on `127.0.0.1:11434`
* Verifies / pulls **`smollm2:135m`** (Reasoning & Planning) & **`functiongemma:latest`** (Tool Calling)
* Caches **`all-MiniLM-L6-v2`** for semantic intent matching
* Downloads **`faster-whisper-tiny.en`** for local speech-to-text

### 4. Configure Environment (Optional)
Copy `.env.example` to `.env` to configure optional cloud LLM providers:
```bash
copy .env.example .env
```
Edit `.env`:
```ini
# Primary Model Provider: 'ollama', 'google', 'groq', or 'deepseek'
JARVIS_MODEL_PROVIDER=ollama
JARVIS_MODEL=smollm2:135m

# Optional Cloud API Keys
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

# Local SLM & WSL Configuration
JARVIS_OLLAMA_HOST=http://127.0.0.1:11434
JARVIS_REASONING_MODEL=smollm2:135m
JARVIS_LOCAL_BRAIN_MODEL=functiongemma:latest
```

---

## 🐧 WSL Ollama Integration

Ollama runs inside WSL2 (`Ubuntu-24.04`) and exposes its REST API to Windows:

```bash
# Inside WSL Ubuntu:
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

JARVIS automatically verifies connectivity to `http://127.0.0.1:11434`, preloads models into memory on startup, and gracefully falls back to 100% deterministic local Fast-Path NLP if the service is stopped.

---

## 🧪 Testing & Validation

Run the complete automated test suite across all subsystems:

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Test Coverage Highlights:
* `test_wsl_ollama_lifecycle.py`: WSL Ollama bridge, service auto-start, model preloading, health diagnostics.
* `test_system_platform_optimization.py`: System & platform telemetry, COM/UIA safety, window management.
* `test_nlp_mini_model_opt.py`: Sub-millisecond router benchmarks & small model JSON recovery.
* `test_tri_paradigm_automation.py`: Deterministic fast-path + local SLM + cloud fallback validation.
* `test_action_patterns.py`: Keyboard, mouse, and multi-step action sequences.

---

## 🛡️ Key Features

* **Sub-Millisecond Execution:** Deterministic Fast-Path NLP handles commands in `<0.1ms`.
* **Zero Window Stealing:** Native Windows API integration checks state before acting.
* **Smart Window Focus & Recovery:** High-reliability focus management using `SetForegroundWindow`, `AttachThreadInput`, and COM UIAutomation.
* **Offline Resilience:** Functions completely offline with local Fast-Path NLP and WSL Ollama SLMs.
* **Built-in Startup Diagnostics:** Real-time dashboard verifying OS APIs, vision/OCR engines, and models on launch.

---

## 📄 License
Apache License 2.0. See [LICENSE](LICENSE) for details.
