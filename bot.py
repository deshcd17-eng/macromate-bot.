import logging
import sqlite3
import datetime
import os
import base64
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook

API_TOKEN = '8804977127:AAESHqGKfjEQQ3gNTa6tkclfYXlzF1TRlpQ'
GEMINI_API_KEY = 'AIzaSyBsUUmLtihYMDxLRBsTPNX9N0KqFI0NKuc'

# 🌐 Render-ის ვებჰუკის პარამეტრები
# WEBHOOK_HOST-ს ავტომატურად ავიღებთ Render-ის გარემოს ცვლადებიდან
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST', '')  
WEBHOOK_PATH = f'/webhook/{API_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.environ.get('PORT', 5000))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'macromate.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            weight REAL,
            goal_weight REAL,
            daily_calories_goal INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            calories INTEGER DEFAULT 0,
            protein INTEGER DEFAULT 0,
            water INTEGER DEFAULT 0
        )
    ''')
    try:
        cursor.execute('ALTER TABLE daily_log ADD COLUMN water INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def update_daily_metric(user_id, date, calories=0, protein=0, water=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, calories, protein, water FROM daily_log WHERE user_id = ? AND date = ?', (user_id, date))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute('INSERT INTO daily_log (user_id, date, calories, protein, water) VALUES (?, ?, ?, ?, ?)',
                       (user_id, date, calories, protein, water))
    else:
        current_cal = row[1] if row[1] is not None else 0
        current_prot = row[2] if row[2] is not None else 0
        current_water = row[3] if row[3] is not None else 0
        
        cursor.execute('UPDATE daily_log SET calories = ?, protein = ?, water = ? WHERE id = ?',
                       (current_cal + calories, current_prot + protein, current_water + water, row[0]))
    conn.commit()
    conn.close()

# --- მენიუები ---
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton('📊 ჩემი პროგრესი'), KeyboardButton('🍎 კალორიის დამატება'))
main_menu.add(KeyboardButton('💧 წყლის დამატება'), KeyboardButton('💡 სპორტული გზამკვლევი'))
main_menu.add(KeyboardButton('⚙️ მიზნის დაყენება'))

water_menu = InlineKeyboardMarkup(row_width=3)
water_menu.add(
    InlineKeyboardButton('+250 მლ', callback_data='w_250'),
    InlineKeyboardButton('+500 მლ', callback_data='w_500'),
    InlineKeyboardButton('+1000 მლ', callback_data='w_1000')
)

tips_menu = InlineKeyboardMarkup(row_width=1)
tips_menu.add(
    InlineKeyboardButton('🧪 კრეატინი: ოპტიმალური სატურაცია', callback_data='t_creatine'),
    InlineKeyboardButton('🥩 ცილის ბალანსი კლებისას', callback_data='t_protein'),
    InlineKeyboardButton('🔥 ცხიმის წვა vs კუნთის შენარჩუნება', callback_data='t_fatloss')
)

# --- ჰენდლერები ---
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (user_id, weight, goal_weight, daily_calories_goal) VALUES (?, ?, ?, ?)', 
                       (user_id, 80.0, 75.0, 2000))
        conn.commit()
    conn.close()

    welcome_text = (
        f"მოგესალმება MacroMate, {message.from_user.first_name}! 🚀\n\n"
        "ეს არის შენი ციფრული ასისტენტი სხეულის რეკომპოზიციისთვის.\n\n"
        "⚙️ **მთავარი ფუნქციონალი:**\n"
        "• **📸 AI ფოტო ანალიზი:** უბრალოდ გადაუღე საჭმელს/სასმელს სურათი და ბოტი რეალურად შეაფასებს მას!\n"
        "• **💧 წყლის თრექერი:** კრეატინის ეფექტურობისთვის წყლის კონტროლი კრიტიკულია.\n"
        "• **📊 ანალიტიკა:** ზუსტი ინფორმაცია შენს დღიურ დეფიციტსა და პროტეინზე."
    )
    await message.answer(welcome_text, reply_markup=main_menu)

@dp.message_handler(lambda message: message.text == '💧 წყლის დამატება')
async def ask_water(message: types.Message):
    await message.answer("აირჩიე მიღებული წყლის ზუსტი მოცულობა:", reply_markup=water_menu)

@dp.message_handler(lambda message: message.text == '⚙️ მიზნის დაყენება')
async def set_goal(message: types.Message):
    await message.answer("დღიური კალორიების კორექტირებისთვის გამოიყენე სპეციალური ბრძანება:\n\n`მიზანი 1800` (ან ნებისმიერი შენი ციფრი)", parse_mode='Markdown')

@dp.message_handler(lambda message: message.text.startswith('მიზანი '))
async def update_goal(message: types.Message):
    try:
        new_goal = int(message.text.split()[1])
        user_id = message.from_user.id
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET daily_calories_goal = ? WHERE user_id = ?', (new_goal, user_id))
        conn.commit()
        conn.close()
        await message.answer(f"🎯 მიზნობრივი მაჩვენებელი განახლდა: **{new_goal} კალორია / დღეში**.", parse_mode='Markdown')
    except Exception:
        await message.answer("ფორმატი არასწორია. შეიყვანე სტრუქტურულად, მაგალითად: `მიზანი 2100`")

@dp.message_handler(lambda message: message.text == '📊 ჩემი პროგრესი')
async def show_progress(message: types.Message):
    user_id = message.from_user.id
    today = datetime.date.today().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(calories), SUM(protein), SUM(water) FROM daily_log WHERE user_id = ? AND date = ?', (user_id, today))
    result = cursor.fetchone()
    
    total_cal = result[0] if result[0] else 0
    total_prot = result[1] if result[1] else 0
    total_water = result[2] if result[2] else 0
    
    cursor.execute('SELECT daily_calories_goal FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    goal_cal = user_data[0] if user_data else 2000
    conn.close()
    
    remaining_cal = goal_cal - total_cal
    if remaining_cal >= 0:
        status_text = f"🎯 მიზნამდე დარჩენილია: **{remaining_cal} კალ**"
    else:
        status_text = f"⚠️ ენერგეტიკულ ლიმიტს გადააჭარბე: **{abs(remaining_cal)} კალორიით**"

    progress_text = (
        f"📊 **დღიური ბალანსის მონიტორინგი ({today}):**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🍎 კალორიები: `{total_cal}` / `{goal_cal}` კალ\n"
        f"🥩 ცილა (Protein): `{total_prot} გრ` (მიზანი: ~1.6-2გ კგ-ზე)\n"
        f"💧 ჰიდრატაცია: `{total_water} მლ` / `3000 მლ`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_text}"
    )
    await message.answer(progress_text, parse_mode='Markdown')

# --- 🔥 რეალური AI ფოტო ანალიზი Gemini-ს მეშვეობით ---
@dp.message_handler(content_types=['photo'])
async def handle_food_photo(message: types.Message):
    status_msg = await message.answer("🔄 მიმდინარეობს გამოსახულების სკანირება ნამდვილი AI მოდულით... გთხოვთ დაელოდოთ.")
    
    photo = message.photo[-1]
    photo_path = os.path.join(BASE_DIR, f"user_{message.from_user.id}_food.jpg")
    await photo.download(destination_file=photo_path)
    
    try:
        with open(photo_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
        gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        prompt = (
            "Identify the food or drink item in this image. Respond strictly in Georgian language. "
            "Estimate total calories and protein in grams. Format your answer EXACTLY like this template, "
            "do not add any markdown bolding to the numbers themselves, just keep the exact structure:\n\n"
            "📸 **ინტელექტუალური ანალიზის შედეგი:**\n\n"
            "🥗 იდენტიფიცირებული საკვები: [Write item name in Georgian]\n"
            "🔥 სავარაუდო ენერგეტიკული ღირებულება: ~[Write only number] კალ\n"
            "🥩 მაკრონუტრიენტი (ცილა): ~[Write only number] გრ\n\n"
            "📝 მონაცემების დღიურ პროგრესში ავტომატურად დასამატებლად, უბრალოდ გამოგვიგზავნე ეს ციფრები ასე: [Number] [Number]"
        )
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/jpeg", "data": img_base64}}
                ]
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(gemini_url, json=payload) as response:
                result = await response.json()
                
                if 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown API Error')
                    await status_msg.edit_text(f"❌ Google Gemini API შეცდომა:\n`{error_msg}`", parse_mode='Markdown')
                    return
                    
                ai_response = result['candidates'][0]['content']['parts'][0]['text']
                
        await status_msg.delete()
        await message.answer(ai_response, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"AI Error: {e}")
        await status_msg.edit_text(f"❌ სისტემური კოდის შეცდომა:\n`{str(e)}`", parse_mode='Markdown')
        
    if os.path.exists(photo_path):
        os.remove(photo_path)

@dp.message_handler(lambda message: message.text.replace(' ', '').isdigit())
async def log_macros(message: types.Message):
    user_id = message.from_user.id
    data = message.text.split()
    calories = int(data[0])
    protein = int(data[1]) if len(data) > 1 else 0
    today = datetime.date.today().isoformat()
    
    update_daily_metric(user_id, today, calories=calories, protein=protein)
    await message.answer(f"✅ პროგრესში დაემატა: +{calories} კალორია და +{protein}გ ცილა.")

@dp.callback_query_handler(lambda c: c.data.startswith('w_') or c.data.startswith('t_'))
async def process_callbacks(callback_query: types.CallbackQuery):
    code = callback_query.data
    user_id = callback_query.from_user.id
    today = datetime.date.today().isoformat()
    
    if code.startswith('w_'):
        amount = int(code.split('_')[1])
        update_daily_metric(user_id, today, water=amount)
        await callback_query.answer(f"დაემატა {amount} მლ წყალი! 💧")
        await bot.send_message(user_id, f"✅ დღიურ ჰიდრატაციას დაემატა +{amount} მლ წყალი.")
        
    elif code == 't_creatine':
        await callback_query.answer()
        text = (
            "🧪 **კრეატინის მეცნიერული პროტოკოლი:**\n\n"
            "• **ოპტიმალური დოზა:** 3-5 გრამი ყოველდღიურად (ჩატვირთვის ფაზა საჭირო არ არის).\n"
            "• **მექანიზმი:** კრეატინი ზრდის კუნთში ფოსფოკრეატინის მარაგებს (ATP რესინთეზი) და იწვევს წყლის შეკავებას უჯჯრედშიდა დონეზე (უჯრედის ვოლუმიზაცია).\n"
            "• **ჰიდრატაცია:** რადგან კრეატინს წყალი კუნთოვან ქსოვილში გადააქვს, დეჰიდრატაციის თავიდან ასაცილებლად აუცილებელია მინიმუმ 3-3.5 ლიტრი წყლის მიღება."
        )
        await bot.send_message(user_id, text)
        
    elif code == 't_protein':
        await callback_query.answer()
        text = (
            "🥩 **ცილის სინთეზი და კუნთის დაცვა:**\n\n"
            "• **ნორმა:** მჭლე მასის (Lean Mass) შესანარჩუნებლად ცილის მიღება უნდა აიწიოს **1.6 - 2.2 გრამამდე** სხეულის ყოველ კილოგრამზე.\n"
            "• **სტრატეგია:** პრიორიტეტი მიანიჭე მაღალი ბიოლოგიური ღირებულების მქონე ცილებს (ქათამი, საქონელი, კვერცხი, თევზი)."
        )
        await bot.send_message(user_id, text)
        
    elif code == 't_fatloss':
        await callback_query.answer()
        text = (
            "🔥 **რეკომპოზიცია: ცხიმის კლება კუნთის დაკარგვის გარეშე:**\n\n"
            "• **ილუზია სასწორზე:** კრეატინის მიღების დაწყებისას სასწორზე წონა შეიძლება გაიზარდოს 1-2 კგ-ით. ეს წყალია და არა ცხიმი!\n"
            "• **დეფიციტი:** კლებისთვის ოპტიმალურია მცირე დეფიციტი (300-500 კალორია მიზნობრივი ნორმიდან)."
        )
        await bot.send_message(user_id, text)

@dp.message_handler(lambda message: message.text == '💡 სპორტული გზამკვლევი')
async def show_tips(message: types.Message):
    await message.answer("აირჩიე სპორტული მეცნიერების თემატიკა სიღრმისეული ანალიზისთვის:", reply_markup=tips_menu)

@dp.message_handler(lambda message: message.text == '🍎 კალორიის დამატება')
async def ask_calories(message: types.Message):
    await message.answer("შეიყვანე მიღებული საკვების კალორია და ცილა გამოტოვებით.\n\nმაგალითად: `450 30` (450 კალორია და 30გ ცილა)")

# --- 🚀 ვებჰუკის სტარტაპ ლოგიკა ---
async def on_startup(dp):
    logging.info(f"Setting webhook to: {WEBHOOK_URL}")
    init_db()
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    logging.warning('Shutting down..')
    await bot.delete_webhook()
    logging.warning('Bye!')

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
