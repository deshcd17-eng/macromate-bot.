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

# ტოკენებს იღებს Render-ის Environment-დან
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# მონაცემთა ბაზის ინიციალიზაცია
def init_db():
    conn = sqlite3.connect("macromate.db")
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

# ღილაკების მენიუ
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🍎 კალორიების ანალიზი", callback_data="calories"),
        InlineKeyboardButton("ℹ️ დახმარება", callback_data="help")
    )
    return markup

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    init_db()
    await message.answer(
        "🥗 **გამარჯობა! მე ვარ Macromate.**\n\n"
        "ატვირთე საკვების ფოტო და მე დაგითვლი კალორიებს, ცილებს, ცხიმებსა და ნახშირწყლებს!", 
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == 'calories')
async def calories_info(callback: types.CallbackQuery):
    await callback.message.answer("გამომიგზავნე საკვების ფოტო და დავიწყებ ანალიზს!")

@dp.callback_query_handler(lambda c: c.data == 'help')
async def help_info(callback: types.CallbackQuery):
    await callback.message.answer("უბრალოდ ატვირთე ფოტო და მე გავაკეთებ დანარჩენს!")

@dp.message_handler(content_types=['photo'])
async def photo_handler(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        image = Image.open(io.BytesIO(file_bytes.getvalue()))
        
        prompt = "გააანალიზე ამ ფოტოზე არსებული საკვები: დაწერე დასახელება, დათვალე კალორიები, ცილები, ცხიმები და ნახშირწყლები (დაახლოებით). იყავი მოკლე და ზუსტი."
        response = model.generate_content([image, prompt])
        
        await message.answer(f"🍽️ **ანალიზის შედეგი:**\n\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ შეცდომა ანალიზისას: {str(e)}")

# ვებჰუკის მართვა
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

if __name__ == '__main__':
    if os.environ.get("RENDER"):
        executor.start_webhook(dp, "/", on_startup=on_startup, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    else:
        executor.start_polling(dp, skip_updates=True)
