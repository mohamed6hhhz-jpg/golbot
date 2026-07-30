import re
import os

file_path = "C:/Users/lenovo/Desktop/alltoools/Goldbot/bot_spot.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add _http_fallback_send
fallback_code = """
def _http_fallback_send(text: str, token: str, default_chats: list, chat_id=None) -> bool:
    import requests
    import time
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    headers = {
        "Connection": "close",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    success = True
    targets = [chat_id] if chat_id else default_chats
    for chat in targets:
        payload = {"chat_id": str(chat), "text": text}
        chat_success = False
        for attempt in range(4):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=45)
                r.raise_for_status()
                chat_success = True
                break
            except Exception as e:
                wait = 2 ** attempt
                log.warning(f"⚠️ [HTTP Fallback] {attempt+1}/4 — {e} — انتظار {wait}s")
                time.sleep(wait)
        if not chat_success: success = False
    return success

async def _telethon_bot_send"""

content = content.replace("async def _telethon_bot_send", fallback_code)

# 2. Update Bot 2 fallback
bot2_target = """    except Exception as e:
        log.warning(f"[Bot2 Telethon] {e}")
        return False


def _send_single_bot2(text: str, is_public_allowed: bool = True, chat_id=None) -> bool:"""
bot2_replacement = bot2_target

# Actually we need to replace inside _send_single_bot2
bot2_target2 = """    except Exception as e:
        log.warning(f"[Telethon Bot2] {e}")
    log.error("[Bot2] فشل الإرسال عبر Telethon.")
    return False"""
bot2_replacement2 = """    except Exception as e:
        log.warning(f"[Telethon Bot2] {e}")
    
    log.warning("[Bot2] فشل الإرسال عبر Telethon — جاري المحاولة عبر HTTP...")
    if _http_fallback_send(text, TELEGRAM_BOT_TOKEN_2, BOT2_CHATS, chat_id):
        log.info("✅ [Bot2 HTTP] تم الإرسال بنجاح.")
        return True
    
    log.error("[Bot2] فشل الإرسال عبر جميع الوسائل.")
    return False"""
content = content.replace(bot2_target2, bot2_replacement2)

# 3. Update Bot 3 fallback
bot3_target = """    except Exception as e:
        log.warning(f"[Telethon Bot3] {e}")
    log.error("[Bot3] فشل الارسال عبر Telethon.")
    return False"""
bot3_replacement = """    except Exception as e:
        log.warning(f"[Telethon Bot3] {e}")
        
    log.warning("[Bot3] فشل الإرسال عبر Telethon — جاري المحاولة عبر HTTP...")
    if _http_fallback_send(text, TELEGRAM_BOT_TOKEN_3, BOT3_CHATS, chat_id):
        log.info("✅ [Bot3 HTTP] تم الإرسال بنجاح.")
        return True
        
    log.error("[Bot3] فشل الارسال عبر جميع الوسائل.")
    return False"""
content = content.replace(bot3_target, bot3_replacement)

# 4. Update Bot 4 fallback
bot4_target = """    except Exception as e:
        log.warning(f"[Telethon Bot4] {e}")
    log.error("[Bot4] فشل الارسال عبر Telethon.")
    return False"""
bot4_replacement = """    except Exception as e:
        log.warning(f"[Telethon Bot4] {e}")
        
    log.warning("[Bot4] فشل الإرسال عبر Telethon — جاري المحاولة عبر HTTP...")
    if _http_fallback_send(text, TELEGRAM_BOT_TOKEN_4, BOT4_CHATS, chat_id):
        log.info("✅ [Bot4 HTTP] تم الإرسال بنجاح.")
        return True
        
    log.error("[Bot4] فشل الارسال عبر جميع الوسائل.")
    return False"""
content = content.replace(bot4_target, bot4_replacement)

# 5. Comment out Maaregsovereinefund
m_target = """                    _send_single(final_text, is_public, "@Maaregsovereinefund")"""
m_replacement = """                    # _send_single(final_text, is_public, "@Maaregsovereinefund")"""
content = content.replace(m_target, m_replacement)

m2_target = """                        _send_single_bot2(final_text2, is_public, "@Maaregsovereinefund")"""
m2_replacement = """                        # _send_single_bot2(final_text2, is_public, "@Maaregsovereinefund")"""
content = content.replace(m2_target, m2_replacement)

m3_target = """                        _send_single_bot3(final_text3, "@Maaregsovereinefund")"""
m3_replacement = """                        # _send_single_bot3(final_text3, "@Maaregsovereinefund")"""
content = content.replace(m3_target, m3_replacement)

m4_target = """                        _send_single_bot4(final_text4, "@Maaregsovereinefund")"""
m4_replacement = """                        # _send_single_bot4(final_text4, "@Maaregsovereinefund")"""
content = content.replace(m4_target, m4_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Replacement done!")
