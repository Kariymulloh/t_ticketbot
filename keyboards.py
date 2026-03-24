import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import ANSWER_TYPES, PERMISSIONS, QUESTION_TEMPLATES


# ── Generic ────────────────────────────────────────────────────────────────────

def back_btn(callback="back"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=callback)]])


def confirm_cancel(confirm_data="confirm", cancel_data="cancel"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=confirm_data),
         InlineKeyboardButton("❌ Bekor qilish", callback_data=cancel_data)]
    ])


def yes_no(yes_data="yes", no_data="no"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha", callback_data=yes_data),
         InlineKeyboardButton("❌ Yo'q", callback_data=no_data)]
    ])


# ── Admin main menu ────────────────────────────────────────────────────────────

def admin_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Tadbirlar", callback_data="admin_events"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 Adminlar", callback_data="admin_admins"),
         InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
    ])


def events_list_keyboard(events, prefix="admin_event"):
    rows = []
    for ev in events:
        status = "✅" if ev["is_active"] else "❌"
        rows.append([InlineKeyboardButton(
            f"{status} {ev['name']} ({ev['date']})",
            callback_data=f"{prefix}:{ev['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ Yangi tadbir", callback_data="create_event")])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)


def event_detail_keyboard(event_id, is_active):
    toggle = "🔴 O'chirish" if is_active else "🟢 Yoqish"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_event:{event_id}"),
         InlineKeyboardButton("❓ Savollar", callback_data=f"event_questions:{event_id}")],
        [InlineKeyboardButton("🪑 Sektorlar", callback_data=f"event_sections:{event_id}"),
         InlineKeyboardButton("📋 Ro'yxat", callback_data=f"event_regs:{event_id}")],
        [InlineKeyboardButton("🔗 Havola", callback_data=f"event_link:{event_id}"),
         InlineKeyboardButton(toggle, callback_data=f"toggle_event:{event_id}")],
        [InlineKeyboardButton("🗑️ O'chirish", callback_data=f"delete_event:{event_id}"),
         InlineKeyboardButton("🔙 Orqaga", callback_data="admin_events")],
    ])


def edit_event_fields_keyboard(event_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Nomi", callback_data=f"ef:name:{event_id}"),
         InlineKeyboardButton("📅 Sanasi", callback_data=f"ef:date:{event_id}")],
        [InlineKeyboardButton("🕐 Vaqti", callback_data=f"ef:time:{event_id}"),
         InlineKeyboardButton("📍 Manzil", callback_data=f"ef:location:{event_id}")],
        [InlineKeyboardButton("💵 Narxi", callback_data=f"ef:price:{event_id}"),
         InlineKeyboardButton("📢 Kanallar", callback_data=f"ef:channels:{event_id}")],
        [InlineKeyboardButton("💬 Xabar (yakuniy)", callback_data=f"ef:success_message:{event_id}"),
         InlineKeyboardButton("💳 Xabar (to'lov)", callback_data=f"ef:payment_pending_message:{event_id}")],
        [InlineKeyboardButton("✅ Xabar (tasdiqlandi)", callback_data=f"ef:payment_confirmed_message:{event_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"admin_event:{event_id}")],
    ])


# ── Questions keyboard ─────────────────────────────────────────────────────────

def questions_menu_keyboard(questions, event_id):
    rows = []
    for q in questions:
        rows.append([InlineKeyboardButton(
            f"#{q['order_num']} {q['question_text'][:40]}",
            callback_data=f"qview:{q['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ Savol qo'shish", callback_data=f"qadd:{event_id}")])
    if len(questions) > 1:
        rows.append([InlineKeyboardButton("🔄 Tartib o'zgartirish", callback_data=f"qreorder:{event_id}")])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f"admin_event:{event_id}")])
    return InlineKeyboardMarkup(rows)


def question_detail_keyboard(q_id, event_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Matni", callback_data=f"qedit:text:{q_id}"),
         InlineKeyboardButton("🔄 Turi", callback_data=f"qedit:type:{q_id}")],
        [InlineKeyboardButton("🗑️ O'chirish", callback_data=f"qdel:{q_id}:{event_id}"),
         InlineKeyboardButton("🔙 Orqaga", callback_data=f"event_questions:{event_id}")],
    ])


def answer_type_keyboard(prefix="qtype"):
    rows = []
    for atype, label in ANSWER_TYPES.items():
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{atype}")])
    return InlineKeyboardMarkup(rows)


def question_templates_keyboard():
    rows = []
    for i, t in enumerate(QUESTION_TEMPLATES):
        rows.append([InlineKeyboardButton(t["name"], callback_data=f"qtmpl:{i}")])
    rows.append([InlineKeyboardButton("➕ Yangi savol yaratish", callback_data="qtmpl:new")])
    rows.append([InlineKeyboardButton("✅ Savollar tayyor", callback_data="qtmpl:done")])
    return InlineKeyboardMarkup(rows)


# ── Sections keyboard ──────────────────────────────────────────────────────────

def sections_menu_keyboard(sections, event_id):
    rows = []
    for s in sections:
        rows.append([InlineKeyboardButton(
            f"🪑 {s['name']} - {s['price']:,.0f} so'm ({s['available_seats']}/{s['total_seats']})",
            callback_data=f"sdel:{s['id']}:{event_id}"
        )])
    rows.append([InlineKeyboardButton("📸 Zal rasmini yuklash", callback_data=f"supload:{event_id}")])
    rows.append([InlineKeyboardButton("➕ Sektor qo'shish", callback_data=f"sadd:{event_id}")])
    rows.append([InlineKeyboardButton("🔙 Orqaga", callback_data=f"admin_event:{event_id}")])
    return InlineKeyboardMarkup(rows)


def sections_select_keyboard(sections):
    rows = []
    for s in sections:
        if s["available_seats"] > 0:
            rows.append([InlineKeyboardButton(
                f"🪑 {s['name']} - {s['price']:,.0f} so'm ({s['available_seats']} o'rin)",
                callback_data=f"selsect:{s['id']}"
            )])
    return InlineKeyboardMarkup(rows)


# ── Broadcast keyboards ────────────────────────────────────────────────────────

def broadcast_target_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Hammaga", callback_data="bc_target:all")],
        [InlineKeyboardButton("✅ Tadbirga kelganlar", callback_data="bc_target:attended"),
         InlineKeyboardButton("❌ Kelmaganlar", callback_data="bc_target:not_attended")],
        [InlineKeyboardButton("👤 Muayyan foydalanuvchi", callback_data="bc_target:specific")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")],
    ])


# ── User keyboards ─────────────────────────────────────────────────────────────

def user_events_keyboard(events):
    rows = []
    for ev in events:
        rows.append([InlineKeyboardButton(
            f"📅 {ev['name']} — {ev['date']}",
            callback_data=f"user_event:{ev['id']}"
        )])
    return InlineKeyboardMarkup(rows)


def subscription_check_keyboard(channels, event_id):
    rows = []
    for ch in channels:
        username = ch["channel_username"]
        link = f"https://t.me/{username.lstrip('@')}" if username else f"https://t.me/c/{str(ch['channel_id']).lstrip('-100')}"
        rows.append([InlineKeyboardButton(
            f"📢 {ch['channel_title'] or ch['channel_username']}",
            url=link
        )])
    rows.append([InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{event_id}")])
    return InlineKeyboardMarkup(rows)


def payment_approve_keyboard(reg_id, payment_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok:{reg_id}:{payment_id}"),
         InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_no:{reg_id}:{payment_id}")],
    ])


def admin_reply_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Izoh bilan rad etish", callback_data="reject_with_comment"),
         InlineKeyboardButton("❌ Shunchaki rad etish", callback_data="reject_no_comment")],
    ])


def gender_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨 Erkak", callback_data="ans:Erkak"),
         InlineKeyboardButton("👩 Ayol", callback_data="ans:Ayol")],
    ])


def choices_keyboard(choices):
    rows = []
    for ch in choices:
        rows.append([InlineKeyboardButton(ch, callback_data=f"ans:{ch}")])
    return InlineKeyboardMarkup(rows)


def phone_request_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def attendance_mark_keyboard(reg_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Keldi", callback_data=f"att:yes:{reg_id}"),
            InlineKeyboardButton("❌ Kelmadi", callback_data=f"att:no:{reg_id}"),
        ]
    ])


def permissions_keyboard(current_perms):
    rows = []
    perm_labels = {
        "create_event": "➕ Tadbir yaratish",
        "edit_event": "✏️ Tahrirlash",
        "delete_event": "🗑️ O'chirish",
        "broadcast": "📢 Broadcast",
        "manage_admins": "👥 Adminlar",
        "view_registrations": "📋 Ro'yxat",
        "manage_payments": "💳 To'lovlar",
    }
    for perm, label in perm_labels.items():
        mark = "✅" if perm in current_perms else "☑️"
        rows.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"perm:{perm}")])
    rows.append([InlineKeyboardButton("💾 Saqlash", callback_data="perm:save"),
                 InlineKeyboardButton("🔙 Orqaga", callback_data="admin_admins")])
    return InlineKeyboardMarkup(rows)
