"""
app/local_brain.py  -  FunctionGemma Local Tool-Calling Brain for JARVIS OS
========================================================================

Architecture & Role:
- Interfaces with local Ollama service (hosted in WSL or native Windows).
- Uses `functiongemma:latest` (or configured model) as an edge tool selector.
- Bridges Layer 1 (Fast-NLP Router) and Layer 2 (Full Agent / Gemini / Cloud).
- Uses UnifiedToolBus exclusively as the authoritative tool registry and executor.
- Converts UnifiedToolBus schemas to Ollama tool calling format with caching.
- Validates tool names, argument presence, and argument types before execution.
- Implements a controlled multi-turn tool-calling loop with safety bounds.
- Tracks real latencies (Ollama latency, tool selection latency, execution latency).
"""

import asyncio
import inspect
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Set
try:
    import ollama
except ImportError:
    ollama = None
from app.config import config
from app.events import event_bus
from app.tools.bus import ToolDefinition, tool_bus

logger = logging.getLogger("jarvis.local_brain")


class FunctionGemmaLocalBrain:
    """Local tool-calling brain powered by FunctionGemma via Ollama."""

    def __init__(
        self,
        host: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        max_turns: Optional[int] = None,
        max_tool_executions: Optional[int] = None,
        tool_delay: Optional[float] = None,
        backend: Optional[str] = None,
        gguf_path: Optional[str] = None,
        threads: Optional[int] = None,
        gpu_layers: Optional[int] = None,
    ):
        self.backend = backend or getattr(config, "local_brain_backend", "auto")
        self.gguf_path = gguf_path or getattr(config, "local_brain_gguf_path", "models/functiongemma-270m.gguf")
        self.threads = threads if threads is not None else getattr(config, "local_brain_threads", 4)
        self.gpu_layers = gpu_layers if gpu_layers is not None else getattr(config, "local_brain_gpu_layers", 0)

        self.host = host or getattr(config, "ollama_host", "http://127.0.0.1:11434")
        self.model_name = model_name or getattr(config, "local_brain_model", "functiongemma:latest")
        self.timeout = timeout or getattr(config, "local_brain_timeout", 15.0)
        self.max_turns = max_turns or getattr(config, "local_brain_max_turns", 3)
        self.max_tool_executions = max_tool_executions or getattr(config, "local_brain_max_tools", 5)
        self.tool_delay = tool_delay if tool_delay is not None else getattr(config, "local_brain_tool_delay", 1.0)

        # Async Ollama client instance
        self._client: Optional[ollama.AsyncClient] = None
        # llama-cpp-python instance
        self._llm: Optional[Any] = None

        # Schema cache mapping tool_name -> converted Ollama tool dict
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._last_registry_hash: int = 0

    def get_effective_backend(self) -> str:
        """Resolve backend based on configuration and model availability."""
        if self.backend == "llama_cpp":
            return "llama_cpp"
        if self.backend == "ollama":
            return "ollama"
        # "auto" mode: prefer llama_cpp if GGUF file exists on disk
        import os
        if os.path.isfile(self.gguf_path):
            return "llama_cpp"
        return "ollama"

    def _get_llama(self):
        """Lazy initialization of the llama-cpp-python engine."""
        if self._llm is None:
            import os
            from llama_cpp import Llama

            if not os.path.isfile(self.gguf_path):
                raise FileNotFoundError(f"GGUF model not found at '{self.gguf_path}'")
            logger.info(
                f"Loading local GGUF model via llama-cpp-python: {self.gguf_path} "
                f"(threads={self.threads}, gpu_layers={self.gpu_layers})"
            )
            self._llm = Llama(
                model_path=self.gguf_path,
                n_threads=self.threads,
                n_gpu_layers=self.gpu_layers,
                n_ctx=2048,
                verbose=False,
            )
        return self._llm

    @property
    def client(self) -> Any:
        """Lazily initialize and reuse the async Ollama client."""
        if ollama is None:
            raise RuntimeError(
                "Python 'ollama' package is not installed. Run 'pip install ollama' or use GGUF backend."
            )
        if self._client is None:
            self._client = ollama.AsyncClient(host=self.host)
        return self._client

    # -----------------------------------------------------------------------
    # 1. Health & Model Discovery
    # -----------------------------------------------------------------------
    async def check_health(self) -> Dict[str, Any]:
        """Perform a lightweight health check on the active backend (llama_cpp or Ollama)."""
        effective = self.get_effective_backend()
        if effective == "llama_cpp":
            import os
            t0 = time.perf_counter()
            if os.path.isfile(self.gguf_path):
                model_basename = os.path.basename(self.gguf_path)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "available": True,
                    "backend": "llama_cpp",
                    "host": "in-process",
                    "model": model_basename,
                    "model_path": self.gguf_path,
                    "latency_ms": round(latency_ms, 2),
                    "installed_models": [model_basename],
                    "error": None,
                }
            elif self.backend == "llama_cpp":
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "available": False,
                    "backend": "llama_cpp",
                    "host": "in-process",
                    "model": self.model_name,
                    "latency_ms": round(latency_ms, 2),
                    "installed_models": [],
                    "error": f"GGUF model file not found at '{self.gguf_path}'.",
                }

        t0 = time.perf_counter()
        if ollama is None:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "available": False,
                "host": self.host,
                "model": self.model_name,
                "latency_ms": round(latency_ms, 2),
                "installed_models": [],
                "error": "Python 'ollama' package is not installed. Install it with 'pip install ollama' to connect to Ollama in WSL.",
            }

        try:
            response = await asyncio.wait_for(
                self.client.list(),
                timeout=min(self.timeout, 5.0)
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0

            models_raw = response.get("models", [])
            installed_models = []
            for m in models_raw:
                if isinstance(m, dict):
                    installed_models.append(m.get("model") or m.get("name", ""))
                elif hasattr(m, "model"):
                    installed_models.append(getattr(m, "model"))

            # Determine best match for FunctionGemma
            target = self.model_name.lower()
            matched_model = None

            # Exact match first
            for m in installed_models:
                if m.lower() == target:
                    matched_model = m
                    break

            # Suffix/prefix match (e.g. 'functiongemma' vs 'functiongemma:latest')
            if not matched_model:
                for m in installed_models:
                    if target in m.lower() or m.lower().startswith("functiongemma"):
                        matched_model = m
                        break

            if matched_model:
                self.model_name = matched_model
                return {
                    "available": True,
                    "host": self.host,
                    "model": matched_model,
                    "latency_ms": round(latency_ms, 2),
                    "installed_models": installed_models,
                    "error": None,
                }
            else:
                return {
                    "available": False,
                    "host": self.host,
                    "model": self.model_name,
                    "latency_ms": round(latency_ms, 2),
                    "installed_models": installed_models,
                    "error": f"Model '{self.model_name}' not found in installed models: {installed_models}",
                }

        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "available": False,
                "host": self.host,
                "model": self.model_name,
                "latency_ms": round(latency_ms, 2),
                "error": f"Connection to Ollama host '{self.host}' timed out.",
            }
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "available": False,
                "host": self.host,
                "model": self.model_name,
                "latency_ms": round(latency_ms, 2),
                "error": f"Ollama connection error: {str(exc)}",
            }

    # -----------------------------------------------------------------------
    # 2. Schema Conversion & Caching
    # -----------------------------------------------------------------------
    def convert_tool_definition_to_schema(self, tool_def: ToolDefinition) -> Dict[str, Any]:
        """Convert a UnifiedToolBus ToolDefinition to Ollama JSON schema format."""
        schema_props: Dict[str, Any] = {}
        required_fields: List[str] = []

        raw_schema = tool_def.input_schema or {}

        # Case A: Already a complete JSON schema object with 'properties'
        if raw_schema.get("type") == "object" and "properties" in raw_schema:
            parameters = {
                "type": "object",
                "properties": raw_schema.get("properties", {}),
                "required": raw_schema.get("required", []),
            }
        else:
            # Case B: Standard JARVIS schema dictionary {param_name: param_info}
            for param_name, param_info in raw_schema.items():
                if isinstance(param_info, dict):
                    p_type = param_info.get("type", "string")
                    p_desc = param_info.get("description", "")
                    prop_entry = {"type": p_type}
                    if p_desc:
                        prop_entry["description"] = p_desc
                    if "enum" in param_info:
                        prop_entry["enum"] = param_info["enum"]
                    if "items" in param_info:
                        prop_entry["items"] = param_info["items"]
                    schema_props[param_name] = prop_entry

                    # Determine if required
                    is_optional = "optional" in p_desc.lower() or param_info.get("default", ...) is not ...
                    if not is_optional:
                        required_fields.append(param_name)
                else:
                    schema_props[param_name] = {"type": "string"}
                    required_fields.append(param_name)

            parameters = {
                "type": "object",
                "properties": schema_props,
                "required": required_fields,
            }

        return {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": parameters,
            },
        }

    def _refresh_schema_cache(self) -> None:
        """Refresh the schema cache if the tool registry has changed."""
        if len(tool_bus.tools) == 0:
            try:
                from app.tools.registry import register_all_tools
                register_all_tools()
            except Exception:
                pass
        current_hash = hash(tuple(sorted(tool_bus.tools.keys())))
        if current_hash != self._last_registry_hash:
            self._schema_cache.clear()
            for name, tool_def in tool_bus.tools.items():
                self._schema_cache[name] = self.convert_tool_definition_to_schema(tool_def)
            self._last_registry_hash = current_hash

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return all registered tools converted to Ollama function schemas."""
        self._refresh_schema_cache()
        return list(self._schema_cache.values())

    def filter_tools_for_request(
        self,
        user_input: str,
        max_tools: int = 20,
        categories: Optional[Set[str]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter relevant tools from UnifiedToolBus for the user request.

        For lightweight models (~270M parameters), providing 60+ tools at once dilutes
        attention and slows prompt evaluation on CPU. Dynamically discovering and
        providing the most relevant 10-20 tools keeps tool selection latency low (<1s)
        and accuracy high, while ensuring 100% of UnifiedToolBus tools remain discoverable.
        """
        import re
        self._refresh_schema_cache()

        if categories:
            cat_normalized = {c.upper() for c in categories}
            matching_tools = [
                self._schema_cache[name]
                for name, t in tool_bus.tools.items()
                if t.category.upper() in cat_normalized and name in self._schema_cache
            ]
            return matching_tools[:max_tools]

        tokens = set(re.findall(r"\b\w+\b", user_input.lower()))
        if history:
            for msg in history:
                content = str(msg.get("content", "") or "")
                tokens.update(re.findall(r"\b\w+\b", content.lower())[:25])

        # Category Intent Mappings for semantic domain discovery
        category_intents: Dict[str, Set[str]] = {
            "FILESYSTEM": {
                "file", "files", "folder", "folders", "dir", "dirs", "directory", "directories",
                "read", "write", "search", "delete", "path", "text", "disk", "exists", "save",
                "open_file", "drive", "drives", "cwd", "cd", "change", "create", "rename",
                "move", "copy", "duplicate", "batch", "recycle", "bin", "trash", "restore",
                "tree", "undo", "append", "edit", "replace", "json", "config", "archive",
                "zip", "unzip", "extract", "hash", "sha256", "compare", "diff", "attributes",
                "recent", "large", "empty"
            },
            "TERMINAL": {
                "terminal", "cmd", "powershell", "bash", "run", "command", "shell", "execute",
                "pip", "npm", "git", "python", "build", "test", "pytest", "server", "subprocess",
                "sync", "daemon", "background", "validate", "validation", "output", "pattern"
            },
            "WINDOWS": {
                "window", "windows", "app", "application", "launch", "open", "close", "minimize",
                "maximize", "restore", "focus", "foreground", "screen", "running", "active",
                "desktop", "win32", "enum", "position", "explorer", "reveal", "openwith", "share",
                "selection"
            },
            "UIA": {"button", "ui", "click", "element", "inspect", "accessibility", "control", "tree", "toggle", "checkbox", "dropdown", "select", "expand", "scroll", "search", "bar", "box", "input", "submit", "close", "locate", "location", "detect", "find", "skip", "enter", "inside", "content", "ad", "modal", "dialog", "popup", "banner", "slider", "table", "grid", "row", "cell", "radio", "list", "menu", "tab", "link", "progress", "spinner", "calendar", "header"},
            "INPUT": {"keyboard", "type", "press", "hotkey", "mouse", "click", "scroll", "cursor", "paste", "copy", "clipboard", "cut", "resolution", "down", "up"},
            "BROWSER": {"browser", "web", "page", "tab", "url", "navigate", "website", "chrome", "edge", "html", "dom", "site", "online", "internet"},
            "SYSTEM": {"system", "cpu", "ram", "memory", "battery", "wifi", "network", "volume", "sound", "mute", "audio", "sleep", "shutdown", "restart", "reboot", "process", "processes", "kill", "task", "speak", "voice", "tts", "ollama", "status", "screenshot", "env", "environment", "variable", "lock"},
            "VISION": {"vision", "ocr", "see", "screen", "look", "icon", "image", "paddle"},
            "PATTERNS": {"pattern", "fill", "form", "dialog", "popup", "confirm", "alert", "smart", "search", "navigate", "tab", "context", "right", "menu", "scroll", "discover", "submit", "skip", "enter", "inside", "box"}
        }

        # Calculate intent matches per category
        active_categories: Set[str] = set()
        for cat, kw_set in category_intents.items():
            if len(tokens.intersection(kw_set)) > 0:
                active_categories.add(cat)

        scored_tools: List[Tuple[float, str]] = []

        # High priority base system tools always given baseline relevance
        core_tools = {
            "get_system_information", "take_screenshot", "open_app", "close_app",
            "get_wifi_networks", "web_search", "open_url", "set_volume", "mute_audio"
        }

        clean_input = user_input.lower().replace("-", " ").replace("_", " ")

        for name, tool_def in tool_bus.tools.items():
            score = 0.0
            norm_name = name.lower().replace("_", " ")
            name_tokens = set(re.findall(r"\b\w+\b", norm_name))
            desc_tokens = set(re.findall(r"\b\w+\b", tool_def.description.lower()))

            # Exact name or partial phrase match in raw user input
            if norm_name in clean_input or name.lower() in clean_input:
                score += 8.0

            # Name tokens carry highest weight
            name_overlap = len(tokens.intersection(name_tokens))
            desc_overlap = len(tokens.intersection(desc_tokens))
            score += name_overlap * 3.5 + desc_overlap * 1.2

            # Category intent alignment boost
            if tool_def.category.upper() in active_categories:
                score += 3.0

            # Contextual follow-up boosts
            if "element_id" in tokens and tool_def.category == "UIA":
                score += 4.0
            if any(k in tokens for k in ["pid", "process", "kill"]) and "process" in name:
                score += 5.0
            if any(k in tokens for k in ["file", "dir", "directory", "folder"]) and tool_def.category == "FILESYSTEM":
                score += 4.0
            if any(k in tokens for k in ["recycle", "bin", "trash", "restore"]) and "recycle" in name:
                score += 7.0
            if any(k in tokens for k in ["explorer", "reveal", "selection"]) and "explorer" in name:
                score += 6.0
            if any(k in tokens for k in ["zip", "archive", "unzip", "extract"]) and ("zip" in name or "archive" in name):
                score += 6.0
            if any(k in tokens for k in ["terminal", "cmd", "powershell", "execute", "validate"]) and ("terminal" in name or "validate" in name):
                score += 5.0

            if name in core_tools:
                score += 0.5

            if score > 0:
                scored_tools.append((score, name))

        # Sort descending by score
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        selected_names = [name for _, name in scored_tools[:max_tools]]

        # Ensure fallback baseline set if input was ambiguous
        if len(selected_names) < 5:
            for name in core_tools:
                if name not in selected_names and name in self._schema_cache:
                    selected_names.append(name)

        return [self._schema_cache[n] for n in selected_names[:max_tools] if n in self._schema_cache]

    # -----------------------------------------------------------------------
    # 3. Tool Call Parsing & Validation
    # -----------------------------------------------------------------------
    def parse_tool_call(self, call: Any) -> Optional[Dict[str, Any]]:
        """Safely parse a tool call object from Ollama into normalized format."""
        if call is None:
            return None

        # Case A: ollama.ToolCall object or has function attribute
        if hasattr(call, "function"):
            fn = getattr(call, "function")
            name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else None)
            raw_args = getattr(fn, "arguments", {}) or (fn.get("arguments") if isinstance(fn, dict) else {})
        elif isinstance(call, dict):
            fn = call.get("function", call)
            name = fn.get("name") or call.get("tool_name") or call.get("tool")
            raw_args = fn.get("arguments") or call.get("arguments") or call.get("parameters") or {}
        else:
            return None

        if not name:
            return None

        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}

        return {"tool_name": str(name).strip(), "arguments": args}

    def validate_tool_call(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Validate a proposed tool call against UnifiedToolBus authoritative definition.

        Returns: (is_valid, error_reason, sanitized_arguments)
        """
        # 1. Existence check in authoritative registry
        if tool_name not in tool_bus.tools:
            return False, f"Tool '{tool_name}' is not registered in UnifiedToolBus.", arguments

        tool_def = tool_bus.tools[tool_name]
        raw_schema = tool_def.input_schema or {}

        # Extract properties and required list
        if raw_schema.get("type") == "object" and "properties" in raw_schema:
            properties = raw_schema.get("properties", {})
            required_keys = raw_schema.get("required", [])
        else:
            properties = raw_schema
            required_keys = []
            for p_name, p_info in properties.items():
                if isinstance(p_info, dict):
                    desc = p_info.get("description", "")
                    if "optional" not in desc.lower() and p_info.get("default", ...) is ...:
                        required_keys.append(p_name)

        # 2. Required arguments check
        for req_key in required_keys:
            if req_key not in arguments or arguments[req_key] is None or arguments[req_key] == "":
                return False, f"Missing required argument '{req_key}' for tool '{tool_name}'.", arguments

        # 3. Type checking and safe coercion
        sanitized: Dict[str, Any] = {}
        for arg_key, arg_val in arguments.items():
            if arg_key not in properties:
                # Discard unknown arguments to protect against hallucinated kwargs
                continue

            expected_info = properties[arg_key]
            expected_type = expected_info.get("type", "string") if isinstance(expected_info, dict) else "string"

            # Validate / coerce based on expected schema type
            if expected_type == "integer":
                if not isinstance(arg_val, int) or isinstance(arg_val, bool):
                    try:
                        sanitized[arg_key] = int(arg_val)
                    except (ValueError, TypeError):
                        return False, f"Argument '{arg_key}' must be an integer, got {type(arg_val).__name__}.", arguments
                else:
                    sanitized[arg_key] = arg_val
            elif expected_type == "number":
                if not isinstance(arg_val, (int, float)) or isinstance(arg_val, bool):
                    try:
                        sanitized[arg_key] = float(arg_val)
                    except (ValueError, TypeError):
                        return False, f"Argument '{arg_key}' must be a number, got {type(arg_val).__name__}.", arguments
                else:
                    sanitized[arg_key] = arg_val
            elif expected_type == "boolean":
                if isinstance(arg_val, bool):
                    sanitized[arg_key] = arg_val
                elif isinstance(arg_val, str):
                    sanitized[arg_key] = arg_val.lower() in ("true", "1", "yes")
                else:
                    sanitized[arg_key] = bool(arg_val)
            elif expected_type == "array":
                if not isinstance(arg_val, list):
                    return False, f"Argument '{arg_key}' must be a list, got {type(arg_val).__name__}.", arguments
                sanitized[arg_key] = arg_val
            elif expected_type == "object":
                if not isinstance(arg_val, dict):
                    return False, f"Argument '{arg_key}' must be an object/dict, got {type(arg_val).__name__}.", arguments
                sanitized[arg_key] = arg_val
            else:
                # String or default
                sanitized[arg_key] = str(arg_val)

        return True, None, sanitized

    def _select_tools_llama_cpp(
        self,
        task: str,
        history: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """In-process tool selection using llama-cpp-python engine."""
        import re
        t_start = time.perf_counter()
        llm = self._get_llama()

        messages = list(history) if history else []
        messages.append({"role": "user", "content": task})

        t_inf_start = time.perf_counter()
        response = llm.create_chat_completion(
            messages=messages,
            tools=tools,
            temperature=0.1,
        )
        inf_latency_ms = (time.perf_counter() - t_inf_start) * 1000.0

        choice = response["choices"][0]
        msg = choice.get("message", {})
        raw_tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""

        # Extract text function calls if model emitted them directly in content
        if not raw_tool_calls and content:
            call_matches = re.findall(r"call:(\w+)\s*(\{.*?\})", content, re.DOTALL)
            for c_name, c_args in call_matches:
                try:
                    parsed_args = json.loads(c_args)
                    raw_tool_calls.append({"function": {"name": c_name, "arguments": parsed_args}})
                except Exception:
                    pass

            if not raw_tool_calls:
                json_blocks = re.findall(r"\{.*?\}", content, re.DOTALL)
                for j_str in json_blocks:
                    try:
                        data = json.loads(j_str)
                        name = data.get("name") or data.get("tool") or data.get("tool_name")
                        args = data.get("arguments") or data.get("parameters") or {}
                        if name:
                            raw_tool_calls.append({"function": {"name": name, "arguments": args}})
                    except Exception:
                        pass

        validated_calls: List[Dict[str, Any]] = []
        parsing_errors: List[str] = []

        for raw_call in raw_tool_calls:
            parsed = self.parse_tool_call(raw_call)
            if not parsed:
                continue

            is_valid, err, sanitized_args = self.validate_tool_call(
                parsed["tool_name"], parsed["arguments"]
            )
            if is_valid:
                validated_calls.append({
                    "tool_name": parsed["tool_name"],
                    "arguments": sanitized_args,
                })
            else:
                parsing_errors.append(err or "Unknown validation error")

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        return {
            "has_tool_calls": len(validated_calls) > 0,
            "tool_calls": validated_calls,
            "text": content,
            "errors": parsing_errors if parsing_errors else None,
            "metrics": {
                "llama_cpp_latency_ms": round(inf_latency_ms, 2),
                "total_latency_ms": round(total_latency_ms, 2),
            },
        }

    # -----------------------------------------------------------------------
    # 4. Tool Selection Engine
    # -----------------------------------------------------------------------
    async def select_tools(
        self,
        task: str,
        history: Optional[List[Dict[str, str]]] = None,
        tools_override: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Query FunctionGemma (via llama_cpp or Ollama) to select structured tool calls for a task."""
        # Get relevant tool schemas
        tools = tools_override or self.filter_tools_for_request(task, history=history)

        effective = self.get_effective_backend()
        if effective == "llama_cpp":
            try:
                return await asyncio.to_thread(self._select_tools_llama_cpp, task, history, tools)
            except Exception as exc:
                if self.backend == "llama_cpp":
                    logger.error(f"llama-cpp execution error: {exc}")
                    return {
                        "has_tool_calls": False,
                        "tool_calls": [],
                        "text": "",
                        "errors": [f"llama-cpp execution error: {str(exc)}"],
                        "metrics": {
                            "llama_cpp_latency_ms": 0.0,
                            "total_latency_ms": 0.0,
                        },
                    }
                # If auto, fall through to Ollama
                logger.warning(f"llama-cpp failed ({exc}), falling back to Ollama backend.")

        t_start = time.perf_counter()
        messages = list(history) if history else []
        messages.append({"role": "user", "content": task})

        t_ollama_start = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model_name,
                    messages=messages,
                    tools=tools,
                ),
                timeout=self.timeout,
            )
            ollama_latency_ms = (time.perf_counter() - t_ollama_start) * 1000.0

            msg = getattr(response, "message", None) or response.get("message", {})
            raw_tool_calls = getattr(msg, "tool_calls", None) or (
                msg.get("tool_calls") if isinstance(msg, dict) else None
            ) or []
            content = getattr(msg, "content", "") or (
                msg.get("content", "") if isinstance(msg, dict) else ""
            )

            # Parse and validate each tool call
            validated_calls: List[Dict[str, Any]] = []
            parsing_errors: List[str] = []

            for raw_call in raw_tool_calls:
                parsed = self.parse_tool_call(raw_call)
                if not parsed:
                    continue

                is_valid, err, sanitized_args = self.validate_tool_call(
                    parsed["tool_name"], parsed["arguments"]
                )
                if is_valid:
                    validated_calls.append({
                        "tool_name": parsed["tool_name"],
                        "arguments": sanitized_args,
                    })
                else:
                    parsing_errors.append(err or "Unknown validation error")

            total_latency_ms = (time.perf_counter() - t_start) * 1000.0

            return {
                "has_tool_calls": len(validated_calls) > 0,
                "tool_calls": validated_calls,
                "text": content,
                "errors": parsing_errors if parsing_errors else None,
                "metrics": {
                    "ollama_latency_ms": round(ollama_latency_ms, 2),
                    "total_latency_ms": round(total_latency_ms, 2),
                },
            }

        except asyncio.TimeoutError:
            total_latency_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "has_tool_calls": False,
                "tool_calls": [],
                "text": "",
                "errors": [f"FunctionGemma request timed out after {self.timeout}s."],
                "metrics": {
                    "ollama_latency_ms": round(total_latency_ms, 2),
                    "total_latency_ms": round(total_latency_ms, 2),
                },
            }
        except Exception as exc:
            total_latency_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "has_tool_calls": False,
                "tool_calls": [],
                "text": "",
                "errors": [f"FunctionGemma invocation error: {str(exc)}"],
                "metrics": {
                    "ollama_latency_ms": round(total_latency_ms, 2),
                    "total_latency_ms": round(total_latency_ms, 2),
                },
            }

    # -----------------------------------------------------------------------
    # 5. Controlled Tool-Calling Loop
    # -----------------------------------------------------------------------
    async def run_tool_loop(
        self,
        task: str,
        max_turns: Optional[int] = None,
        max_tool_executions: Optional[int] = None,
        tool_delay: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a controlled multi-turn tool-calling loop using UnifiedToolBus.

        Workflow:
        1. Query FunctionGemma with task and relevant tool schemas.
        2. Validate proposed tool calls against authoritative UnifiedToolBus registry.
        3. Execute approved actions via tool_bus.execute(tool_name, arguments).
        4. Enforce 1-second gap between tool executions to allow system state to settle.
        5. Collect observations and feed back into next turn if needed.
        6. Halt on: completion, max turns, max executions, timeout, or anti-loop detection.
        """
        turns_limit = max_turns or self.max_turns
        tools_limit = max_tool_executions or self.max_tool_executions
        delay = self.tool_delay if tool_delay is None else tool_delay

        loop_start = time.perf_counter()
        history: List[Dict[str, Any]] = [{"role": "user", "content": task}]
        all_observations: List[Dict[str, Any]] = []
        executed_count = 0
        call_signatures_seen: Set[str] = set()

        total_ollama_time = 0.0
        total_exec_time = 0.0

        await event_bus.publish("LocalBrainStarted", {"task": task, "model": self.model_name})

        for turn in range(turns_limit):
            # 1. Propose tool calls
            selection_res = await self.select_tools(task=task, history=history)
            metrics = selection_res.get("metrics", {})
            total_ollama_time += metrics.get("ollama_latency_ms", 0.0)

            # If no tool calls proposed or error encountered, finish
            if not selection_res["has_tool_calls"]:
                break

            tool_calls = selection_res["tool_calls"]
            executed_in_this_turn = False

            for call in tool_calls:
                if executed_count >= tools_limit:
                    all_observations.append({
                        "tool_name": call["tool_name"],
                        "success": False,
                        "data": None,
                        "error": {
                            "type": "LimitExceeded",
                            "message": f"Maximum tool execution limit ({tools_limit}) reached.",
                        },
                    })
                    break

                # Anti-loop protection: detect identical consecutive repeated calls
                call_sig = f"{call['tool_name']}:{json.dumps(call['arguments'], sort_keys=True)}"
                if call_sig in call_signatures_seen:
                    all_observations.append({
                        "tool_name": call["tool_name"],
                        "success": False,
                        "data": None,
                        "error": {
                            "type": "CircularCallDetected",
                            "message": f"Repeated tool call prevented by anti-loop protection: {call_sig}",
                        },
                    })
                    continue
                call_signatures_seen.add(call_sig)

                # 2. Execute via authoritative UnifiedToolBus
                t_exec_start = time.perf_counter()
                try:
                    obs = await tool_bus.execute(call["tool_name"], call["arguments"])
                except Exception as exc:
                    obs = {
                        "success": False,
                        "tool_name": call["tool_name"],
                        "data": None,
                        "error": {"type": "ToolExecutionException", "message": str(exc)},
                    }
                exec_duration_ms = (time.perf_counter() - t_exec_start) * 1000.0
                total_exec_time += exec_duration_ms

                executed_count += 1
                executed_in_this_turn = True
                all_observations.append(obs)

                # Append assistant tool call and tool result to history for model turn
                history.append({
                    "role": "assistant",
                    "content": f"Invoking tool {call['tool_name']}",
                })
                history.append({
                    "role": "tool",
                    "content": json.dumps(obs, default=str),
                })

                # 1-second gap between tool executions to allow system/UI state to settle
                if delay > 0:
                    await asyncio.sleep(delay)

            if not executed_in_this_turn or executed_count >= tools_limit:
                break

        total_loop_time_ms = (time.perf_counter() - loop_start) * 1000.0

        result = {
            "success": len(all_observations) > 0 and any(o.get("success", False) for o in all_observations),
            "executed_count": executed_count,
            "observations": all_observations,
            "metrics": {
                "total_ollama_latency_ms": round(total_ollama_time, 2),
                "total_execution_latency_ms": round(total_exec_time, 2),
                "total_loop_latency_ms": round(total_loop_time_ms, 2),
            },
        }

        await event_bus.publish("LocalBrainCompleted", result)
        return result


# Global singleton instance
local_brain = FunctionGemmaLocalBrain()
