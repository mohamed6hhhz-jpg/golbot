import os
import logging
from telethon import TelegramClient

log = logging.getLogger(__name__)

API_ID = 34105911
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

async def publish_report_to_telegram(report_text: str, target_chats: list):
    log.info(f"📱 محاولة الاتصال بتيليجرام لنشر التقرير إلى {target_chats}...")
    
    # We will use the existing session file if StringSession is empty
    if SESSION_STRING:
        from telethon.sessions import StringSession
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    else:
        # Fallback to local file session which works for the existing V4 bot
        client = TelegramClient("c:\\Users\\lenovo\\Desktop\\alltoools\\Goldbot\\goldbot_bot_session", API_ID, API_HASH)
        
    await client.connect()
    if not await client.is_user_authorized():
        log.error("❌ حساب التيليجرام غير مسجل! تأكد من ملف الـ session.")
        return

    log.info("✅ تم الاتصال بنجاح. جاري النشر للقنوات...")
    
    # Split message if it exceeds Telegram's 4096 character limit
    parts = []
    while len(report_text) > 4000:
        split_idx = report_text.rfind('\n', 0, 4000)
        if split_idx == -1: split_idx = 4000
        parts.append(report_text[:split_idx])
        report_text = report_text[split_idx:]
    if report_text:
        parts.append(report_text)
        
    for chat in target_chats:
        try:
            for i, part in enumerate(parts):
                msg = part
                if len(parts) > 1:
                    msg = f"📄 الجزء {i+1}/{len(parts)}\n" + msg
                await client.send_message(chat, msg)
            log.info(f"✅ تم إرسال التقرير إلى {chat}")
        except Exception as e:
            log.error(f"❌ فشل إرسال التقرير إلى {chat}: {e}")
            
    await client.disconnect()
