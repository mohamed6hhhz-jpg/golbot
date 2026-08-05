with open('Goldbot/ai_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We will add a global cache for rate limited models to avoid retrying them over and over
add_cache = """
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
"""

if "_RATE_LIMITED_MODELS" not in content:
    content = content.replace('def generate_robust_ai_response', add_cache + '\ndef generate_robust_ai_response')

# Update the loop to use the cache
loop_find = """                for model in groq_models:
                    try:
                        resp = client.chat.completions.create("""

loop_replace = """                for model in groq_models:
                    if is_model_rate_limited(model):
                        log.warning(f"⏭️ [AI] تخطي النموذج {model} بسبب حظر مؤقت (Rate Limit).")
                        continue
                        
                    try:
                        resp = client.chat.completions.create("""
                        
content = content.replace(loop_find, loop_replace)

error_find = """                    except Exception as e:
                        err_str = str(e).lower()
                        if "429" in err_str or "too many" in err_str:
                            time.sleep(2)"""

error_replace = """                    except Exception as e:
                        err_str = str(e).lower()
                        if "429" in err_str or "too many" in err_str:
                            log.warning(f"⚠️ [AI] النموذج {model} تعرض لـ 429. سيتم حظره مؤقتاً لـ 5 دقائق.")
                            mark_model_rate_limited(model, 300)
                            time.sleep(1)"""

content = content.replace(error_find, error_replace)

with open('Goldbot/ai_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
