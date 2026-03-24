import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from keyboards import (
    broadcast_target_keyboard, events_list_keyboard, back_btn,
    permissions_keyboard
)
from states import AdminStates
from config import PERMISSIONS

logger = logging.getLogger(__name__)


# ── Broadcast ──────────────────────────────────────────────────────────────────

async def broadcast_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not await db.has_permission(update.effective_user.id, "broadcast"):
        await update.callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await update.callback_query.edit_message_text(
        "📢 <b>Broadcast</b>\n\nKimga xabar yuborasiz?",
        parse_mode="HTML",
        reply_markup=broadcast_target_keyboard()
    )
    return AdminStates.BC_TARGET


async def bc_target_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    ctx.user_data["bc_target"] = "all"
    await update.callback_query.edit_message_text(
        "📢 Hammaga yuboriladigan xabar matnini kiriting\n"
        "(rasm, video yoki matn yuborishingiz mumkin):"
    )
    return AdminStates.BC_MESSAGE


async def bc_target_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    target = update.callback_query.data.split(":")[1]
    ctx.user_data["bc_target_type"] = target
    events = await db.get_all_events()
    await update.callback_query.edit_message_text(
        "📅 Qaysi tadbir ishtirokchilariga?",
        reply_markup=events_list_keyboard(events, prefix="bc_event")
    )
    return AdminStates.BC_EVENT_SELECT


async def bc_event_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    event_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["bc_event_id"] = event_id
    ctx.user_data["bc_target"] = f"event_{ctx.user_data['bc_target_type']}_{event_id}"
    await update.callback_query.edit_message_text(
        "📢 Xabar matnini kiriting (rasm, video yoki matn):"
    )
    return AdminStates.BC_MESSAGE


async def bc_target_specific(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    ctx.user_data["bc_target"] = "specific"
    await update.callback_query.edit_message_text(
        "👤 Foydalanuvchi ismini kiriting (qidirish uchun):"
    )
    return AdminStates.BC_USER_SEARCH


async def bc_user_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    users = await db.search_users(query)
    if not users:
        await update.message.reply_text("😔 Foydalanuvchi topilmadi. Qaytadan kiriting:")
        return AdminStates.BC_USER_SEARCH

    rows = []
    for u in users:
        name = f"{u['first_name'] or ''} {u['last_name'] or ''}".strip()
        if u["username"]:
            name += f" (@{u['username']})"
        rows.append([InlineKeyboardButton(name, callback_data=f"bc_user:{u['telegram_id']}")])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_broadcast")])

    await update.message.reply_text(
        f"🔍 {len(users)} ta natija topildi:",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return AdminStates.BC_USER_SEARCH


async def bc_user_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = int(update.callback_query.data.split(":")[1])
    ctx.user_data["bc_target"] = f"user_{user_id}"
    ctx.user_data["bc_specific_user"] = user_id
    await update.callback_query.edit_message_text(
        "📢 Xabar matnini kiriting (rasm, video yoki matn):"
    )
    return AdminStates.BC_MESSAGE


async def bc_get_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["bc_message"] = update.message
    target = ctx.user_data.get("bc_target", "")

    if target == "all":
        preview = "👥 Hammaga"
    elif target.startswith("event_attended_"):
        event_id = target.split("_")[-1]
        event = await db.get_event(int(event_id))
        preview = f"✅ {event['name']} — kelganlar"
    elif target.startswith("event_not_attended_"):
        event_id = target.split("_")[-1]
        event = await db.get_event(int(event_id))
        preview = f"❌ {event['name']} — kelmaganlar"
    elif target.startswith("user_"):
        user_id = int(target.split("_")[1])
        user = await db.get_user(user_id)
        name = user["first_name"] if user else str(user_id)
        preview = f"👤 {name}"
    else:
        preview = target

    await update.message.reply_text(
        f"📢 Yuborish tasdiqlansinmi?\n\nKimga: {preview}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yuborish", callback_data="bc_send"),
             InlineKeyboardButton("❌ Bekor", callback_data="admin_broadcast")]
        ])
    )
    return AdminStates.BC_CONFIRM


async def bc_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("⏳ Yuborilmoqda...")
    target = ctx.user_data.get("bc_target", "")
    message = ctx.user_data.get("bc_message")

    # Determine recipients
    if target == "all":
        user_ids = await db.get_all_user_ids()
    elif target.startswith("event_attended_"):
        event_id = int(target.split("_")[-1])
        user_ids = await db.get_users_attended_event(event_id)
    elif target.startswith("event_not_attended_"):
        event_id = int(target.split("_")[-1])
        user_ids = await db.get_users_not_attended_event(event_id)
    elif target.startswith("user_"):
        user_ids = [int(target.split("_")[1])]
    else:
        user_ids = []

    bot = update.get_bot()
    sent = 0
    failed = 0

    for uid in user_ids:
        try:
            if message.photo:
                await bot.send_photo(
                    chat_id=uid,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or ""
                )
            elif message.video:
                await bot.send_video(
                    chat_id=uid,
                    video=message.video.file_id,
                    caption=message.caption or ""
                )
            elif message.document:
                await bot.send_document(
                    chat_id=uid,
                    document=message.document.file_id,
                    caption=message.caption or ""
                )
            elif message.text:
                await bot.send_message(chat_id=uid, text=message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await update.callback_query.edit_message_text(
        f"✅ Broadcast yakunlandi!\n\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Xatolik: {failed}",
        reply_markup=back_btn("admin_broadcast")
    )
    return ConversationHandler.END


# ── Admin management ───────────────────────────────────────────────────────────

async def admins_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not await db.has_permission(update.effective_user.id, "manage_admins"):
        await update.callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    admins = await db.get_all_admins()
    rows = []
    for adm in admins:
        user = await db.get_user(adm["telegram_id"])
        name = (user["first_name"] if user else "") or str(adm["telegram_id"])
        mark = "👑" if adm["is_main"] else "👤"
        rows.append([InlineKeyboardButton(
            f"{mark} {name}",
            callback_data=f"adm_view:{adm['telegram_id']}"
        )])
    rows.append([InlineKeyboardButton("➕ Admin qo'shish", callback_data="adm_add")])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])

    await update.callback_query.edit_message_text(
        f"👥 <b>Adminlar</b> ({len(admins)} ta):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def admin_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    target_id = int(update.callback_query.data.split(":")[1])
    adm = await db.get_admin(target_id)
    user = await db.get_user(target_id)

    name = (user["first_name"] if user else "") or str(target_id)
    perms = json.loads(adm["permissions"] or "[]")
    perm_text = ", ".join(perms) if perms else "Yo'q"

    rows = []
    if not adm["is_main"]:
        rows.append([
            InlineKeyboardButton("✏️ Ruxsatlar", callback_data=f"adm_perms:{target_id}"),
            InlineKeyboardButton("🗑️ O'chirish", callback_data=f"adm_del:{target_id}"),
        ])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_admins")])

    await update.callback_query.edit_message_text(
        f"👤 <b>{name}</b>\n\nID: {target_id}\nRuxsatlar: {perm_text}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def admin_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "👤 Yangi admin Telegram ID sini kiriting:\n\n"
        "(Admin avvalo botga /start bosgan bo'lishi kerak)"
    )
    return AdminStates.ADM_ADD_ID


async def admin_add_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Telegram ID raqam bo'lishi kerak:")
        return AdminStates.ADM_ADD_ID

    user = await db.get_user(target_id)
    if not user:
        await update.message.reply_text(
            "❌ Bu ID li foydalanuvchi botda topilmadi.\n"
            "Avvalo u botga /start bosishi kerak.\nQaytadan kiriting:"
        )
        return AdminStates.ADM_ADD_ID

    ctx.user_data["new_admin_id"] = target_id
    ctx.user_data["new_admin_perms"] = []
    name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()

    await update.message.reply_text(
        f"👤 <b>{name}</b> ({target_id})\n\nRuxsatlarni tanlang:",
        parse_mode="HTML",
        reply_markup=permissions_keyboard([])
    )
    return AdminStates.ADM_PERMISSIONS


async def admin_toggle_perm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data.split(":")[1]

    if data == "save":
        target_id = ctx.user_data.get("new_admin_id")
        perms = ctx.user_data.get("new_admin_perms", [])
        existing = await db.get_admin(target_id)
        if existing:
            await db.update_admin_permissions(target_id, perms)
        else:
            await db.add_admin(target_id, perms, update.effective_user.id)
        action_text = "yangilandi" if existing else "qo'shildi"
        perms_text = ", ".join(perms) or "Yo'q"
        await update.callback_query.edit_message_text(
            f"✅ Admin muvaffaqiyatli {action_text}!\n"
            f"Ruxsatlar: {perms_text}"
        )
        return ConversationHandler.END

    perms = ctx.user_data.get("new_admin_perms", [])
    if data in perms:
        perms.remove(data)
    else:
        perms.append(data)
    ctx.user_data["new_admin_perms"] = perms

    await update.callback_query.edit_message_reply_markup(
        reply_markup=permissions_keyboard(perms)
    )
    return AdminStates.ADM_PERMISSIONS


async def admin_perms_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    target_id = int(update.callback_query.data.split(":")[1])
    adm = await db.get_admin(target_id)
    perms = json.loads(adm["permissions"] or "[]")
    ctx.user_data["new_admin_id"] = target_id
    ctx.user_data["new_admin_perms"] = perms

    await update.callback_query.edit_message_text(
        f"✏️ Ruxsatlarni tahrirlang:",
        reply_markup=permissions_keyboard(perms)
    )
    return AdminStates.ADM_PERMISSIONS


async def admin_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    target_id = int(update.callback_query.data.split(":")[1])
    await db.remove_admin(target_id)
    await update.callback_query.edit_message_text(
        "✅ Admin o'chirildi!",
        reply_markup=back_btn("admin_admins")
    )


# ── Stats ──────────────────────────────────────────────────────────────────────

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    all_users = await db.get_all_user_ids()
    all_events = await db.get_all_events()
    active_events = [e for e in all_events if e["is_active"]]

    await update.callback_query.edit_message_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {len(all_users)}\n"
        f"📅 Jami tadbirlar: {len(all_events)}\n"
        f"🟢 Faol tadbirlar: {len(active_events)}",
        parse_mode="HTML",
        reply_markup=back_btn("admin_back")
    )
