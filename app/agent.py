from pydantic_ai import Agent, Tool, RunContext
from pydantic import create_model, Field
from app.model import get_model
from app.tools.bus import tool_bus
import typing

def parse_json_schema_type(name: str, schema: dict, required: bool = True):
    from typing import Any, Optional
    type_str = schema.get("type", "string")
    
    if type_str == "integer": ptype = int
    elif type_str == "number": ptype = float
    elif type_str == "boolean": ptype = bool
    elif type_str == "string": ptype = str
    elif type_str == "array":
        items_schema = schema.get("items", {})
        item_type = parse_json_schema_type(f"{name}_item", items_schema, True)[0]
        ptype = list[item_type]
    elif type_str == "object":
        properties = schema.get("properties", {})
        req_fields = schema.get("required", [])
        fields = {}
        for prop_name, prop_schema in properties.items():
            is_req = prop_name in req_fields
            if "Optional" in str(prop_schema.get("description", "")):
                is_req = False
            fields[prop_name] = parse_json_schema_type(f"{name}_{prop_name}", prop_schema, is_req)
        
        if not properties:
            ptype = dict
        else:
            ptype = create_model(f"{name.capitalize()}Model", **fields)
    elif type_str == "null":
        ptype = type(None)
    else:
        ptype = typing.Any
        
    description = schema.get("description", "")
    default = schema.get("default", ...)
    
    if not required:
        ptype = Optional[ptype]
        if default is ...:
            default = None
            
    return (ptype, Field(default=default, description=description))

def json_schema_to_pydantic_fields(schema: dict) -> dict:
    fields = {}
    is_nested_obj = schema.get("type") == "object" and "properties" in schema
    props = schema.get("properties", schema) if is_nested_obj else schema
    req_fields = schema.get("required", []) if is_nested_obj else []

    for param_name, param_info in props.items():
        if not isinstance(param_info, dict):
            continue
        is_req = param_name in req_fields if req_fields else ("Optional" not in str(param_info.get("description", "")))
        fields[param_name] = parse_json_schema_type(param_name, param_info, is_req)
    return fields

def build_dynamic_tools(categories: set[str] | None = None):
    """Build dynamic tool proxies, optionally filtered by categories.
    Args:
        categories: Set of category names to include. If None, include all.
    """
    tools = []
    # Normalise categories for case‑insensitive matching
    cat_set = {c.lower() for c in categories} if categories else None
    for tool_name, tool_def in tool_bus.tools.items():
        if cat_set and tool_def.category.lower() not in cat_set:
            continue
        fields = json_schema_to_pydantic_fields(tool_def.input_schema)
        InputModel = create_model(f"{tool_def.name}Args", **fields)
        
        def make_tool_func(name, description, model_cls=InputModel):
            async def tool_func(ctx: RunContext, args: model_cls):
                kwargs = args.model_dump(exclude_none=True)
                return await tool_bus.execute(name, kwargs)
                
            tool_func.__name__ = name
            tool_func.__doc__ = description
            return tool_func
            
        proxy_func = make_tool_func(tool_def.name, tool_def.description)
        tools.append(Tool(proxy_func, name=tool_def.name, description=tool_def.description))
    return tools

_jarvis_agent = None

def get_agent():
    """
    Returns the global PydanticAI Agent instance to avoid rebuilds.
    """
    global _jarvis_agent
    if _jarvis_agent is None:
        # Build tools ONCE globally
        tools = build_dynamic_tools()
        _jarvis_agent = Agent(get_model(), tools=tools)
        
        @_jarvis_agent.system_prompt
        def get_system_prompt(ctx: RunContext) -> str:
            return """You are JARVIS — an autonomous desktop AI operator for Windows.
Your brain is powered by local SmolLM2-135M as the reasoning and planning model, with FunctionGemma for tool calling.

CORE OPERATING INSTRUCTIONS:
1. REASONING & PLANNING: Use step-by-step reasoning to decompose complex goals into discrete, ordered tasks.
2. DIRECT TOOL EXECUTION: Immediately invoke relevant tools via the tool bus. Never output conversational guides or instructions when an action is requested.
3. NATIVE APIS FIRST: Always prioritize native Windows APIs, PowerShell/CMD, and filesystem tools over visual screenshots or mouse coordinates.
4. CONTROL & VALIDATION: Track system state, verify execution outcomes, and handle retries or fallbacks gracefully.
5. CONCISE REPORTING: Return precise, one-line execution confirmations without conversational filler."""

    return _jarvis_agent
