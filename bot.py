import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, CallbackQuery
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.railway.app")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", 8080))

DATA_FILE = "tasks.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

REPEAT_LABELS = {
    "none": "Bir martalik",
    "daily": "Har kun 🔁",
    "weekly": "Har hafta 📅",
    "workdays": "Ish kunlari (Du-Ju) 💼",
    "custom": "Tanlangan kunlar ✅"
}

WEEKDAY_NAMES = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


def load_tasks() -> dict:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tasks(tasks: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def should_remind_today(task: dict) -> bool:
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()  # 0=Monday ... 6=Sunday
    repeat = task.get("repeat", "none")

    if repeat == "none":
        return task.get("date") == today_str
    elif repeat == "daily":
        start = task.get("date", "")
        return today_str >= start
    elif repeat == "weekly":
        start_date = datetime.strptime(task.get("date", today_str), "%Y-%m-%d")
        return weekday == start_date.weekday() and today_str >= task.get("date", "")
    elif repeat == "workdays":
        return weekday < 5 and today_str >= task.get("date", "")
    elif repeat == "custom":
        days = task.get("repeat_days", [])
        return weekday in days and today_str >= task.get("date", "")
    return False


def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Rejalarni boshqarish",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/webapp?user_id={user_id}")
        )],
        [InlineKeyboardButton(text="📌 Bugungi rejalar", callback_data="today")],
        [InlineKeyboardButton(text="📊 Barcha rejalar", callback_data="all_tasks")],
    ])


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    tasks = load_tasks()
    if str(user_id) not in tasks:
        tasks[str(user_id)] = []
        save_tasks(tasks)

    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        "🤖 Men sizning kunlik <b>eslatma botingizman</b>.\n\n"
        "✅ Reja qo'shing\n"
        "⏰ Vaqtini belgilang\n"
        "🔁 Takrorlanishni sozlang\n"
        "🔔 Kerakli vaqtda eslataman!\n\n"
        "Pastdagi tugmani bosing 👇",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "today")
async def show_today(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    tasks = load_tasks()
    user_tasks = tasks.get(user_id, [])

    today_tasks = [t for t in user_tasks if should_remind_today(t) and not t.get("done")]

    if not today_tasks:
        await callback.message.answer("📭 Bugun uchun rejalanmagan vazifalar yo'q.")
    else:
        text = "📅 <b>Bugungi rejalar:</b>\n\n"
        for i, task in enumerate(today_tasks, 1):
            time_str = task.get("time", "--:--")
            repeat = REPEAT_LABELS.get(task.get("repeat", "none"), "")
            text += f"{i}. ⏰ <b>{time_str}</b> — {task['title']}"
            if task.get("repeat", "none") != "none":
                text += f" <i>({repeat})</i>"
            text += "\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "all_tasks")
async def show_all(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    tasks = load_tasks()
    user_tasks = tasks.get(user_id, [])
    active = [t for t in user_tasks if not t.get("done")]

    if not active:
        await callback.message.answer(
            "📭 Hozircha hech qanday reja yo'q.\n"
            "Qo'shish uchun «Rejalarni boshqarish» tugmasini bosing."
        )
    else:
        text = "📋 <b>Barcha rejalar:</b>\n\n"
        for i, task in enumerate(active, 1):
            date_str = task.get("date", "")
            time_str = task.get("time", "")
            repeat = REPEAT_LABELS.get(task.get("repeat", "none"), "")
            text += f"{i}. <b>{date_str} {time_str}</b>\n"
            text += f"   📌 {task['title']}\n"
            if task.get("repeat", "none") != "none":
                text += f"   🔁 {repeat}\n"
            text += "\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


async def check_and_remind():
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    tasks = load_tasks()
    changed = False

    for user_id, user_tasks in tasks.items():
        for task in user_tasks:
            if task.get("done"):
                continue
            if task.get("time") != current_time:
                continue
            if not should_remind_today(task):
                continue

            # Takrorlanadigan vazifalar: bugun reminded bo'lmagan bo'lsin
            reminded_today = task.get("reminded_date") == current_date
            if reminded_today:
                continue

            try:
                repeat = task.get("repeat", "none")
                repeat_text = ""
                if repeat != "none":
                    repeat_text = f"\n🔁 <i>{REPEAT_LABELS.get(repeat, '')}</i>"

                await bot.send_message(
                    int(user_id),
                    f"🔔 <b>Eslatma!</b>\n\n"
                    f"📌 <b>{task['title']}</b>{repeat_text}\n\n"
                    f"⏰ Vaqt keldi!",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"done_{task['id']}"),
                        InlineKeyboardButton(text="⏩ Keyinroq", callback_data=f"snooze_{task['id']}")
                    ]])
                )
                task["reminded_date"] = current_date
                # Bir martalik bo'lsa reminded=True qilamiz
                if repeat == "none":
                    task["reminded"] = True
                changed = True
                logger.info(f"Reminded user {user_id}: {task['title']}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {user_id}: {e}")

    if changed:
        save_tasks(tasks)


@dp.callback_query(F.data.startswith("done_"))
async def mark_done(callback: CallbackQuery):
    task_id = callback.data.replace("done_", "")
    user_id = str(callback.from_user.id)
    tasks = load_tasks()

    for task in tasks.get(user_id, []):
        if task.get("id") == task_id:
            repeat = task.get("repeat", "none")
            if repeat == "none":
                task["done"] = True
            else:
                # Takrorlanadigan — faqat bugungi "done" deb belgilaymiz
                task["reminded_date"] = datetime.now().strftime("%Y-%m-%d")
            break

    save_tasks(tasks)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Bajarildi!</b>",
        parse_mode="HTML"
    )
    await callback.answer("Bajarildi ✅")


@dp.callback_query(F.data.startswith("snooze_"))
async def snooze_task(callback: CallbackQuery):
    await callback.message.edit_text(
        callback.message.text + "\n\n⏩ <b>10 daqiqadan keyin yana eslataman.</b>",
        parse_mode="HTML"
    )
    await callback.answer("10 daqiqadan keyin ⏩")


async def handle_webapp_data(request: web.Request) -> web.Response:
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if request.method == "OPTIONS":
        return web.Response(headers=cors_headers)

    data = await request.json()
    action = data.get("action")
    user_id = str(data.get("user_id"))
    tasks = load_tasks()

    if user_id not in tasks:
        tasks[user_id] = []

    if action == "add":
        task = {
            "id": f"{user_id}_{int(datetime.now().timestamp())}",
            "title": data["title"],
            "desc": data.get("desc", ""),
            "date": data["date"],
            "time": data["time"],
            "repeat": data.get("repeat", "none"),
            "repeat_days": data.get("repeat_days", []),
            "done": False,
            "reminded": False,
            "reminded_date": "",
            "created_at": datetime.now().isoformat()
        }
        tasks[user_id].append(task)
        save_tasks(tasks)
        return web.json_response({"ok": True, "task": task}, headers=cors_headers)

    elif action == "get":
        user_tasks = [t for t in tasks.get(user_id, []) if not t.get("done")]
        return web.json_response({"ok": True, "tasks": user_tasks}, headers=cors_headers)

    elif action == "delete":
        task_id = data.get("id")
        tasks[user_id] = [t for t in tasks[user_id] if t.get("id") != task_id]
        save_tasks(tasks)
        return web.json_response({"ok": True}, headers=cors_headers)

    elif action == "done":
        task_id = data.get("id")
        for task in tasks.get(user_id, []):
            if task.get("id") == task_id:
                task["done"] = True
        save_tasks(tasks)
        return web.json_response({"ok": True}, headers=cors_headers)

    return web.json_response({"ok": False, "error": "Unknown action"}, headers=cors_headers)


async def serve_webapp(request: web.Request) -> web.Response:
    html_path = Path(__file__).parent / "webapp" / "index.html"
    content = html_path.read_text(encoding="utf-8")
    return web.Response(text=content, content_type="text/html")


async def on_startup(app: web.Application):
    scheduler.add_job(check_and_remind, "cron", minute="*")
    scheduler.start()

    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        logger.info(f"Webhook set: {WEBHOOK_URL}/webhook")


async def main():
    app = web.Application()
    app.router.add_get("/webapp", serve_webapp)
    app.router.add_post("/api/tasks", handle_webapp_data)
    app.router.add_get("/api/tasks", handle_webapp_data)
    app.router.add_route("OPTIONS", "/api/tasks", handle_webapp_data)

    if WEBHOOK_URL:
        webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Server started on port {PORT}")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
