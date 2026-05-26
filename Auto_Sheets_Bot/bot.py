import re
import logging
import os
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ==========================================
# 1. إعدادات تيليجرام
# ==========================================
API_ID = 34105911  
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'  
TARGET_CHANNEL = ['https://t.me/egxupdates', 'me'] 

# رابط الـ Web App الخاص بـ Google Apps Script
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL", "")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ==========================================
# 2. دالة الاتصال بـ Apps Script
# ==========================================
def copy_google_sheet(sheet_id):
    if not APPS_SCRIPT_URL:
        logging.error("❌ رابط APPS_SCRIPT_URL غير موجود في إعدادات Hugging Face (Secrets)!")
        return

    try:
        logging.info(f"جاري إرسال أمر النسخ لسكربت جوجل للشيت رقم: {sheet_id} ...")
        # استدعاء الرابط مع تمرير الـ ID الخاص بالشيت
        response = requests.get(f"{APPS_SCRIPT_URL}?sheet_id={sheet_id}", timeout=30)
        
        if "SUCCESS" in response.text:
            logging.info(f"✅ تم إنشاء مجلد جديد ونسخ الشيت بنجاح! الرابط: {response.text.replace('SUCCESS: ', '')}")
        else:
            logging.error(f"❌ حدث خطأ داخل سكربت جوجل: {response.text}")
            
    except Exception as e:
        logging.error(f"❌ فشل الاتصال بسكربت جوجل: {e}")

# ==========================================
# 3. تشغيل بوت تيليجرام
# ==========================================
session_string = os.environ.get("SHEETS_SESSION_STRING", "")
client = TelegramClient(StringSession(session_string), API_ID, API_HASH)

@client.on(events.NewMessage(chats=TARGET_CHANNEL))
async def handler(event):
    message_text = event.message.message
    if message_text:
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', message_text)
        if match:
            sheet_id = match.group(1)
            copy_google_sheet(sheet_id)

async def start_sheets_bot():
    if not session_string:
        logging.error("❌ SHEETS_SESSION_STRING is missing from environment variables!")
        return
    logging.info("🚀 البوت شغال دلوقتي ومستني الرسايل...")
    await client.start()
    await client.run_until_disconnected()