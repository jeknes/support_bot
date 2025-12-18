
import os
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Настройка логгера
logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Простое хранилище: user_id → user info (в памяти)
# В продакшене замени на SQLite/PostgreSQL
active_users = {}  # {user_id: {'name': str, 'username': str or None}}


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    active_users[user.id] = {
        "name": user.full_name,
        "username": user.username
    }
    await message.answer(
        "👋 Здравствуйте! Это служба поддержки.\n"
        "Опишите вашу проблему — мы ответим вам через этого бота.\n\n"
        "❗ Чтобы мы могли ответить, не удаляйте этот чат."
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_message(message: Message):
    user = message.from_user

    # Обновляем/фиксируем данные на случай, если юзер изменил имя/юзернейм
    active_users[user.id] = {
        "name": user.full_name,
        "username": user.username
    }

    # Формируем сообщение для админа
    username = f"@{user.username}" if user.username else "нет юзернейма"
    text_for_admin = (
        f"📩 Новое обращение:\n"
        f"🔹 ID: {user.id}\n"
        f"🔹 Имя: {user.full_name}\n"
        f"🔹 Юзернейм: {username}\n"
        f"🔹 Сообщение:\n> {message.text}"
    )

    try:
        await bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=text_for_admin,
            parse_mode="Markdown"
        )
        await message.answer("✅ Ваше обращение отправлено. Ожидайте ответа от поддержки!")
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")
        await message.answer("❌ Не удалось отправить сообщение. Обратитесь позже.")


# ======== Админ-команда: /reply <user_id> <текст> ========
@router.message(Command("reply"))
async def cmd_reply(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("🚫 Эта команда доступна только администратору.")
        return

    args = command.args
    if not args or " " not in args:
        await message.answer(
            "📌 Использование: /reply <user_id> <текст ответа>\n"
            "Пример: /reply 123456789 Здравствуйте! Проблема решена.",
            parse_mode="Markdown"
        )
        return

    try:
        user_id_str, reply_text = args.split(" ", 1)
        user_id = int(user_id_str)
    except ValueError:
        await message.answer("❌ Неверный формат ID. Укажите целое число.")
        return

    # Проверяем, известен ли нам этот пользователь
    if user_id not in active_users:
        await message.answer(
            f"⚠️ Пользователь с ID {user_id} не найден в активных обращениях.\n"
            "Возможно, он ещё не писал боту или давно не обращался.",
            parse_mode="Markdown"
        )
        return

    # Отправляем ответ пользователю
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "📬 Ответ от службы поддержки:\n\n"
                f"{reply_text}"
            )
        )
        # Подтверждение админу
        user_info = active_users[user_id]
        name = user_info['name']
        await message.answer(f"✅ Ответ отправлен пользователю {name} (ID: {user_id}).")
    except Exception as e:
        logging.error(f"Не удалось отправить ответ пользователю {user_id}: {e}")
        await message.answer(
            f"❌ Не удалось отправить сообщение пользователю (ID: {user_id}).\n"
            "Возможно, он заблокировал бота или удалил чат.",
            parse_mode="Markdown"
        )


# Перехват неизвестных команд
@router.message(F.text.startswith("/"))
async def unknown_command(message: Message):
    await message.answer("❓ Неизвестная команда. Используйте /start для начала обращения.")


# Обработка всего остального (медиа, стикеры и т.д.)
@router.message()
async def fallback(message: Message):
    if message.from_user.id == ADMIN_USER_ID:
        await message.answer("ℹ️ Совет: используйте /reply <ID> текст, чтобы ответить.")
    else:
        await message.answer("📩 Пожалуйста, отправьте текстовое сообщение с описанием проблемы.")


async def main():
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
