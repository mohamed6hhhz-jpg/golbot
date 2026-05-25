import asyncio
import threading
import sys
import os
import importlib

sys.path.append(os.path.join(os.path.dirname(__file__), 'python'))

# Import the existing FastAPI app from python/main.py
from python.main import app

# Import the Goldbot monitoring function
from Goldbot.bot import run_bot as run_goldbot

# Import the Auto_Sheets_Bot async function
from Auto_Sheets_Bot.bot import start_sheets_bot

# Since 'auto-copy' has a hyphen, we must import it dynamically
auto_copy_bot = importlib.import_module("auto-copy.bot")
start_telethon_bot = auto_copy_bot.start_telethon_bot

@app.get("/")
async def root():
    return {"status": "ok", "message": "All bots are running smoothly! 🚀"}

@app.on_event("startup")
async def startup_event():
    """
    This lifecycle event triggers when the FastAPI server starts.
    We launch the continuous scripts in separate threads, and the async Telegram bots as asyncio tasks.
    """
    print("[Orchestrator] Starting background bots...")

    # 1. Start Goldbot in a separate background thread (since it uses while True + time.sleep)
    goldbot_thread = threading.Thread(target=run_goldbot, daemon=True)
    goldbot_thread.start()
    print("[Orchestrator] Goldbot thread started.")

    # 2. Start auto-copy Telegram bot on the main asyncio event loop
    asyncio.create_task(start_telethon_bot())
    print("[Orchestrator] Auto-copy Telethon bot task created.")

    # 3. Start Auto_Sheets_Bot Telegram bot on the main asyncio event loop
    asyncio.create_task(start_sheets_bot())
    print("[Orchestrator] Auto_Sheets_Bot Telethon bot task created.")

    print("[Orchestrator] All background bots are running. FastAPI is ready to accept requests.")


if __name__ == "__main__":
    import uvicorn
    # When deployed to Render, the web service will use `uvicorn main:app --host 0.0.0.0 --port $PORT`
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
