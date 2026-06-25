import os

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "deepseek-r1-distill-llama-70b",
    "mixtral-8x7b-32768"
]

GROQ_API_KEY = "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"

# Hard minimum limits according to rule 8
MIN_CONFIDENCE = 65

# Telegram targets
TARGET_CHATS_SPOT = ['@spotGol']
TARGET_CHATS_FUTURES = ['@GooldFut']
