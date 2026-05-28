import logging
import os
import sqlite3
import io
from PIL import Image
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai

# კონფიგურაცია
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Gemini-ს კონფიგურაცია
genai.configure(api_key=GEMINI_API_KEY)
# ვიყენებთ სტანდარტულ მოდელს, რომელსაც Google ყველაზე მყარად უჭერს მხარს
model = genai.GenerativeModel('gemini-1.5-flash')

# მონაცემთა ბაზა (მომხმარებლების აღრიცხვა)
def init_db():
    conn = sqlite3.connect("macromate.db")
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

# მენიუ
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🥗 კალორიების ანალიზი", callback_data="calories_help"),
        InlineKeyboardButton("💡 რჩევები", callback_data="advice_help")
    )
    return markup

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    init_db()
    await message.answer(
        "👋 **გამარჯობა! მე ვარ შენი AI ნუტრიციოლოგი.**\n\n"
        "ატვირთე საკვების ფოტო და მე დაგითვლი:\n"
        "• კალორიებს\n• ცილებს, ცხიმებს, ნახშირწყლებს\n• მოგცემ რჩევას ჯანსაღ კვებაზე.",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == 'calories_help')
async def calories_help(callback: types.CallbackQuery):
    await callback.message.answer("გამომიგზავნე საკვების ფოტო და დეტალურად გაგიანალიზებ მის შემადგენლობას!")

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        
        # ფოტოს გადმოწერა
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        image = Image.open(io.BytesIO(file_bytes.getvalue()))
        
        # AI-ს პრომპტი
        prompt = (
            "შენ ხარ პროფესიონალი ნუტრიციოლოგი. გააანალიზე ეს საკვები ფოტოზე. "
            "დაწერე: 1. კერძის სავარაუდო სახელი. 2. კალორიები (დაახლოებით). "
            "3. მაკროელემენტები (ცილები, ცხიმები, ნახშირწყლები). "
            "4. მოკლე რჩევა, არის თუ არა ეს ჯანსაღი არჩევანი."
        )
        
        response = model.generate_content([image, prompt])
        await message.answer(f"📊 **ანალიზი:**\n\n{response.text}", parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("❌ ბოდიში, ანალიზისას შეცდომა მოხდა. სცადე მოგვიანებით.")

@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        response = model.generate_content(message.text)
        await message.answer(response.text)
    except Exception as e:
        await message.answer("❌ ვერ გიპასუხე, სცადე მოგვიანებით.")

async def on_startup(dp):
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)

if __name__ == '__main__':
    if os.environ.get("RENDER"):
        executor.start_webhook(dp, "/", on_startup=on_startup, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    else:
        executor.start_polling(dp, skip_updates=True)
