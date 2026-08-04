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


# Global cache for rate-limited models
_RATE_LIMITED_MODELS = {}

def is_model_rate_limited(model: str) -> bool:
    import time
    if model in _RATE_LIMITED_MODELS:
        # If the penalty time (e.g. 5 minutes) hasn't passed, skip it
        if time.time() < _RATE_LIMITED_MODELS[model]:
            return True
        else:
            del _RATE_LIMITED_MODELS[model]
    return False

def mark_model_rate_limited(model: str, penalty_seconds: int = 300):
    import time
    _RATE_LIMITED_MODELS[model] = time.time() + penalty_seconds

def generate_robust_ai_response(system_prompt: str, user_prompt: str, max_tokens: int = 1500, temperature: float = 0.1) -> str:
    """
    Robust generator that attempts all available API keys (Groq and OpenAI) until success.
    Prevents crashing and gracefully falls back to OpenAI if Groq hits 429/401 limit.
    """
    import time
    
    strict_math_rule = "\n\n🚨 قاعدة حسابية صارمة جداً 🚨: في أي قالب يطلب منك وضع نسبة مئوية لاحتمالات متعاكسة (مثل نسبة الصعود مقابل نسبة الهبوط)، يجب أن يكون مجموع النسبتين 100% بالضبط! لا يجوز أبداً أن يكون المجموع غير 100%. مثلاً: إذا قررت أن نسبة الصعود 70%، يجب أن تكون نسبة الهبوط 30%. ممنوع استخدام 50% أو 50/50 إلا نادراً جداً ومبررة. طبق هذا على جميع التحليلات دون استثناء."
    final_verdict_rule = "\n\n⚖️ قاعدة الخاتمة الإجبارية: في نهاية أي تقرير أو قالب تقوم بإنشائه، يجب أن تختم بفقرة واضحة تحت عنوان '⚖️ الحكم النهائي على الذهب:' وتكتب فيها استنتاجاً نهائياً قاطعاً بخصوص اتجاه الذهب (صاعد / هابط / متذبذب) بناءً على المعطيات التي ذكرتها في التقرير."
    system_prompt = system_prompt.rstrip() + strict_math_rule + final_verdict_rule
    
    all_keys = get_api_keys()
    if not all_keys:
        return "⚠️ لم يتم العثور على أي مفاتيح ذكاء اصطناعي للعمل."
    
    groq_models = [
        "llama-3.3-70b-versatile"
    ]
    
    for key in all_keys:
        is_openai = key.startswith("sk-")
        try:
            client = UniversalAIClient(api_key=key)
            if is_openai:
                resp = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                if hasattr(resp, "choices") and resp.choices:
                    return resp.choices[0].message.content
                return str(resp)
            else:
                # Iterate models for Groq keys to handle 429 inside the same key
                for model in groq_models:
                    if is_model_rate_limited(model):
                        log.warning(f"⏭️ [AI] تخطي النموذج {model} بسبب حظر مؤقت (Rate Limit).")
                        continue
                        
                    try:
                        resp = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        if hasattr(resp, "choices") and resp.choices:
                            return resp.choices[0].message.content
                        return str(resp)
                    except Exception as e:
                        err_str = str(e).lower()
                        if "429" in err_str or "too many" in err_str:
                            log.warning(f"⚠️ [AI] النموذج {model} تعرض لـ 429. سيتم حظره مؤقتاً لـ 5 دقائق.")
                            mark_model_rate_limited(model, 300)
                            time.sleep(1)
                            continue # Try next model
                        # Auth or other error, break model loop to try next key
                        log.warning(f"⚠️ [AI Robust] Key {key[:10]}... model {model} failed: {e}. Trying next key...")
                        break 
        except Exception as key_err:
            log.warning(f"⚠️ [AI Robust] Key {key[:10]}... failed: {key_err}. Trying next key...")
            continue
            
    return "⚠️ فشل توليد التقرير: جميع المفاتيح استنفدت أو غير صالحة."
