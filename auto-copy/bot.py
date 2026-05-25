import os
import logging
import asyncio

from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ══════════════════════════════════════════════════════════════
# الإعدادات (CONFIGURATION)
# ══════════════════════════════════════════════════════════════

API_ID   = 34105911
API_HASH = 'b444ab6b4eeba8a66db4143b934dc540'

# بعد تشغيل الكود على جهازك لأول مرة، هتاخد نص الجلسة (StringSession) الطويل
# وفي ريندر (Render) هتحطه كمتغير بيئة (Environment Variable) باسم SESSION_STRING.
SESSION_STRING = os.environ.get('SESSION_STRING', '')

SOURCE_CHANNELS = ['@protrading36', '@protradingg1', 'me']
DEST_CHANNEL    = '@mycryptoappTT20'

FLASK_PORT    = 10000
CACHE_LIMIT   = 1000

# ══════════════════════════════════════════════════════════════
# السجلات (LOGGING)
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('AutoCopier')

# ══════════════════════════════════════════════════════════════
# نظام منع التكرار (ANTI-DUPLICATION CACHE)
# ══════════════════════════════════════════════════════════════

processed: set = set()

def register(msg_id: int) -> bool:
    """ترجع True لو رسالة جديدة (مش مكررة)."""
    if msg_id in processed:
        return False
    processed.add(msg_id)
    if len(processed) > CACHE_LIMIT:
        processed.clear()
        log.info('تم تفريغ ذاكرة التكرار المؤقتة.')
    return True

# ══════════════════════════════════════════════════════════════
# تهيئة عميل تليجرام (TELETHON CLIENT)
# ══════════════════════════════════════════════════════════════

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

# ══════════════════════════════════════════════════════════════
# المعالج الأساسي — نسخ (Copy) وليس تحويل (Forward)
# ══════════════════════════════════════════════════════════════

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handle_new_message(event: events.NewMessage.Event):
    try:
        msg    = event.message
        msg_id = msg.id

        if not register(msg_id):
            log.warning(f'تم تجاهل رسالة مكررة — msg_id={msg_id}')
            return

        source = getattr(event.chat, 'username', str(event.chat_id))
        log.info(f'رسالة جديدة من @{source} | msg_id={msg_id}')

        # إرسال الرسالة كأنها جديدة تماماً بدون أي أثر للمصدر
        await client.send_message(DEST_CHANNEL, msg)

        log.info(f'تم النسخ إلى {DEST_CHANNEL} بنجاح.')

    except Exception:
        log.exception('حدث خطأ أثناء نسخ الرسالة.')

# ══════════════════════════════════════════════════════════════
# نقطة البداية (ENTRY POINT)
# ══════════════════════════════════════════════════════════════

async def main():
    await client.start()

    # أول تشغيل على جهازك: هيطبع نص الجلسة عشان تنسخه وتحفظه
    if not SESSION_STRING:
        saved = client.session.save()
        log.info('════════════════════════════════════════')
        log.info('التشغيل الأول — انسخ نص الـ StringSession ده واحفظه فوراً:')
        log.info(saved)
        log.info('════════════════════════════════════════')

    me = await client.get_me()
    log.info(f'تم تسجيل الدخول باسم: {me.first_name} (@{me.username})')
    log.info(f'جاري مراقبة القنوات: {SOURCE_CHANNELS}')
    log.info(f'قناة النشر المستهدفة: {DEST_CHANNEL}')

    await client.run_until_disconnected()


async def start_telethon_bot():
    await main()