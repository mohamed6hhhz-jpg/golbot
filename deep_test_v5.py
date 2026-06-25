import asyncio
import logging
from Goldbot.v5.bot_orchestrator_v5 import orchestrate_v5

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger("DeepTest")

async def deep_test():
    log.info("🔍 بدء اختبار عميق (Deep Test) لجميع أنظمة V5...")
    try:
        # Run one complete cycle of the orchestrator
        await orchestrate_v5()
        log.info("✅ الاختبار العميق اكتمل بنجاح تام وبدون أخطاء!")
    except Exception as e:
        log.error(f"❌ حدث خطأ فادح أثناء الاختبار: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(deep_test())
