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

# ⚠️ ВРЕМЕННО ДЛЯ МОДЕРАЦИИ - ЗАКОММЕНТИРОВАНО
# REGISTRATION_URL = "https://u3.shortink.io/register?utm_campaign=817094&utm_source=affiliate&utm_medium=sr&a=6uw2UJ3XfkHJR8&ac=nikita"
SUPPORT_URL = "https://youtu.be/4xU63QT-jVY"
# CHANNEL_URL = "https://youtu.be/4xU63QT-jVY"

# --- 🖼️ КАРТИНКИ ---
IMAGES = {
    "main_menu": "https://i.ibb.co/ks2XGqv9/4dfe73c9-8ba6-405a-a875-ad0fb73b6cd1.png",
    "about": "https://i.ibb.co/whqtDdrt/9616dc74-bca7-4f78-95b4-1780d161a783.png",
    "stats": "https://i.ibb.co/8LHck6YQ/Generated-Image-January-27-2026-4-06-AM.jpg",
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

# --- FSM STATES ---
class LanguageStates(StatesGroup):
    choosing_language = State()

# --- МНОГОЯЗЫЧНОСТЬ ---
LANGUAGES = {
    "ru": {
        "choose_language": "🌍 Выберите язык / Choose language:",
        "language_changed": "✅ Язык изменен на русский",
        "disclaimer": (
            "\n\n⚠️ <b>Дисклеймер:</b> Данный бот — образовательный инструмент "
            "для изучения технического анализа, а не финансовый советник. "
            "Торговля сопряжена с риском полной потери капитала. "
            "Все решения принимаются пользователем самостоятельно."
        ),
        "main_menu": (
            "👋 <b>Добро пожаловать в CAESAR Chart Analyzer</b>\n\n"
            "Образовательный инструмент для изучения технического анализа торговых графиков.\n\n"
            "⚡ <b>Функции обучения:</b>\n"
            "• Визуализация технических индикаторов\n"
            "• Примеры анализа волатильности\n"
            "• Демонстрация данных рынка\n\n"
            "👇 <i>Используйте меню для изучения:</i>"
        ),
        "about": (
            "🧠 <b>О платформе CAESAR</b>\n\n"
            "CAESAR — образовательная платформа для изучения технического анализа. "
            "Мы используем данные с TradingView и других открытых источников "
            "для демонстрации работы индикаторов.\n\n"
            "Это учебный инструмент. Мы не даем торговых рекомендаций, "
            "не обещаем прибыль и не управляем средствами пользователей.\n\n"
            "<i>Используйте для образовательных целей и изучения рынка.</i>"
        ),
        "stats": (
            "📊 <b>О платформе</b>\n\n"
            "CAESAR помогает пользователям изучать технический анализ "
            "на примере тысяч графиков и индикаторов.\n\n"
            "<i>Это образовательный проект для изучения рынков.</i>"
        ),
        "btn_about": "🧠 О платформе",
        "btn_stats": "📊 Информация",
        "btn_support": "💬 Инструкция",
        "btn_language": "🌍 Язык",
        "btn_open_demo": "🚀 Открыть демо-интерфейс",
        "btn_back": "🔙 В главное меню",
        "demo_info": (
            "🎓 <b>Демонстрационный интерфейс</b>\n\n"
            "Откройте Trading HUD для изучения интерфейса анализа графиков.\n\n"
            "Это демонстрационная версия для ознакомления с возможностями "
            "технического анализа.\n\n"
            "<i>Для образовательных целей.</i>"
        ),
    },
    "en": {
        "choose_language": "🌍 Choose language / Выберите язык:",
        "language_changed": "✅ Language changed to English",
        "disclaimer": (
            "\n\n⚠️ <b>Disclaimer:</b> This bot is an educational tool "
            "for learning technical analysis, not a financial advisor. "
            "Trading involves risk of complete capital loss. "
            "All decisions are made by the user independently."
        ),
        "main_menu": (
            "👋 <b>Welcome to CAESAR Chart Analyzer</b>\n\n"
            "Educational tool for learning technical analysis of trading charts.\n\n"
            "⚡ <b>Learning features:</b>\n"
            "• Technical indicator visualization\n"
            "• Volatility analysis examples\n"
            "• Market data demonstration\n\n"
            "👇 <i>Use the menu to learn:</i>"
        ),
        "about": (
            "🧠 <b>About CAESAR Platform</b>\n\n"
            "CAESAR is an educational platform for learning technical analysis. "
            "We use data from TradingView and other open sources "
            "to demonstrate how indicators work.\n\n"
            "This is an educational tool. We do not give trading recommendations, "
            "promise profits, or manage user funds.\n\n"
            "<i>Use for educational purposes and market study.</i>"
        ),
        "stats": (
            "📊 <b>About Platform</b>\n\n"
            "CAESAR helps users learn technical analysis "
            "using thousands of charts and indicators as examples.\n\n"
            "<i>This is an educational project for market study.</i>"
        ),
        "btn_about": "🧠 About Platform",
        "btn_stats": "📊 Information",
        "btn_support": "💬 Support",
        "btn_language": "🌍 Language",
        "btn_open_demo": "🚀 Open Demo Interface",
        "btn_back": "🔙 Main Menu",
        "demo_info": (
            "🎓 <b>Demo Interface</b>\n\n"
            "Open Trading HUD to explore the chart analysis interface.\n\n"
            "This is a demo version to familiarize yourself with "
            "technical analysis capabilities.\n\n"
            "<i>For educational purposes.</i>"
        ),
    }
}

# --- HELPER FUNCTIONS ---
async def get_user_language(state: FSMContext) -> str:
    """Получить язык пользователя из state"""
    data = await state.get_data()
    return data.get("language", "ru")

def get_text(lang: str, key: str, *args) -> str:
    """Получить текст на нужном языке"""
    text = LANGUAGES.get(lang, LANGUAGES["ru"]).get(key, key)
    if args:
        text = text.format(*args)
    # Добавляем дисклеймер к основным текстам
    if key in ["main_menu", "about", "stats"]:
        text += LANGUAGES[lang]["disclaimer"]
    return text

# --- ⌨️ КЛАВИАТУРЫ ---

def get_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    """⚠️ УПРОЩЕННОЕ МЕНЮ ДЛЯ МОДЕРАЦИИ - без канала и обучения"""
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_about"), callback_data="about_ai")],
        [InlineKeyboardButton(text=get_text(lang, "btn_stats"), callback_data="show_stats"),
         InlineKeyboardButton(text=get_text(lang, "btn_support"), url=SUPPORT_URL)],
        [InlineKeyboardButton(text=get_text(lang, "btn_language"), callback_data="change_language")],
        [InlineKeyboardButton(text=get_text(lang, "btn_open_demo"), callback_data="open_demo")]
    ])
    return builder

def get_back_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_back"), callback_data="back_to_main")]
    ])

def get_demo_keyboard(lang: str) -> InlineKeyboardMarkup:
    """⚠️ ПРЯМОЙ ДОСТУП К HUD - без проверки ID"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_open_demo"), web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text=get_text(lang, "btn_back"), callback_data="back_to_main")]
    ])

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    # Всегда показываем выбор языка при /start
    await message.answer(
        LANGUAGES["ru"]["choose_language"],
        reply_markup=get_language_keyboard()
    )
    await state.set_state(LanguageStates.choosing_language)

# --- ВЫБОР ЯЗЫКА ---

@dp.callback_query(F.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    
    # Сохраняем язык в state
    await state.update_data(language=lang)
    await callback.answer(get_text(lang, "language_changed"), show_alert=True)
    
    # Показываем главное меню
    await callback.message.delete()
    
    try:
        await callback.message.answer_photo(
            photo=IMAGES["main_menu"],
            caption=get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang)
        )
    except:
        await callback.message.answer(
            get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang)
        )
    
    await state.clear()
    await state.update_data(language=lang)

@dp.callback_query(F.data == "change_language")
async def change_language(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(state)
    await callback.message.answer(
        get_text(lang, "choose_language"),
        reply_markup=get_language_keyboard()
    )
    await state.set_state(LanguageStates.choosing_language)

# --- МЕНЮ НАВИГАЦИИ ---

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(state)
    
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["main_menu"],
            caption=get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang)
        )
    except:
        await callback.message.answer(
            get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang)
        )

@dp.callback_query(F.data == "about_ai")
async def show_about(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(state)
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["about"],
            caption=get_text(lang, "about"),
            parse_mode="HTML",
            reply_markup=get_back_kb(lang)
        )
    except:
        await callback.message.answer(
            get_text(lang, "about"),
            parse_mode="HTML",
            reply_markup=get_back_kb(lang)
        )

@dp.callback_query(F.data == "show_stats")
async def show_stats(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(state)
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["stats"],
            caption=get_text(lang, "stats"),
            parse_mode="HTML",
            reply_markup=get_back_kb(lang)
        )
    except:
        await callback.message.answer(
            get_text(lang, "stats"),
            parse_mode="HTML",
            reply_markup=get_back_kb(lang)
        )

# --- ДЕМО HUD (БЕЗ ПРОВЕРКИ ID) ---

@dp.callback_query(F.data == "open_demo")
async def open_demo(callback: CallbackQuery, state: FSMContext):
    """⚠️ ДЛЯ МОДЕРАЦИИ: прямой доступ к HUD без проверки"""
    lang = await get_user_language(state)
    
    await callback.message.answer(
        get_text(lang, "demo_info"),
        parse_mode="HTML",
        reply_markup=get_demo_keyboard(lang)
    )

# --- TELETHON (оставляем, но не используем) ---

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
    
    print("🚀 CAESAR AI BOT STARTED (MODERATION VERSION)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
