"""
Telegram Affiliate Bot for Pocket Option
Updated: Deposit Logic requested
"""
import os
import re
import asyncio
from typing import Optional, Tuple
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
from aiohttp import web

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL")
MONITOR_CHANNEL_ID = -1003440607760
# Ссылка на регистрацию
REGISTRATION_URL = "https://u3.shortink.io/register?utm_campaign=817094&utm_source=affiliate&utm_medium=sr&a=6uw2UJ3XfkHJR8&ac=nikita"
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-web-app-url.com")
SUPPORT_URL = "https://t.me/jezzseller"
GUIDE_IMAGE_URL = "https://i.ibb.co/2YY2sNv9/photo-2026-01-22-07-03-16.jpg"

# --- SERVER FOR RENDER ---
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
# -------------------------

# Initialize
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

if not DATABASE_URL:
    print("❌ ОШИБКА: DATABASE_URL не найден.")
db = Database(DATABASE_URL)
telethon_client: Optional[TelegramClient] = None

class ValidationStates(StatesGroup):
    waiting_for_id = State()

# --- KEYBOARDS ---

def get_launch_keyboard() -> InlineKeyboardMarkup:
    """Полный доступ (после депозита)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить Trading HUD", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def get_deposit_check_keyboard() -> InlineKeyboardMarkup:
    """Только кнопка проверки депозита."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я пополнил", callback_data="check_deposit_again")],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def get_registration_keyboard() -> InlineKeyboardMarkup:
    """Если ID не найден вообще."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Регистрация", url=REGISTRATION_URL)],
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="try_again")],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def get_try_again_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="try_again")],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

# --- HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    
    # Если юзер уже есть в базе (полная верификация)
    if await db.is_user_verified(tg_id):
        pocket_id = await db.get_user_pocket_id(tg_id)
        await message.answer(
            f"✅ Вы уже верифицированы!\nВаш ID: {pocket_id}\n\nЗапустите Trading HUD:",
            reply_markup=get_launch_keyboard()
        )
    else:
        # Приветствие
        caption_text = (
            "👋 Добро пожаловать!\n\n"
            "Для доступа к Trading HUD необходимо верифицировать ваш аккаунт.\n"
            "Отправьте ваш цифровой ID (как на картинке) сообщением:"
        )
        try:
            await message.answer_photo(
                photo=GUIDE_IMAGE_URL,
                caption=caption_text,
                reply_markup=get_try_again_keyboard()
            )
        except Exception:
            await message.answer(caption_text, reply_markup=get_try_again_keyboard())
            
        await state.set_state(ValidationStates.waiting_for_id)

@dp.message(ValidationStates.waiting_for_id)
async def process_pocket_id(message: Message, state: FSMContext):
    user_input = message.text.strip()
    if not user_input.isdigit():
        await message.answer("❌ Введите только цифры ID:", reply_markup=get_try_again_keyboard())
        return

    pocket_id = user_input
    tg_id = message.from_user.id
    msg = await message.answer("🔍 Проверяю данные...")
    
    # Проверяем ID в канале
    is_found, is_deposit = await deep_search_channel(pocket_id)
    
    if is_found:
        if is_deposit:
            # Сценарий: ЕСТЬ ДЕПОЗИТ -> ПУСКАЕМ
            await db.add_to_cache(pocket_id) 
            await db.verify_user(tg_id, pocket_id)
            await state.clear()
            
            await msg.edit_text(
                f"✅ **Доступ открыт!**\nID: {pocket_id}\nДепозит подтвержден.",
                reply_markup=get_launch_keyboard()
            )
        else:
            # Сценарий: ТОЛЬКО РЕГИСТРАЦИЯ -> ПРОСИМ ПОПОЛНИТЬ
            # Сохраняем ID в память, чтобы кнопка сработала
            await state.update_data(current_id=pocket_id)
            
            await msg.edit_text(
                f"⚠️ ID: {pocket_id} найден.\n\n"
                "Для полноценного доступа к боту нужно пополнить баланс аккаунта Pocket Option, который вы создали.\n\n"
                "После пополнения нажмите кнопку ниже:",
                reply_markup=get_deposit_check_keyboard()
            )
    else:
        # Сценарий: ВООБЩЕ НЕ НАЙДЕН
        await msg.edit_text(
            f"❌ ID {pocket_id} не найден.\n"
            f"Проверьте правильность ввода или зарегистрируйтесь по ссылке.",
            reply_markup=get_registration_keyboard()
        )

@dp.callback_query(F.data == "try_again")
async def try_again_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Введите ваш Pocket Option ID (цифры):")
    await state.set_state(ValidationStates.waiting_for_id)

@dp.callback_query(F.data == "check_deposit_again")
async def check_deposit_again(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка 'Я пополнил'. Снова проверяет канал на наличие депозита.
    """
    data = await state.get_data()
    pocket_id = data.get("current_id")
    
    if not pocket_id:
        await callback.message.answer("⚠️ ID сбросился. Введите ID заново:")
        await state.set_state(ValidationStates.waiting_for_id)
        return

    await callback.answer("Проверяю постбэки...") # Всплывающее уведомление
    
    # Повторная проверка
    is_found, is_deposit = await deep_search_channel(pocket_id)
    
    if is_deposit:
        # ДЕПОЗИТ НАЙДЕН
        tg_id = callback.from_user.id
        await db.verify_user(tg_id, pocket_id)
        await state.clear()
        
        await callback.message.edit_text(
            f"✅ **Отлично! Депозит найден.**\nID: {pocket_id}\n\nДоступ к боту открыт:",
            reply_markup=get_launch_keyboard()
        )
    else:
        # ДЕПОЗИТА ВСЕ ЕЩЕ НЕТ
        # Не меняем текст сообщения кардинально, просто говорим подождать
        try:
            await callback.message.answer(
                "⏳ Постбэк о депозите еще не пришел.\n"
                "Обычно это занимает 1-2 минуты. Попробуйте нажать кнопку еще раз чуть позже.",
                reply_markup=get_deposit_check_keyboard() # Дублируем кнопку внизу
            )
        except:
            pass # Игнорируем ошибки API если юзер спамит

# --- TELETHON LOGIC ---

async def deep_search_channel(pocket_id: str) -> Tuple[bool, bool]:
    """
    Ищет ID и статус.
    Возвращает: (найден_ли_вообще, был_ли_депозит)
    """
    global telethon_client
    if not telethon_client:
        return False, False
        
    search_pattern = f"ID: {pocket_id}"
    is_found = False
    is_deposit = False
    
    try:
        # Проходим по последним 100 сообщениям с этим ID
        async for message in telethon_client.iter_messages(MONITOR_CHANNEL_ID, search=search_pattern, limit=100):
            if message.text and search_pattern in message.text:
                is_found = True
                txt = message.text.lower()
                
                # Проверка на депозит (по эмодзи 💰 или слову Депчик)
                if "депчик" in txt or "💰" in txt:
                    is_deposit = True
                    break # Нашли депозит — супер, выходим
                    
        return is_found, is_deposit
    except Exception as e:
        print(f"Error checking channel: {e}")
        return False, False

async def handle_new_message(event):
    """Кэширование в реальном времени (не обязательно для основной логики, но полезно)"""
    if event.chat_id != MONITOR_CHANNEL_ID:
        return
    text = event.message.text
    if text:
        ids = re.findall(r"ID:\s*(\d+)", text)
        for pid in ids:
            await db.add_to_cache(pid)

async def start_monitoring():
    global telethon_client
    if not telethon_client:
        return
    telethon_client.add_event_handler(handle_new_message, events.NewMessage(chats=MONITOR_CHANNEL_ID))

async def init_telethon():
    global telethon_client
    if not API_ID or not API_HASH: 
        return
    telethon_client = TelegramClient("session", API_ID, API_HASH)
    await telethon_client.start()

async def main():
    if DATABASE_URL:
        await db.init_db()
    
    await start_server()
    await init_telethon()
    await start_monitoring()
    
    print("🚀 Bot started with Deposit Logic")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
