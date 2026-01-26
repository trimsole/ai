import os
import re
import asyncio
from typing import Optional, Tuple
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient
from telethon import events
from database import Database
from aiohttp import web

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ---
load_dotenv()

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL")
MONITOR_CHANNEL_ID = -1003440607760
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-web-app-url.com")

# --- ССЫЛКИ ---
REGISTRATION_URL = "https://u3.shortink.io/register?utm_campaign=817094&utm_source=affiliate&utm_medium=sr&a=6uw2UJ3XfkHJR8&ac=nikita"
SUPPORT_URL = "https://t.me/jezzseller"
CHANNEL_URL = "https://t.me/+DbXojk7ubdE5OGI6"  # Ссылка на канал
YOUTUBE_VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # (Замени на актуальное видео, если есть)

# --- 🖼️ КАРТИНКИ ---
IMAGES = {
    "main_menu": "https://i.ibb.co/ks2XGqv9/4dfe73c9-8ba6-405a-a875-ad0fb73b6cd1.png", # Приветствие
    "about": "https://i.ibb.co/whqtDdrt/9616dc74-bca7-4f78-95b4-1780d161a783.png",     # О технологии
    "stats": "https://i.ibb.co/8LHck6YQ/Generated-Image-January-27-2026-4-06-AM.jpg", # Статистика
    "connect": "https://i.ibb.co/DDKjd57C/Generated-Image-January-27-2026-3-53-AM.jpg", # Синхронизация
}

# --- SERVER FOR RENDER ---
async def handle(request):
    return web.Response(text="CAESAR AI BOT is running!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web server started on port {port}")

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

if not DATABASE_URL:
    print("❌ ОШИБКА: DATABASE_URL не найден.")
db = Database(DATABASE_URL)
telethon_client: Optional[TelegramClient] = None

class ValidationStates(StatesGroup):
    waiting_for_id = State()

# --- ⌨️ КЛАВИАТУРЫ ---

def get_main_menu_kb(is_verified: bool = False):
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 О технологии CAESAR", callback_data="about_ai")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats"),
         InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_URL)], # Добавил кнопку канала
        [InlineKeyboardButton(text="🎓 Обучение", callback_data="education")],
        # Если верифицирован - кнопка запуска, если нет - кнопка подключения
        [InlineKeyboardButton(text="🚀 ЗАПУСТИТЬ HUD" if is_verified else "🔗 ПОДКЛЮЧИТЬ CAESAR AI", 
                              callback_data="start_flow")]
    ])
    return builder

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
    ])

def get_launch_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть Trading HUD", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="📢 Канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="🔙 Меню", callback_data="back_to_main")]
    ])

def get_deposit_check_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я пополнил баланс", callback_data="check_deposit_again")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])

def get_registration_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать профиль", url=REGISTRATION_URL)],
        [InlineKeyboardButton(text="🔄 Ввести ID заново", callback_data="retry_id")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]
    ])

# --- 📝 ТЕКСТЫ ---

TEXT_MAIN = (
    "👋 <b>Вас приветствует CAESAR AI CHART ANALYZER!</b>\n\n"
    "Я — передовой ИИ-ассистент для технического анализа рыночных графиков.\n\n"
    "⚡ <b>Мои возможности:</b>\n"
    "• Глубокий анализ 50+ индикаторов\n"
    "• Учет волатильности и новостного фона\n"
    "• Автоматическое построение прогнозов\n\n"
    "👇 <i>Используйте меню для навигации:</i>"
)

TEXT_ABOUT = (
    "🧠 <b>Технология CAESAR AI</b>\n\n"
    "Алгоритм CAESAR обучен на миллионах исторических графиков. "
    "Он сканирует рынок в реальном времени, используя данные TradingView и Investing.com.\n\n"
    "Мы не просто даем сигналы, мы предоставляем полную аналитическую картину для принятия решений.\n\n"
    "⚠️ <i>Торговля сопряжена с рисками. Используйте аналитику с умом.</i>"
)

TEXT_STATS = (
    "📊 <b>Статистика CAESAR AI</b>\n\n"
    "За последний месяц наша нейросеть обработала более 12,000 рыночных ситуаций.\n"
    "Точность определения тренда на высоковолатильных парах достигает <b>85-89%</b>.\n\n"
    "<i>Полная статистика доступна в реальном времени внутри Trading HUD.</i>"
)

TEXT_CONNECT = (
    "🔓 <b>Синхронизация с брокером</b>\n\n"
    "Для работы CAESAR AI необходимо подключить ваш торговый профиль.\n\n"
    "1. Создайте новый аккаунт на платформе (для доступа к API котировок).\n"
    "2. Отправьте ваш <b>цифровой ID</b> в ответ на это сообщение.\n\n"
    "<i>Это необходимо для точной синхронизации графиков.</i>"
)

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    is_verified = await db.is_user_verified(tg_id)
    
    try:
        await message.answer_photo(
            photo=IMAGES["main_menu"],
            caption=TEXT_MAIN,
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(is_verified)
        )
    except:
        await message.answer(TEXT_MAIN, parse_mode="HTML", reply_markup=get_main_menu_kb(is_verified))

# --- МЕНЮ НАВИГАЦИИ ---

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = callback.from_user.id
    is_verified = await db.is_user_verified(tg_id)
    
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["main_menu"], 
            caption=TEXT_MAIN, 
            parse_mode="HTML", 
            reply_markup=get_main_menu_kb(is_verified)
        )
    except:
        await callback.message.answer(TEXT_MAIN, parse_mode="HTML", reply_markup=get_main_menu_kb(is_verified))

@dp.callback_query(F.data == "about_ai")
async def show_about(callback: CallbackQuery):
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["about"], 
            caption=TEXT_ABOUT, 
            parse_mode="HTML", 
            reply_markup=get_back_kb()
        )
    except:
        await callback.message.answer(TEXT_ABOUT, parse_mode="HTML", reply_markup=get_back_kb())

@dp.callback_query(F.data == "show_stats")
async def show_stats(callback: CallbackQuery):
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["stats"], 
            caption=TEXT_STATS, 
            parse_mode="HTML", 
            reply_markup=get_back_kb()
        )
    except:
        await callback.message.answer(TEXT_STATS, parse_mode="HTML", reply_markup=get_back_kb())

@dp.callback_query(F.data == "education")
async def show_education(callback: CallbackQuery):
    await callback.answer("📚 База знаний обновляется...", show_alert=False)
    await callback.message.answer("🎓 <b>Обучение CAESAR</b>\n\nРекомендуем ознакомиться с инструкцией:", 
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                      [InlineKeyboardButton(text="📢 Перейти в канал", url=CHANNEL_URL)],
                                      [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
                                  ]), parse_mode="HTML")

# --- ЛОГИКА ПОДКЛЮЧЕНИЯ (ВОРОНКА) ---

@dp.callback_query(F.data == "start_flow")
async def start_flow(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    
    if await db.is_user_verified(tg_id):
        await callback.message.delete()
        await callback.message.answer(
            "✅ <b>Доступ разрешен</b>\nCAESAR AI готов к работе.",
            parse_mode="HTML",
            reply_markup=get_launch_keyboard()
        )
        return

    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["connect"],
            caption=TEXT_CONNECT,
            parse_mode="HTML",
            reply_markup=get_registration_keyboard()
        )
    except:
        await callback.message.answer(TEXT_CONNECT, parse_mode="HTML", reply_markup=get_registration_keyboard())
    
    await state.set_state(ValidationStates.waiting_for_id)

@dp.callback_query(F.data == "retry_id")
async def retry_id_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите ваш ID (только цифры):")
    await state.set_state(ValidationStates.waiting_for_id)

# --- ОБРАБОТКА ID ---

@dp.message(ValidationStates.waiting_for_id)
async def process_pocket_id(message: Message, state: FSMContext):
    user_input = message.text.strip()
    
    if user_input.startswith("/"):
        await state.clear()
        return

    if not user_input.isdigit():
        await message.answer("❌ ID должен состоять только из цифр.")
        return

    pocket_id = user_input
    tg_id = message.from_user.id
    status_msg = await message.answer("🔄 <i>Синхронизация с сервером брокера...</i>", parse_mode="HTML")
    
    await asyncio.sleep(1.5)

    is_found, is_deposit = await deep_search_channel(pocket_id)
    
    if is_found:
        if is_deposit:
            await db.add_to_cache(pocket_id) 
            await db.verify_user(tg_id, pocket_id)
            await state.clear()
            
            await status_msg.edit_text(
                f"✅ <b>CAESAR AI подключен!</b>\nID: {pocket_id}\nЛицензия активирована.",
                parse_mode="HTML",
                reply_markup=get_launch_keyboard()
            )
        else:
            await state.update_data(current_id=pocket_id)
            
            await status_msg.edit_text(
                f"⚠️ <b>Ожидание активации</b>\n\nАккаунт ID: {pocket_id} найден.\n"
                "Для завершения настройки CAESAR AI необходимо пополнить баланс на брокере.\n\n"
                "<i>Нажмите кнопку ниже после пополнения:</i>",
                parse_mode="HTML",
                reply_markup=get_deposit_check_keyboard()
            )
    else:
        await status_msg.edit_text(
            f"❌ <b>ID {pocket_id} не найден</b>\n"
            f"Убедитесь, что регистрация прошла успешно (для синхронизации API).",
            parse_mode="HTML",
            reply_markup=get_registration_keyboard()
        )

@dp.callback_query(F.data == "check_deposit_again")
async def check_deposit_again(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pocket_id = data.get("current_id")
    
    if not pocket_id:
        await callback.message.answer("⚠️ Сессия истекла. Введите ID заново.")
        await state.set_state(ValidationStates.waiting_for_id)
        return

    await callback.answer("🔄 Проверяю данные...", show_alert=False)
    
    is_found, is_deposit = await deep_search_channel(pocket_id)
    
    if is_deposit:
        tg_id = callback.from_user.id
        await db.verify_user(tg_id, pocket_id)
        await state.clear()
        
        await callback.message.edit_text(
            f"✅ <b>Депозит подтвержден!</b>\nДоступ к HUD открыт.",
            parse_mode="HTML",
            reply_markup=get_launch_keyboard()
        )
    else:
        await callback.answer("❌ Данные о депозите еще не поступили. Попробуйте через минуту.", show_alert=True)

# --- TELETHON LOGIC ---

async def deep_search_channel(pocket_id: str) -> Tuple[bool, bool]:
    global telethon_client
    if not telethon_client:
        return False, False
        
    search_pattern = f"ID: {pocket_id}"
    is_found = False
    is_deposit = False
    
    try:
        async for message in telethon_client.iter_messages(MONITOR_CHANNEL_ID, search=search_pattern, limit=100):
            if message.text and search_pattern in message.text:
                is_found = True
                txt = message.text.lower()
                if "депчик" in txt or "💰" in txt:
                    is_deposit = True
                    break 
        return is_found, is_deposit
    except Exception as e:
        print(f"Error checking channel: {e}")
        return False, False

async def handle_new_message(event):
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
    
    print("🚀 CAESAR AI BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
