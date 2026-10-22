# JARVIS OS Codebase Refactoring & Cleanup Audit Report

**Date**: 2026-10-19  
**Auditor**: Senior Systems Architect & Refactoring Engineer  
**Repository**: `jarvis` (JARVIS OS v0.7)  

---

## 1. Repository Architecture Summary

JARVIS OS is organized into an asynchronous, capability-oriented Windows assistant:

```mermaid
flowchart TD
    UI[Voice Stream / CLI Input] --> Router[Layer 1: NLP Router (app/router.py)]
    Router -->|is_direct = True| Bus[UnifiedToolBus (app/tools/bus.py)]
    Router -->|is_direct = False| LocalBrain[Layer 1.5: FunctionGemma Local Brain (app/local_brain.py)]
    LocalBrain -->|Tools Proposed| Bus
    LocalBrain -->|No Tools / Ambiguous| Agent[Layer 2: PydanticAI Reasoning Agent (app/agent.py)]
    Agent --> Bus
    Bus --> Permissions[PermissionEngine (app/permissions.py)]
    Bus --> Executors[Authoritative Tool Executors]
    Executors --> OS[Windows API / UIA / Process / Playwright]
```

### Core Components
* **`app/core.py` (`JarvisCore`)**: Central coordinator orchestrating the request lifecycle.
* **`app/router.py`**: Heuristic command parsing, delimiter splitting, and pronoun context tracking. Pure deterministic actions execute in <1ms without LLM overhead.
* **`app/local_brain.py` (`FunctionGemmaLocalBrain`)**: Bridges Layer 1 and Layer 2 via local Ollama. Converts schemas from `UnifiedToolBus`, validates arguments, and executes structured tool loops.
* **`app/agent.py`**: Layer 2 reasoning agent for multi-turn conversational or planning tasks.
* **`app/model.py`**: Authoritative model provider configuration (Ollama, Groq, Gemini, DeepSeek).
* **`app/tools/bus.py` (`UnifiedToolBus`)**: Single authoritative tool registry, executor, permission checker, and retry/timeout engine.
* **`app/tools/registry.py`**: Central registry wiring 60 tools across system, windows, terminal, process, macro, UIA, browser, vision, and wifi domains.
* **`app/voice/`**: Streaming audio pipeline (`manager.py`, `stt.py` INT8 Faster-Whisper, `vad.py` Silero ONNX, `tts.py`).

---

## 2. Duplicate Files Identified

| File Path | Duplicate / Overlap Of | Evidence & Callers | Category |
| :--- | :--- | :--- | :--- |
| `tracer.py` | `profiler.py` | Line-by-line identical to `profiler.py` with hardcoded Groq provider overrides (`TracingCore` vs `ProfilingCore`). | **SAFE** to consolidate |
| `validate_nlp_and_mini_models.py` | `tests/test_nlp_mini_model_opt.py` | Standalone script whose entire test suite was ported into `TestNLPRouterValidation` and `TestMiniAIModelOptimization` in pytest. | **SAFE** to consolidate |
| `run_verification.py` | `tests/test_router.py` | 25-line scratch script testing pronoun resolution; identical assertions exist in `test_router.py::test_match_direct_command_pronoun_resolution`. | **SAFE** to remove |
| `app/tools/browser.py` | `app/tools/advanced_browser/` | Legacy Playwright browser controller (204 lines). `app/tools/registry.py` exclusively registers `PlaywrightBrowserController` from `advanced_browser/`. Only referenced in outdated `test_integration_v0_5_1.py`. | **CAUTION** |
| `app/tools/windows_ui.py` | `app/tools/window_manager.py` | 68-line early UIAutomation script. `app/tools/registry.py` uses native Win32 `window_manager.py` and `app/tools/computer/windows.py`. Only referenced in ad-hoc scripts `get_tree.py` and `manual_test_uia.py`. | **CAUTION** |

---

## 3. Duplicate Functions, Classes & Inconsistencies

1. **`app/agent.py` Model Provider Inconsistency**:
   * **Issue**: `app/agent.py` imports `get_router_model()` from `app.router`, which is an obsolete stub returning `None`.
   * **Evidence**: When `get_agent()` initializes `Agent(get_router_model(), ...)`, it passes `None`, leading to a crash if Layer 2 is invoked without monkey-patching.
   * **Solution**: `get_agent()` should import `get_model()` from `app.model` or `get_router_model()` in `router.py` must delegate to `app.model.get_model()`.
   * **Category**: **SAFE** to fix.

2. **`app/permissions.py` Dead Code**:
   * **Issue**: Lines 38–62 of `check_permission` are completely unreachable due to an unconditional `return True` on line 36.
   * **Evidence**:
     ```python
     # Override for testing/development (similar to V0.4 disablement)
     return True
     
     if decision == PermissionDecision.ALLOW:  # Dead code below
         allowed = True
     ...
     ```
   * **Solution**: Clean up unreachable dead code or wrap the development bypass cleanly.
   * **Category**: **SAFE** to fix.

3. **`pytest.ini` & `sys.path` Configuration**:
   * **Issue**: Running pytest or inline Python from subdirectories (e.g. `cd app` or `cd ..`) yields `ModuleNotFoundError: No module named 'app'`.
   * **Evidence**: User reproduction: `python -m pytest tests/test_local_brain.py` failed when executed from `jarvis/app`.
   * **Solution**: Add `pythonpath = .` to `jarvis/pytest.ini` and root `pytest.ini` so test runners and imports resolve `app` deterministically regardless of working directory.
   * **Category**: **SAFE** to fix.

4. **`app/voice/hud.py` Missing Dependency**:
   * **Issue**: `hud.py` imports `PyQt6`, which is not installed in the environment (`PyQt6: NOT INSTALLED`).
   * **Evidence**: The project uses `tkinter_gui.py` (built with standard library `tkinter`) as the actual working HUD.
   * **Category**: **KEEP / CAUTION** (Retain as reference; document missing optional dependency).

---

## 4. Audit Table: Detailed Risk Assessment

| Target Item | Type | Risk Level | Rationale & Recommendation |
| :--- | :--- | :--- | :--- |
| `tracer.py` | File | **SAFE** | Duplicate fork of `profiler.py`. Merge any unique tracer metric options into `profiler.py` and remove redundant file. |
| `run_verification.py` | File | **SAFE** | One-off 25-line scratch verification script. All checks are fully verified by `tests/test_router.py`. |
| `validate_nlp_and_mini_models.py` | File | **SAFE** | Standalone runner entirely mirrored in `tests/test_nlp_mini_model_opt.py`. |
| `app/permissions.py` (lines 38-62) | Dead Code | **SAFE** | Unreachable code block following early `return True`. Clean up dead block while preserving bypass. |
| `app/agent.py` (`get_router_model`) | Defect/Dead Ref | **SAFE** | Link `get_agent()` to `app.model.get_model()` so the Layer 2 agent has a valid model provider. |
| `jarvis/pytest.ini` & `pytest.ini` | Config | **SAFE** | Add `pythonpath = .` to ensure seamless test execution from any directory. |
| `app/tools/windows_ui.py` | File | **CAUTION** | Unused by `registry.py`, but imported by `manual_test_uia.py`. Consolidate or deprecate cleanly. |
| `app/tools/browser.py` | File | **CAUTION** | Superseded by `app/tools/advanced_browser/`. Only referenced in legacy integration test. |
| `app/tools/computer/` (unused classes) | Classes | **KEEP** | Companion classes in `computer/` (`ApplicationController`, `SystemInfoProvider`, `ScreenController`) belong to a cohesive OOP adapter design. Do not strip. |
| `models/OmniParser/` | Directory | **KEEP** | Specialized 3rd-party local vision parsing repository. Do not modify or delete. |
| `app/voice/wake_word.py` | File | **KEEP** | Architecture placeholder interface for openwakeword. Retain as extension interface. |
| `test_report.json`, `whatsapp_tree.json` | Data / Logs | **KEEP** | User-generated test artifacts. Retain per user guidelines. |
| `jarvis.log`, `*.txt` | Output Logs | **KEEP** | User execution logs. Do not delete. |

---

## 5. Phased Cleanup Plan

* **Step 1**: Fix `pytest.ini` paths so pytest and Python imports work cleanly from both repository root and `jarvis/`.
* **Step 2**: Remove redundant standalone scratch scripts (`tracer.py`, `run_verification.py`, `validate_nlp_and_mini_models.py`). Ensure all profiling features remain available via `profiler.py`.
* **Step 3**: Fix the model provider linkage in `app/agent.py` and `app/router.py` to route to `app/model.py::get_model`.
* **Step 4**: Clean up the dead code block in `app/permissions.py`.
* **Step 5**: Run the full pytest test suite (17 existing tests + 15 local brain tests = 32 tests) to verify 100% pass rate.

---

## 6. Execution & Verification Results

* **Files Deleted**:
  * `jarvis/tracer.py` (duplicate profiler script, 132 lines removed)
  * `jarvis/run_verification.py` (redundant scratch script, 25 lines removed)
  * `jarvis/validate_nlp_and_mini_models.py` (redundant test runner, 145 lines removed)
* **Code Cleaned & Consolidated**:
  * `app/permissions.py`: Removed 25 lines of dead/unreachable code following early `return True`.
  * `app/agent.py`: Swapped obsolete stub `get_router_model()` for `app.model.get_model()`.
  * `app/router.py`: Delegated `get_router_model()` stub to `app.model.get_model()` for backward compatibility.
  * `app/local_brain.py`: Added automatic lazy tool registration in `_refresh_schema_cache()` when the registry is empty, enabling seamless direct CLI usage.
  * `jarvis/pytest.ini` & root `pytest.ini`: Added `pythonpath` configurations preventing `ModuleNotFoundError` across environments.
* **Test Verification**:
  * Full suite: **32 passed, 0 failed in 69.29s**.
  * Standalone CLI test: `res = asyncio.run(local_brain.run_tool_loop('What wifi networks are currently visible?'))` passed with 2 executed tools and zero errors.

