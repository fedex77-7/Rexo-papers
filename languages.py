# code -> (display label shown in bot)
LANGUAGES = {
    "ml": "മലയാളം",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "kn": "ಕನ್ನಡ",
    "hi": "हिन्दी",
    "bn": "বাংলা",
    "mr": "मराठी",
    "gu": "ગુજરાતી",
    "pa": "ਪੰਜਾਬੀ",
    "or": "ଓଡ଼ିଆ",
    "as": "অসমীয়া",
    "ur": "اردو",
    "sa": "संस्कृतम्",
    "ks": "کٲشُر",
    "sd": "سنڌي",
    "kok": "कोंकणी",
    "mni": "মৈতৈলোন্",
    "ne": "नेपाली",
    "brx": "बड़ो",
    "doi": "डोगरी",
    "mai": "मैथिली",
    "sat": "ᱥᱟᱱᱛᱟᱲᱤ",
    "en": "English",
    "es": "Español",
    "zh": "中文",
    "ru": "Русский",
    "ja": "日本語",
    "fr": "Français",
    "de": "Deutsch",
    "ar": "العربية",
    "pt": "Português",
    "it": "Italiano",
    "si": "සිංහල",
}

# Paginate into chunks of 8 for inline keyboards
def paginate(codes, page_size=8):
    items = list(codes.items())
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]
