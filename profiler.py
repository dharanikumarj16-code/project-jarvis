import time
import os
import sys
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.mcp_client import FileSystemMCPClient
from app.core import JarvisCore, parse_fallback_json
from app.tools.bus import tool_bus
from app.agent import get_agent
from app.voice.config import VoiceConfig

VoiceConfig.VOICE_ENABLED = False
VoiceConfig.TTS_ENABLED = False

class ProfilingCore(JarvisCore):
    def __init__(self, mcp_client):
        super().__init__(mcp_client)
        self.metrics = {
            "llm_calls": 0,
            "tool_calls": 0,
            "agent_rebuilds": 0,
            "fallback_parser_used": False,
            "stages": {
                "agent_initialization": 0,
                "network_api": 0,
                "tool_execution": 0,
            }
        }
        
        # Patch tool bus for profiling inside this core
        self.orig_execute = tool_bus.execute
        
        async def profiling_execute(tool_name, args):
            self.metrics["tool_calls"] += 1
            start = time.perf_counter()
            try:
                res = await self.orig_execute(tool_name, args)
                return res
            finally:
                self.metrics["stages"]["tool_execution"] += (time.perf_counter() - start) * 1000
                
        tool_bus.execute = profiling_execute

    async def process_request(self, user_input: str, history: list) -> tuple[list, str]:
        current_prompt = user_input
        
        while True:
            # 1. Agent Init
            start_agent = time.perf_counter()
            agent = get_agent()
            self.metrics["stages"]["agent_initialization"] += (time.perf_counter() - start_agent) * 1000
            self.metrics["agent_rebuilds"] += 1
            
            try:
                # 2. LLM Call
                self.metrics["llm_calls"] += 1
                start_llm = time.perf_counter()
                
                # We time the actual execution
                result = await agent.run(current_prompt, message_history=history)
                
                self.metrics["stages"]["network_api"] += (time.perf_counter() - start_llm) * 1000
                
                history = result.all_messages()
                final_response = getattr(result, 'data', getattr(result, 'output', str(result)))

                    
                if "{" in final_response and "}" in final_response:
                    calls = parse_fallback_json(final_response)
                    if calls:
                        self.metrics["fallback_parser_used"] = True
                        observations = []
                        for call in calls:
                            tool_name = call["tool_name"]
                            args = call["arguments"]
                            obs = await tool_bus.execute(tool_name, args)
                            observations.append(f"Tool '{tool_name}' returned:\n{json.dumps(obs, default=str)}")
                        
                        if observations:
                            current_prompt = "\n\n".join(observations)
                            continue
                            
                return history, final_response
                
            except Exception as e:
                return history, f"An error occurred: {str(e)}"

async def run_test(core, name, command):
    core.metrics["llm_calls"] = 0
    core.metrics["tool_calls"] = 0
    core.metrics["agent_rebuilds"] = 0
    core.metrics["fallback_parser_used"] = False
    core.metrics["stages"] = {k: 0 for k in core.metrics["stages"]}
    
    print(f"\n--- Running Test: {name} ---")
    start = time.perf_counter()
    history, response = await core.process_request(command, [])
    total = (time.perf_counter() - start) * 1000
    
    print(f"Command: {command}")
    print(f"Total latency: {total:.2f} ms")
    print(f"Stage-by-stage latency:")
    for stage, duration in core.metrics["stages"].items():
        if duration > 0:
            print(f"  - {stage}: {duration:.2f} ms")
    print(f"Number of LLM calls: {core.metrics['llm_calls']}")
    print(f"Number of tool calls: {core.metrics['tool_calls']}")
    print(f"Number of agent rebuilds: {core.metrics['agent_rebuilds']}")
    print(f"Fallback parser used: {'YES' if core.metrics['fallback_parser_used'] else 'NO'}")

async def main():
    mcp = FileSystemMCPClient("C:\\")
    await mcp.connect()
    core = ProfilingCore(mcp)
    
    await run_test(core, "1. Simple command", "Hello! What is 2 + 2?")
    await run_test(core, "2. Simple tool command", "Write 'Hello World' to C:\\temp_jarvis_test.txt")
    await run_test(core, "3. Multi-step command", "Create a file C:\\temp_jarvis2.txt, then read it back and tell me the contents.")
    await run_test(core, "4. Capability activation command", "Please activate the BROWSER capability.")
    await run_test(core, "5. Invalid tool call", "Call a tool named nonexistent_tool with no arguments.")
    await run_test(core, "6. Tool execution failure", "Read the file C:\\this_file_does_not_exist_at_all_123.txt")
    
    await mcp.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
