import json
import logging
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from openpyxl import Workbook

import database as db
from keyboards import (
    admin_main_menu, events_list_keyboard, event_detail_keyboard,
    edit_event_fields_keyboard, questions_menu_keyboard, question_detail_keyboard,
    answer_type_keyboard, question_templates_keyboard, sections_menu_keyboard,
    yes_no, back_btn, confirm_cancel
)
from states import AdminStates
from config import QUESTION_TEMPLATES, DEFAULT_SUCCESS_MESSAGE

logger = logging.getLogger(__name__)


# ── Admin entry point ──────────────────────────────────────────────────────────

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await db.is_admin(user_id):
        return

    text = "👨‍💼 <b>Admin panel</b>\n\nNimani boshqarmoqchisiz?"
    kb = admin_main_menu()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


# ── Events list ────────────────────────────────────────────────────────────────

async def admin_events_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    events = await db.get_all_events()
    text = "📅 <b>Tadbirlar ro'yxati</b>"
    if not events:
        text += "\n\nHali hech qanday tadbir yo'q."
    await update.callback_query.edit_message_text(
        text, reply_markup=events_list_keyboard(events), parse_mode="HTML"
    )


# ── Event detail ───────────────────────────────────────────────────────────────

async def admin_event_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    if not event:
        await update.callback_query.answer("Tadbir topilmadi!", show_alert=True)
        return

    bot_info = await update.get_bot().get_me()
    link = f"https://t.me/{bot_info.username}?start=event_{event_id}"

    channels = await db.get_event_channels(event_id)
    ch_text = ", ".join(c["channel_title"] or c["channel_username"] for c in channels) or "Yo'q"

    payment_text = f"Ha — {event['price']} so'm" if event["is_paid"] else "Yo'q"
    text = (
        f"📅 <b>{event['name']}</b>\n\n"
        f"📅 Sana: {event['date'] or '—'}\n"
        f"🕐 Vaqt: {event['time'] or '—'}\n"
        f"📍 Manzil: {event['location'] or '—'}\n"
        f"💰 To'lov: {payment_text}\n"
        f"📢 Kanallar: {ch_text}\n"
        f"🔗 Havola: {link}\n"
        f"🟢 Holat: {'Faol' if event['is_active'] else 'Nofaol'}"
    )
    await update.callback_query.edit_message_text(
        text,
        reply_markup=event_detail_keyboard(event_id, event["is_active"]),
        parse_mode="HTML"
    )


# ── Create event: step-by-step ─────────────────────────────────────────────────

async def start_create_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    ctx.user_data["new_event"] = {}
    ctx.user_data["new_event"]["created_by"] = update.effective_user.id
    await update.callback_query.edit_message_text(
        "📝 <b>Yangi tadbir yaratish</b>\n\n1/8 — Tadbir nomini kiriting:",
        parse_mode="HTML",
        reply_markup=back_btn("admin_events")
    )
    return AdminStates.EV_NAME


async def ev_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_event"]["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 2/8 — Tadbir sanasini kiriting (masalan: 2025-06-15):",
        reply_markup=back_btn("admin_events")
    )
    return AdminStates.EV_DATE


async def ev_get_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_event"]["date"] = update.message.text.strip()
    await update.message.reply_text(
        "🕐 3/8 — Tadbir vaqtini kiriting (masalan: 14:00):",
        reply_markup=back_btn("admin_events")
    )
    return AdminStates.EV_TIME


async def ev_get_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_event"]["time"] = update.message.text.strip()
    await update.message.reply_text(
        "📍 4/8 — Tadbir manzilini kiriting:",
        reply_markup=back_btn("admin_events")
    )
    return AdminStates.EV_LOCATION


async def ev_get_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_event"]["location"] = update.message.text.strip()
    await update.message.reply_text(
        "💵 5/8 — Tadbir pullikmi?",
        reply_markup=yes_no("ev_paid:yes", "ev_paid:no")
    )
    return AdminStates.EV_PAID


async def ev_paid_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    choice = update.callback_query.data.split(":")[1]
    if choice == "yes":
        ctx.user_data["new_event"]["is_paid"] = 1
        await update.callback_query.edit_message_text("💵 Tadbir narxini kiriting (so'mda):")
        return AdminStates.EV_PRICE
    else:
        ctx.user_data["new_event"]["is_paid"] = 0
        ctx.user_data["new_event"]["price"] = 0
        await update.callback_query.edit_message_text(
            "📢 6/8 — Majburiy obuna kanallarini qo'shasizmi?\n\n"
            "Kanal havolasini yuboring (masalan: @mening_kanalim)\n"
            "Yoki o'tkazib yuborish uchun /skip yozing:",
        )
        return AdminStates.EV_CHANNELS


async def ev_get_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(" ", "").replace(",", ""))
        ctx.user_data["new_event"]["price"] = price
    except ValueError:
        await update.message.reply_text("❌ Iltimos, raqam kiriting:")
        return AdminStates.EV_PRICE

    await update.message.reply_text(
        "📢 6/8 — Majburiy obuna kanallarini qo'shasizmi?\n\n"
        "Kanal havolasini yuboring (masalan: @mening_kanalim)\n"
        "Yoki o'tkazib yuborish uchun /skip yozing:"
    )
    ctx.user_data["new_event"]["channels"] = []
    return AdminStates.EV_CHANNELS


async def ev_add_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/skip":
        return await _ev_go_to_questions(update, ctx)

    # Try to get channel info
    bot = update.get_bot()
    try:
        if text.startswith("@"):
            chat = await bot.get_chat(text)
        elif text.startswith("https://t.me/"):
            username = "@" + text.split("t.me/")[1].split("/")[0]
            chat = await bot.get_chat(username)
        else:
            chat = await bot.get_chat(text)

        if "channels" not in ctx.user_data["new_event"]:
            ctx.user_data["new_event"]["channels"] = []

        ctx.user_data["new_event"]["channels"].append({
            "channel_id": str(chat.id),
            "channel_title": chat.title,
            "channel_username": chat.username or "",
        })
        await update.message.reply_text(
            f"✅ <b>{chat.title}</b> kanali qo'shildi!\n\n"
            "Yana kanal qo'shish uchun havolasini yuboring.\n"
            "Tugallash uchun /skip yozing:",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Kanal topilmadi. Botni kanalga admin qilib qo'shing va qaytadan urining.\n"
            f"Xatolik: {e}\n\n"
            "Boshqa kanal kiriting yoki /skip:"
        )
    return AdminStates.EV_CHANNELS


async def _ev_go_to_questions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "❓ 7/8 — Ro'yxatdan o'tish savollari\n\n"
        "Shablondan tanlang yoki yangi savol yarating:",
        reply_markup=question_templates_keyboard()
    )
    ctx.user_data["new_event"]["questions"] = []
    return AdminStates.EV_QUESTIONS_MENU


async def ev_questions_template(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data

    if data == "qtmpl:done":
        return await _ev_go_to_success_msg(update, ctx)

    if data == "qtmpl:new":
        await update.callback_query.edit_message_text(
            "❓ Yangi savol matnini kiriting:"
        )
        return AdminStates.EV_ADD_QUESTION_TEXT

    idx = int(data.split(":")[1])
    tmpl = QUESTION_TEMPLATES[idx]
    ctx.user_data["current_question"] = {
        "question_text": tmpl["question_text"],
        "answer_type": tmpl["answer_type"],
        "min_length": tmpl.get("min_length", 0),
        "choices": tmpl.get("choices"),
        "from_template": True,
    }

    if tmpl["answer_type"] == "choice" and tmpl.get("choices"):
        choices_text = "\n".join(f"• {c}" for c in tmpl["choices"])
        await update.callback_query.edit_message_text(
            f"📋 Shablon: <b>{tmpl['name']}</b>\n\n"
            f"Savol: {tmpl['question_text']}\n"
            f"Variantlar:\n{choices_text}\n\n"
            f"Bu savolni qo'shish kerakmi?",
            parse_mode="HTML",
            reply_markup=yes_no("qtmpl_add:yes", "qtmpl_add:no")
        )
    else:
        await update.callback_query.edit_message_text(
            f"📋 Shablon: <b>{tmpl['name']}</b>\n\n"
            f"Savol: {tmpl['question_text']}\n"
            f"Tur: {tmpl['answer_type']}\n\n"
            f"Bu savolni qo'shish kerakmi?",
            parse_mode="HTML",
            reply_markup=yes_no("qtmpl_add:yes", "qtmpl_add:no")
        )
    return AdminStates.EV_QUESTIONS_MENU


async def ev_template_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    choice = update.callback_query.data.split(":")[1]

    if choice == "yes":
        q = ctx.user_data.get("current_question", {})
        if "questions" not in ctx.user_data["new_event"]:
            ctx.user_data["new_event"]["questions"] = []
        ctx.user_data["new_event"]["questions"].append(q)
        await update.callback_query.edit_message_text(
            f"✅ Savol qo'shildi! Jami: {len(ctx.user_data['new_event']['questions'])} ta\n\n"
            "Yana savol qo'shish yoki tugallash:",
            reply_markup=question_templates_keyboard()
        )
    else:
        await update.callback_query.edit_message_text(
            "Yana savol tanlang yoki yangi yarating:",
            reply_markup=question_templates_keyboard()
        )
    return AdminStates.EV_QUESTIONS_MENU


async def ev_new_question_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["current_question"] = {"question_text": update.message.text.strip()}
    await update.message.reply_text(
        "🔢 Savol turini tanlang:",
        reply_markup=answer_type_keyboard()
    )
    return AdminStates.EV_ADD_QUESTION_TYPE


async def ev_new_question_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    atype = update.callback_query.data.split(":")[1]
    ctx.user_data["current_question"]["answer_type"] = atype
    ctx.user_data["current_question"]["min_length"] = 0
    ctx.user_data["current_question"]["choices"] = None

    if atype == "choice":
        await update.callback_query.edit_message_text(
            "🔘 Variantlarni kiriting (har birini alohida qatorda).\n"
            "Tugagach /done yozing:"
        )
        ctx.user_data["current_question"]["choices"] = []
        return AdminStates.EV_ADD_QUESTION_CHOICES
    elif atype == "text":
        await update.callback_query.edit_message_text(
            "📏 Minimal harf soni kiriting (0 = cheklovsiz):"
        )
        return AdminStates.EV_ADD_QUESTION_MIN
    elif atype == "number":
        await update.callback_query.edit_message_text(
            "📏 Minimal xona soni kiriting (masalan 2):"
        )
        return AdminStates.EV_ADD_QUESTION_MIN
    elif atype == "phone":
        ctx.user_data["current_question"]["min_length"] = 9
        _add_current_question(ctx)
        await update.callback_query.edit_message_text(
            f"✅ Savol qo'shildi! Jami: {len(ctx.user_data['new_event']['questions'])} ta\n\n"
            "Yana savol qo'shish yoki tugallash:",
            reply_markup=question_templates_keyboard()
        )
        return AdminStates.EV_QUESTIONS_MENU
    else:
        _add_current_question(ctx)
        await update.callback_query.edit_message_text(
            f"✅ Savol qo'shildi! Jami: {len(ctx.user_data['new_event']['questions'])} ta\n\n"
            "Yana savol qo'shish yoki tugallash:",
            reply_markup=question_templates_keyboard()
        )
        return AdminStates.EV_QUESTIONS_MENU


async def ev_add_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/done":
        if not ctx.user_data["current_question"].get("choices"):
            await update.message.reply_text("❌ Kamida 1 ta variant kiriting:")
            return AdminStates.EV_ADD_QUESTION_CHOICES
        _add_current_question(ctx)
        await update.message.reply_text(
            f"✅ Savol qo'shildi! Jami: {len(ctx.user_data['new_event']['questions'])} ta\n\n"
            "Yana savol qo'shish yoki tugallash:",
            reply_markup=question_templates_keyboard()
        )
        return AdminStates.EV_QUESTIONS_MENU
    ctx.user_data["current_question"]["choices"].append(text)
    await update.message.reply_text(
        f"✅ '{text}' qo'shildi. Yana yoki /done:"
    )
    return AdminStates.EV_ADD_QUESTION_CHOICES


async def ev_question_min(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["current_question"]["min_length"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Raqam kiriting:")
        return AdminStates.EV_ADD_QUESTION_MIN

    _add_current_question(ctx)
    await update.message.reply_text(
        f"✅ Savol qo'shildi! Jami: {len(ctx.user_data['new_event']['questions'])} ta\n\n"
        "Yana savol qo'shish yoki tugallash:",
        reply_markup=question_templates_keyboard()
    )
    return AdminStates.EV_QUESTIONS_MENU


def _add_current_question(ctx):
    q = ctx.user_data.get("current_question", {})
    if "questions" not in ctx.user_data["new_event"]:
        ctx.user_data["new_event"]["questions"] = []
    ctx.user_data["new_event"]["questions"].append(q)


async def _ev_go_to_success_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.callback_query.message if update.callback_query else update.message
    event_data = ctx.user_data["new_event"]
    default = DEFAULT_SUCCESS_MESSAGE.replace(
        "{date}", event_data.get("date", "xxx")
    ).replace("{time}", event_data.get("time", "xxx")).replace(
        "{location}", event_data.get("location", "xxx")
    ).replace("{name}", event_data.get("name", "xxx"))

    await msg.reply_text(
        f"💬 8/8 — Ro'yxatdan o'tgani haqidagi xabar matnini kiriting.\n\n"
        f"Siz kiritmasangiz quyidagi standart xabar yuboriladi:\n\n"
        f"<i>{DEFAULT_SUCCESS_MESSAGE}</i>\n\n"
        f"O'zgartirmaslik uchun /skip yozing.\n\n"
        f"Foydalanish mumkin bo'lgan o'zgaruvchilar:\n"
        f"{{name}} — tadbir nomi\n{{date}} — sana\n{{time}} — vaqt\n{{location}} — manzil",
        parse_mode="HTML"
    )
    return AdminStates.EV_SUCCESS_MSG


async def ev_get_success_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "/skip":
        ctx.user_data["new_event"]["success_message"] = text
    else:
        ctx.user_data["new_event"]["success_message"] = None

    if ctx.user_data["new_event"].get("is_paid"):
        await update.message.reply_text(
            "💳 To'lov talab qilinganda yuboriluvchi xabar matnini kiriting.\n"
            "Bu xabar savollarga javob berilgach, to'lov chekini yuborish so'ralganda chiqadi.\n"
            "/skip — standart xabar:"
        )
        return AdminStates.EV_PAYMENT_MSG
    else:
        return await _ev_finalize(update, ctx)


async def ev_get_payment_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "/skip":
        ctx.user_data["new_event"]["payment_pending_message"] = text
    await update.message.reply_text(
        "✅ To'lov tasdiqlanganda yuboriluvchi xabar matnini kiriting.\n"
        "/skip — standart xabar:"
    )
    return AdminStates.EV_PAYMENT_CONFIRMED_MSG


async def ev_get_payment_confirmed_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "/skip":
        ctx.user_data["new_event"]["payment_confirmed_message"] = text
    return await _ev_finalize(update, ctx)


async def _ev_finalize(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    event_data = ctx.user_data["new_event"]
    questions = event_data.pop("questions", [])
    channels = event_data.pop("channels", [])

    event_id = await db.create_event(event_data)

    for i, q in enumerate(questions):
        await db.add_question(
            event_id, i + 1,
            q["question_text"],
            q["answer_type"],
            q.get("choices"),
            q.get("min_length", 0),
            q.get("min_value", 0)
        )

    for ch in channels:
        await db.add_event_channel(event_id, ch["channel_id"], ch["channel_title"], ch["channel_username"])

    bot_info = await update.get_bot().get_me()
    link = f"https://t.me/{bot_info.username}?start=event_{event_id}"

    await update.message.reply_text(
        f"🎉 <b>Tadbir muvaffaqiyatli yaratildi!</b>\n\n"
        f"📅 {event_data['name']}\n"
        f"🔗 Havola: {link}\n\n"
        f"Endi sektorlar qo'shishni xohlaysizmi?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🪑 Sektorlar qo'shish", callback_data=f"event_sections:{event_id}")],
            [InlineKeyboardButton("✅ Tayyor", callback_data=f"admin_event:{event_id}")],
        ])
    )
    ctx.user_data.pop("new_event", None)
    return ConversationHandler.END


# ── Toggle / Delete event ──────────────────────────────────────────────────────

async def toggle_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    new_status = 0 if event["is_active"] else 1
    await db.update_event(event_id, {"is_active": new_status})
    status_text = "yoqildi ✅" if new_status else "o'chirildi ❌"
    await update.callback_query.answer(f"Tadbir {status_text}", show_alert=True)
    await admin_event_detail(update, ctx)


async def delete_event_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    await update.callback_query.edit_message_text(
        f"⚠️ <b>{event['name']}</b> tadbirini o'chirmoqchimisiz?\n\n"
        "Bu amalni qaytarib bo'lmaydi!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Ha, o'chirish", callback_data=f"del_event_yes:{event_id}"),
             InlineKeyboardButton("❌ Yo'q", callback_data=f"admin_event:{event_id}")]
        ])
    )


async def delete_event_execute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    await db.delete_event(event_id)
    await update.callback_query.edit_message_text(
        "✅ Tadbir o'chirildi.",
        reply_markup=back_btn("admin_events")
    )


# ── Edit event ─────────────────────────────────────────────────────────────────

async def edit_event_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    await update.callback_query.edit_message_text(
        f"✏️ <b>{event['name']}</b> — nimani tahrirlash?",
        parse_mode="HTML",
        reply_markup=edit_event_fields_keyboard(event_id)
    )


async def edit_event_field_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, field, event_id = update.callback_query.data.split(":")
    event_id = int(event_id)
    ctx.user_data["edit_event_id"] = event_id
    ctx.user_data["edit_field"] = field

    field_names = {
        "name": "nomi", "date": "sanasi", "time": "vaqti",
        "location": "manzili", "price": "narxi",
        "success_message": "yakuniy xabar",
        "payment_pending_message": "to'lov xabari",
        "payment_confirmed_message": "tasdiqlash xabari",
    }

    if field == "channels":
        channels = await db.get_event_channels(event_id)
        rows = []
        for ch in channels:
            rows.append([InlineKeyboardButton(
                f"🗑️ {ch['channel_title'] or ch['channel_username']}",
                callback_data=f"delch:{ch['id']}:{event_id}"
            )])
        rows.append([InlineKeyboardButton("➕ Kanal qo'shish", callback_data=f"addch:{event_id}")])
        rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f"edit_event:{event_id}")])
        await update.callback_query.edit_message_text(
            "📢 Majburiy obuna kanallarini boshqarish:",
            reply_markup=InlineKeyboardMarkup(rows)
        )
        return AdminStates.EDIT_FIELD

    variables_hint = ""
    if "message" in field:
        variables_hint = "(o'zgaruvchilar: {name}, {date}, {time}, {location})"
    await update.callback_query.edit_message_text(
        f"✏️ Yangi {field_names.get(field, field)} kiriting:\n{variables_hint}",
        reply_markup=back_btn(f"edit_event:{event_id}")
    )
    return AdminStates.EDIT_VALUE


async def edit_event_save_value(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    field = ctx.user_data.get("edit_field")
    event_id = ctx.user_data.get("edit_event_id")
    value = update.message.text.strip()

    if field == "price":
        try:
            value = float(value.replace(" ", "").replace(",", ""))
        except ValueError:
            await update.message.reply_text("❌ Raqam kiriting:")
            return AdminStates.EDIT_VALUE

    await db.update_event(event_id, {field: value})
    await update.message.reply_text(
        "✅ Saqlandi!",
        reply_markup=edit_event_fields_keyboard(event_id)
    )
    return ConversationHandler.END


async def delete_channel_from_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, ch_id, event_id = update.callback_query.data.split(":")
    await db.delete_event_channel(int(ch_id))
    await update.callback_query.answer("Kanal o'chirildi", show_alert=True)
    # Refresh channels list
    channels = await db.get_event_channels(int(event_id))
    rows = []
    for ch in channels:
        rows.append([InlineKeyboardButton(
            f"🗑️ {ch['channel_title'] or ch['channel_username']}",
            callback_data=f"delch:{ch['id']}:{event_id}"
        )])
    rows.append([InlineKeyboardButton("➕ Kanal qo'shish", callback_data=f"addch:{event_id}")])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f"edit_event:{event_id}")])
    await update.callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(rows))


async def add_channel_to_event_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["add_channel_event_id"] = event_id
    await update.callback_query.edit_message_text(
        "📢 Kanal havolasini yuboring (@username yoki t.me/... havolasi):"
    )
    return AdminStates.EV_ADD_CHANNEL


async def add_channel_to_event_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    event_id = ctx.user_data.get("add_channel_event_id")
    text = update.message.text.strip()
    bot = update.get_bot()
    try:
        if text.startswith("@"):
            chat = await bot.get_chat(text)
        elif "t.me/" in text:
            username = "@" + text.split("t.me/")[1].split("/")[0]
            chat = await bot.get_chat(username)
        else:
            chat = await bot.get_chat(text)

        await db.add_event_channel(event_id, str(chat.id), chat.title, chat.username or "")
        await update.message.reply_text(
            f"✅ <b>{chat.title}</b> qo'shildi!",
            parse_mode="HTML",
            reply_markup=back_btn(f"edit_event:{event_id}")
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik: {e}\nBotni kanalga admin qilib qo'shing!"
        )
    return ConversationHandler.END


# ── Questions management ───────────────────────────────────────────────────────

async def event_questions_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    questions = await db.get_questions(event_id)
    await update.callback_query.edit_message_text(
        f"❓ Savollar ro'yxati ({len(questions)} ta):",
        reply_markup=questions_menu_keyboard(questions, event_id)
    )


async def question_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    q_id = int(update.callback_query.data.split(":")[1])
    q = await db.get_question(q_id)
    choices = json.loads(q["choices"]) if q["choices"] else []
    text = (
        f"❓ <b>Savol #{q['order_num']}</b>\n\n"
        f"Matn: {q['question_text']}\n"
        f"Tur: {q['answer_type']}\n"
        f"Minimal: {q['min_length']}\n"
    )
    if choices:
        text += f"Variantlar: {', '.join(choices)}\n"

    await update.callback_query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=question_detail_keyboard(q_id, q["event_id"])
    )


async def question_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, q_id, event_id = update.callback_query.data.split(":")
    await db.delete_question(int(q_id))
    questions = await db.get_questions(int(event_id))
    await update.callback_query.edit_message_text(
        f"✅ Savol o'chirildi!\n\n❓ Savollar ro'yxati ({len(questions)} ta):",
        reply_markup=questions_menu_keyboard(questions, int(event_id))
    )


async def add_question_to_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["add_q_event_id"] = event_id
    ctx.user_data["current_question"] = {}
    ctx.user_data["new_event"] = ctx.user_data.get("new_event", {})
    ctx.user_data["new_event"]["questions"] = []

    await update.callback_query.edit_message_text(
        "❓ Savol matnini kiriting:"
    )
    return AdminStates.EV_ADD_QUESTION_TEXT


async def add_question_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["current_question"]["question_text"] = update.message.text.strip()
    await update.message.reply_text("🔢 Savol turini tanlang:", reply_markup=answer_type_keyboard())
    return AdminStates.EV_ADD_QUESTION_TYPE


async def add_question_type_existing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    atype = update.callback_query.data.split(":")[1]
    ctx.user_data["current_question"]["answer_type"] = atype
    event_id = ctx.user_data.get("add_q_event_id")

    if atype == "choice":
        await update.callback_query.edit_message_text(
            "🔘 Variantlarni kiriting (har birini alohida qatorda).\nTugagach /done yozing:"
        )
        ctx.user_data["current_question"]["choices"] = []
        return AdminStates.EV_ADD_QUESTION_CHOICES
    elif atype in ("text", "number"):
        await update.callback_query.edit_message_text(
            "📏 Minimal uzunlik/xona soni (0 = cheklovsiz):"
        )
        return AdminStates.EV_ADD_QUESTION_MIN
    else:
        # Save directly
        q = ctx.user_data["current_question"]
        questions = await db.get_questions(event_id)
        await db.add_question(event_id, len(questions) + 1, q["question_text"], atype)
        questions = await db.get_questions(event_id)
        await update.callback_query.edit_message_text(
            f"✅ Savol qo'shildi! Jami: {len(questions)} ta",
            reply_markup=questions_menu_keyboard(questions, event_id)
        )
        return ConversationHandler.END


async def add_question_choice_existing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    event_id = ctx.user_data.get("add_q_event_id")
    if text == "/done":
        q = ctx.user_data["current_question"]
        questions = await db.get_questions(event_id)
        await db.add_question(event_id, len(questions) + 1, q["question_text"],
                               q["answer_type"], q.get("choices"), 0, 0)
        questions = await db.get_questions(event_id)
        await update.message.reply_text(
            f"✅ Savol qo'shildi!",
            reply_markup=questions_menu_keyboard(questions, event_id)
        )
        return ConversationHandler.END
    ctx.user_data["current_question"]["choices"].append(text)
    await update.message.reply_text(f"✅ '{text}' qo'shildi. Yana yoki /done:")
    return AdminStates.EV_ADD_QUESTION_CHOICES


async def add_question_min_existing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    event_id = ctx.user_data.get("add_q_event_id")
    try:
        min_val = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Raqam kiriting:")
        return AdminStates.EV_ADD_QUESTION_MIN

    q = ctx.user_data["current_question"]
    questions = await db.get_questions(event_id)
    await db.add_question(event_id, len(questions) + 1, q["question_text"],
                           q["answer_type"], None, min_val, 0)
    questions = await db.get_questions(event_id)
    await update.message.reply_text(
        f"✅ Savol qo'shildi!",
        reply_markup=questions_menu_keyboard(questions, event_id)
    )
    return ConversationHandler.END


# ── Sections management ────────────────────────────────────────────────────────

async def event_sections_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    sections = await db.get_sections(event_id)
    event = await db.get_event(event_id)

    text = f"🪑 <b>{event['name']}</b> — Sektorlar"
    if event["seating_image_id"]:
        text += "\n📸 Zal rasmi yuklangan"

    await update.callback_query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=sections_menu_keyboard(sections, event_id)
    )


async def section_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, s_id, event_id = update.callback_query.data.split(":")
    await db.delete_section(int(s_id))
    sections = await db.get_sections(int(event_id))
    await update.callback_query.edit_message_text(
        "✅ Sektor o'chirildi!",
        reply_markup=sections_menu_keyboard(sections, int(event_id))
    )


async def start_add_section(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["add_section"] = {"event_id": event_id}
    await update.callback_query.edit_message_text("🪑 Sektor nomini kiriting (masalan: VIP, A, B):")
    return AdminStates.EV_SECTION_NAME


async def section_get_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["add_section"]["name"] = update.message.text.strip()
    await update.message.reply_text("💵 Narxini kiriting (so'mda):")
    return AdminStates.EV_SECTION_PRICE


async def section_get_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(" ", "").replace(",", ""))
        ctx.user_data["add_section"]["price"] = price
    except ValueError:
        await update.message.reply_text("❌ Raqam kiriting:")
        return AdminStates.EV_SECTION_PRICE
    await update.message.reply_text("🪑 O'rindiqlar sonini kiriting:")
    return AdminStates.EV_SECTION_SEATS


async def section_get_seats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        seats = int(update.message.text.strip())
        s = ctx.user_data["add_section"]
        event_id = s["event_id"]
        await db.add_section(event_id, s["name"], s["price"], seats)
        await db.update_event(event_id, {"has_sections": 1})
        sections = await db.get_sections(event_id)
        await update.message.reply_text(
            f"✅ Sektor qo'shildi!",
            reply_markup=sections_menu_keyboard(sections, event_id)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Raqam kiriting:")
        return AdminStates.EV_SECTION_SEATS


async def upload_seating_image_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["seating_event_id"] = event_id
    await update.callback_query.edit_message_text(
        "📸 Zal rasmini (sektorlar belgilangan holda) yuboring:"
    )
    return AdminStates.EV_SECTIONS_IMAGE


async def save_seating_image(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    event_id = ctx.user_data.get("seating_event_id")
    photo = update.message.photo
    if photo:
        file_id = photo[-1].file_id
        await db.update_event_seating_image(event_id, file_id)
        await update.message.reply_text("✅ Zal rasmi saqlandi!")
        return ConversationHandler.END
    await update.message.reply_text("❌ Iltimos, rasm yuboring.")
    return AdminStates.EV_SECTIONS_IMAGE


# ── Event link ─────────────────────────────────────────────────────────────────

async def show_event_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    bot_info = await update.get_bot().get_me()
    link = f"https://t.me/{bot_info.username}?start=event_{event_id}"
    await update.callback_query.edit_message_text(
        f"🔗 <b>{event['name']}</b> tadbiri uchun havola:\n\n"
        f"<code>{link}</code>",
        parse_mode="HTML",
        reply_markup=back_btn(f"admin_event:{event_id}")
    )


# ── Registrations list ─────────────────────────────────────────────────────────

async def event_registrations(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    regs = await db.get_event_registrations(event_id)

    total = len(regs)
    confirmed = sum(1 for r in regs if r["status"] in ("confirmed", "completed"))
    pending = sum(1 for r in regs if r["status"] == "payment_pending")
    attended = sum(1 for r in regs if r["attendance_status"] == "attended")
    not_attended = sum(1 for r in regs if r["attendance_status"] == "not_attended")

    await update.callback_query.edit_message_text(
        f"📋 <b>{event['name']}</b> — Ro'yxat\n\n"
        f"Jami: {total}\n"
        f"✅ Tasdiqlangan: {confirmed}\n"
        f"⏳ Kutilayotgan: {pending}\n"
        f"🟢 Kelgan: {attended}\n"
        f"🔴 Kelmagan: {not_attended}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Excel yuklab olish", callback_data=f"event_regs_export:{event_id}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data=f"admin_event:{event_id}")],
        ])
    )


async def export_event_registrations_excel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Excel tayyorlanmoqda...")
    event_id = int(update.callback_query.data.split(":")[1])
    event = await db.get_event(event_id)
    regs = await db.get_event_registrations(event_id)
    questions = await db.get_questions(event_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"

    headers = [
        "Registration ID",
        "Status",
        "Attendance",
        "User ID",
        "Username",
        "First name",
        "Last name",
        "Section",
        "Registered at",
        "Confirmed at",
    ]
    for q in questions:
        headers.append(q["question_text"])
    ws.append(headers)

    for reg in regs:
        user = await db.get_user(reg["user_id"])
        answers = await db.get_registration_answers(reg["id"])
        ans_map = {a["question_text"]: a["answer_text"] for a in answers}
        section_name = ""
        if reg["section_id"]:
            section = await db.get_section(reg["section_id"])
            section_name = section["name"] if section else ""

        row = [
            reg["id"],
            reg["status"],
            reg["attendance_status"],
            reg["user_id"],
            user["username"] if user else "",
            user["first_name"] if user else "",
            user["last_name"] if user else "",
            section_name,
            reg["registered_at"],
            reg["confirmed_at"],
        ]
        for q in questions:
            row.append(ans_map.get(q["question_text"], ""))
        ws.append(row)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    bio.name = f"{event['name']}_registrations.xlsx".replace(" ", "_")

    await update.callback_query.message.reply_document(
        document=bio,
        filename=bio.name,
        caption=f"📥 {event['name']} registratsiya ro'yxati",
    )
