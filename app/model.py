import os
from app.config import config

def get_model():
    provider = config.model_provider
    model_name = config.model_name
    
    # Let PydanticAI infer native Google Gemini provider if it's a Gemini model
    if "gemini" in model_name.lower():
        return f"google:{model_name}"
        
    # Route Ollama locally
    if provider == "ollama":
        return f"ollama:{model_name}"
        
    # Route Groq
    if provider == "groq":
        return f"groq:{model_name}"
        
    # Use existing LiteLLM/OpenAI-compatible abstraction
    if provider in ["openai-compatible", "litellm", "deepseek"]:
        return f"openai:{model_name}"
        
    return model_name
