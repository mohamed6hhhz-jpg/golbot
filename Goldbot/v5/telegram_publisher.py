import os
import logging
from telethon import TelegramClient

log = logging.getLogger(__name__)

API_ID = 34105911
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

async def publish_report_to_telegram(reports_list: list, target_chats: list):
    log.info(f"📱 محاولة الاتصال بتيليجرام لنشر التقرير إلى {target_chats}...")
    
    session_path = "Goldbot/goldbot_bot_session"
    client = TelegramClient(session_path, API_ID, API_HASH)
        
    await client.connect()
    if not await client.is_user_authorized():
        log.error("❌ حساب التيليجرام غير مسجل! تأكد من ملف الـ session.")
        return

    log.info("✅ تم الاتصال بنجاح. جاري النشر للقنوات...")
    
    for chat in target_chats:
        try:
            for index, report_text in enumerate(reports_list):
                if not report_text.strip():
                    continue
                # Split if a single template somehow exceeds 4000
                parts = []
                temp_text = report_text
                while len(temp_text) > 4000:
                    split_idx = temp_text.rfind('\n', 0, 4000)
                    if split_idx == -1: split_idx = 4000
                    parts.append(temp_text[:split_idx])
                    temp_text = temp_text[split_idx:]
                if temp_text:
                    parts.append(temp_text)
                    
                for msg in parts:
                    await client.send_message(chat, msg)
                    await asyncio.sleep(1) # Sleep slightly between messages to avoid flood
            log.info(f"✅ تم إرسال {len(reports_list)} قوالب بنجاح إلى {chat}")
        except Exception as e:
            log.error(f"❌ فشل إرسال التقرير إلى {chat}: {e}")
            
    await client.disconnect()
