import os
import logging
import io
import sqlite3
from PIL import Image
from aiogram import Bot, Dispatcher, executor, types
import google.generativeai as genai

# =====================================================================
# 1. სისტემური კონფიგურაცია და ლოგირება
# =====================================================================
logging.basicConfig(level=logging.INFO)

# ტოკენების წამოღება (Render Environment-დან ან პირდაპირ კოდიდან)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "აქ_ჩასვი_შენი_ტელეგრამ_ბოტის_ტოკენი")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "აქ_ჩასვი_შენი_ჯემინის_key")

# Render-ის ქსელური პარამეტრები ვებჰუკისთვის
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST", "https://macromate-bot-ku1o.onrender.com")
WEBHOOK_PATH = "/"  # მთავარი გზა "POST / 404" შეცდომის მოსახსნელად
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

DB_PATH = "macromate.db"

# ბოტის, დისპეტჩერისა და ჯემინის ინიციალიზაცია
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# =====================================================================
# 2. მონაცემთა ბაზის (SQLite) ლოგიკა
# =====================================================================
def init_db():
    """ქმნის ბაზას და ცხრილებს ავტომატურად, თუ ისინი არ არსებობს"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # მომხმარებლების ცხრილი
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # მესიჯების ისტორიის ცხრილი (სურვილისამებრ, ლოგებისთვის)
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
    logging.info("მონაცემთა ბაზა და ცხრილები წარმატებით შემოწმდა/შეიქმნა.")

def register_user(user_id, username, first_name):
    """არეგისტრირებს ახალ მომხმარებელს ბაზაში"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def log_interaction(user_id, msg_type, text):
    """ინახავს მიმოწერის ლოგს ბაზაში"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO message_logs (user_id, message_type, text_content) VALUES (?, ?, ?)',
        (user_id, msg_type, text)
    )
    conn.commit()
    conn.close()

# =====================================================================
# 3. ტელეგრამ ბოტის ბრძანებები (Commands Handlers)
# =====================================================================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    log_interaction(message.from_user.id, "command", "/start")
    
    welcome_text = (
        "🤖 **გამარჯობა! Macromate წარმატებით გაეშვა Render-ზე!** 🚀\n\n"
        "მე ვარ ინტელექტუალური ასისტენტი, რომელიც მუშაობს Google Gemini 1.5 Flash მოდელზე.\n\n"
        "📥 **რა შემიძლია:**\n"
        "• ვუპასუხო ნებისმიერ რთულ ტექსტურ შეკითხვას.\n"
        "• გავაანალიზო შენ მიერ გამოგზავნილი ფოტოები.\n\n"
        "გამომიგზავნე ნებისმიერი რამ და დავიწყოთ!"
    )
    await message.reply(welcome_text, parse_mode="Markdown")

@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    log_interaction(message.from_user.id, "command", "/help")
    help_text = (
        "💡 **როგორ გამოვიყენოთ ბოტი:**\n\n"
        "1. **ტექსტური რეჟიმი:** უბრალოდ მოწერე ნებისმიერი კითხვა (მაგ. კოდის დაწერა, თარგმნა, იდეები).\n"
        "2. **ფოტო რეჟიმი:** ატვირთე ფოტო და აღწერაში მიაწერე კითხვა (მაგ. 'რა არის ეს?', 'გადათარგმნე ტექსტი ფოტოდან')."
    )
    await message.reply(help_text, parse_mode="Markdown")

@dp.message_handler(commands=['stats'])
async def send_stats(message: types.Message):
    log_interaction(message.from_user.id, "command", "/stats")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        conn.close()
        
        await message.reply(f"📊 **ბოტის სტატისტიკა (Render ლაივში):**\n• აქტიური მომხმარებლები ბაზაში: {total_users}")
    except Exception as e:
        await message.reply(f"❌ სტატისტიკის წაკითხვის შეცდომა: {e}")

# =====================================================================
# 4. ძირითადი შეტყობინებების დამუშავება (Text & Photo Handlers)
# =====================================================================
@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    # მომხმარებლის და მესიჯის ბაზაში გატარება
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    log_interaction(message.from_user.id, "text", message.text)
    
    # ბოტი აჩვენებს, რომ ბეჭდავს (Typing...)
    await bot.send_chat_action(chat_id=message.chat.id, action=types.ChatActions.TYPING)
    
    try:
        response = model.generate_content(message.text)
        await message.reply(response.text)
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        await message.reply(f"❌ Gemini-ს შეცდომა: {e}\nსცადეთ ცოტა ხანში ხელახლა.")

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    # თუ ფოტოს გამოყოლებული აქვს ტექსტი, წამოვიღოთ, თუ არა - სტანდარტული ინსტრუქცია
    user_prompt = message.caption if message.caption else "გააანალიზე ეს ფოტო და აღწერე დეტალურად"
    log_interaction(message.from_user.id, "photo", user_prompt)
    
    await bot.send_chat_action(chat_id=message.chat.id, action=types.ChatActions.TYPING)
    
    try:
        # ყველაზე მაღალი ხარისხის ფოტოს არჩევა
        photo = message.photo[-1]
        photo_info = await bot.get_file(photo.file_id)
        
        # ფაილის გადმოწერა RAM-ში
        file_byte = await bot.download_file(photo_info.file_path)
        
        # PIL ფორმატში კონვერტაცია მულტიმოდალური Gemini-სთვის
        image = Image.open(io.BytesIO(file_byte.getvalue()))
        
        # მოთხოვნის გაგზავნა
        response = model.generate_content([image, user_prompt])
        await message.reply(response.text)
        
    except Exception as e:
        logging.error(f"Photo Processing Error: {e}")
        await message.reply(f"❌ ფოტოს დამუშავების შეცდომა: {e}")

# =====================================================================
# 5. ვებჰუკის მართვის სისტემა (Startup / Shutdown)
# =====================================================================
async def on_startup(dispatcher):
    # 1. პირველ რიგში ვქოქავთ მონაცემთა ბაზას
    init_db()
    # 2. ვუკავშირდებით ტელეგრამის ვებჰუკს
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"======> ბოტი ჩაირთო! ვებჰუკი დაყენდა: {WEBHOOK_URL} <======")

async def on_shutdown(dispatcher):
    # სერვერის გათიშვისას ვასუფთავებთ ვებჰუკს
    await bot.delete_webhook()
    logging.info("======> სერვერი გაითიშა, ვებჰუკი წაიშალა. <======")

if __name__ == '__main__':
    # ვებჰუკ სერვერის გაშვება შიდა პორტზე
    executor.start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host='0.0.0.0',
        port=PORT,
    )
