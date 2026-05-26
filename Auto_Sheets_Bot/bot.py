import re
import logging
import os
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import tempfile
import json
import pdfplumber
import arabic_reshaper
from bidi.algorithm import get_display

# ==========================================
# 1. إعدادات تيليجرام
# ==========================================
API_ID = 34105911  
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'  
TARGET_CHANNEL = ['https://t.me/egxupdates', 'https://t.me/Teamstock', 'me'] 

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
# 2.5 دالة استخراج الجداول من الـ PDF وإرسالها لجوجل
# ==========================================
def process_pdf_and_send(pdf_path, pdf_name):
    if not APPS_SCRIPT_URL:
        logging.error("❌ رابط APPS_SCRIPT_URL غير موجود!")
        return

    extracted_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        cleaned_row = []
                        for cell in row:
                            if cell:
                                # معالجة اللغة العربية في ملفات الـ PDF
                                reshaped_text = arabic_reshaper.reshape(str(cell).replace('\\n', ' '))
                                bidi_text = get_display(reshaped_text)
                                cleaned_row.append(bidi_text)
                            else:
                                cleaned_row.append("")
                        if any(cleaned_row):
                            extracted_data.append(cleaned_row)
                            
        if not extracted_data:
            logging.info(f"⚠️ لم يتم العثور على أي جداول في الملف: {pdf_name}")
            return
            
        logging.info(f"📊 تم استخراج {len(extracted_data)} صف. جاري الإرسال لجوجل شيت...")
        
        payload = {
            "fileName": f"بيانات مستخرجة - {pdf_name}",
            "data": extracted_data
        }
        
        response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=60)
        
        if "SUCCESS" in response.text:
            logging.info(f"✅ تم إنشاء جوجل شيت بالبيانات بنجاح! الرابط: {response.text.replace('SUCCESS: ', '')}")
        else:
            logging.error(f"❌ حدث خطأ داخل سكربت جوجل أثناء إنشاء الشيت: {response.text}")
            
    except Exception as e:
        logging.error(f"❌ فشل استخراج أو إرسال الـ PDF: {e}")

# ==========================================
# 3. تشغيل بوت تيليجرام
# ==========================================
session_string = os.environ.get("SHEETS_SESSION_STRING", "")
client = TelegramClient(StringSession(session_string), API_ID, API_HASH)

@client.on(events.NewMessage(chats=TARGET_CHANNEL))
async def handler(event):
    message_text = event.message.message or ""
    
    # 1. فحص روابط جوجل شيت
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', message_text)
    if match:
        sheet_id = match.group(1)
        # تنفيذ النسخ في خلفية عشان ما يعطلش البوت
        asyncio.get_event_loop().run_in_executor(None, copy_google_sheet, sheet_id)
        return
        
    # 2. فحص ملفات الـ PDF
    if event.document:
        file_name = "document.pdf"
        for attr in event.document.attributes:
            if hasattr(attr, 'file_name'):
                file_name = attr.file_name
                break
                
        if file_name.lower().endswith('.pdf'):
            logging.info(f"📥 تم رصد ملف PDF: {file_name}. جاري التحميل...")
            
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, file_name)
            
            await event.download_media(file=file_path)
            logging.info(f"📄 اكتمل تحميل {file_name}. جاري استخراج البيانات...")
            
            # تنفيذ الاستخراج في خلفية لمنع تجميد التليجرام
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, process_pdf_and_send, file_path, file_name)
            
            # مسح الملف بعد الانتهاء
            if os.path.exists(file_path):
                os.remove(file_path)

async def start_sheets_bot():
    if not session_string:
        logging.error("❌ SHEETS_SESSION_STRING is missing from environment variables!")
        return
    logging.info("🚀 البوت شغال دلوقتي ومستني الرسايل...")
    await client.start()
    await client.run_until_disconnected()