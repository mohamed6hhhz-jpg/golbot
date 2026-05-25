from telethon import TelegramClient

# دي بياناتك الأساسية مفيش فيها تغيير
API_ID = 34105911  
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'  

# ده اسم الملف اللي هيطلع
client = TelegramClient('my_bot_session', API_ID, API_HASH)

async def main():
    print("✅ تم تسجيل الدخول وإنشاء ملف my_bot_session.session بنجاح!")
    
with client:
    client.loop.run_until_complete(main())