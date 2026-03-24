import re
from telegram import Bot
from telegram.error import TelegramError
from config import DEFAULT_SUCCESS_MESSAGE


def format_success_message(template, event):
    if not template:
        template = DEFAULT_SUCCESS_MESSAGE
    return template.format(
        date=event["date"] or "—",
        time=event["time"] or "—",
        location=event["location"] or "—",
        name=event["name"] or "—",
    )


def validate_answer(answer_text, answer_type, min_length=0, min_value=0):
    """Returns (is_valid, error_message)"""
    if answer_type == "text":
        if len(answer_text.strip()) < max(min_length, 1):
            return False, f"❌ Kamida {min_length} ta harfdan iborat bo'lishi kerak."
        return True, None

    elif answer_type == "number":
        try:
            num = int(answer_text.strip())
            if len(str(num)) < min_value:
                return False, f"❌ Kamida {min_value} xonali raqam kiriting."
            return True, None
        except ValueError:
            return False, "❌ Iltimos, raqam kiriting."

    elif answer_type == "phone":
        digits = re.sub(r'\D', '', answer_text)
        if len(digits) < 9:
            return False, "❌ Telefon raqam kamida 9 ta raqamdan iborat bo'lishi kerak."
        return True, None

    elif answer_type in ("choice", "gender"):
        return True, None  # choices are validated via button press

    return True, None


async def check_user_subscribed(bot: Bot, user_id: int, channel_id: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except TelegramError:
        return False


async def check_all_subscriptions(bot: Bot, user_id: int, channels) -> list:
    """Returns list of channels user is NOT subscribed to"""
    not_subscribed = []
    for ch in channels:
        ch_id = ch["channel_id"]
        subscribed = await check_user_subscribed(bot, user_id, ch_id)
        if not subscribed:
            not_subscribed.append(ch)
    return not_subscribed


def user_display_name(user):
    if not user:
        return "Noma'lum"
    name = user.get("first_name") or ""
    if user.get("last_name"):
        name += f" {user['last_name']}"
    if user.get("username"):
        name += f" (@{user['username']})"
    return name.strip() or str(user.get("telegram_id", ""))


def format_registration_info(reg, answers, event, section=None):
    text = f"📋 <b>Ro'yxatdan o'tish #{reg['id']}</b>\n"
    text += f"📅 Tadbir: {event['name']}\n"
    text += f"👤 Foydalanuvchi ID: {reg['user_id']}\n\n"
    for ans in answers:
        text += f"❓ {ans['question_text']}\n"
        text += f"✏️ {ans['answer_text']}\n\n"
    if section:
        text += f"🪑 Sektor: {section['name']} — {section['price']:,.0f} so'm\n"
    text += f"\nHolat: {reg['status']}"
    return text
