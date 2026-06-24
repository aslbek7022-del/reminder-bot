# 🤖 Kunlik Eslatma Boti — O'rnatish Qo'llanmasi

## 1-qadam: Bot token olish

1. Telegramda **@BotFather** ga yozing
2. `/newbot` yuboring
3. Bot nomini kiriting (masalan: `Kunlik Rejalarim`)
4. Username kiriting (masalan: `my_daily_reminder_bot`)
5. BotFather sizga **token** beradi — uni saqlang!

---

## 2-qadam: Railway.app da joylashtirish (Bepul!)

### A) GitHub ga yuklash
1. [github.com](https://github.com) da yangi repository yarating
2. Bu papkadagi barcha fayllarni yuklang:
   - `bot.py`
   - `requirements.txt`
   - `railway.toml`
   - `webapp/index.html`

### B) Railway da ulash
1. [railway.app](https://railway.app) ga kiring (GitHub bilan)
2. **"New Project"** → **"Deploy from GitHub repo"**
3. Sizning repositoryni tanlang
4. Deploy bo'lishini kuting (1-2 daqiqa)
5. **Sizning URL ni oling**: Settings → Domains → Generate Domain

### C) Environment Variables qo'shish
Railway da **Variables** bo'limiga o'ting va quyidagilarni qo'shing:

```
BOT_TOKEN = 7123456789:AAHxxxxx...    (BotFather dan olgan token)
WEBAPP_URL = https://your-app.railway.app
WEBHOOK_URL = https://your-app.railway.app
PORT = 8080
```

---

## 3-qadam: Mini App ulash

1. @BotFather ga `/mybots` yuboring
2. Botingizni tanlang
3. **"Bot Settings"** → **"Menu Button"** → **"Edit Menu Button URL"**
4. URLni kiriting: `https://your-app.railway.app/webapp`

---

## 4-qadam: Botni sinash

1. Telegramda botingizga `/start` yuboring
2. **"Rejalarni boshqarish"** tugmasini bosing
3. Mini App ochiladi!
4. Vazifa qo'shing va eslatma oling ✅

---

## Bot imkoniyatlari

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni ishga tushirish |
| 📋 Rejalarni boshqarish | Mini App ochish |
| 📌 Bugungi rejalar | Bugungi vazifalar |
| 📊 Barcha rejalar | Barcha vazifalar ro'yxati |

---

## Muammolar bo'lsa

- **Bot javob bermayapti**: BOT_TOKEN to'g'ri ekanligini tekshiring
- **Mini App ochilmayapti**: WEBAPP_URL to'g'ri ekanligini tekshiring  
- **Eslatma kelmayapti**: Vaqt zonasi (Asia/Tashkent) to'g'ri

---

## Texnik ma'lumot

- Python 3.11+
- aiogram 3.x (async Telegram library)
- APScheduler (har daqiqada vazifalarni tekshiradi)
- Ma'lumotlar `tasks.json` faylda saqlanadi
- Toshkent vaqt zonasida ishlaydi (UTC+5)
