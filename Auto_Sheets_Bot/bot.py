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
def copy_google_sheet(sheet_id):
    try:
        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        drive_service = build('drive', 'v3', credentials=credentials)

        file_metadata = {'parents': [DESTINATION_FOLDER_ID]}
        
        logging.info(f"جاري نسخ الشيت رقم: {sheet_id} ...")
        copied_file = drive_service.files().copy(
            fileId=sheet_id, body=file_metadata, supportsAllDrives=True
        ).execute()
        
        try:
            # Fetch the owner of the destination folder automatically
            folder_info = drive_service.files().get(fileId=DESTINATION_FOLDER_ID, fields="owners", supportsAllDrives=True).execute()
            owner_email = folder_info['owners'][0]['emailAddress']
            
            # Transfer ownership to the folder's owner
            permission = {
                'type': 'user',
                'role': 'owner',
                'emailAddress': owner_email
            }
            drive_service.permissions().create(
                fileId=copied_file['id'],
                body=permission,
                transferOwnership=True,
                supportsAllDrives=True
            ).execute()
            logging.info(f"✅ تم نقل ملكية الملف بنجاح إلى: {owner_email}")
        except Exception as perm_error:
            logging.warning(f"⚠️ تحذير: فشل نقل الملكية التلقائي (قد يكون بسبب قيود Google للحسابات العادية): {perm_error}")
            
        logging.info(f"✅ تم النسخ بنجاح! الشيت موجود دلوقتي في فولدرك.")
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