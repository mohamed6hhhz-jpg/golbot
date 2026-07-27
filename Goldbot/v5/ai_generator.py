import logging
import time
try:
    from Goldbot.ai_client import UniversalAIClient as Groq
except ImportError:
    from ai_client import UniversalAIClient as Groq
from Goldbot.v5.config import GROQ_API_KEY, GROQ_MODELS
from Goldbot.v5.prompts import get_system_prompt, get_template

log = logging.getLogger(__name__)

def generate_ai_section(section_name: str, title: str, context_str: str, is_spot: bool) -> str:
    """
    Generates a single section of the report securely using the fallback system.
    Ensures complete separation of Spot and Futures via system prompt injection.
    """
    if not GROQ_API_KEY:
        return f"⚠️ مفتاح API غير متوفر لتوليد {title}"

    client = Groq(api_key=GROQ_API_KEY)
    
    system_prompt = get_system_prompt(is_spot)
    template_format = get_template(section_name, is_spot)
    
    user_prompt = f"""
البيانات الحية الدقيقة:
{context_str}

المطلوب:
قم بملء هذا القالب حصرياً وباحترافية عالية جداً، بناءً على القواعد الصارمة:
{template_format}

تأكد من عدم وجود أي تناقض، ولا تكتب أي مقدمات أو خاتمات خارج القالب.
"""

    for model_name in GROQ_MODELS:
        try:
            for attempt in range(3):
                try:
                    log.info(f"🤖 [{model_name}] جاري توليد {title}...")
                    resp = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        model=model_name,
                        temperature=0.3,
                        max_tokens=2048,
                    )
                    content = resp.choices[0].message.content
                    # Quick sanity check for crossover
                    if is_spot and "آجل" in content:
                        content = content.replace("آجل", "[فوري]") # Force correction if hallucinated
                    elif not is_spot and "فوري" in content:
                        content = content.replace("فوري", "[آجل]")

                    return content.strip()
                except Exception as e:
                    err_str = str(e).lower()
                    if 'rate limit' in err_str or '429' in err_str:
                        log.warning(f"⏳ [{model_name}] Rate Limit! الانتظار 25 ثانية ثم إعادة المحاولة...")
                        time.sleep(25)
                        continue
                    else:
                        log.warning(f"⚠️ [{model_name}] فشل توليد {title}: {e}")
                        time.sleep(2)
                        break # Break out of attempt loop to try next model
        except Exception as e:
            pass
            
    return f"⚠️ جميع النماذج فشلت في توليد {title}"
