import aiosqlite
import json
from datetime import datetime
from config import DB_PATH, MAIN_ADMIN_ID


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                permissions TEXT DEFAULT '[]',
                added_by INTEGER,
                is_main INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date TEXT,
                time TEXT,
                location TEXT,
                description TEXT,
                is_paid INTEGER DEFAULT 0,
                price REAL DEFAULT 0,
                success_message TEXT,
                payment_pending_message TEXT,
                payment_confirmed_message TEXT,
                has_sections INTEGER DEFAULT 0,
                seating_image_id TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS event_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                channel_id TEXT,
                channel_title TEXT,
                channel_username TEXT,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                order_num INTEGER,
                question_text TEXT,
                answer_type TEXT,
                choices TEXT,
                min_length INTEGER DEFAULT 0,
                min_value INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 1,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                user_id INTEGER,
                status TEXT DEFAULT 'questions',
                attendance_status TEXT DEFAULT 'unknown',
                section_id INTEGER,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_id INTEGER,
                question_id INTEGER,
                answer_text TEXT,
                FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_id INTEGER,
                file_id TEXT,
                file_type TEXT,
                status TEXT DEFAULT 'pending',
                admin_comment TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (registration_id) REFERENCES registrations(id)
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                name TEXT,
                price REAL,
                total_seats INTEGER,
                available_seats INTEGER,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS support_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                registration_id INTEGER,
                message_text TEXT,
                from_user INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Lightweight migration for existing databases
        async with db.execute("PRAGMA table_info(registrations)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
        if "attendance_status" not in cols:
            await db.execute(
                "ALTER TABLE registrations ADD COLUMN attendance_status TEXT DEFAULT 'unknown'"
            )

        # Ensure main admin exists
        await db.execute(
            """INSERT OR IGNORE INTO admins (telegram_id, permissions, is_main)
               VALUES (?, ?, 1)""",
            (MAIN_ADMIN_ID, json.dumps(["create_event","edit_event","delete_event",
                                         "broadcast","manage_admins","view_registrations","manage_payments"]))
        )
        await db.commit()


# ── Users ──────────────────────────────────────────────────────────────────────

async def upsert_user(telegram_id, username, first_name, last_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id, username, first_name, last_name)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                 username=excluded.username,
                 first_name=excluded.first_name,
                 last_name=excluded.last_name""",
            (telegram_id, username, first_name, last_name)
        )
        await db.commit()


async def get_user(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)) as cur:
            return await cur.fetchone()


async def search_users(query):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM users WHERE
               first_name LIKE ? OR last_name LIKE ? OR username LIKE ?
               LIMIT 20""",
            (f"%{query}%", f"%{query}%", f"%{query}%")
        ) as cur:
            return await cur.fetchall()


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


# ── Admins ─────────────────────────────────────────────────────────────────────

async def get_admin(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE telegram_id=?", (telegram_id,)) as cur:
            return await cur.fetchone()


async def is_admin(telegram_id):
    row = await get_admin(telegram_id)
    return row is not None


async def has_permission(telegram_id, perm):
    row = await get_admin(telegram_id)
    if not row:
        return False
    if row["is_main"]:
        return True
    perms = json.loads(row["permissions"] or "[]")
    return perm in perms


async def add_admin(telegram_id, permissions, added_by):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO admins (telegram_id, permissions, added_by)
               VALUES (?, ?, ?)""",
            (telegram_id, json.dumps(permissions), added_by)
        )
        await db.commit()


async def update_admin_permissions(telegram_id, permissions):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE admins SET permissions=? WHERE telegram_id=?",
            (json.dumps(permissions), telegram_id)
        )
        await db.commit()


async def remove_admin(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE telegram_id=? AND is_main=0", (telegram_id,))
        await db.commit()


async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins") as cur:
            return await cur.fetchall()


# ── Events ─────────────────────────────────────────────────────────────────────

async def create_event(data):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO events
               (name, date, time, location, description, is_paid, price,
                success_message, payment_pending_message, payment_confirmed_message,
                has_sections, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("name"), data.get("date"), data.get("time"),
                data.get("location"), data.get("description", ""),
                int(data.get("is_paid", 0)), float(data.get("price", 0)),
                data.get("success_message"), data.get("payment_pending_message"),
                data.get("payment_confirmed_message"),
                int(data.get("has_sections", 0)),
                data.get("created_by"),
            )
        )
        await db.commit()
        return cur.lastrowid


async def get_event(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE id=?", (event_id,)) as cur:
            return await cur.fetchone()


async def get_active_events():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE is_active=1 ORDER BY date") as cur:
            return await cur.fetchall()


async def get_all_events():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events ORDER BY created_at DESC") as cur:
            return await cur.fetchall()


async def update_event(event_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ", ".join(f"{k}=?" for k in data)
        values = list(data.values()) + [event_id]
        await db.execute(f"UPDATE events SET {fields} WHERE id=?", values)
        await db.commit()


async def delete_event(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM events WHERE id=?", (event_id,))
        await db.commit()


# ── Event Channels ─────────────────────────────────────────────────────────────

async def add_event_channel(event_id, channel_id, channel_title, channel_username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO event_channels (event_id, channel_id, channel_title, channel_username) VALUES (?,?,?,?)",
            (event_id, str(channel_id), channel_title, channel_username)
        )
        await db.commit()


async def get_event_channels(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM event_channels WHERE event_id=?", (event_id,)) as cur:
            return await cur.fetchall()


async def delete_event_channel(channel_db_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM event_channels WHERE id=?", (channel_db_id,))
        await db.commit()


async def delete_all_event_channels(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM event_channels WHERE event_id=?", (event_id,))
        await db.commit()


# ── Questions ──────────────────────────────────────────────────────────────────

async def add_question(event_id, order_num, question_text, answer_type,
                        choices=None, min_length=0, min_value=0):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO questions
               (event_id, order_num, question_text, answer_type, choices, min_length, min_value)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id, order_num, question_text, answer_type,
             json.dumps(choices) if choices else None, min_length, min_value)
        )
        await db.commit()
        return cur.lastrowid


async def get_questions(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM questions WHERE event_id=? ORDER BY order_num", (event_id,)
        ) as cur:
            return await cur.fetchall()


async def get_question(question_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM questions WHERE id=?", (question_id,)) as cur:
            return await cur.fetchone()


async def update_question(question_id, data):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ", ".join(f"{k}=?" for k in data)
        values = list(data.values()) + [question_id]
        await db.execute(f"UPDATE questions SET {fields} WHERE id=?", values)
        await db.commit()


async def delete_question(question_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM questions WHERE id=?", (question_id,))
        await db.commit()


async def reorder_questions(event_id, question_ids_ordered):
    async with aiosqlite.connect(DB_PATH) as db:
        for i, qid in enumerate(question_ids_ordered):
            await db.execute("UPDATE questions SET order_num=? WHERE id=? AND event_id=?",
                             (i + 1, qid, event_id))
        await db.commit()


# ── Sections ───────────────────────────────────────────────────────────────────

async def add_section(event_id, name, price, total_seats):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO sections (event_id, name, price, total_seats, available_seats) VALUES (?,?,?,?,?)",
            (event_id, name, price, total_seats, total_seats)
        )
        await db.commit()
        return cur.lastrowid


async def get_sections(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sections WHERE event_id=?", (event_id,)) as cur:
            return await cur.fetchall()


async def get_section(section_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sections WHERE id=?", (section_id,)) as cur:
            return await cur.fetchone()


async def decrease_section_seats(section_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sections SET available_seats=available_seats-1 WHERE id=? AND available_seats>0",
            (section_id,)
        )
        await db.commit()


async def increase_section_seats(section_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sections SET available_seats=available_seats+1 WHERE id=?",
            (section_id,)
        )
        await db.commit()


async def delete_section(section_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sections WHERE id=?", (section_id,))
        await db.commit()


async def update_event_seating_image(event_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET seating_image_id=? WHERE id=?", (file_id, event_id))
        await db.commit()


# ── Registrations ──────────────────────────────────────────────────────────────

async def create_registration(event_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO registrations (event_id, user_id, status) VALUES (?,?,'questions')",
            (event_id, user_id)
        )
        await db.commit()
        return cur.lastrowid


async def get_registration(reg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM registrations WHERE id=?", (reg_id,)) as cur:
            return await cur.fetchone()


async def get_user_event_registration(user_id, event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM registrations WHERE user_id=? AND event_id=? ORDER BY id DESC LIMIT 1",
            (user_id, event_id)
        ) as cur:
            return await cur.fetchone()


async def update_registration_status(reg_id, status, section_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if section_id is not None:
            await db.execute(
                "UPDATE registrations SET status=?, section_id=? WHERE id=?",
                (status, section_id, reg_id)
            )
        else:
            if status in ("confirmed", "completed"):
                await db.execute(
                    "UPDATE registrations SET status=?, confirmed_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, reg_id)
                )
            else:
                await db.execute(
                    "UPDATE registrations SET status=? WHERE id=?",
                    (status, reg_id)
                )
        await db.commit()


async def set_registration_attendance(reg_id, attendance_status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE registrations SET attendance_status=? WHERE id=?",
            (attendance_status, reg_id),
        )
        await db.commit()


async def save_answer(reg_id, question_id, answer_text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO answers (registration_id, question_id, answer_text) VALUES (?,?,?)",
            (reg_id, question_id, answer_text)
        )
        await db.commit()


async def get_registration_answers(reg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT a.answer_text, q.question_text, q.order_num
               FROM answers a JOIN questions q ON a.question_id=q.id
               WHERE a.registration_id=? ORDER BY q.order_num""",
            (reg_id,)
        ) as cur:
            return await cur.fetchall()


async def get_event_registrations(event_id, status=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                "SELECT * FROM registrations WHERE event_id=? AND status=?", (event_id, status)
            ) as cur:
                return await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM registrations WHERE event_id=?", (event_id,)
            ) as cur:
                return await cur.fetchall()


async def get_users_attended_event(event_id):
    """Users marked as attended."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT user_id FROM registrations WHERE event_id=? AND attendance_status='attended'",
            (event_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_users_not_attended_event(event_id):
    """Users not marked as attended."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT DISTINCT user_id FROM registrations
               WHERE event_id=? AND status IN ('confirmed','completed') AND attendance_status!='attended'""",
            (event_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_registration_count(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id=? AND status IN ('confirmed','completed','payment_pending')",
            (event_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0]


# ── Payments ───────────────────────────────────────────────────────────────────

async def create_payment(reg_id, file_id, file_type):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (registration_id, file_id, file_type) VALUES (?,?,?)",
            (reg_id, file_id, file_type)
        )
        await db.commit()
        return cur.lastrowid


async def get_payment_by_registration(reg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE registration_id=? ORDER BY id DESC LIMIT 1", (reg_id,)
        ) as cur:
            return await cur.fetchone()


async def update_payment_status(payment_id, status, comment=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status=?, admin_comment=? WHERE id=?",
            (status, comment, payment_id)
        )
        await db.commit()


# ── Support Chat ───────────────────────────────────────────────────────────────

async def save_support_message(user_id, reg_id, message_text, from_user=1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO support_chat (user_id, registration_id, message_text, from_user) VALUES (?,?,?,?)",
            (user_id, reg_id, message_text, from_user)
        )
        await db.commit()


async def get_support_chat(reg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_chat WHERE registration_id=? ORDER BY created_at", (reg_id,)
        ) as cur:
            return await cur.fetchall()
