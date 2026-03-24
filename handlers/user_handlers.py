import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from keyboards import (
    subscription_check_keyboard, user_events_keyboard, sections_select_keyboard,
    gender_keyboard, choices_keyboard, payment_approve_keyboard, back_btn,
    phone_request_keyboard, attendance_mark_keyboard
)
from states import UserStates
from utils import (
    format_success_message, validate_answer, check_all_subscriptions,
    user_display_name, format_registration_info
)
from config import MAIN_ADMIN_ID, DEFAULT_SUCCESS_MESSAGE

logger = logging.getLogger(__name__)
ATTENDANCE_GROUP_ID = -1003710936860


def clear_registration_context(ctx):
    for key in (
        "reg_id",
        "event_id",
        "current_q_index",
        "sent_messages",
        "selected_section",
        "awaiting_payment",
        "pending_event_id",
    ):
        ctx.user_data.pop(key, None)


# ── /start handler ─────────────────────────────────────────────────────────────

async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.upsert_user(user.id, user.username, user.first_name, user.last_name)

    args = ctx.args
    is_admin = await db.is_admin(user.id)

    # If arrived via event link
    if args and args[0].startswith("event_"):
        try:
            event_id = int(args[0].replace("event_", ""))
            return await start_event_registration(update, ctx, event_id)
        except (ValueError, IndexError):
            pass

    # Admin panel
    if is_admin:
        from handlers.admin_events import admin_panel
        await admin_panel(update, ctx)
        return ConversationHandler.END

    # Regular user: show upcoming events
    events = await db.get_active_events()
    if not events:
        await update.message.reply_text(
            "👋 Salom! Hozirda faol tadbirlar yo'q.\n"
            "Kuting, tez orada yangi tadbirlar qo'shiladi! 🎉"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Salom! Quyidagi tadbirlardan birini tanlang:",
        reply_markup=user_events_keyboard(events)
    )
    return ConversationHandler.END


async def start_event_registration(update: Update, ctx: ContextTypes.DEFAULT_TYPE, event_id: int):
    user = update.effective_user
    event = await db.get_event(event_id)

    if not event or not event["is_active"]:
        await update.message.reply_text("❌ Bu tadbir mavjud emas yoki faol emas.")
        return ConversationHandler.END

    # Check existing registration
    existing = await db.get_user_event_registration(user.id, event_id)
    if existing and existing["status"] in ("confirmed", "completed"):
        # Show their ticket
        await show_registration_ticket(update, ctx, existing["id"])
        return ConversationHandler.END

    # Check mandatory channels
    channels = await db.get_event_channels(event_id)
    if channels:
        not_subbed = await check_all_subscriptions(update.get_bot(), user.id, channels)
        if not_subbed:
            await update.message.reply_text(
                f"📢 <b>{event['name']}</b> tadbiriga ro'yxatdan o'tish uchun\n"
                f"avvalo quyidagi kanallarga obuna bo'ling:",
                parse_mode="HTML",
                reply_markup=subscription_check_keyboard(not_subbed, event_id)
            )
            ctx.user_data["pending_event_id"] = event_id
            return ConversationHandler.END

    # Start questions
    clear_registration_context(ctx)
    return await begin_questions(update, ctx, event_id, user.id)


async def check_subscription_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    user_id = update.effective_user.id

    channels = await db.get_event_channels(event_id)
    not_subbed = await check_all_subscriptions(update.get_bot(), user_id, channels)

    if not_subbed:
        await update.callback_query.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True
        )
        return ConversationHandler.END

    # All subscribed — start registration
    event = await db.get_event(event_id)
    # Delete the subscription message
    try:
        await update.callback_query.message.delete()
    except Exception:
        pass

    # Create fake message to reuse begin_questions
    clear_registration_context(ctx)
    return await begin_questions(update, ctx, event_id, user_id, via_callback=True)


async def begin_questions(update, ctx, event_id, user_id, via_callback=False):
    event = await db.get_event(event_id)
    questions = await db.get_questions(event_id)

    if not questions:
        # No questions — register directly
        reg_id = await db.create_registration(event_id, user_id)
        await db.update_registration_status(reg_id, "confirmed")
        msg_text = format_success_message(event["success_message"], event)
        target = update.callback_query if via_callback else update
        send = target.message.reply_text if via_callback else update.message.reply_text
        await send(msg_text, parse_mode="HTML")
        return ConversationHandler.END

    reg_id = await db.create_registration(event_id, user_id)
    ctx.user_data["reg_id"] = reg_id
    ctx.user_data["event_id"] = event_id
    ctx.user_data["current_q_index"] = 0
    ctx.user_data["sent_messages"] = []

    await send_question(update, ctx, questions[0], via_callback=via_callback)
    return UserStates.REG_QUESTION


async def send_question(update, ctx, question, via_callback=False):
    q_text = question["question_text"]
    atype = question["answer_type"]
    choices = json.loads(question["choices"]) if question["choices"] else []

    if atype == "gender":
        kb = gender_keyboard()
    elif atype == "choice" and choices:
        kb = choices_keyboard(choices)
    elif atype == "phone":
        kb = phone_request_keyboard()
    else:
        kb = None

    target = update.callback_query if via_callback else update
    msg_fn = target.message.reply_text if via_callback else update.message.reply_text

    sent = await msg_fn(q_text, reply_markup=kb)
    if "sent_messages" not in ctx.user_data:
        ctx.user_data["sent_messages"] = []
    ctx.user_data["sent_messages"].append(sent.message_id)


async def handle_registration_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle text/number/phone answers during registration"""
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")

    if not reg_id:
        return ConversationHandler.END

    questions = await db.get_questions(event_id)
    q_index = ctx.user_data.get("current_q_index", 0)

    if q_index >= len(questions):
        return ConversationHandler.END

    question = questions[q_index]

    # Validate
    answer_text = update.message.text.strip() if update.message.text else ""
    is_valid, error_msg = validate_answer(answer_text, question["answer_type"], question["min_length"])

    if not is_valid:
        err = await update.message.reply_text(error_msg)
        ctx.user_data["sent_messages"].append(err.message_id)
        ctx.user_data["sent_messages"].append(update.message.message_id)
        return UserStates.REG_QUESTION

    # Save answer
    await db.save_answer(reg_id, question["id"], answer_text)

    # Delete previous messages
    bot = update.get_bot()
    for msg_id in ctx.user_data.get("sent_messages", []):
        try:
            await bot.delete_message(update.effective_chat.id, msg_id)
        except Exception:
            pass
    try:
        await update.message.delete()
    except Exception:
        pass
    ctx.user_data["sent_messages"] = []

    # Next question
    q_index += 1
    ctx.user_data["current_q_index"] = q_index

    if q_index < len(questions):
        await send_question(update, ctx, questions[q_index])
        return UserStates.REG_QUESTION
    else:
        return await finish_questions(update, ctx)


async def handle_contact_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")
    if not reg_id:
        return ConversationHandler.END

    questions = await db.get_questions(event_id)
    q_index = ctx.user_data.get("current_q_index", 0)
    if q_index >= len(questions):
        return ConversationHandler.END

    question = questions[q_index]
    if question["answer_type"] != "phone":
        await update.message.reply_text("❌ Bu bosqichda telefon emas.")
        return UserStates.REG_QUESTION

    contact = update.message.contact
    if not contact or not contact.phone_number:
        await update.message.reply_text("❌ Iltimos, tugma orqali telefon raqam yuboring.")
        return UserStates.REG_QUESTION

    answer_text = contact.phone_number
    await db.save_answer(reg_id, question["id"], answer_text)

    bot = update.get_bot()
    for msg_id in ctx.user_data.get("sent_messages", []):
        try:
            await bot.delete_message(update.effective_chat.id, msg_id)
        except Exception:
            pass
    try:
        await update.message.delete()
    except Exception:
        pass
    ctx.user_data["sent_messages"] = []

    q_index += 1
    ctx.user_data["current_q_index"] = q_index

    if q_index < len(questions):
        await update.effective_chat.send_message("✅ Qabul qilindi.", reply_markup=ReplyKeyboardRemove())
        await send_question(update, ctx, questions[q_index])
        return UserStates.REG_QUESTION

    await update.effective_chat.send_message("✅ Qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    return await finish_questions(update, ctx)


async def handle_choice_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle button choice answers"""
    await update.callback_query.answer()
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")

    if not reg_id:
        return ConversationHandler.END

    answer_text = update.callback_query.data.replace("ans:", "")
    questions = await db.get_questions(event_id)
    q_index = ctx.user_data.get("current_q_index", 0)

    if q_index >= len(questions):
        return ConversationHandler.END

    question = questions[q_index]
    await db.save_answer(reg_id, question["id"], answer_text)

    # Delete previous messages
    bot = update.get_bot()
    for msg_id in ctx.user_data.get("sent_messages", []):
        try:
            await bot.delete_message(update.effective_chat.id, msg_id)
        except Exception:
            pass
    try:
        await update.callback_query.message.delete()
    except Exception:
        pass
    ctx.user_data["sent_messages"] = []

    # Next question
    q_index += 1
    ctx.user_data["current_q_index"] = q_index

    if q_index < len(questions):
        await send_question(update, ctx, questions[q_index], via_callback=True)
        return UserStates.REG_QUESTION
    else:
        return await finish_questions(update, ctx, via_callback=True)


async def finish_questions(update, ctx, via_callback=False):
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")
    event = await db.get_event(event_id)
    user_id = update.effective_user.id

    # Has sections?
    if event["has_sections"]:
        sections = await db.get_sections(event_id)
        available = [s for s in sections if s["available_seats"] > 0]

        if available:
            await db.update_registration_status(reg_id, "section_select")
            text = "🪑 O'zingizga ma'qul sektordagi o'rindiqni tanlang:"

            if event["seating_image_id"]:
                bot = update.get_bot()
                sent = await bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=event["seating_image_id"],
                    caption=text,
                    reply_markup=sections_select_keyboard(available)
                )
            else:
                target = update.callback_query if via_callback else update
                send_fn = target.message.reply_text if via_callback else update.message.reply_text
                sent = await send_fn(text, reply_markup=sections_select_keyboard(available))

            if "sent_messages" not in ctx.user_data:
                ctx.user_data["sent_messages"] = []
            ctx.user_data["sent_messages"].append(sent.message_id)
            return UserStates.REG_SECTION_SELECT

    # No sections
    if event["is_paid"]:
        return await request_payment(update, ctx, via_callback=via_callback)

    # Free event — confirm
    await db.update_registration_status(reg_id, "confirmed")
    await notify_registration_to_group(update.get_bot(), reg_id)
    success_msg = format_success_message(event["success_message"], event)

    target = update.callback_query if via_callback else update
    send_fn = target.message.reply_text if via_callback else update.message.reply_text
    await send_fn(f"🎉 {success_msg}", parse_mode="HTML")

    # Show main menu
    events = await db.get_active_events()
    if events:
        await send_fn(
            "📅 Boshqa tadbirlar:",
            reply_markup=user_events_keyboard(events)
        )

    clear_registration_context(ctx)
    return ConversationHandler.END


async def handle_section_selection(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    section_id = int(update.callback_query.data.split(":")[1])
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")

    section = await db.get_section(section_id)
    event = await db.get_event(event_id)

    if not section or section["available_seats"] <= 0:
        await update.callback_query.answer("❌ Bu sektorda o'rin yo'q!", show_alert=True)
        return UserStates.REG_SECTION_SELECT

    # Save section
    await db.update_registration_status(reg_id, "section_selected", section_id=section_id)
    await db.decrease_section_seats(section_id)

    # Delete selection message
    try:
        await update.callback_query.message.delete()
    except Exception:
        pass

    ctx.user_data["selected_section"] = section_id

    if event["is_paid"]:
        return await request_payment(update, ctx, via_callback=True, section=section)

    # Free but with section
    await db.update_registration_status(reg_id, "confirmed")
    await notify_registration_to_group(update.get_bot(), reg_id)
    success_msg = format_success_message(event["success_message"], event)
    await update.callback_query.message.reply_text(
        f"🎉 {success_msg}\n\n🪑 Sektor: {section['name']}",
        parse_mode="HTML"
    )
    clear_registration_context(ctx)
    return ConversationHandler.END


async def request_payment(update, ctx, via_callback=False, section=None):
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")
    event = await db.get_event(event_id)

    price = section["price"] if section else event["price"]
    section_text = f"\n🪑 Sektor: {section['name']}" if section else ""

    pending_msg = event.get("payment_pending_message") or (
        f"💳 To'lov haqida ma'lumot:\n\n"
        f"💰 Summa: {price:,.0f} so'm{section_text}\n\n"
        f"To'lovni amalga oshirib, chekini (rasm yoki fayl holida) shu yerga yuboring."
    )

    await db.update_registration_status(reg_id, "payment_pending")
    ctx.user_data["awaiting_payment"] = True

    target = update.callback_query if via_callback else update
    send_fn = target.message.reply_text if via_callback else update.message.reply_text
    await send_fn(
        f"✅ Ro'yxatdan o'tish ma'lumotlari qabul qilindi!\n\n{pending_msg}",
        parse_mode="HTML"
    )
    return UserStates.PAYMENT_WAITING


async def handle_payment_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User sends payment receipt (photo or document)"""
    reg_id = ctx.user_data.get("reg_id")
    event_id = ctx.user_data.get("event_id")

    if not reg_id:
        # Try to find pending registration
        user_id = update.effective_user.id
        # Check all events for pending payment
        events = await db.get_active_events()
        for ev in events:
            reg = await db.get_user_event_registration(user_id, ev["id"])
            if reg and reg["status"] == "payment_pending":
                reg_id = reg["id"]
                event_id = ev["id"]
                ctx.user_data["reg_id"] = reg_id
                ctx.user_data["event_id"] = event_id
                break

    if not reg_id:
        return

    event = await db.get_event(event_id)
    reg = await db.get_registration(reg_id)
    user = update.effective_user

    # Determine file
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "photo"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    else:
        await update.message.reply_text("❌ Iltimos, rasm yoki fayl yuboring.")
        return UserStates.PAYMENT_WAITING

    payment_id = await db.create_payment(reg_id, file_id, file_type)

    # Notify admin
    answers = await db.get_registration_answers(reg_id)
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if user.username:
        name += f" (@{user.username})"

    admin_text = (
        f"💳 <b>Yangi to'lov cheki</b>\n\n"
        f"Tadbir: {event['name']}\n"
        f"Foydalanuvchi: {name}\n"
        f"ID: {user.id}\n\n"
    )
    for ans in answers:
        admin_text += f"• {ans['question_text']}: {ans['answer_text']}\n"

    section_id = reg["section_id"]
    if section_id:
        section = await db.get_section(section_id)
        if section:
            admin_text += f"\n🪑 Sektor: {section['name']} — {section['price']:,.0f} so'm"

    approve_kb = payment_approve_keyboard(reg_id, payment_id)

    bot = update.get_bot()
    # Send to all admins with manage_payments permission
    admins = await db.get_all_admins()
    for adm in admins:
        if adm["is_main"] or "manage_payments" in json.loads(adm["permissions"] or "[]"):
            try:
                if file_type == "photo":
                    await bot.send_photo(
                        chat_id=adm["telegram_id"],
                        photo=file_id,
                        caption=admin_text,
                        parse_mode="HTML",
                        reply_markup=approve_kb
                    )
                else:
                    await bot.send_document(
                        chat_id=adm["telegram_id"],
                        document=file_id,
                        caption=admin_text,
                        parse_mode="HTML",
                        reply_markup=approve_kb
                    )
            except Exception as e:
                logger.error(f"Admin notify error: {e}")

    await update.message.reply_text(
        "✅ Chekingiz adminlarga yuborildi. Tez orada tekshirib tasdiqlashadi."
    )
    return UserStates.PAYMENT_WAITING


async def payment_approve_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin approves payment"""
    await update.callback_query.answer()
    _, reg_id, payment_id = update.callback_query.data.split(":")
    reg_id, payment_id = int(reg_id), int(payment_id)

    reg = await db.get_registration(reg_id)
    event = await db.get_event(reg["event_id"])

    await db.update_payment_status(payment_id, "approved")
    await db.update_registration_status(reg_id, "confirmed")
    await notify_registration_to_group(update.get_bot(), reg_id)

    # Notify user
    confirmed_msg = event.get("payment_confirmed_message") or (
        f"🎉 To'lovingiz tasdiqlandi!\n\n"
        + format_success_message(event["success_message"], event)
    )

    bot = update.get_bot()
    try:
        await bot.send_message(
            chat_id=reg["user_id"],
            text=confirmed_msg,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"User notify error: {e}")

    # Update admin message
    await update.callback_query.edit_message_caption(
        caption=update.callback_query.message.caption + "\n\n✅ <b>TASDIQLANDI</b>",
        parse_mode="HTML"
    )


async def payment_reject_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin rejects payment — ask for comment"""
    await update.callback_query.answer()
    _, reg_id, payment_id = update.callback_query.data.split(":")
    ctx.user_data["reject_reg_id"] = int(reg_id)
    ctx.user_data["reject_payment_id"] = int(payment_id)

    await update.callback_query.edit_message_caption(
        caption=update.callback_query.message.caption + "\n\n❌ Rad etilmoqda...",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Izoh bilan rad etish", callback_data=f"reject_comment:{reg_id}:{payment_id}")],
            [InlineKeyboardButton("❌ Izohsiz rad etish", callback_data=f"reject_no_comment:{reg_id}:{payment_id}")],
        ])
    )


async def reject_with_comment_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, reg_id, payment_id = update.callback_query.data.split(":")
    ctx.user_data["reject_reg_id"] = int(reg_id)
    ctx.user_data["reject_payment_id"] = int(payment_id)
    ctx.user_data["awaiting_reject_comment"] = True
    await update.callback_query.message.reply_text("💬 Rad etish sababini kiriting:")


async def reject_no_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, reg_id, payment_id = update.callback_query.data.split(":")
    await _reject_payment(update.get_bot(), int(reg_id), int(payment_id), None)
    await update.callback_query.edit_message_caption(
        caption=update.callback_query.message.caption + "\n\n❌ <b>RAD ETILDI</b>",
        parse_mode="HTML"
    )


async def handle_reject_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("awaiting_reject_comment"):
        return

    reg_id = ctx.user_data.pop("reject_reg_id", None)
    payment_id = ctx.user_data.pop("reject_payment_id", None)
    ctx.user_data.pop("awaiting_reject_comment", None)

    if not reg_id:
        return

    comment = update.message.text.strip()
    await _reject_payment(update.get_bot(), reg_id, payment_id, comment)
    await update.message.reply_text("✅ Rad etildi va foydalanuvchiga xabar yuborildi.")


async def _reject_payment(bot, reg_id, payment_id, comment):
    import database as db
    await db.update_payment_status(payment_id, "rejected", comment)
    await db.update_registration_status(reg_id, "payment_rejected")

    reg = await db.get_registration(reg_id)

    if comment:
        msg = (
            f"❌ To'lovingiz rad etildi.\n\n"
            f"Sabab: {comment}\n\n"
            f"To'lovni qayta tekshirib ko'ring va yana urinib ko'ring."
        )
    else:
        msg = (
            "❌ To'lovingiz adminlar tarafidan rad etildi.\n\n"
            "Iltimos, haqiqatan to'lov o'tganini qaytadan tekshirib ko'ring va qayta urinib ko'ring.\n\n"
            "Yoki adminga biror gapingiz bo'lsa, bu yerga yozing — yetkazaman:"
        )

    try:
        await bot.send_message(chat_id=reg["user_id"], text=msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending rejection: {e}")


# ── Support chat ───────────────────────────────────────────────────────────────

async def handle_support_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User writes after payment rejection — forward to admins"""
    user = update.effective_user
    text = update.message.text

    # Find rejected registration
    events = await db.get_active_events()
    reg_id = None
    for ev in events:
        reg = await db.get_user_event_registration(user.id, ev["id"])
        if reg and reg["status"] == "payment_rejected":
            reg_id = reg["id"]
            break

    if not reg_id:
        return

    await db.save_support_message(user.id, reg_id, text)

    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if user.username:
        name += f" (@{user.username})"

    bot = update.get_bot()
    admins = await db.get_all_admins()
    for adm in admins:
        if adm["is_main"] or "manage_payments" in json.loads(adm["permissions"] or "[]"):
            try:
                await bot.send_message(
                    chat_id=adm["telegram_id"],
                    text=f"💬 <b>Foydalanuvchi xabari</b>\n\n{name}: {text}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💬 Javob berish", callback_data=f"reply_user:{user.id}")]
                    ])
                )
            except Exception:
                pass

    await update.message.reply_text("✅ Xabaringiz adminga yuborildi.")


async def admin_reply_to_user_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["reply_to_user"] = user_id
    await update.callback_query.message.reply_text(
        "💬 Foydalanuvchiga javob yozing:"
    )


async def admin_reply_to_user_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    target_id = ctx.user_data.pop("reply_to_user", None)
    if not target_id:
        return

    bot = update.get_bot()
    try:
        await bot.send_message(
            chat_id=target_id,
            text=f"💬 Admin javobi:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Javob yuborildi!")
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {e}")


# ── User event detail / ticket ─────────────────────────────────────────────────

async def user_event_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    user_id = update.effective_user.id

    event = await db.get_event(event_id)
    if not event:
        await update.callback_query.answer("Tadbir topilmadi!", show_alert=True)
        return ConversationHandler.END

    existing = await db.get_user_event_registration(user_id, event_id)
    if existing and existing["status"] in ("confirmed", "completed"):
        await show_registration_ticket(update, ctx, existing["id"], via_callback=True)
        return ConversationHandler.END

    # Show event info and start registration
    channels = await db.get_event_channels(event_id)
    if channels:
        not_subbed = await check_all_subscriptions(update.get_bot(), user_id, channels)
        if not_subbed:
            await update.callback_query.edit_message_text(
                f"📢 <b>{event['name']}</b> tadbiriga ro'yxatdan o'tish uchun\n"
                f"avvalo quyidagi kanallarga obuna bo'ling:",
                parse_mode="HTML",
                reply_markup=subscription_check_keyboard(not_subbed, event_id)
            )
            ctx.user_data["pending_event_id"] = event_id
            return ConversationHandler.END

    try:
        await update.callback_query.message.delete()
    except Exception:
        pass

    clear_registration_context(ctx)
    return await begin_questions(update, ctx, event_id, user_id, via_callback=True)


async def show_registration_ticket(update, ctx, reg_id, via_callback=False):
    reg = await db.get_registration(reg_id)
    event = await db.get_event(reg["event_id"])
    answers = await db.get_registration_answers(reg_id)

    success_msg = format_success_message(event["success_message"], event)

    target = update.callback_query if via_callback else update
    send_fn = target.message.reply_text if via_callback else update.message.reply_text
    await send_fn(
        f"🎟️ <b>Sizning chiptangiz</b>\n\n{success_msg}",
        parse_mode="HTML"
    )


async def notify_registration_to_group(bot, reg_id):
    reg = await db.get_registration(reg_id)
    if not reg:
        return
    event = await db.get_event(reg["event_id"])
    answers = await db.get_registration_answers(reg_id)
    user = await db.get_user(reg["user_id"])

    user_name = f"{(user['first_name'] if user else '') or ''} {(user['last_name'] if user else '') or ''}".strip()
    if not user_name:
        user_name = str(reg["user_id"])
    username = f"@{user['username']}" if user and user["username"] else "—"

    lines = [
        "🆕 <b>Yangi ro'yxatdan o'tgan foydalanuvchi</b>",
        f"📅 Tadbir: {event['name'] if event else reg['event_id']}",
        f"👤 Ism: {user_name}",
        f"🆔 Telegram ID: <code>{reg['user_id']}</code>",
        f"🔗 Username: {username}",
        "",
        "<b>Javoblar:</b>",
    ]
    for ans in answers:
        lines.append(f"• {ans['question_text']}: {ans['answer_text']}")

    try:
        await bot.send_message(
            chat_id=ATTENDANCE_GROUP_ID,
            text="\n".join(lines),
            parse_mode="HTML",
            reply_markup=attendance_mark_keyboard(reg_id),
        )
    except Exception as e:
        logger.error(f"Attendance group notify error: {e}")


async def attendance_mark_present(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Kelgan deb belgilandi ✅")
    reg_id = int(update.callback_query.data.split(":")[2])
    await db.set_registration_attendance(reg_id, "attended")


async def attendance_mark_absent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Kelmagan deb belgilandi ❌")
    reg_id = int(update.callback_query.data.split(":")[2])
    await db.set_registration_attendance(reg_id, "not_attended")


async def handle_registration_unexpected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Iltimos, savolga mos formatda javob bering (matn/tanlov/tugma)."
    )
    return UserStates.REG_QUESTION


async def handle_payment_waiting_unexpected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Bu bosqichda to'lov cheki rasmi yoki faylini yuboring."
    )
    return UserStates.PAYMENT_WAITING
