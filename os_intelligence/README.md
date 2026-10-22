# JARVIS PC-Expert SLM (FunctionGemma 270M)

A specialized Small Language Model (SLM) training pipeline for Windows PC automation intelligence, operating as **Layer 3 (Local Brain)** in the JARVIS 6-layer architecture.

---

## 1. System Architecture & Role

```
[Layer 1: Fast NLP Router]  ---> (Exact regex & embeddings for 0.02ms instant catches)
           |
           v (Unmatched or multi-step requests)
[Layer 3: Local Brain]     ---> **JARVIS PC-Expert SLM (FunctionGemma 270M GGUF)**
           |                    In-process via `llama-cpp-python` (~180MB RAM footprint)
           |                    Breaks tasks into verified OS action trajectories
           v
[Layer 5: UnifiedToolBus]   ---> Win32 native APIs, UI Automation, Keyboard, Mouse, Terminal
           |
           v (Fallback for complex vision/coding)
[Layer 4: Cloud Brain]     ---> Groq / Gemini via PydanticAI
```

### Core Responsibilities
- **Windows OS Fundamentals:** Process lifecycles, HWNDs, foreground window state checks.
- **State-Aware Reasoning:** Inspects tool execution observations (`{"success": bool, "data": ...}`) before issuing next actions.
- **Focus Before Type:** Guarantees target application is foregrounded and active before injecting keystrokes.
- **Anti-Loop Protection:** Never repeats failed commands in a loop; diagnoses errors and pivots or halts.
- **Tool Grounding:** Emits strictly valid tool calls matching the authoritative `UnifiedToolBus` registry schemas.

---

## 2. Directory Layout

```
os_intelligence/
├── configs/
│   └── training_config.yaml       # LoRA, SFTTrainer, and completion loss masking configs
├── data/
│   ├── train.jsonl                # 80% train split (leak-free group partitioned)
│   ├── val.jsonl                  # 10% validation split
│   └── test.jsonl                 # 10% held-out test split
├── training/
│   ├── prepare_dataset.py         # Multi-turn dataset generator across Domains A-E
│   ├── validate_dataset.py        # Schema compliance & leakage separation validator
│   ├── train.py                   # SFT training script (CPU smoke test & GPU cloud modes)
│   ├── evaluate.py                # Deterministic state-aware evaluation & regression suite
│   └── export_gguf.py             # LoRA merge and GGUF quantization for local deployment
├── JARVIS_FunctionGemma_Colab.ipynb # 1-click Google Colab training notebook
└── README.md                      # Pipeline documentation & deployment guide
```

---

## 3. Dataset Specification (Domains A–E)

The dataset contains structured multi-turn trajectories across 5 core automation domains:

| Domain | Focus Area | Example Pattern |
|---|---|---|
| **Domain A: Computer Fundamentals** | Window handles, process lifecycles, minimized/maximized state | `win32_get_foreground_window`, `open_app`, `kill_process` |
| **Domain B: PC Interaction Behavior** | Keystroke injection, context menus, mouse scroll directions | `keyboard_type`, `mouse_scroll`, `mouse_right_click` |
| **Domain C: State-Aware Reasoning** | Differentiating observed vs assumed state; stale window detection | Handling app launch failures, verifying activation |
| **Domain D: Task Planning & Dependencies** | Multi-step causal action chains, stop when verified | Inspect folder -> verify file exists -> read content |
| **Domain E: Failure Recovery** | Diagnosing errors, pivoting without loops, handling missing elements | Terminal safe error recovery, missing UI element recovery |

### Data Quality Guarantees
- **Filtered Tool Schemas:** Each sample only presents 3–10 relevant tool definitions (matching `local_brain.py` runtime filtering).
- **Format Compliance:** Strict FunctionGemma chat format:
  ```
  <start_of_turn>user\nAvailable Tools:\n[...]\n\nTask: ...<end_of_turn>
  <start_of_turn>model\ncall:tool_name{arguments}<end_of_turn>
  <start_of_turn>tool\n{"success": true, "data": ...}<end_of_turn>
  <start_of_turn>model\nTask completed successfully.<end_of_turn>
  ```
- **Zero Leakage:** Train/Val/Test splits are strictly partitioned by `scenario_group`. No variation of a test scenario exists in the training set.

---

## 4. Step-by-Step Execution Guide

### Step 1: Generate & Validate Datasets (Local CPU)
```powershell
# Generate train.jsonl, val.jsonl, test.jsonl
uv run python os_intelligence/training/prepare_dataset.py

# Verify schema compliance, tool definitions, and zero leakage
uv run python os_intelligence/training/validate_dataset.py
```

### Step 2: Validate Training Pipeline (Local CPU)
```powershell
# Validate prompt assembly and completion template without downloading models
uv run python os_intelligence/training/train.py --validate-pipeline
```

### Step 3: Train on GPU (Google Colab / Cloud)
Because FunctionGemma 270M fine-tuning requires a CUDA GPU for optimal convergence, use the included Google Colab notebook:
1. Open `os_intelligence/JARVIS_FunctionGemma_Colab.ipynb` in [Google Colab](https://colab.research.google.com/).
2. Select a free **T4 GPU** runtime (`Runtime -> Change runtime type -> T4 GPU`).
3. Run the notebook to train the LoRA adapter (~10 minutes) and export `functiongemma-270m.gguf`.

Alternatively, if running on a local CUDA machine:
```bash
python os_intelligence/training/train.py --device cuda --hf-token YOUR_HF_TOKEN
```

### Step 4: Export & Quantize to GGUF
```bash
python os_intelligence/training/export_gguf.py \
    --base-model google/functiongemma-270m-it \
    --adapter-path models/functiongemma-270m-jarvis-sft \
    --merged-dir models/functiongemma-270m-merged \
    --gguf-out models/functiongemma-270m.gguf
```

### Step 5: Run Evaluation Suite
```powershell
# Run deterministic state-aware evaluation and regression benchmarks
uv run python os_intelligence/training/evaluate.py
```

---

## 5. Regression Test Benchmarks

The evaluation suite tests against 4 key real-world regressions:

1. **`REG-01-ANTI-LOOP`**: When `terminal_run_safe` returns an error, verify the model never issues the identical command again.
2. **`REG-02-SCROLL`**: Verifies `mouse_scroll` outputs valid directions (`"up"`, `"down"`) and integer clicks.
3. **`REG-03-RIGHT-CLICK`**: Verifies `mouse_right_click` executes cleanly without hallucinated arguments.
4. **`REG-04-FOCUS-BEFORE-TYPE`**: When observation shows another window is active, verifies model activates the target window before calling `keyboard_type`.

---

## 6. Local Deployment in JARVIS

Once `functiongemma-270m.gguf` is placed in `models/functiongemma-270m.gguf`:
- `app/local_brain.py` automatically detects the GGUF file in `auto` mode and activates `llama-cpp-python`.
- Edge execution operates completely offline in-process at sub-500ms latency with ~180MB RAM footprint on Windows 11 CPU.
