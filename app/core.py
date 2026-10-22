import asyncio
import json
import re
from typing import Dict, Any, List

from app.events import event_bus
from app.tools.registry import register_all_tools
from app.tools.bus import tool_bus

from app.config import config

# Module-level references – can be monkey-patched by tests.
try:
    from app.agent import get_agent
except Exception:
    get_agent = None  # type: ignore[assignment]

try:
    from app.local_brain import local_brain
except Exception:
    local_brain = None  # type: ignore[assignment]


def parse_fallback_json(text: str) -> List[Dict[str, Any]]:
    """Safely parse fallback tool calls from models not using native tools."""
    jsons = re.findall(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if not jsons:
        jsons = [text]

    parsed_calls = []
    for j_str in jsons:
        j_str = j_str.replace("<nil>", "null").strip()
        if not j_str:
            continue
        try:
            parsed = json.loads(j_str)
            if isinstance(parsed, dict):
                parsed_calls.append(parsed)
            elif isinstance(parsed, list):
                parsed_calls.extend(parsed)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            pos = 0
            while pos < len(j_str):
                start = None
                for i in range(pos, len(j_str)):
                    if j_str[i] in ("{", "["):
                        start = i
                        break
                if start is None:
                    break
                try:
                    obj, end = decoder.raw_decode(j_str[start:])
                    if isinstance(obj, dict):
                        parsed_calls.append(obj)
                    elif isinstance(obj, list):
                        parsed_calls.extend(obj)
                    pos = start + end
                except Exception:
                    pos = start + 1

    normalized = []
    for call in parsed_calls:
        tool_name = call.get("tool") or call.get("name") or call.get("function")
        if tool_name:
            args = call.get("arguments") or call.get("parameters") or {}
            normalized.append({"tool_name": tool_name, "arguments": args})

    return normalized


def _format_clean_tool_output(tool_name: str, tool_args: dict, raw_result: Any) -> str:
    """Format tool execution result into clean, human-readable UI text."""
    if isinstance(raw_result, dict):
        is_success = raw_result.get("success", True)
        data = raw_result.get("data")
        error = raw_result.get("error")

        if not is_success or error:
            err_msg = ""
            if isinstance(error, dict):
                err_msg = error.get("message") or str(error)
            elif error:
                err_msg = str(error)
            elif isinstance(data, dict) and data.get("error"):
                err_msg = str(data["error"])
            else:
                err_msg = "Execution failed"
            return f"[{tool_name}] ✖ {err_msg}"

        if isinstance(data, dict):
            # 1. Directory listings (list_directory)
            if "entries" in data and ("path" in data or "total_count" in data):
                entries = data.get("entries", [])
                path_str = data.get("path", ".")
                total = data.get("total_count", len(entries))
                lines = [f"[{tool_name}] ✔ Directory: {path_str} ({total} items)"]
                if not entries:
                    lines.append("  (empty directory)")
                else:
                    for item in entries:
                        is_dir = item.get("is_dir", False)
                        name = item.get("name", "")
                        if is_dir:
                            lines.append(f"  📁 [DIR]  {name}")
                        else:
                            size_str = item.get("size_formatted") or ""
                            lines.append(f"  📄 [FILE] {name:<35} {size_str:>10}")
                    if total > len(entries):
                        lines.append(f"  ... ({total - len(entries)} more items)")
                return "\n".join(lines)

            # 2. File search matches (search_files)
            if "matches" in data and ("query" in data or "root_dir" in data):
                matches = data.get("matches", [])
                count = data.get("count", len(matches))
                root = data.get("root_dir", "")
                q = data.get("query", "")
                lines = [f"[{tool_name}] ✔ Found {count} match(es) for '{q}' in {root}:"]
                if not matches:
                    lines.append("  (no matches found)")
                else:
                    for m in matches:
                        lines.append(f"  • {m}")
                return "\n".join(lines)

            # 3. File content search results (search_file_contents)
            if "results" in data and "query" in data:
                results = data.get("results", [])
                total = data.get("total_matches", len(results))
                q = data.get("query", "")
                lines = [f"[{tool_name}] ✔ Found {total} match(es) containing '{q}':"]
                if not results:
                    lines.append("  (no matches found)")
                else:
                    for r in results:
                        lines.append(f"  • {r.get('path')}:{r.get('line_number')}: {r.get('line_content', '').strip()}")
                return "\n".join(lines)

            # 4. File reading (read_text_file)
            if "content" in data and ("path" in data or "total_lines" in data):
                content = data.get("content", "")
                path_str = data.get("path", "")
                total_lines = data.get("total_lines", len(content.splitlines()))
                return f"[{tool_name}] ✔ Content of {path_str} ({total_lines} lines):\n{content}"

            # 5. Directory tree (get_directory_tree)
            if "tree" in data and "root" in data:
                tree = data.get("tree", "")
                root = data.get("root", "")
                nodes = data.get("total_nodes", "")
                return f"[{tool_name}] ✔ Directory tree for {root} ({nodes} nodes):\n{tree}"

            # 6. Recycle bin (inspect_recycle_bin)
            if "items" in data and "total_items" in data:
                items = data.get("items", [])
                total = data.get("total_items", len(items))
                lines = [f"[{tool_name}] ✔ Recycle Bin ({total} items):"]
                if not items:
                    lines.append("  (Recycle Bin is empty)")
                else:
                    for it in items:
                        name = it.get("name", "")
                        sz = it.get("size_formatted", "")
                        del_t = it.get("deletion_date", "")
                        lines.append(f"  🗑 {name:<30} {sz:>10} (deleted {del_t})")
                return "\n".join(lines)

            # 7. File comparison (compare_files)
            if "identical" in data and "diff" in data:
                if data.get("identical"):
                    return f"[{tool_name}] ✔ Files are identical."
                diff = data.get("diff", "")
                return f"[{tool_name}] ✔ File differences:\n{diff}"

            # 8. Terminal execution (terminal_execute / execute_and_validate)
            if "stdout" in data or "stderr" in data:
                stdout = (data.get("stdout") or "").strip()
                stderr = (data.get("stderr") or "").strip()
                exit_code = data.get("exit_code", 0)
                out_parts = []
                if stdout:
                    out_parts.append(stdout)
                if stderr:
                    out_parts.append(f"[STDERR]\n{stderr}")
                out_body = "\n".join(out_parts)
                if out_body:
                    return f"[{tool_name}] ✔ (exit code {exit_code})\n{out_body}"
                return f"[{tool_name}] ✔ Command completed successfully (exit code {exit_code})"

            # 9. Generic preformatted output/message/status
            if data.get("output"):
                return f"[{tool_name}] ✔\n{data['output']}"
            elif data.get("message"):
                return f"[{tool_name}] ✔ {data['message']}"
            elif data.get("status"):
                return f"[{tool_name}] ✔ {data['status']}"
        elif isinstance(data, str) and data:
            return f"[{tool_name}] ✔ {data}"

        arg_summary = ", ".join(f"{k}={v}" for k, v in tool_args.items() if v)
        if arg_summary:
            return f"[{tool_name}] ✔ Executed successfully ({arg_summary})"
        return f"[{tool_name}] ✔ Executed successfully"

    res_str = str(raw_result).strip()
    if res_str.startswith("ERROR:"):
        return f"[{tool_name}] ✖ {res_str}"
    return f"[{tool_name}] ✔ {res_str}"


class JarvisCore:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        register_all_tools(self.mcp_client)

    async def process_request(self, user_input: str, history: list) -> tuple[list, str]:
        """Process a user request.

        Strategy:
        1. Try lightweight NLP routing via ``plan_user_input``.
        2. If every step is a directly-mapped tool, execute them without any LLM.
        3. If the request is complex, attempt the full PydanticAI agent (which can
           be monkey-patched in tests via ``app.core.get_agent``).
        4. If no model is configured, return a helpful error message.
        """
        await event_bus.publish("PlanningStarted", {"status": "Routing request..."})

        from app.router import ExecutionContext, plan_user_input, match_direct_command
        ctx = ExecutionContext()
        steps = plan_user_input(user_input, ctx)

        # ---- Conversational Greeting Fast Path ----
        if steps and any(s.routing_result and s.routing_result.intent == "conversation" for s in steps):
            greeting_resp = "Hello! I am JARVIS, your autonomous desktop assistant. How can I help you today?"
            await event_bus.publish("SpeechStarted", {"text": greeting_resp})
            return history, greeting_resp

        # ---- Layer 6: Clarification check ----
        clarification_steps = [s for s in steps if s.routing_result and s.routing_result.needs_clarification]
        if clarification_steps:
            prompts = [s.routing_result.clarification_prompt for s in clarification_steps if s.routing_result.clarification_prompt]
            final_response = "\n".join(prompts)
            await event_bus.publish("SpeechStarted", {"text": final_response})
            return history, final_response

        # ---- Fast path: all steps are direct tool calls ----
        if steps and all(step.is_direct for step in steps):
            observations = []
            for i, step in enumerate(steps):
                if i > 0:
                    await asyncio.sleep(1.0)
                step = match_direct_command(step.command, ctx)
                try:
                    result = await tool_bus.execute(step.tool_name, step.tool_args)
                except Exception as exc:
                    result = f"ERROR: {exc}"
                observations.append(_format_clean_tool_output(step.tool_name, step.tool_args, result))
                if step.tool_name == "open_app":
                    app_n = step.tool_args.get("app_name") or step.tool_args.get("application")
                    if app_n:
                        ctx.last_app_name = app_n
            final_response = "\n".join(observations)
            await event_bus.publish("SpeechStarted", {"text": final_response})
            return history, final_response

        # ---- Planning & Reasoning Path: SmolLM2-135M Task Decomposition ----
        try:
            from app.planner import plan_task_with_reasoning, execute_plan
            plan = plan_task_with_reasoning(user_input, ctx)
            if plan and len(plan.steps) > 1 and all(s.tool_name for s in plan.steps):
                exec_plan = await execute_plan(plan, ctx, step_delay=1.0)
                observations = []
                for s in exec_plan.steps:
                    obs_text = _format_clean_tool_output(
                        s.tool_name,
                        s.tool_args,
                        {"success": s.status == "completed", "data": s.result, "error": s.error}
                    )
                    observations.append(obs_text)
                final_response = "\n".join(observations)
                await event_bus.publish("SpeechStarted", {"text": final_response})
                return history, final_response
        except Exception:
            pass

        # ---- Intermediate path: Local Brain (FunctionGemma) tool selection ----
        import app.core as _self_module
        _local_brain = getattr(_self_module, "local_brain", None)
        if _local_brain is not None and getattr(config, "local_brain_enabled", True):
            try:
                brain_res = await _local_brain.run_tool_loop(user_input, tool_delay=1.0)
                if brain_res.get("executed_count", 0) > 0 and brain_res.get("observations"):
                    observations = []
                    for obs in brain_res["observations"]:
                        tool_n = obs.get("tool_name", "unknown")
                        observations.append(_format_clean_tool_output(tool_n, {}, obs))
                    final_response = "\n".join(observations)
                    await event_bus.publish("SpeechStarted", {"text": final_response})
                    return history, final_response
            except Exception:
                pass  # Fall through to Layer 2 agent

        # ---- Slow path: complex request → LLM agent ----
        # get_agent can be monkey-patched by tests (see app.core.get_agent)
        _get_agent = getattr(_self_module, "get_agent", None)
        if _get_agent is None:
            return history, (
                "⚠️  No language model is configured.\n"
                "For simple commands (open / type / maximize / close) no model is needed.\n"
                "For complex requests please set MODEL_NAME in your .env file."
            )

        try:
            from pydantic_ai import UsageLimits
            agent = _get_agent()
            current_prompt = user_input
            while True:
                result = await agent.run(
                    current_prompt,
                    message_history=history,
                    usage_limits=UsageLimits(request_limit=5),
                )
                history = result.all_messages()
                final_response = getattr(result, "data", getattr(result, "output", str(result)))

                # Hybrid fallback for models that return JSON tool calls as text
                if "{" in final_response and "}" in final_response:
                    calls = parse_fallback_json(final_response)
                    if calls:
                        observations = []
                        for i, call in enumerate(calls):
                            if i > 0:
                                await asyncio.sleep(1.0)
                            tool_name = call["tool_name"]
                            args = call["arguments"]
                            print(f"[Fallback Parser] Executing tool: {tool_name}")
                            obs = await tool_bus.execute(tool_name, args)
                            observations.append(
                                f"Tool '{tool_name}' returned:\n{json.dumps(obs, default=str)}"
                            )
                        if observations:
                            current_prompt = "\n\n".join(observations)
                            continue

                await event_bus.publish("SpeechStarted", {"text": final_response})
                return history, final_response

        except Exception as e:
            await event_bus.publish("Error", {"message": str(e)})
            return history, (
                f"⚠️  Could not process request with the language model.\n"
                f"Reason: {e}\n\n"
                f"For simple commands (open / type / maximize / close) no model is needed.\n"
                f"For complex requests please set MODEL_NAME in your .env file."
            )
