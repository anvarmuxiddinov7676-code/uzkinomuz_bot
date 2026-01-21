import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import openai
import sqlite3

# --- SETUP ---
BOT_TOKEN = os.getenv("BOT_TOKEN")          # Telegram token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # OpenAI API key
openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- DATABASE ---
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    lang TEXT DEFAULT 'uz',
    premium INTEGER DEFAULT 0
)
""")
conn.commit()

def add_user(user_id, lang="uz"):
    cursor.execute("INSERT OR IGNORE INTO users(user_id, lang) VALUES (?,?)", (user_id, lang))
    conn.commit()

def is_premium(user_id):
    cursor.execute("SELECT premium FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return bool(row[0]) if row else False

def get_lang(user_id):
    cursor.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "uz"

def update_lang(user_id, lang):
    cursor.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
    conn.commit()

# --- FSM STATES ---
class MenuState(StatesGroup):
    waiting_for_text = State()
    waiting_for_lang = State()

# --- LANGUAGE SETUP ---
langs = {"uz":"O‘zbekcha","ru":"Русский","en":"English","tr":"Türkçe"}
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
for name in langs.values():
    lang_kb.add(KeyboardButton(name))

# --- HANDLERS ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = message.from_user.language_code
    if lang not in langs: lang="uz"
    add_user(user_id, lang)
    await message.answer("Salom! Kino, qo‘shiq yoki serial nomini yozing 🎬🎵\nTilni o‘zgartirish: /lang")
    await MenuState.waiting_for_text.set()

@dp.message_handler(commands=['lang'])
async def choose_lang(message: types.Message):
    await message.answer("Tilni tanlang:", reply_markup=lang_kb)
    await MenuState.waiting_for_lang.set()

@dp.message_handler(state=MenuState.waiting_for_lang)
async def set_lang(message: types.Message, state: FSMContext):
    for code,name in langs.items():
        if message.text == name:
            update_lang(message.from_user.id, code)
            await message.answer(f"Til {name} ga o‘zgartirildi.", reply_markup=None)
            await state.finish()
            return
    await message.answer("Iltimos, menyudan tanlang.")

@dp.message_handler(commands=['premium'])
async def premium_info(message: types.Message):
    await message.answer("Premium foydalanuvchi:\n- Premyera kinolar\n- Tanishuvlar yozish\n- Nick’lar ko‘rinadi\n\nAdmin orqali faollashtiriladi.")

@dp.message_handler(state=MenuState.waiting_for_text)
async def search_content(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_lang = get_lang(user_id)
    text = message.text.strip()

    # --- AI JAVOB ---
    try:
        prompt = f"Foydalanuvchi tilida javob ber: {user_lang}\nSavol: {text}"
        response = openai.ChatCompletion.create(
            model="gpt-4-mini",
            messages=[{"role":"user","content":prompt}],
            max_tokens=300
        )
        answer = response['choices'][0]['message']['content']
    except Exception as e:
        answer = "Hozir AI javob bera olmayapti 😢"

    # --- PREMIUM TEKSHIR ---
    if "premyera" in answer.lower() and not is_premium(user_id):
        await message.answer("Bu premyera kino. Premium uchun /premium")
    else:
        await message.answer(answer)

    await MenuState.waiting_for_text.set()

# --- START BOT ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
