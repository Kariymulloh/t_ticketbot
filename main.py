import logging
import asyncio
import json

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)

from config import BOT_TOKEN, MAIN_ADMIN_ID
import database as db
from states import AdminStates, UserStates

# Import handlers
from handlers.admin_events import (
    admin_panel, admin_events_list, admin_event_detail,
    start_create_event, ev_get_name, ev_get_date, ev_get_time, ev_get_location,
    ev_paid_choice, ev_get_price, ev_add_channel, ev_questions_template,
    ev_template_confirm, ev_new_question_text, ev_new_question_type, ev_add_choice,
    ev_question_min, ev_get_success_msg, ev_get_payment_msg, ev_get_payment_confirmed_msg,
    toggle_event, delete_event_confirm, delete_event_execute,
    edit_event_menu, edit_event_field_start, edit_event_save_value,
    delete_channel_from_event, add_channel_to_event_start, add_channel_to_event_save,
    event_questions_menu, question_view, question_delete,
    add_question_to_event, add_question_text, add_question_type_existing,
    add_question_choice_existing, add_question_min_existing,
    event_sections_menu, section_delete_confirm, start_add_section,
    section_get_name, section_get_price, section_get_seats,
    upload_seating_image_start, save_seating_image,
    show_event_link, event_registrations
)

from handlers.admin_broadcast import (
    broadcast_menu, bc_target_all, bc_target_event, bc_event_selected,
    bc_target_specific, bc_user_search, bc_user_selected, bc_get_message, bc_send,
    admins_list, admin_view, admin_add_start, admin_add_id, admin_toggle_perm,
    admin_perms_edit, admin_delete, admin_stats
)

from handlers.user_handlers import (
    start_command, check_subscription_callback,
    handle_registration_answer, handle_choice_answer,
    handle_section_selection, handle_payment_receipt,
    payment_approve_callback, payment_reject_callback,
    reject_with_comment_start, reject_no_comment,
    handle_reject_comment, handle_support_message,
    admin_reply_to_user_start, admin_reply_to_user_send,
    user_event_detail
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def on_startup(app: Application) -> None:
    """Initialize database in the same event loop as PTB."""
    await db.init_db()
    logger.info("Ma'lumotlar bazasi tayyor")


def build_application():
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    # ── Admin: Create Event ConversationHandler ────────────────────────────────
    create_event_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create_event, pattern="^create_event$")],
        states={
            AdminStates.EV_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_name)],
            AdminStates.EV_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_date)],
            AdminStates.EV_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_time)],
            AdminStates.EV_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_location)],
            AdminStates.EV_PAID: [CallbackQueryHandler(ev_paid_choice, pattern="^ev_paid:")],
            AdminStates.EV_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_price)],
            AdminStates.EV_CHANNELS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_add_channel),
                CommandHandler("skip", lambda u, c: asyncio.ensure_future(_ev_go_to_q(u, c))),
            ],
            AdminStates.EV_QUESTIONS_MENU: [
                CallbackQueryHandler(ev_questions_template, pattern="^qtmpl:"),
                CallbackQueryHandler(ev_template_confirm, pattern="^qtmpl_add:"),
            ],
            AdminStates.EV_ADD_QUESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_new_question_text)
            ],
            AdminStates.EV_ADD_QUESTION_TYPE: [
                CallbackQueryHandler(ev_new_question_type, pattern="^qtype:")
            ],
            AdminStates.EV_ADD_QUESTION_CHOICES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_add_choice),
                CommandHandler("done", ev_add_choice),
            ],
            AdminStates.EV_ADD_QUESTION_MIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_question_min)
            ],
            AdminStates.EV_SUCCESS_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_success_msg),
                CommandHandler("skip", ev_get_success_msg),
            ],
            AdminStates.EV_PAYMENT_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_payment_msg),
                CommandHandler("skip", ev_get_payment_msg),
            ],
            AdminStates.EV_PAYMENT_CONFIRMED_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ev_get_payment_confirmed_msg),
                CommandHandler("skip", ev_get_payment_confirmed_msg),
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_events_list, pattern="^admin_events$")],
        allow_reentry=True,
        per_message=False,
    )

    # ── Admin: Edit Event ConversationHandler ──────────────────────────────────
    edit_event_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_event_field_start, pattern="^ef:")],
        states={
            AdminStates.EDIT_FIELD: [
                CallbackQueryHandler(delete_channel_from_event, pattern="^delch:"),
                CallbackQueryHandler(add_channel_to_event_start, pattern="^addch:"),
            ],
            AdminStates.EV_ADD_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_to_event_save)
            ],
            AdminStates.EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_save_value)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    # ── Admin: Add Question to Existing Event ──────────────────────────────────
    add_q_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_question_to_event, pattern="^qadd:")],
        states={
            AdminStates.EV_ADD_QUESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_text)
            ],
            AdminStates.EV_ADD_QUESTION_TYPE: [
                CallbackQueryHandler(add_question_type_existing, pattern="^qtype:")
            ],
            AdminStates.EV_ADD_QUESTION_CHOICES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_choice_existing),
                CommandHandler("done", add_question_choice_existing),
            ],
            AdminStates.EV_ADD_QUESTION_MIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_min_existing)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    # ── Admin: Sections ────────────────────────────────────────────────────────
    sections_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_section, pattern="^sadd:"),
            CallbackQueryHandler(upload_seating_image_start, pattern="^supload:"),
        ],
        states={
            AdminStates.EV_SECTION_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, section_get_name)
            ],
            AdminStates.EV_SECTION_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, section_get_price)
            ],
            AdminStates.EV_SECTION_SEATS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, section_get_seats)
            ],
            AdminStates.EV_SECTIONS_IMAGE: [
                MessageHandler(filters.PHOTO, save_seating_image)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    # ── Admin: Broadcast ───────────────────────────────────────────────────────
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_menu, pattern="^admin_broadcast$")],
        states={
            AdminStates.BC_TARGET: [
                CallbackQueryHandler(bc_target_all, pattern="^bc_target:all$"),
                CallbackQueryHandler(bc_target_event, pattern="^bc_target:(attended|not_attended)$"),
                CallbackQueryHandler(bc_target_specific, pattern="^bc_target:specific$"),
            ],
            AdminStates.BC_EVENT_SELECT: [
                CallbackQueryHandler(bc_event_selected, pattern="^bc_event:"),
            ],
            AdminStates.BC_USER_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bc_user_search),
                CallbackQueryHandler(bc_user_selected, pattern="^bc_user:"),
            ],
            AdminStates.BC_MESSAGE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, bc_get_message),
            ],
            AdminStates.BC_CONFIRM: [
                CallbackQueryHandler(bc_send, pattern="^bc_send$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern="^admin_back$")],
        allow_reentry=True,
        per_message=False,
    )

    # ── Admin: Manage Admins ───────────────────────────────────────────────────
    admin_mgmt_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^adm_add$")],
        states={
            AdminStates.ADM_ADD_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_id)
            ],
            AdminStates.ADM_PERMISSIONS: [
                CallbackQueryHandler(admin_toggle_perm, pattern="^perm:"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    edit_perm_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_perms_edit, pattern="^adm_perms:")],
        states={
            AdminStates.ADM_PERMISSIONS: [
                CallbackQueryHandler(admin_toggle_perm, pattern="^perm:"),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    # ── User: Registration ConversationHandler ─────────────────────────────────
    user_reg_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_event_detail, pattern="^user_event:"),
            CallbackQueryHandler(check_subscription_callback, pattern="^check_sub:"),
        ],
        states={
            UserStates.REG_QUESTION: [
                CallbackQueryHandler(handle_choice_answer, pattern="^ans:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration_answer),
            ],
            UserStates.REG_SECTION_SELECT: [
                CallbackQueryHandler(handle_section_selection, pattern="^selsect:"),
            ],
            UserStates.PAYMENT_WAITING: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_payment_receipt),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    # ── Register all handlers ──────────────────────────────────────────────────

    # Conversations first (priority)
    app.add_handler(create_event_conv)
    app.add_handler(edit_event_conv)
    app.add_handler(add_q_conv)
    app.add_handler(sections_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(admin_mgmt_conv)
    app.add_handler(edit_perm_conv)
    app.add_handler(user_reg_conv)

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_panel))

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin_events_list, pattern="^admin_events$"))
    app.add_handler(CallbackQueryHandler(admin_event_detail, pattern="^admin_event:"))
    app.add_handler(CallbackQueryHandler(toggle_event, pattern="^toggle_event:"))
    app.add_handler(CallbackQueryHandler(delete_event_confirm, pattern="^delete_event:"))
    app.add_handler(CallbackQueryHandler(delete_event_execute, pattern="^del_event_yes:"))
    app.add_handler(CallbackQueryHandler(edit_event_menu, pattern="^edit_event:"))
    app.add_handler(CallbackQueryHandler(event_questions_menu, pattern="^event_questions:"))
    app.add_handler(CallbackQueryHandler(question_view, pattern="^qview:"))
    app.add_handler(CallbackQueryHandler(question_delete, pattern="^qdel:"))
    app.add_handler(CallbackQueryHandler(event_sections_menu, pattern="^event_sections:"))
    app.add_handler(CallbackQueryHandler(section_delete_confirm, pattern="^sdel:"))
    app.add_handler(CallbackQueryHandler(show_event_link, pattern="^event_link:"))
    app.add_handler(CallbackQueryHandler(event_registrations, pattern="^event_regs:"))

    # Admin management callbacks
    app.add_handler(CallbackQueryHandler(admins_list, pattern="^admin_admins$"))
    app.add_handler(CallbackQueryHandler(admin_view, pattern="^adm_view:"))
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^adm_del:"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))

    # Payment callbacks
    app.add_handler(CallbackQueryHandler(payment_approve_callback, pattern="^pay_ok:"))
    app.add_handler(CallbackQueryHandler(payment_reject_callback, pattern="^pay_no:"))
    app.add_handler(CallbackQueryHandler(reject_with_comment_start, pattern="^reject_comment:"))
    app.add_handler(CallbackQueryHandler(reject_no_comment, pattern="^reject_no_comment:"))
    app.add_handler(CallbackQueryHandler(admin_reply_to_user_start, pattern="^reply_user:"))

    # Fallback message handlers for admins (reject comment, reply to user)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_admin_text_fallback
    ))

    # Photo/document fallback for payment receipts
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        handle_payment_receipt
    ))

    return app


async def handle_admin_text_fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle admin text inputs that aren't caught by conversation handlers"""
    user_id = update.effective_user.id

    # Admin sending reply to user
    if ctx.user_data.get("reply_to_user"):
        await admin_reply_to_user_send(update, ctx)
        return

    # Admin sending reject comment
    if ctx.user_data.get("awaiting_reject_comment"):
        await handle_reject_comment(update, ctx)
        return

    # User support message after payment rejection
    # Check if this user has a rejected payment
    events = await db.get_active_events()
    for ev in events:
        reg = await db.get_user_event_registration(user_id, ev["id"])
        if reg and reg["status"] == "payment_rejected":
            await handle_support_message(update, ctx)
            return

    # If admin and nothing matches, show admin menu
    if await db.is_admin(user_id):
        await admin_panel(update, ctx)


async def _ev_go_to_q(update, ctx):
    """Skip channels step"""
    from handlers.admin_events import _ev_go_to_questions
    return await _ev_go_to_questions(update, ctx)


def main():
    app = build_application()
    logger.info("Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
