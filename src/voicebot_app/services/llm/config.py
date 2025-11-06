"""
LLM Configuration Module
"""

import os
from dotenv import load_dotenv

load_dotenv()

class LLMConfig:
    """Configuration for Language Model providers"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq.com")
        # Groq-specific configuration
        self.groq_api_url = os.getenv("GROQ_LLM_API_URL")
        self.groq_api_key = os.getenv("GROQ_LLM_API_KEY")
        self.groq_model = os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant")
        self.groq_completions_path = os.getenv("GROQ_LLM_COMPLETIONS_PATH", "/openai/v1/chat/completions")
        
        # Mistral.ai-specific configuration
        self.mistral_api_url = os.getenv("MISTRAL_LLM_API_URL", "https://api.mistral.ai/v1")
        self.mistral_api_key = os.getenv("MISTRAL_LLM_API_KEY")
        self.mistral_model = os.getenv("MISTRAL_LLM_MODEL", "mistral-large-latest")
        self.mistral_completions_path = os.getenv("MISTRAL_LLM_COMPLETIONS_PATH", "/chat/completions")
        
        # OpenRouter.ai-specific configuration
        self.openrouter_api_url = os.getenv("OPENROUTER_LLM_API_URL", "https://openrouter.ai/api/v1")
        self.openrouter_api_key = os.getenv("OPENROUTER_LLM_API_KEY")
        self.openrouter_model = os.getenv("OPENROUTER_LLM_MODEL", "anthropic/claude-3.5-sonnet")
        self.openrouter_completions_path = os.getenv("OPENROUTER_LLM_COMPLETIONS_PATH", "/chat/completions")
        self.openrouter_app_name = os.getenv("OPENROUTER_LLM_APP_NAME", "VoiceBot")
        self.openrouter_app_url = os.getenv("OPENROUTER_LLM_APP_URL", "https://github.com/etienne/voicebot")
        
        # Llama.cpp-specific configuration
        self.llama_cpp_api_url = os.getenv("LLAMA_CPP_LLM_API_URL", "http://llama-cpp:8002")
        self.llama_cpp_api_key = os.getenv("LLAMA_CPP_LLM_API_KEY", "")
        self.llama_cpp_model = os.getenv("LLAMA_CPP_LLM_MODEL", "default")
        self.llama_cpp_completions_path = os.getenv("LLAMA_CPP_LLM_COMPLETIONS_PATH", "/v1/chat/completions")

    def get_provider(self):
        """Get the current LLM provider"""
        return self.provider

    def get_groq_config(self):
        """Get Groq-specific configuration"""
        return {
            "api_url": self.groq_api_url,
            "api_key": self.groq_api_key,
            "model": self.groq_model,
            "completions_path": self.groq_completions_path
        }
    
    def get_mistral_config(self):
        """Get Mistral.ai-specific configuration"""
        return {
            "api_url": self.mistral_api_url,
            "api_key": self.mistral_api_key,
            "model": self.mistral_model,
            "completions_path": self.mistral_completions_path
        }
    
    def get_openrouter_config(self):
        """Get OpenRouter.ai-specific configuration"""
        return {
            "api_url": self.openrouter_api_url,
            "api_key": self.openrouter_api_key,
            "model": self.openrouter_model,
            "completions_path": self.openrouter_completions_path,
            "app_name": self.openrouter_app_name,
            "app_url": self.openrouter_app_url
        }
    
    def get_llama_cpp_config(self):
        """Get Llama.cpp-specific configuration"""
        return {
            "api_url": self.llama_cpp_api_url,
            "api_key": self.llama_cpp_api_key,
            "model": self.llama_cpp_model,
            "completions_path": self.llama_cpp_completions_path
        }

# Initialize the configuration
llm_config = LLMConfig()