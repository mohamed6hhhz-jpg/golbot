"""
secrets_config.py — ملف الإعدادات والمفاتيح الخارجية لإبعاد المفاتيح الحساسة عن الأكواد البرمجية الأساسية.
"""
import os

GROQ_KEYS_FALLBACK = [
    "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",
    "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"
]

TWELVEDATA_API_KEY_FALLBACK = "a40631d26cb64ba99916a3162880aff3"

TELEGRAM_TOKENS = {
    "bot1": "8135586080:AAFS1ZI2XcsPrnjtTvAPlXxlTMrSO_Lu3Qc",
    "bot2": "8718236248:AAGIlK8xTWUvRB_WcYOGN2Qx1kEKZwRqihQ",
    "bot3": "8696806326:AAEDKqSNoHAaMEHD8oqjaLm4oSci_3KOUWA",  # @Dsssoppp78_bot — القوالب الفورية S1-S12
    "bot4": "8930341910:AAHzqUUrPgMYf0vkkORWX25HGVgo_BDLRDI",
    "bot5": "8834685171:AAGLBVBU0jOMXRjjnQ1EaHfiwKfSVGmS3FM",  # @Summariesboot54_bot
    "bot_daily": "8874443139:AAGusTNj2-SRkODsFTPBUXC2xLyz_JrZch0",  # @Bottest42_bot — المستويات اليومية الكلاسيكية والكاماريلا
    "bot7": "8849395600:AAF9m7kraZxAP4qv9rHt05dOQcUjkIlybSk",  # @goldbot7_bot
    "bot_atr": "8945210764:AAHc2PxXEDFz-ui8F0WZpKCsIJiegt7mvao",  # البوت الخاص بقالب ATR
}

BOT_DAILY_CHAT_ID = "-1003920252656"  # جروب "bot testt" — المستويات اليومية
BOT7_CHAT_ID = "-1003794399517"  # تم ترقيته إلى سوبر جروب (كان -5344329888)
BOT_ATR_CHAT_ID = "-1003794399517"  # الجروب السابع الجديد الخاص بالـ ATR

