import re
import logging
import os
from telethon import TelegramClient, events
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ==========================================
# 1. إعدادات تيليجرام وجوجل
# ==========================================
API_ID = 34105911  
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'  
TARGET_CHANNEL = ['https://t.me/egxupdates', 'me']

DESTINATION_FOLDER_ID = '10qMINGvBxf_O57xnv90LflgklfTPyh0J' 
CREDENTIALS_FILE = 'credentials.json' 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ==========================================
# 2. السيرفر الوهمي (عشان Render ماينامش)
# ==========================================
# تم حذف الفلاسك هنا لأننا نستخدم FastAPI كأساس

# ==========================================
# 3. دالة الاتصال بجوجل درايف والنسخ
# ==========================================
def get_drive_service():
    """Build Google Drive service from env var secret or fallback to local file."""
    import json
    scopes = ['https://www.googleapis.com/auth/drive']
    
    google_creds_env = os.environ.get("GOOGLE_CREDENTIALS")
    if google_creds_env:
        logging.info("🔑 تحميل بيانات الاعتماد من متغير البيئة GOOGLE_CREDENTIALS...")
        creds_info = json.loads(google_creds_env)
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
    elif os.path.exists(CREDENTIALS_FILE):
        logging.info(f"🔑 تحميل بيانات الاعتماد من الملف المحلي: {CREDENTIALS_FILE}")
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    else:
        logging.error("❌ لا يوجد ملف credentials.json ولا متغير بيئة GOOGLE_CREDENTIALS. البوت لن يعمل.")
        return None
    
    return build('drive', 'v3', credentials=credentials)

def copy_google_sheet(sheet_id):
    """Create a Drive Shortcut (alias) to the sheet instead of a physical copy.
    Shortcuts consume ZERO storage against the Service Account's quota."""
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return

        # Fetch the original file name so the shortcut has a meaningful label
        try:
            original = drive_service.files().get(
                fileId=sheet_id, fields="name", supportsAllDrives=True
            ).execute()
            original_name = original.get("name", sheet_id)
        except Exception:
            original_name = sheet_id

        shortcut_metadata = {
            'name': f"[رابط] {original_name}",
            'mimeType': 'application/vnd.google-apps.shortcut',
            'shortcutDetails': {'targetId': sheet_id},
            'parents': [DESTINATION_FOLDER_ID]
        }

        logging.info(f"جاري إنشاء اختصار للشيت: {original_name} ({sheet_id}) ...")
        drive_service.files().create(
            body=shortcut_metadata, supportsAllDrives=True
        ).execute()
        logging.info(f"✅ تم إنشاء الاختصار بنجاح! الشيت متاح في فولدرك بدون استهلاك أي مساحة.")
    except Exception as e:
        logging.error(f"❌ حصلت مشكلة في جوجل درايف: {e}")

# ==========================================
# 4. تشغيل بوت تيليجرام
# ==========================================
from telethon.sessions import StringSession
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