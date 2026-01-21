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

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
MONITOR_CHANNEL_ID = -1003440607760
REGISTRATION_URL = "https://u3.shortink.io/register?utm_campaign=817094&utm_source=affiliate&utm_medium=sr&a=6uw2UJ3XfkHJR8&ac=nikita"
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-web-app-url.com")  # Replace with actual Web App URL

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize database
db = Database()

# Initialize Telethon client
telethon_client: Optional[TelegramClient] = None

# FSM States
class ValidationStates(StatesGroup):
    waiting_for_id = State()


def get_launch_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with Launch Trading HUD button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚀 Запустить Trading HUD",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )
    ]])


def get_registration_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with Registration and Try Again buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Регистрация", url=REGISTRATION_URL)],
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="try_again")]
    ])


def get_try_again_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with Try Again button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="try_again")
    ]])


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    tg_id = message.from_user.id
    
    # Check if user is already verified
    if await db.is_user_verified(tg_id):
        pocket_id = await db.get_user_pocket_id(tg_id)
        await message.answer(
            f"✅ Вы уже верифицированы!\n"
            f"Ваш Pocket Option ID: {pocket_id}\n\n"
            f"Запустите Trading HUD для начала работы:",
            reply_markup=get_launch_keyboard()
        )
    else:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Для доступа к Trading HUD необходимо верифицировать ваш Pocket Option ID.\n\n"
            "Пожалуйста, введите ваш Pocket Option ID (только цифры):"
        )
        await state.set_state(ValidationStates.waiting_for_id)


@dp.message(ValidationStates.waiting_for_id)
async def process_pocket_id(message: Message, state: FSMContext):
    """Process Pocket Option ID input."""
    user_input = message.text.strip()
    
    # Validate input (should be numeric)
    if not user_input.isdigit():
        await message.answer(
            "❌ Неверный формат. Пожалуйста, введите только цифры:"
        )
        return
    
    pocket_id = user_input
    tg_id = message.from_user.id
    
    # Show searching message
    search_msg = await message.answer("🔍 Проверяю кэш...")
    
    # Step A: Check local cache
    if await db.is_id_in_cache(pocket_id):
        # ID found in cache, verify user
        await search_msg.edit_text("✅ ID найден в кэше! Верифицирую...")
        if await db.verify_user(tg_id, pocket_id):
            await search_msg.edit_text(
                f"✅ Верификация успешна!\n"
                f"Ваш Pocket Option ID: {pocket_id}\n\n"
                f"Теперь вы можете использовать Trading HUD:",
                reply_markup=get_launch_keyboard()
            )
            await state.clear()
            return
    
    # Step B: Deep search in channel history
    await search_msg.edit_text("🔍 Ищу в архивах канала...")
    
    found = await deep_search_channel(pocket_id)
    
    if found:
        # Add to cache and verify user
        await db.add_to_cache(pocket_id)
        if await db.verify_user(tg_id, pocket_id):
            await search_msg.edit_text(
                f"✅ ID найден в архивах! Верификация успешна.\n"
                f"Ваш Pocket Option ID: {pocket_id}\n\n"
                f"Теперь вы можете использовать Trading HUD:",
                reply_markup=get_launch_keyboard()
            )
            await state.clear()
            return
    
    # ID not found
    await search_msg.edit_text(
        f"❌ ID {pocket_id} не найден в системе.\n\n"
        f"Если вы еще не зарегистрированы, пройдите регистрацию:",
        reply_markup=get_registration_keyboard()
    )


@dp.callback_query(F.data == "try_again")
async def try_again_callback(callback: CallbackQuery, state: FSMContext):
    """Handle Try Again button."""
    await callback.answer()
    await callback.message.edit_text(
        "Пожалуйста, введите ваш Pocket Option ID (только цифры):"
    )
    await state.set_state(ValidationStates.waiting_for_id)


async def deep_search_channel(pocket_id: str) -> bool:
    """Search for Pocket Option ID in channel history using Telethon."""
    global telethon_client
    
    if not telethon_client:
        return False
    
    try:
        # Search for messages containing "ID: {pocket_id}"
        search_pattern = f"ID: {pocket_id}"
        
        async for message in telethon_client.iter_messages(
            MONITOR_CHANNEL_ID,
            search=search_pattern,
            limit=100
        ):
            if message.text and search_pattern in message.text:
                return True
        
        return False
    except Exception as e:
        print(f"Error in deep search: {e}")
        return False


async def extract_ids_from_message(text: str) -> list[str]:
    """Extract Pocket Option IDs from message text using regex."""
    pattern = r"ID:\s*(\d+)"
    matches = re.findall(pattern, text)
    return matches


async def handle_new_message(event):
    """Handle new messages in the monitored channel."""
    if event.chat_id != MONITOR_CHANNEL_ID:
        return
    
    if event.message.text:
        # Extract IDs from message
        ids = await extract_ids_from_message(event.message.text)
        
        # Add each ID to cache
        for pocket_id in ids:
            await db.add_to_cache(pocket_id)
            print(f"Added ID to cache: {pocket_id}")


async def start_monitoring():
    """Start real-time channel monitoring."""
    global telethon_client
    
    if not telethon_client:
        return
    
    try:
        # Register event handler for new messages
        telethon_client.add_event_handler(
            handle_new_message,
            events.NewMessage(chats=MONITOR_CHANNEL_ID)
        )
        print("Channel monitoring started (real-time)")
    except Exception as e:
        print(f"Error starting monitoring: {e}")


async def init_telethon():
    """Initialize Telethon client."""
    global telethon_client
    
    if not API_ID or not API_HASH or API_ID == 0:
        print("Warning: API_ID or API_HASH not set. Telethon features will be disabled.")
        return
    
    try:
        telethon_client = TelegramClient("session", API_ID, API_HASH)
        await telethon_client.start()
        print("Telethon client initialized successfully")
    except Exception as e:
        print(f"Error initializing Telethon: {e}")
        telethon_client = None


async def main():
    """Main function to start the bot."""
    # Initialize database
    await db.init_db()
    print("Database initialized")
    
    # Initialize Telethon
    await init_telethon()
    
    # Start channel monitoring
    await start_monitoring()
    
    # Start polling (Telethon client is already running from start())
    print("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
    finally:
        if telethon_client:
            try:
                asyncio.run(telethon_client.disconnect())
            except:
                pass
