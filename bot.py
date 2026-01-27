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
CHANNEL_URL = "https://t.me/+DbXojk7ubdE5OGI6"

# --- 🖼️ КАРТИНКИ ---
IMAGES = {
    "main_menu": "https://i.ibb.co/ks2XGqv9/4dfe73c9-8ba6-405a-a875-ad0fb73b6cd1.png",
    "about": "https://i.ibb.co/whqtDdrt/9616dc74-bca7-4f78-95b4-1780d161a783.png",
    "stats": "https://i.ibb.co/8LHck6YQ/Generated-Image-January-27-2026-4-06-AM.jpg",
    "connect": "https://i.ibb.co/DDKjd57C/Generated-Image-January-27-2026-3-53-AM.jpg",
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
class ValidationStates(StatesGroup):
    waiting_for_id = State()

class LanguageStates(StatesGroup):
    choosing_language = State()

# --- МНОГОЯЗЫЧНОСТЬ ---
LANGUAGES = {
    "ru": {
        "choose_language": "🌍 Выберите язык / Choose language:",
        "language_changed": "✅ Язык изменен на русский",
        "disclaimer": (
            "\n\n⚠️ <b>Дисклеймер:</b> Данный бот — информационный инструмент, "
            "а не финансовый советник. Торговля сопряжена с риском полной потери капитала. "
            "Все решения принимаются пользователем самостоятельно."
        ),
        "main_menu": (
            "👋 <b>Добро пожаловать в CAESAR Chart Analyzer</b>\n\n"
            "Инструмент для технического анализа торговых графиков.\n\n"
            "⚡ <b>Возможности:</b>\n"
            "• Анализ технических индикаторов\n"
            "• Отслеживание волатильности\n"
            "• Визуализация данных рынка\n\n"
            "👇 <i>Используйте меню для навигации:</i>"
        ),
        "about": (
            "🧠 <b>О технологии CAESAR</b>\n\n"
            "CAESAR — инструмент технического анализа, использующий данные "
            "с TradingView и других открытых источников рыночной информации.\n\n"
            "Мы предоставляем информацию для анализа, но не даем торговых рекомендаций или гарантий.\n\n"
            "<i>Результаты зависят от рыночных условий и решений пользователя.</i>"
        ),
        "stats": (
            "📊 <b>Статистика использования</b>\n\n"
            "Ежемесячно обрабатываем тысячи графиков и технических индикаторов.\n\n"
            "<i>Детальная статистика доступна в интерфейсе Trading HUD.</i>"
        ),
        "connect": (
            "🔓 <b>Подключение учетной записи</b>\n\n"
            "Для доступа к функциям необходима регистрация на торговой платформе.\n\n"
            "1. Зарегистрируйтесь на платформе (для API доступа к котировкам)\n"
            "2. Отправьте ваш <b>цифровой ID</b> в ответ на это сообщение\n\n"
            "<b>Важно:</b> Мы не управляем вашими средствами и не имеем доступа к балансу."
        ),
        "btn_about": "🧠 О технологии CAESAR",
        "btn_stats": "📊 Статистика",
        "btn_channel": "📢 Наш канал",
        "btn_education": "🎓 Обучение",
        "btn_support": "💬 Поддержка",
        "btn_language": "🌍 Язык",
        "btn_start": "🚀 ЗАПУСТИТЬ HUD",
        "btn_connect": "🔗 ПОДКЛЮЧИТЬ CAESAR",
        "btn_back": "🔙 В главное меню",
        "btn_open_hud": "🚀 Открыть Trading HUD",
        "btn_menu": "🔙 Меню",
        "btn_deposit_check": "✅ Я пополнил баланс",
        "btn_cancel": "🔙 Отмена",
        "btn_register": "📝 Создать профиль",
        "btn_retry": "🔄 Ввести ID заново",
        "education_text": "🎓 <b>Обучение CAESAR</b>\n\nРекомендуем ознакомиться с материалами в нашем канале:",
        "access_granted": "✅ <b>Доступ разрешен</b>\nCAESAR Chart Analyzer готов к работе.",
        "enter_id": "✍️ Введите ваш ID (только цифры):",
        "id_error": "❌ ID должен состоять только из цифр.",
        "syncing": "🔄 <i>Синхронизация с сервером...</i>",
        "verified": "✅ <b>CAESAR подключен!</b>\nID: {}\nДоступ активирован.",
        "waiting_deposit": (
            "⚠️ <b>Ожидание активации</b>\n\n"
            "Аккаунт ID: {} найден.\n"
            "Для завершения настройки необходимо пополнить баланс на платформе.\n\n"
            "<i>Нажмите кнопку ниже после пополнения:</i>"
        ),
        "id_not_found": (
            "❌ <b>ID {} не найден</b>\n"
            "Убедитесь, что регистрация прошла успешно."
        ),
        "session_expired": "⚠️ Сессия истекла. Введите ID заново.",
        "checking": "🔄 Проверяю данные...",
        "deposit_confirmed": "✅ <b>Депозит подтвержден!</b>\nДоступ к HUD открыт.",
        "deposit_not_found": "❌ Данные о депозите еще не поступили. Попробуйте через минуту.",
    },
    "en": {
        "choose_language": "🌍 Choose language / Выберите язык:",
        "language_changed": "✅ Language changed to English",
        "disclaimer": (
            "\n\n⚠️ <b>Disclaimer:</b> This bot is an informational tool, "
            "not a financial advisor. Trading involves risk of complete capital loss. "
            "All decisions are made by the user independently."
        ),
        "main_menu": (
            "👋 <b>Welcome to CAESAR Chart Analyzer</b>\n\n"
            "A tool for technical analysis of trading charts.\n\n"
            "⚡ <b>Features:</b>\n"
            "• Technical indicator analysis\n"
            "• Volatility tracking\n"
            "• Market data visualization\n\n"
            "👇 <i>Use the menu to navigate:</i>"
        ),
        "about": (
            "🧠 <b>About CAESAR Technology</b>\n\n"
            "CAESAR is a technical analysis tool using data from "
            "TradingView and other open market information sources.\n\n"
            "We provide information for analysis but do not give trading recommendations or guarantees.\n\n"
            "<i>Results depend on market conditions and user decisions.</i>"
        ),
        "stats": (
            "📊 <b>Usage Statistics</b>\n\n"
            "We process thousands of charts and technical indicators monthly.\n\n"
            "<i>Detailed statistics are available in the Trading HUD interface.</i>"
        ),
        "connect": (
            "🔓 <b>Account Connection</b>\n\n"
            "Registration on the trading platform is required to access features.\n\n"
            "1. Register on the platform (for API access to quotes)\n"
            "2. Send your <b>digital ID</b> in response to this message\n\n"
            "<b>Important:</b> We do not manage your funds and have no access to your balance."
        ),
        "btn_about": "🧠 About CAESAR",
        "btn_stats": "📊 Statistics",
        "btn_channel": "📢 Our Channel",
        "btn_education": "🎓 Education",
        "btn_support": "💬 Support",
        "btn_language": "🌍 Language",
        "btn_start": "🚀 LAUNCH HUD",
        "btn_connect": "🔗 CONNECT CAESAR",
        "btn_back": "🔙 Main Menu",
        "btn_open_hud": "🚀 Open Trading HUD",
        "btn_menu": "🔙 Menu",
        "btn_deposit_check": "✅ I made a deposit",
        "btn_cancel": "🔙 Cancel",
        "btn_register": "📝 Create Profile",
        "btn_retry": "🔄 Re-enter ID",
        "education_text": "🎓 <b>CAESAR Education</b>\n\nWe recommend checking out materials in our channel:",
        "access_granted": "✅ <b>Access Granted</b>\nCAESAR Chart Analyzer is ready.",
        "enter_id": "✍️ Enter your ID (numbers only):",
        "id_error": "❌ ID must contain only digits.",
        "syncing": "🔄 <i>Syncing with server...</i>",
        "verified": "✅ <b>CAESAR Connected!</b>\nID: {}\nAccess activated.",
        "waiting_deposit": (
            "⚠️ <b>Waiting for Activation</b>\n\n"
            "Account ID: {} found.\n"
            "To complete setup, deposit is required on the platform.\n\n"
            "<i>Click the button below after depositing:</i>"
        ),
        "id_not_found": (
            "❌ <b>ID {} not found</b>\n"
            "Make sure registration was successful."
        ),
        "session_expired": "⚠️ Session expired. Enter ID again.",
        "checking": "🔄 Checking data...",
        "deposit_confirmed": "✅ <b>Deposit Confirmed!</b>\nHUD access granted.",
        "deposit_not_found": "❌ Deposit data not received yet. Try again in a minute.",
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
    if key in ["main_menu", "about", "stats", "connect"]:
        text += LANGUAGES[lang]["disclaimer"]
    return text

# --- ⌨️ КЛАВИАТУРЫ ---

def get_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_main_menu_kb(lang: str, is_verified: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_about"), callback_data="about_ai")],
        [InlineKeyboardButton(text=get_text(lang, "btn_stats"), callback_data="show_stats"),
         InlineKeyboardButton(text=get_text(lang, "btn_channel"), url=CHANNEL_URL)],
        [InlineKeyboardButton(text=get_text(lang, "btn_education"), callback_data="education"),
         InlineKeyboardButton(text=get_text(lang, "btn_support"), url=SUPPORT_URL)],
        [InlineKeyboardButton(text=get_text(lang, "btn_language"), callback_data="change_language")],
        [InlineKeyboardButton(
            text=get_text(lang, "btn_start") if is_verified else get_text(lang, "btn_connect"),
            callback_data="start_flow"
        )]
    ])
    return builder

def get_back_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_back"), callback_data="back_to_main")]
    ])

def get_launch_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_open_hud"), web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text=get_text(lang, "btn_channel"), url=CHANNEL_URL)],
        [InlineKeyboardButton(text=get_text(lang, "btn_menu"), callback_data="back_to_main")]
    ])

def get_deposit_check_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_deposit_check"), callback_data="check_deposit_again")],
        [InlineKeyboardButton(text=get_text(lang, "btn_cancel"), callback_data="back_to_main")]
    ])

def get_registration_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(lang, "btn_register"), url=REGISTRATION_URL)],
        [InlineKeyboardButton(text=get_text(lang, "btn_retry"), callback_data="retry_id")],
        [InlineKeyboardButton(text=get_text(lang, "btn_menu"), callback_data="back_to_main")]
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
    tg_id = callback.from_user.id
    is_verified = await db.is_user_verified(tg_id)
    await callback.message.delete()
    
    try:
        await callback.message.answer_photo(
            photo=IMAGES["main_menu"],
            caption=get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang, is_verified)
        )
    except:
        await callback.message.answer(
            get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang, is_verified)
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
    tg_id = callback.from_user.id
    lang = await get_user_language(state)
    is_verified = await db.is_user_verified(tg_id)
    
    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["main_menu"],
            caption=get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang, is_verified)
        )
    except:
        await callback.message.answer(
            get_text(lang, "main_menu"),
            parse_mode="HTML",
            reply_markup=get_main_menu_kb(lang, is_verified)
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

@dp.callback_query(F.data == "education")
async def show_education(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(state)
    await callback.answer("📚", show_alert=False)
    await callback.message.answer(
        get_text(lang, "education_text"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "btn_channel"), url=CHANNEL_URL)],
            [InlineKeyboardButton(text=get_text(lang, "btn_back"), callback_data="back_to_main")]
        ]),
        parse_mode="HTML"
    )

# --- ЛОГИКА ПОДКЛЮЧЕНИЯ (ВОРОНКА) ---

@dp.callback_query(F.data == "start_flow")
async def start_flow(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    lang = await get_user_language(state)
    
    if await db.is_user_verified(tg_id):
        await callback.message.delete()
        await callback.message.answer(
            get_text(lang, "access_granted"),
            parse_mode="HTML",
            reply_markup=get_launch_keyboard(lang)
        )
        return

    await callback.message.delete()
    try:
        await callback.message.answer_photo(
            photo=IMAGES["connect"],
            caption=get_text(lang, "connect"),
            parse_mode="HTML",
            reply_markup=get_registration_keyboard(lang)
        )
    except:
        await callback.message.answer(
            get_text(lang, "connect"),
            parse_mode="HTML",
            reply_markup=get_registration_keyboard(lang)
        )
    
    await state.set_state(ValidationStates.waiting_for_id)

@dp.callback_query(F.data == "retry_id")
async def retry_id_handler(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(state)
    await callback.message.answer(get_text(lang, "enter_id"))
    await state.set_state(ValidationStates.waiting_for_id)

# --- ОБРАБОТКА ID ---

@dp.message(ValidationStates.waiting_for_id)
async def process_pocket_id(message: Message, state: FSMContext):
    user_input = message.text.strip()
    lang = await get_user_language(state)
    
    if user_input.startswith("/"):
        return

    if not user_input.isdigit():
        await message.answer(get_text(lang, "id_error"))
        return

    pocket_id = user_input
    tg_id = message.from_user.id
    status_msg = await message.answer(get_text(lang, "syncing"), parse_mode="HTML")
    
    await asyncio.sleep(1.5)

    is_found, is_deposit = await deep_search_channel(pocket_id)
    
    if is_found:
        if is_deposit:
            await db.add_to_cache(pocket_id) 
            await db.verify_user(tg_id, pocket_id)
            
            await status_msg.edit_text(
                get_text(lang, "verified", pocket_id),
                parse_mode="HTML",
                reply_markup=get_launch_keyboard(lang)
            )
        else:
            await state.update_data(current_id=pocket_id)
            
            await status_msg.edit_text(
                get_text(lang, "waiting_deposit", pocket_id),
                parse_mode="HTML",
                reply_markup=get_deposit_check_keyboard(lang)
            )
    else:
        await status_msg.edit_text(
            get_text(lang, "id_not_found", pocket_id),
            parse_mode="HTML",
            reply_markup=get_registration_keyboard(lang)
        )

@dp.callback_query(F.data == "check_deposit_again")
async def check_deposit_again(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pocket_id = data.get("current_id")
    lang = await get_user_language(state)
    
    if not pocket_id:
        await callback.message.answer(get_text(lang, "session_expired"))
        await state.set_state(ValidationStates.waiting_for_id)
        return

    await callback.answer(get_text(lang, "checking"), show_alert=False)
    
    is_found, is_deposit = await deep_search_channel(pocket_id)
    
    if is_deposit:
        tg_id = callback.from_user.id
        await db.verify_user(tg_id, pocket_id)
        
        await callback.message.edit_text(
            get_text(lang, "deposit_confirmed"),
            parse_mode="HTML",
            reply_markup=get_launch_keyboard(lang)
        )
    else:
        await callback.answer(get_text(lang, "deposit_not_found"), show_alert=True)

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
