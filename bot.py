import asyncio
import json
import logging
import os
from datetime import datetime
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


def load_tasks() -> dict:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tasks(tasks: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


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
    today = datetime.now().strftime("%Y-%m-%d")

    today_tasks = [t for t in user_tasks if t.get("date") == today and not t.get("done")]

    if not today_tasks:
        await callback.message.answer("📭 Bugun uchun rejalanmagan vazifalar yo'q.")
    else:
        text = "📅 <b>Bugungi rejalar:</b>\n\n"
        for i, task in enumerate(today_tasks, 1):
            time_str = task.get("time", "--:--")
            text += f"{i}. ⏰ <b>{time_str}</b> — {task['title']}\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "all_tasks")
async def show_all(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    tasks = load_tasks()
    user_tasks = tasks.get(user_id, [])
    active = [t for t in user_tasks if not t.get("done")]

    if not active:
        await callback.message.answer("📭 Hozircha hech qanday reja yo'q.\nQo'shish uchun «Rejalarni boshqarish» tugmasini bosing.")
    else:
        text = "📋 <b>Barcha rejalar:</b>\n\n"
        for i, task in enumerate(active, 1):
            date_str = task.get("date", "")
            time_str = task.get("time", "")
            text += f"{i}. <b>{date_str} {time_str}</b>\n   📌 {task['title']}\n\n"
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
            if (
                not task.get("done")
                and not task.get("reminded")
                and task.get("date") == current_date
                and task.get("time") == current_time
            ):
                try:
                    await bot.send_message(
                        int(user_id),
                        f"🔔 <b>Eslatma!</b>\n\n"
                        f"📌 <b>{task['title']}</b>\n\n"
                        f"⏰ Vaqt keldi!",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"done_{task['id']}"),
                            InlineKeyboardButton(text="⏩ Keyinroq", callback_data=f"snooze_{task['id']}")
                        ]])
                    )
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
            task["done"] = True
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
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    data = await request.json()
    action = data.get("action")
    user_id = str(data.get("user_id"))
    tasks = load_tasks()

    if user_id not in tasks:
        tasks[user_id] = []

    if action == "add":
        task = {
            "id": f"{user_id}_{len(tasks[user_id])}_{int(datetime.now().timestamp())}",
            "title": data["title"],
            "date": data["date"],
            "time": data["time"],
            "done": False,
            "reminded": False,
            "created_at": datetime.now().isoformat()
        }
        tasks[user_id].append(task)
        save_tasks(tasks)
        return web.json_response({"ok": True, "task": task}, headers={"Access-Control-Allow-Origin": "*"})

    elif action == "get":
        user_tasks = [t for t in tasks.get(user_id, []) if not t.get("done")]
        return web.json_response({"ok": True, "tasks": user_tasks}, headers={"Access-Control-Allow-Origin": "*"})

    elif action == "delete":
        task_id = data.get("id")
        tasks[user_id] = [t for t in tasks[user_id] if t.get("id") != task_id]
        save_tasks(tasks)
        return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

    elif action == "done":
        task_id = data.get("id")
        for task in tasks.get(user_id, []):
            if task.get("id") == task_id:
                task["done"] = True
        save_tasks(tasks)
        return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

    return web.json_response({"ok": False, "error": "Unknown action"}, headers={"Access-Control-Allow-Origin": "*"})


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
    else:
        await dp.start_polling(bot)


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

    if not WEBHOOK_URL:
        await dp.start_polling(bot)
    else:
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
