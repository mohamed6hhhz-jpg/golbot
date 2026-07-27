"""
Universal AI Client wrapper supporting both OpenAI (sk-...) and Groq (gsk_...) keys.
Enables seamless switching or fallback between OpenAI and Groq without changing LLM calling syntax.
"""
import os
import random
import logging

log = logging.getLogger(__name__)

# Primary keys list - starts with working OpenAI key
DEFAULT_KEYS = [
    "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",
]

def get_api_keys():
    env_keys = (
        os.environ.get("OPENAI_API_KEY", "") or 
        os.environ.get("GROQ_API_KEY", "") or 
        os.environ.get("GROQ_KEYS", "") or
        os.environ.get("AI_API_KEY", "")
    )
    if env_keys:
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        if keys:
            seen = set()
            combined = []
            for k in (keys + DEFAULT_KEYS):
                if k not in seen:
                    seen.add(k)
                    combined.append(k)
            return combined
    return DEFAULT_KEYS


class UniversalAIClient:
    """
    Drop-in replacement for Groq client that supports both OpenAI and Groq API keys.
    """
    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key or ""
        self.is_openai = self.api_key.startswith("sk-")
        if self.is_openai:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                from groq import Groq as _Groq
                self._client = _Groq(api_key=self.api_key, base_url="https://api.openai.com/v1")
        else:
            from groq import Groq as _Groq
            self._client = _Groq(api_key=self.api_key, **kwargs)
            
    @property
    def chat(self):
        return self._UniversalChat(self)
        
    class _UniversalChat:
        def __init__(self, parent):
            self.parent = parent
        @property
        def completions(self):
            return self.parent._UniversalCompletions(self.parent)
            
    class _UniversalCompletions:
        def __init__(self, parent):
            self.parent = parent
        def create(self, messages, model=None, temperature=0.1, max_tokens=700, **kwargs):
            if self.parent.is_openai:
                model = "gpt-4o-mini"
            return self.parent._client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
