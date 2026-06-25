import asyncio
import threading
import sys
import os
import importlib
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'python'))

# Import the existing FastAPI app from python/main.py
from python.main import app

# Import the V5 Orchestrator
from Goldbot.v5.bot_orchestrator_v5 import main_loop as run_goldbot_v5

# Import the Auto_Sheets_Bot async function
from Auto_Sheets_Bot.bot import start_sheets_bot

# Since 'auto-copy' has a hyphen, we must import it dynamically
auto_copy_bot = importlib.import_module("auto-copy.bot")
start_telethon_bot = auto_copy_bot.start_telethon_bot

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "message": "All bots are running smoothly! 🚀"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    """Lightweight health check — returns 200 instantly. Use this for UptimeRobot."""
    return {"status": "ok"}


from fastapi import HTTPException

@app.get("/test_gold")
async def test_gold(secret: str = ""):
    if secret != "gold2026vip":
        raise HTTPException(status_code=403, detail="Forbidden: Invalid secret key")
    """
    يجلب البيانات، يولد تقرير، يبعته لتيليجرام،
    ويرجع النتيجة الكاملة في المتصفح مباشرة.
    ملاحظة: يستغرق 2-4 دقائق بسبب جلب البيانات.
    """
    import asyncio, traceback

    def _run():
        result = {"steps": {}}
        try:
            from Goldbot.bot_spot import get_full_market_data, generate_report, send_to_telegram

            # الخطوة 1: جلب البيانات
            result["steps"]["fetch"] = "جاري..."
            data = get_full_market_data()
            if not data:
                result["steps"]["fetch"] = "❌ FAILED — get_full_market_data() returned None"
                send_to_telegram("❌ [TEST] فشل جلب البيانات من yfinance.")
                result["status"] = "error"
                return result
            result["steps"]["fetch"] = f"✅ gold={data['gold']:.2f}$, indicators loaded"

            # الخطوة 2: توليد التقرير
            result["steps"]["generate"] = "جاري..."
            report = generate_report(data, is_alert=False)
            if not report:
                result["steps"]["generate"] = "❌ FAILED — generate_report() returned None (Groq API error?)"
                send_to_telegram("❌ [TEST] فشل توليد التقرير — تحقق من GROQ_API_KEY.")
                result["status"] = "error"
                return result
            result["steps"]["generate"] = f"✅ تقرير جُنِّز بنجاح ({len(report)} حرف)"

            # الخطوة 3: الإرسال
            result["steps"]["send"] = "جاري..."
            ok = send_to_telegram("🧪 [TEST REPORT — تقرير اختبار]\n" + report)
            result["steps"]["send"] = "✅ وصل لتيليجرام" if ok else "❌ فشل الإرسال لتيليجرام"
            result["status"] = "success" if ok else "send_failed"
            result["report_preview"] = report[:300] + "..."

        except Exception as e:
            result["status"]  = "exception"
            result["error"]   = str(e)
            result["traceback"] = traceback.format_exc()[-1000:]
            try:
                from Goldbot.bot_spot import send_to_telegram
                send_to_telegram(f"❌ [TEST EXCEPTION]\n{str(e)[:300]}")
            except Exception:
                pass
        return result

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run)
    return result

@app.get("/trigger_v5")
async def trigger_v5(secret: str = ""):
    if secret != "gold2026vip":
        raise HTTPException(status_code=403, detail="Forbidden: Invalid secret key")
    
    from Goldbot.v5.bot_orchestrator_v5 import orchestrate_v5
    # Run in background so it doesn't block the HTTP request timeout
    asyncio.create_task(orchestrate_v5())
    
    return {
        "status": "success", 
        "message": "🚀 تم إعطاء الأمر لمحرك الجيل الخامس V5 بالبدء فوراً! ستصلك التقارير على قنوات التيليجرام خلال دقائق."
    }



@app.on_event("startup")
async def startup_event():
    """
    This lifecycle event triggers when the FastAPI server starts.
    We launch the continuous scripts in separate threads, and the async Telegram bots as asyncio tasks.
    """
    print("[Orchestrator] Starting background bots...")

    # 1. Start Goldbot V5 Orchestrator on the main asyncio event loop
    asyncio.create_task(run_goldbot_v5())
    print("[Orchestrator] Goldbot V5 Grand Orchestrator task created.")

    # 2. Start auto-copy Telegram bot on the main asyncio event loop
    asyncio.create_task(start_telethon_bot())
    print("[Orchestrator] Auto-copy Telethon bot task created.")

    # 3. Start Auto_Sheets_Bot Telegram bot on the main asyncio event loop
    asyncio.create_task(start_sheets_bot())
    print("[Orchestrator] Auto_Sheets_Bot Telethon bot task created.")

    print("[Orchestrator] All background bots are running. FastAPI is ready to accept requests.")

    # 4. Keep-alive self-ping to prevent HuggingFace from sleeping the Space
    space_url = os.environ.get("SPACE_URL", "https://mohameddd52-my-all-bots.hf.space")
    def _keep_alive():
        import time as _time
        while True:
            _time.sleep(4 * 60)  # ping every 4 minutes
            try:
                requests.get(f"{space_url}/health", timeout=10)
                print("[KeepAlive] ✅ ping ok")
            except Exception as e:
                print(f"[KeepAlive] ⚠️ ping failed: {e}")
    ka_thread = threading.Thread(target=_keep_alive, daemon=True)
    ka_thread.start()
    print("[Orchestrator] Keep-alive thread started (ping every 4 min).")


if __name__ == "__main__":
    import uvicorn
    # When deployed to Render, the web service will use `uvicorn main:app --host 0.0.0.0 --port $PORT`
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
