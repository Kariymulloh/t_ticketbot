# 🤖 Event Registration Bot

Telegram orqali tadbirlarni boshqarish va ro'yxatdan o'tishni avtomatlashtiradigan to'liq funksional bot.

---

## ✨ Imkoniyatlar

### 👨‍💼 Admin uchun
- 📅 Tadbir yaratish, tahrirlash, o'chirish
- 🔗 Har bir tadbir uchun maxsus havola
- 📢 Majburiy kanal obunasi (har tadbir uchun alohida)
- ❓ Savollar yaratish va boshqarish (shablonlar + yangi)
- 🪑 Sektorlar va o'rindiqlar (narxlar bilan)
- 💰 Pullik tadbirlar + to'lov tasdiqlash
- 📢 Broadcast: hammaga, guruhga yoki ayrim shaxsga
- 👥 Boshqa adminlarni tayinlash + ruxsatlarni boshqarish

### 👤 Foydalanuvchi uchun
- 🔔 Majburiy kanalga obuna bo'lish
- 📝 Bosqichma-bosqich ro'yxatdan o'tish (eski xabarlar o'chib ketadi)
- 🪑 Sektorni tanlash (rasm bilan)
- 💳 To'lov chekini yuborish va tasdiqlash kutish
- 🎟️ Muvaffaqiyatli ro'yxatdan o'tish chiptasi

---

## 🚀 O'rnatish va ishga tushirish

### 1. Klonlash
```bash
git clone https://github.com/sizning-username/eventbot.git
cd eventbot
```

### 2. Virtual muhit
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Kutubxonalar
```bash
pip install -r requirements.txt
```

### 4. Ishga tushirish
```bash
python main.py
```

---

## ☁️ Deploy (Railway)

1. [Railway.app](https://railway.app) ga kiring
2. **New Project → Deploy from GitHub repo** tanlang
3. Reponi ulang
4. **Procfile** avtomatik taniladi: `worker: python main.py`
5. Deploy bosing — bot ishga tushadi!

---

## ☁️ Deploy (Render)

1. [Render.com](https://render.com) ga kiring
2. **New → Background Worker** tanlang
3. Reponi ulang
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`

---

## 📁 Fayl tuzilmasi

```
eventbot/
├── main.py                  # Asosiy fayl
├── config.py                # Sozlamalar
├── database.py              # Ma'lumotlar bazasi
├── keyboards.py             # Tugmalar
├── states.py                # Holatlar
├── utils.py                 # Yordamchi funksiyalar
├── handlers/
│   ├── admin_events.py      # Admin: tadbirlar
│   ├── admin_broadcast.py   # Admin: broadcast + adminlar
│   └── user_handlers.py     # Foydalanuvchilar
├── requirements.txt
├── Procfile
└── README.md
```

---

## 🔧 Sozlamalar (config.py)

| Sozlama | Qiymat |
|---------|--------|
| `BOT_TOKEN` | `8665324490:AAEx...` |
| `MAIN_ADMIN_ID` | `5672908862` |

---

## 📋 Bot buyruqlari

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni ishga tushirish |
| `/start event_ID` | Tadbirga ro'yxatdan o'tish |
| `/admin` | Admin panelni ochish |

---

## 💡 Savol turlari

| Tur | Tavsif |
|-----|--------|
| `text` | Matn (kamida N harf) |
| `number` | Raqam (kamida N xona) |
| `phone` | Telefon (kamida 9 raqam) |
| `choice` | Bir nechta variantdan tanlash |
| `gender` | Erkak/Ayol |

---

## 🪑 Sektorlar tizimi

Admin tadbir uchun sektorlar yaratishi mumkin:
1. **Zal rasmini yuklash** (sektorlar belgilangan holda)
2. **Sektor nomi, narxi va o'rindiqlar soni** kiritiladi
3. Foydalanuvchi savolga javob bergach, sektor tanlaydi
4. Tanlangan sektorning narxi to'lov uchun ko'rsatiladi

---

## 💳 To'lov tizimi

1. Foydalanuvchi ro'yxatdan o'tib, sektor tanlaydi
2. To'lov chekini (rasm/fayl) yuboradi
3. Admin tasdiqlaydi → foydalanuvchi chipta oladi
4. Admin rad etadi → foydalanuvchi izoh bilan xabar oladi
5. Foydalanuvchi admin bilan chat orqali muloqot qila oladi

---

## 📢 Broadcast turlari

- **Hammaga** — barcha foydalanuvchilarga
- **Tadbirga kelganlar** — ma'lum tadbir ishtirokchilariga  
- **Kelmaganlar** — ro'yxatdan o'tgan lekin kelmaganlar
- **Muayyan shaxs** — ism bo'yicha qidirish va yuborish

---

## 👥 Admin ruxsatlari

| Ruxsat | Tavsif |
|--------|--------|
| `create_event` | Tadbir yaratish |
| `edit_event` | Tahrirlash |
| `delete_event` | O'chirish |
| `broadcast` | Xabar tarqatish |
| `manage_admins` | Adminlarni boshqarish |
| `view_registrations` | Ro'yxatni ko'rish |
| `manage_payments` | To'lovlarni boshqarish |
