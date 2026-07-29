import os

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "deepseek-r1-distill-llama-70b",
    "llama3-8b-8192"
]

try:
    from Goldbot.ai_client import get_api_keys
except ImportError:
    from ai_client import get_api_keys

GROQ_API_KEY = get_api_keys()[0]

# Hard minimum limits according to rule 8
MIN_CONFIDENCE = 65

# Telegram targets
TARGET_CHATS_SPOT = ['@spotGol']
TARGET_CHATS_FUTURES = ['@GooldFut']
