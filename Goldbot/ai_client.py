"""
Universal AI Client wrapper supporting both OpenAI (sk-...) and Groq (gsk_...) keys.
Enables seamless switching or fallback between OpenAI and Groq without changing LLM calling syntax.
"""
import os
import random
import logging

log = logging.getLogger(__name__)

# Primary keys list - loaded safely from environment variables (Hugging Face Secrets)
DEFAULT_KEYS = []

def get_api_keys():
    try:
        from Goldbot.secrets_config import GROQ_KEYS_FALLBACK
    except ImportError:
        try:
            from secrets_config import GROQ_KEYS_FALLBACK
        except ImportError:
            GROQ_KEYS_FALLBACK = []

    env_keys = (
        os.environ.get("OPENAI_API_KEY", "") or 
        os.environ.get("GROQ_API_KEY", "") or 
        os.environ.get("GROQ_KEYS", "") or
        os.environ.get("AI_API_KEY", "")
    )
    keys = []
    if env_keys:
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        
    combined = []
    seen = set()
    for k in (GROQ_KEYS_FALLBACK + keys + DEFAULT_KEYS):
        if k and k not in seen:
            seen.add(k)
            combined.append(k)
    return combined


class SimpleOpenAIClient:
    """Fallback HTTP client for OpenAI that requires zero external SDK dependencies."""
    def __init__(self, api_key):
        self.api_key = api_key
    @property
    def chat(self): return self
    @property
    def completions(self): return self
    def create(self, messages, model="gpt-4o-mini", temperature=0.1, max_tokens=700, **kwargs):
        import requests
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        res_json = resp.json()
        content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        class _Msg:
            def __init__(self, c): self.content = c
        class _Choice:
            def __init__(self, c): self.message = _Msg(c)
        class _Resp:
            def __init__(self, c): self.choices = [_Choice(c)]
        return _Resp(content)


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
                # Use dependency-free SimpleOpenAIClient instead of Groq base_url which appends /openai/v1
                self._client = SimpleOpenAIClient(api_key=self.api_key)
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
            try:
                return self.parent._client.chat.completions.create(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            except Exception as e:
                err_str = str(e).lower()
                if "401" in err_str or "auth" in err_str or "unauthorized" in err_str or "invalid_api_key" in err_str:
                    log.warning(f"⚠️ [UniversalAIClient] Key {self.parent.api_key[:12]}... failed ({e}). Trying another key...")
                    all_keys = [k for k in get_api_keys() if k != self.parent.api_key]
                    if all_keys:
                        new_key = random.choice(all_keys)
                        self.parent.__init__(api_key=new_key)
                        if self.parent.is_openai:
                            model = "gpt-4o-mini"
                        return self.parent._client.chat.completions.create(
                            messages=messages,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                raise
