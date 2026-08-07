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
    "bot_atr": "8826926237:AAGqZAMRcxxCOkV9E3nQ8jkpyUHLqvKY2oc",  # البوت الخاص بقالب ATR
    "bot8": "8825896064:AAHYTDqZXSCChz4M_WuEdXZ_TcGbVHyZL30",  # @mixbivotat54r_bot
    "bot9": "8799053849:AAE-iuvr6cyqtQH4hURvYM7ECLlUhPdSTNE",  # @Goldspot8_bot
    "bot10": "8844598069:AAGHMO7el1BZZu9v4koywskOKhojL1rv46Q", # @sposBt9_bot
}

BOT_DAILY_CHAT_ID = "-1003920252656"  # جروب "bot testt" — المستويات اليومية
BOT7_CHAT_ID = "-1003794399517"  # تم ترقيته إلى سوبر جروب (كان -5344329888)
BOT_ATR_CHAT_ID = "-1003505602460"  # الجروب الثامن الجديد الخاص بالـ ATR
BOT8_CHAT_ID = "-5544085313"  # الجروب الجديد لبوت bot8
BOT9_CHAT_ID = "-5447338955"  # الجروب الجديد لبوت bot9
BOT10_CHAT_ID = "-5326265307" # الجروب الجديد لبوت bot10


