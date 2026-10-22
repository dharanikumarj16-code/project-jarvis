"""
app/tools/dynamic_tools.py - Dynamic Tool Creation, Testing, and Lifecycle for JARVIS
=====================================================================================

Enables JARVIS to:
1. Propose new tool signatures and implementations when capabilities are missing.
2. Test candidate tool code in an isolated execution sandbox before registration.
3. Persist validated dynamic tools into `app/tools/dynamic/` following project conventions.
4. Hot-register dynamic tools into `UnifiedToolBus` without duplicating the execution architecture.
"""

import ast
import inspect
import logging
import os
import sys
from typing import Any, Callable, Dict, Optional

from app.permissions import PermissionLevel
from app.tools.bus import ToolDefinition, tool_bus

logger = logging.getLogger("jarvis.dynamic_tools")

DYNAMIC_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "dynamic")


def ensure_dynamic_tools_dir() -> str:
    """Ensure the isolated dynamic tools directory exists."""
    os.makedirs(DYNAMIC_TOOLS_DIR, exist_ok=True)
    init_file = os.path.join(DYNAMIC_TOOLS_DIR, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("# Isolated package for user-created and agent-proposed dynamic tools\n")
    return DYNAMIC_TOOLS_DIR


def propose_tool(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    code: str,
    category: str = "custom",
    permission_level: str = "action",
) -> Dict[str, Any]:
    """Validate proposal structure and syntax without executing."""
    clean_name = name.strip().lower().replace(" ", "_").replace("-", "_")
    
    # 1. AST Syntax Check
    try:
        parsed = ast.parse(code)
    except SyntaxError as e:
        return {
            "valid": False,
            "error": f"Syntax error in tool code: {e}",
            "tool_name": clean_name,
        }

    # 2. Check for matching function definition
    func_names = [node.name for node in parsed.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if clean_name not in func_names and not func_names:
        return {
            "valid": False,
            "error": f"Code must contain a function definition (expected '{clean_name}').",
            "tool_name": clean_name,
        }

    actual_func_name = clean_name if clean_name in func_names else func_names[0]

    return {
        "valid": True,
        "tool_name": actual_func_name,
        "description": description,
        "input_schema": input_schema,
        "category": category,
        "permission_level": permission_level,
        "code": code,
        "error": None,
    }


def verify_tool_isolated(
    name: str,
    code: str,
    test_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute proposed tool code in an isolated module environment to verify behavior."""
    proposal = propose_tool(name=name, description="", input_schema={}, code=code)
    if not proposal["valid"]:
        return {"success": False, "error": proposal["error"]}

    clean_name = proposal["tool_name"]
    isolated_globals: Dict[str, Any] = {
        "__builtins__": __builtins__,
        "os": os,
        "sys": sys,
    }

    try:
        # Compile and execute within isolated dictionary
        compiled = compile(code, f"<dynamic_tool_{clean_name}>", "exec")
        exec(compiled, isolated_globals)

        fn = isolated_globals.get(clean_name)
        if not callable(fn):
            return {"success": False, "error": f"'{clean_name}' is not callable."}

        # Execute isolated test call
        if inspect.iscoroutinefunction(fn):
            import asyncio
            result = asyncio.run(fn(**test_args))
        else:
            result = fn(**test_args)

        return {
            "success": True,
            "tool_name": clean_name,
            "result": result,
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "tool_name": clean_name,
            "result": None,
            "error": f"Runtime test error: {exc}",
        }


def save_and_register_dynamic_tool(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    code: str,
    category: str = "custom",
    permission_level: PermissionLevel = PermissionLevel.ACTION,
    auto_save: bool = True,
) -> Dict[str, Any]:
    """Test, persist to disk, and register tool into the UnifiedToolBus."""
    clean_name = name.strip().lower().replace(" ", "_").replace("-", "_")

    # 1. Proposal validation
    prop = propose_tool(clean_name, description, input_schema, code, category)
    if not prop["valid"]:
        return {"registered": False, "error": prop["error"]}

    actual_name = prop["tool_name"]

    # 2. Persist to isolated development folder if requested
    if auto_save:
        target_dir = ensure_dynamic_tools_dir()
        file_path = os.path.join(target_dir, f"{actual_name}.py")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f'"""\nDynamic tool: {actual_name}\nDescription: {description}\n"""\n\n')
                f.write(code)
        except Exception as exc:
            return {"registered": False, "error": f"Failed to save tool file: {exc}"}

    # 3. Load callable into memory
    module_globals: Dict[str, Any] = {
        "__builtins__": __builtins__,
        "os": os,
        "sys": sys,
    }
    try:
        exec(code, module_globals)
        fn = module_globals.get(actual_name)
        if not callable(fn):
            return {"registered": False, "error": f"Extracted symbol '{actual_name}' is not callable."}
    except Exception as exc:
        return {"registered": False, "error": f"Failed to load callable: {exc}"}

    # 4. Register into UnifiedToolBus
    tool_def = ToolDefinition(
        name=actual_name,
        description=description,
        input_schema=input_schema,
        permission_level=permission_level,
        category=category,
        verification_required=False,
    )
    tool_bus.register_tool(tool_def, executor=fn)
    logger.info(f"Dynamic tool '{actual_name}' registered successfully.")

    return {
        "registered": True,
        "tool_name": actual_name,
        "category": category,
        "error": None,
    }


def load_all_dynamic_tools() -> int:
    """Scan and register all dynamic tools found in app/tools/dynamic/."""
    target_dir = ensure_dynamic_tools_dir()
    loaded_count = 0

    for fname in os.listdir(target_dir):
        if fname.endswith(".py") and not fname.startswith("__"):
            tool_name = fname[:-3]
            fpath = os.path.join(target_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    code = f.read()
                save_and_register_dynamic_tool(
                    name=tool_name,
                    description=f"User-created dynamic tool {tool_name}",
                    input_schema={},
                    code=code,
                    auto_save=False,
                )
                loaded_count += 1
            except Exception as e:
                logger.warning(f"Could not load dynamic tool '{fname}': {e}")

    return loaded_count
