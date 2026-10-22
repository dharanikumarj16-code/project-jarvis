import os
from typing import Optional

class JarvisConfig:
    def __init__(self):
        # AI/Model
        self.model_provider = os.getenv("JARVIS_MODEL_PROVIDER", "ollama")
        self.model_name = os.getenv("JARVIS_MODEL", "smollm2:135m")
        
        # Voice
        self.voice_enabled = os.getenv("VOICE_ENABLED", "false").lower() == "true"
        self.tts_enabled = os.getenv("TTS_ENABLED", "false").lower() == "true"
        
        # Tools & Engine
        self.max_steps = int(os.getenv("JARVIS_MAX_STEPS", "15"))
        self.max_retries = int(os.getenv("JARVIS_MAX_RETRIES", "2"))
        
        # Layer 2: Fast-NLP Semantic Router
        self.router_semantic_enabled = os.getenv("JARVIS_ROUTER_SEMANTIC", "true").lower() in ("true", "1", "yes")
        self.router_semantic_threshold = float(os.getenv("JARVIS_ROUTER_SEMANTIC_THRESHOLD", "0.78"))

        # Layer 3: Local Brain (FunctionGemma via llama-cpp-python GGUF or Ollama)
        self.local_brain_backend = os.getenv("JARVIS_LOCAL_BRAIN_BACKEND", "auto").lower()  # "llama_cpp", "ollama", or "auto"
        self.local_brain_gguf_path = os.getenv("JARVIS_LOCAL_BRAIN_GGUF_PATH", "models/functiongemma-270m.gguf")
        self.local_brain_threads = int(os.getenv("JARVIS_LOCAL_BRAIN_THREADS", "4"))
        self.local_brain_gpu_layers = int(os.getenv("JARVIS_LOCAL_BRAIN_GPU_LAYERS", "0"))
        self.ollama_host = os.getenv("JARVIS_OLLAMA_HOST", "http://127.0.0.1:11434")
        self.reasoning_model = os.getenv("JARVIS_REASONING_MODEL", "smollm2:135m")
        self.local_brain_model = os.getenv("JARVIS_LOCAL_BRAIN_MODEL", "functiongemma:latest")
        self.local_brain_enabled = os.getenv("JARVIS_LOCAL_BRAIN_ENABLED", "true").lower() in ("true", "1", "yes")
        self.local_brain_timeout = float(os.getenv("JARVIS_LOCAL_BRAIN_TIMEOUT", "15.0"))
        self.local_brain_max_turns = int(os.getenv("JARVIS_LOCAL_BRAIN_MAX_TURNS", "3"))
        self.local_brain_max_tools = int(os.getenv("JARVIS_LOCAL_BRAIN_MAX_TOOLS", "5"))
        
        # PydanticAI expects GOOGLE_API_KEY for Gemini, but we use GEMINI_API_KEY
        if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")
            
        # PydanticAI natively requires OLLAMA_BASE_URL for Ollama
        if self.model_provider == "ollama" and not os.getenv("OLLAMA_BASE_URL"):
            os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"
            
        # Configuration for Deepseek
        if self.model_provider == "deepseek":
            if not os.getenv("OPENAI_BASE_URL"):
                os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"
            if os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"):
                os.environ["OPENAI_API_KEY"] = os.getenv("DEEPSEEK_API_KEY")
            
        # Hide the PydanticAI ASCII Art Banner in the CLI
        os.environ["PYDANTIC_AI_NO_BANNER"] = "1"

config = JarvisConfig()
