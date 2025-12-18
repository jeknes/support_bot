import os
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_USER_ID", "").split(",") if x.strip()]

# Render даёт URL вида: https://ваш-бот.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = "my-secret"  # можно любой, но лучше сложный
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://ваш-бот.onrender.com")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
active_users = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    active_users[user.id] = {"name": user.full_name, "username": user.username}
    await message.answer(
        "👋 Здравствуйте! Это служба поддержки.\n"
        "Опишите вашу проблему — мы ответим вам через этого бота."
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_message(message: Message):
    user = message.from_user
    active_users[user.id] = {"name": user.full_name, "username": user.username}

    username = f"@{user.username}" if user.username else "нет юзернейма"
    text_for_admin = (
        f"📩 Новое обращение:\n"
        f"🔹 ID: {user.id}\n"
        f"🔹 Имя: {user.full_name}\n"
        f"🔹 Юзернейм: {username}\n"
        f"🔹 Сообщение:\n> {message.text}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text_for_admin, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Не отправить админу {admin_id}: {e}")
    await message.answer("✅ Ваше обращение отправлено. Ожидайте ответа!")


@router.message(Command("reply"))
async def cmd_reply(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Эта команда доступна только администраторам.")
        return

    args = command.args
    if not args or " " not in args:
        await message.answer("📌 Используйте: /reply <ID> текст", parse_mode="Markdown")
        return

    try:
        user_id_str, reply_text = args.split(" ", 1)
        user_id = int(user_id_str)
    except:
        await message.answer("❌ Неверный ID.")
        return

    if user_id not in active_users:
        await message.answer(f"⚠️ Пользователь с ID {user_id} не найден.", parse_mode="Markdown")
        return

    try:
        await bot.send_message(user_id, f"📬 Ответ от поддержки:\n\n{reply_text}")
        name = active_users[user_id]['name']
        await message.answer(f"✅ Ответ отправлен: {name} (ID: {user_id})")
    except:
        await message.answer(f"❌ Не удалось отправить пользователю {user_id}.")


# --- Webhook setup ---
async def on_startup(app: web.Application):
    webhook_url = f"{BASE_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True
    )
    logging.info(f"Webhook установлен на: {webhook_url}")


async def on_shutdown(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()


if name == "main":
    # Регистрируем роутер
    dp.include_router(router)

    # Создаём aiohttp-приложение
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Render даёт PORT, нужно использовать его
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)
