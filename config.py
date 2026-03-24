BOT_TOKEN = "8665324490:AAExRLSHvGTDDEBM55LHqg04K25InohDib8"
MAIN_ADMIN_ID = 5672908862
MAIN_ADMIN_PHONE = "+998949068333"
DB_PATH = "bot.db"

PERMISSIONS = [
    "create_event",
    "edit_event",
    "delete_event",
    "broadcast",
    "manage_admins",
    "view_registrations",
    "manage_payments",
]

ANSWER_TYPES = {
    "text": "📝 Matn",
    "number": "🔢 Raqam",
    "phone": "📞 Telefon raqam",
    "choice": "🔘 Tanlov (variantli)",
    "gender": "👤 Jins",
}

QUESTION_TEMPLATES = [
    {
        "name": "👤 Ism",
        "question_text": "Ismingizni kiriting:",
        "answer_type": "text",
        "min_length": 3,
        "choices": None,
    },
    {
        "name": "🎂 Yosh",
        "question_text": "Yoshingizni kiriting:",
        "answer_type": "number",
        "min_length": 2,
        "choices": None,
    },
    {
        "name": "📍 Manzil",
        "question_text": "Manzilingizni tanlang:",
        "answer_type": "choice",
        "min_length": 0,
        "choices": ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Farg'ona", "Qashqadaryo", "Surxondaryo", "Xorazm", "Navoiy", "Sirdaryo", "Jizzax", "Qoraqalpog'iston"],
    },
    {
        "name": "👤 Jins",
        "question_text": "Jinsingizni tanlang:",
        "answer_type": "gender",
        "min_length": 0,
        "choices": ["Erkak", "Ayol"],
    },
    {
        "name": "📞 Telefon raqam",
        "question_text": "Telefon raqamingizni kiriting:",
        "answer_type": "phone",
        "min_length": 9,
        "choices": None,
    },
    {
        "name": "💡 Qiziqish",
        "question_text": "Qiziqishlaringizni kiriting:",
        "answer_type": "text",
        "min_length": 3,
        "choices": None,
    },
]

DEFAULT_SUCCESS_MESSAGE = (
    "✅ Siz tadbirga muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
    "📅 Sana: {date}\n"
    "🕐 Vaqt: {time}\n"
    "📍 Manzil: {location}\n\n"
    "Mana shu xabarni tashkilotchilarga ko'rsatsangiz, chipta o'rnida o'tadi."
)
