"""
Telegram Affiliate Bot with Hybrid ID Validation for Pocket Option
"""
import os
import re
import asyncio
from typing import Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient
from telethon import events
from database import Database

# Импортируем aiohttp для создания сервера-пустышки
from aiohttp import web

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL")
MONITOR_CHANNEL_ID = -1003440607760
REGISTRATION_URL = "https://u3.shortink.io/register?utm_campaign=817094&utm_source=affiliate&utm_medium=sr&a=6uw2UJ3XfkHJR8&ac=nikita"
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-web-app-url.com")
SUPPORT_URL = "https://t.me/jezzseller"  # Ссылка на поддержку

# Ссылка на картинку-инструкцию
GUIDE_IMAGE_URL = "https://i.ibb.co/2YY2sNv9/photo-2026-01-22-07-03-16.jpg"

# --- СЕКЦИЯ СЕРВЕРА-ПУСТЫШКИ ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web server started on port {port}")
# ------------------------------------------

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize database
if not DATABASE_URL:
    print("❌ ОШИБКА: DATABASE_URL не найден.")
db = Database(DATABASE_URL)

telethon_client: Optional[TelegramClient] = None

class ValidationStates(StatesGroup):
    waiting_for_id = State()

def get_launch_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для запуска WebApp (уже верифицирован)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить Trading HUD", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def get_registration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура если ID не найден."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Регистрация", url=REGISTRATION_URL)],
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="try_again")],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def get_try_again_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при ошибке ввода или старте."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="try_again")],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    tg_id = message.from_user.id
    
    # Если пользователь уже верифицирован
    if await db.is_user_verified(tg_id):
        pocket_id = await db.get_user_pocket_id(tg_id)
        await message.answer(
            f"✅ Вы уже верифицированы!\nВаш Pocket Option ID: {pocket_id}\n\nЗапустите Trading HUD для начала работы:",
            reply_markup=get_launch_keyboard()
        )
    else:
        # Если пользователь НЕ верифицирован — отправляем ФОТО с инструкцией
        caption_text = (
            "👋 Добро пожаловать!\n\n"
            "Для доступа к Trading HUD необходимо верифицировать ваш Pocket Option ID.\n\n"
            "1. Зайдите в профиль на платформе.\n"
            "2. Скопируйте ваш ID (цифры), как показано на картинке.\n"
            "3. Отправьте эти цифры сюда сообщением."
        )
        try:
            # Пытаемся отправить фото
            await message.answer_photo(
                photo=GUIDE_IMAGE_URL,
                caption=caption_text,
                reply_markup=get_try_again_keyboard()
            )
        except Exception as e:
            # Если ссылка на фото не сработает, отправляем просто текст
            print(f"Error sending photo: {e}")
            await message.answer(caption_text, reply_markup=get_try_again_keyboard())
            
        await state.set_state(ValidationStates.waiting_for_id)

@dp.message(ValidationStates.waiting_for_id)
async def process_pocket_id(message: Message, state: FSMContext):
    """Process Pocket Option ID input."""
    user_input = message.text.strip()
    
    # Проверка на цифры
    if not user_input.isdigit():
        await message.answer(
            "❌ Неверный формат. Пожалуйста, отправьте только цифры (ваш ID):",
            reply_markup=get_try_again_keyboard()
        )
        return

    pocket_id = user_input
    tg_id = message.from_user.id
    search_msg = await message.answer("🔍 Проверяю ID...")
    
    # 1. Проверка в кэше базы данных
    if await db.is_id_in_cache(pocket_id):
        await search_msg.edit_text("✅ ID найден в базе! Верифицирую...")
        if await db.verify_user(tg_id, pocket_id):
            await search_msg.edit_text(
                f"✅ Верификация успешна!\nВаш ID: {pocket_id}\n\nТеперь вы можете использовать бот:",
                reply_markup=get_launch_keyboard()
            )
            await state.clear()
            return
            
    await search_msg.edit_text("🔍 Ищу в архивах канала...")
    
    # 2. Проверка через Telethon (история канала)
    found = await deep_search_channel(pocket_id)
    if found:
        await db.add_to_cache(pocket_id)
        if await db.verify_user(tg_id, pocket_id):
            await search_msg.edit_text(
                f"✅ ID найден! Верификация успешна.\nВаш ID: {pocket_id}\n\nТорговля доступна:",
                reply_markup=get_launch_keyboard()
            )
            await state.clear()
            return
            
    # 3. Если не найдено
    await search_msg.edit_text(
        f"❌ ID {pocket_id} не найден в списке партнеров.\n\n"
        f"Убедитесь, что вы зарегистрированы по нашей ссылке и ID введен верно.\n\n"
        f"Если вы только что зарегистрировались, подождите 5-10 минут.",
        reply_markup=get_registration_keyboard()
    )

@dp.callback_query(F.data == "try_again")
async def try_again_callback(callback: CallbackQuery, state: FSMContext):
    """Handle Try Again button."""
    await callback.answer()
    
    # Просто просим ввести ID текстом, кнопки "Поддержка" остаются доступны из предыдущего сообщения
    await callback.message.answer(
        "Пожалуйста, введите ваш Pocket Option ID (только цифры):",
        reply_markup=None
    )
    await state.set_state(ValidationStates.waiting_for_id)

async def deep_search_channel(pocket_id: str) -> bool:
    """Search for Pocket Option ID in channel history using Telethon."""
    global telethon_client
    if not telethon_client:
        return False
    try:
        search_pattern = f"ID: {pocket_id}"
        async for message in telethon_client.iter_messages(MONITOR_CHANNEL_ID, search=search_pattern, limit=100):
            if message.text and search_pattern in message.text:
                return True
        return False
    except Exception as e:
        print(f"Error in deep search: {e}")
        return False

async def extract_ids_from_message(text: str) -> list[str]:
    pattern = r"ID:\s*(\d+)"
    return re.findall(pattern, text)

async def handle_new_message(event):
    if event.chat_id != MONITOR_CHANNEL_ID:
        return
    if event.message.text:
        ids = await extract_ids_from_message(event.message.text)
        for pocket_id in ids:
            await db.add_to_cache(pocket_id)
            print(f"Added ID to cache: {pocket_id}")

async def start_monitoring():
    global telethon_client
    if not telethon_client:
        return
    try:
        telethon_client.add_event_handler(handle_new_message, events.NewMessage(chats=MONITOR_CHANNEL_ID))
        print("Channel monitoring started (real-time)")
    except Exception as e:
        print(f"Error starting monitoring: {e}")

async def init_telethon():
    global telethon_client
    if not API_ID or not API_HASH or API_ID == 0:
        print("Warning: API_ID or API_HASH not set.")
        return
    try:
        telethon_client = TelegramClient("session", API_ID, API_HASH)
        await telethon_client.start()
        print("Telethon client initialized successfully")
    except Exception as e:
        print(f"Error initializing Telethon: {e}")
        telethon_client = None

async def main():
    if DATABASE_URL:
        await db.init_db()
        print("✅ Database initialized (PostgreSQL)")
    
    await start_server()
    await init_telethon()
    await start_monitoring()
    
    print("🚀 Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        if telethon_client:
            await telethon_client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
