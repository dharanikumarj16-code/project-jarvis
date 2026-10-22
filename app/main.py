"""
main.py  –  JARVIS CLI entry point
====================================

Two-layer request pipeline:
    ┌─────────────────────────────────────────────────────┐
    │  Layer 1 – NLP Router  (router.py)                  │
    │  • Splits input on &&, ;, comma, newline, "and"     │
    │  • Maps 40+ verbs to tools directly                 │
    │  • Resolves pronouns ("it", "that") from context    │
    │  • Executes simple steps without calling an LLM     │
    └──────────────────────┬──────────────────────────────┘
                           │ complex / unknown verbs
                           ▼
    ┌─────────────────────────────────────────────────────┐
    │  Layer 2 – LLM Agent  (agent.py + core.py)         │
    │  • PydanticAI agent with dynamic tool loading      │
    │  • Filters tools by category hint from Layer 1     │
    │  • Falls back gracefully when no model configured  │
    └─────────────────────────────────────────────────────┘
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Ensure the jarvis package root is importable when running from jarvis/app/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mcp_client import FileSystemMCPClient
from app.core import JarvisCore
from app.router import ExecutionContext, plan_user_input


# Enable Virtual Terminal Processing for Windows consoles to support ANSI colors
os.system("")

# ---------------------------------------------------------------------------
# High-tech Cyber Terminal Theme
# ---------------------------------------------------------------------------
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[90m"
RESET = "\033[0m"


def _banner():
    print(f"{CYAN}{BOLD}")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                     J  A  R  V  I  S   O S                           ║")
    print("║             Next-Gen Windows AI & Voice Automation                   ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║  {GREEN}⚡ Layer 1   {CYAN}: Fast-Path NLP Router    {DIM}(<0.1ms direct execution)     {CYAN}║")
    print(f"║  {MAGENTA}🧠 Layer 1.5 {CYAN}: FunctionGemma Brain     {DIM}(Local Ollama tool caller)   {CYAN}║")
    print(f"║  {BLUE}🌐 Layer 2   {CYAN}: Agentic Cloud Fallback  {DIM}(PydanticAI LLM)             {CYAN}║")
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║  {DIM}Type in plain English (e.g. 'press ctrl+n', 'scroll down', 'exit')  {CYAN}║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(RESET)


def _routing_hint(user_input: str) -> str:
    """Return a styled routing preview shown before execution."""
    ctx = ExecutionContext()
    steps = plan_user_input(user_input, ctx)
    if not steps:
        return f"  {BLUE}🌐 [Layer 2 → LLM Agent]{RESET}"
    all_direct = all(s.is_direct for s in steps)
    if all_direct:
        tools = ", ".join(f"{CYAN}{s.tool_name or '?'}{RESET}" for s in steps)
        return f"  {GREEN}⚡ [Layer 1 → {tools}{GREEN}]{RESET}"
    direct = [s for s in steps if s.is_direct]
    complex_ = [s for s in steps if not s.is_direct]
    parts = []
    if direct:
        parts.append(f"{GREEN}Layer 1 ({len(direct)} direct){RESET}")
    if complex_:
        cats = {c for s in complex_ for c in s.categories}
        parts.append(f"{BLUE}Layer 2 (LLM: {', '.join(sorted(cats))}){RESET}")
    return f"  [{' + '.join(parts)}]"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def agent_loop():
    # Initialize Windows COM for the current event loop thread
    try:
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
    except Exception:
        pass
    try:
        from app.tools.uia import ensure_com_initialized
        ensure_com_initialized()
    except Exception:
        pass

    sandbox_dir = "C:\\"

    _banner()

    # Run startup health checks and diagnostics
    from app.diagnostics import run_startup_diagnostics, print_startup_dashboard
    diag = run_startup_diagnostics()
    print_startup_dashboard(diag)

    # Connect MCP filesystem client
    mcp_client = FileSystemMCPClient(sandbox_dir)
    try:
        await mcp_client.connect()
        print(f"  {GREEN}✔{RESET} {BOLD}MCP Filesystem{RESET} : {DIM}sandbox={sandbox_dir}{RESET}")
    except Exception as e:
        print(f"  {YELLOW}⚠ MCP connect failed{RESET}: {DIM}{e} (filesystem tools unavailable){RESET}")
        mcp_client = None

    # Check / start Ollama & verify FunctionGemma model readiness
    from app.ollama_lifecycle import initialize_local_brain_lifecycle
    brain_status = await initialize_local_brain_lifecycle(additional_models=["qwen2.5-coder:1.5b"])
    if brain_status.get("ollama_running") and brain_status.get("model_available"):
        print(f"  {GREEN}✔{RESET} {BOLD}Local Brain SLM{RESET}: {DIM}model={brain_status['model_name']} ({brain_status['host']}) [Preloaded]{RESET}\n")
    else:
        print(f"  {YELLOW}⚡{RESET} {BOLD}Fast-Path NLP{RESET}   : {DIM}Deterministic routing active (Ollama SLM offline){RESET}\n")

    core = JarvisCore(mcp_client)
    history: list = []

    loop = asyncio.get_running_loop()
    while True:
        try:
            prompt_str = f"{CYAN}{BOLD}User ❯{RESET} "
            user_input = await loop.run_in_executor(None, input, prompt_str)
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CYAN}JARVIS:{RESET} Goodbye! 👋")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            print(f"{CYAN}JARVIS:{RESET} System shutting down. Goodbye! 👋")
            break

        # Show routing decision preview
        hint = _routing_hint(user_input)
        print(f"{DIM}Routing:{RESET}{hint}")

        # Process request through pipeline
        try:
            history, response = await core.process_request(user_input, history)
        except Exception as exc:
            response = f"⚠ Unexpected error: {exc}"

        # Clean formatted output
        print(f"{CYAN}{BOLD}JARVIS:{RESET}")
        for line in str(response).splitlines():
            if line.startswith("ERROR:") or "✖" in line or "⚠" in line:
                print(f"  {RED}{line}{RESET}")
            elif "✔" in line:
                print(f"  {GREEN}{line}{RESET}")
            else:
                print(f"  {line}")
        print()  # blank line for readability

    if mcp_client:
        try:
            await mcp_client.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    if "--gui" in sys.argv or "-g" in sys.argv:
        from app.gui import run_gui
        run_gui()
    else:
        asyncio.run(agent_loop())
