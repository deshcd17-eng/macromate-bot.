import logging
import os
from aiogram import Bot, Dispatcher, executor, types
import google.generativeai as genai

# კონფიგურაცია
logging.basicConfig(level=logging.INFO)

# ტოკენებს ავიღებთ Render-ის "Environment"-დან
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Gemini-ს კონფიგურაცია
genai.configure(api_key=GEMINI_API_KEY)
# ვიყენებთ flash-ს, რომელიც ყველაზე სტაბილურია
model = genai.GenerativeModel('gemini-1.5-flash')

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "👋 გამარჯობა! მე ვარ შენი AI ასისტენტი.\n\n"
        "შეგიძლია დამიწერო ნებისმიერი კითხვა, გიპასუხებ დეტალურად!\n"
        "ფოტოების ანალიზი მალე დაემატება. 🔜"
    )

@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    try:
        # ინდიკატორი, რომ ბოტი ფიქრობს
        await bot.send_chat_action(message.chat.id, "typing")
        
        response = model.generate_content(message.text)
        await message.answer(response.text)
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        await message.answer("❌ სამწუხაროდ, პასუხის გაცემა ვერ მოხერხდა. სცადე მოგვიანებით.")

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    # აქ არის ჩვენი "მალე დაემატება" ფუნქცია
    await message.answer("🖼️ ფოტოების დამუშავების ფუნქცია მალე დაემატება! ახლა მხოლოდ ტექსტური კითხვებით შემოვიფარგლოთ.")

async def on_startup(dp):
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info("Webhook დაყენდა წარმატებით.")

if __name__ == '__main__':
    # Render-ზე ვებჰუკით, ლოკალურად პოლინგით
    if "RENDER" in os.environ:
        executor.start_webhook(
            dispatcher=dp,
            webhook_path="/",
            on_startup=on_startup,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 10000))
        )
    else:
        executor.start_polling(dp, skip_updates=True)
