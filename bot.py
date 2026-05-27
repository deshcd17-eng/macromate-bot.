import os
import logging
import io
import sqlite3
from PIL import Image
from aiogram import Bot, Dispatcher, executor, types
# ვიყენებთ Google-ის ახალ, ოფიციალურ SDK-ს შეცდომების თავიდან ასაცილებლად
from google import genai

# =====================================================================
# 1. კონფიგურაცია
# =====================================================================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "აქ_ჩასვი_შენი_ტელეგრამ_ბოტის_ტოკენი")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "აქ_ჩასვი_შენი_ჯემინის_key")

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST", "https://macromate-bot-ku1o.onrender.com")
WEBHOOK_PATH = "/"  
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

DB_PATH = "macromate.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ახალი SDK-ს ინიციალიზაცია
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# =====================================================================
# 2. მონაცემთა ბაზა (SQLite)
# =====================================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_type TEXT,
            text_content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def register_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def log_interaction(user_id, msg_type, text):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO message_logs (user_id, message_type, text_content) VALUES (?, ?, ?)',
        (user_id, msg_type, text)
    )
    conn.commit()
    conn.close()

# =====================================================================
# 3. ბრძანებები
# =====================================================================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    log_interaction(message.from_user.id, "command", "/start")
    
    welcome_text = (
        "🤖 **Macromate წარმატებით მუშაობს Render-ზე!** 🚀\n\n"
        "გამომიგზავნე ნებისმიერი ტექსტი ან ფოტო ბლინების, მანქანების თუ კოდის შესახებ და უცებ გაგიანალიზებ!"
    )
    await message.reply(welcome_text, parse_mode="Markdown")

@dp.message_handler(commands=['stats'])
async def send_stats(message: types.Message):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        conn.close()
        await message.reply(f"📊 **ბოტის სტატისტიკა:**\n• მომხმარებლები ბაზაში: {total_users}")
    except Exception as e:
        await message.reply(f"❌ შეცდომა: {e}")

# =====================================================================
# 4. ტექსტისა და ფოტოების დამუშავება (Gemini 1.5 Flash)
# =====================================================================
@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    log_interaction(message.from_user.id, "text", message.text)
    
    await bot.send_chat_action(chat_id=message.chat.id, action=types.ChatActions.TYPING)
    
    try:
        # ახალი SDK სტრუქტურა მოდელისთვის
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=message.text,
        )
        await message.reply(response.text)
    except Exception as e:
        logging.error(f"Gemini Text Error: {e}")
        await message.reply(f"❌ Gemini-ს შეცდომა: {e}")

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    user_prompt = message.caption if message.caption else "აღწერე რა არის ამ ფოტოზე დეტალურად"
    log_interaction(message.from_user.id, "photo", user_prompt)
    
    await bot.send_chat_action(chat_id=message.chat.id, action=types.ChatActions.TYPING)
    
    try:
        photo = message.photo[-1]
        photo_info = await bot.get_file(photo.file_id)
        file_byte = await bot.download_file(photo_info.file_path)
        
        image = Image.open(io.BytesIO(file_byte.getvalue()))
        
        # ახალი SDK-ს მულტიმოდალური მოთხოვნა
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[image, user_prompt]
        )
        await message.reply(response.text)
        
    except Exception as e:
        logging.error(f"Gemini Photo Error: {e}")
        await message.reply(f"❌ ფოტოს დამუშავების შეცდომა: {e}")

# =====================================================================
# 5. ვებჰუკის მართვა
# =====================================================================
async def on_startup(dispatcher):
    init_db()
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"======> Webhook დაყენდა: {WEBHOOK_URL} <======")

async def on_shutdown(dispatcher):
    await bot.delete_webhook()
    logging.info("======> Webhook წაიშალა. <======")

if __name__ == '__main__':
    executor.start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host='0.0.0.0',
        port=PORT,
    )
