import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import google.generativeai as genai

# ==========================================
# ⚠️ KALITLARINGIZNI SHU YERGA YOZING:
# ==========================================
BOT_TOKEN = "BU_YERGA_BOTFATHER_TOKENINI_YOZING"
GEMINI_API_KEY = "BU_YERGA_GEMINI_API_KALITINI_YOZING"

# ------------------------------------------
# MA'LUMOTLAR BAZASI TIZIMI (SQLite)
# ------------------------------------------
def init_db():
    conn = sqlite3.connect("caloraa.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        gender TEXT,
        age INTEGER,
        height INTEGER,
        weight REAL,
        calorie_target INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS food_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        food_name TEXT,
        calories INTEGER,
        log_date TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, gender, age, height, weight, target):
    conn = sqlite3.connect("caloraa.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO users (user_id, gender, age, height, weight, calorie_target)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, gender, age, height, weight, target))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("caloraa.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_food_log(user_id, food_name, calories):
    conn = sqlite3.connect("caloraa.db")
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
    INSERT INTO food_logs (user_id, food_name, calories, log_date)
    VALUES (?, ?, ?, ?)
    """, (user_id, food_name, calories, today))
    conn.commit()
    conn.close()

def get_today_calories(user_id):
    conn = sqlite3.connect("caloraa.db")
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
    SELECT SUM(calories) FROM food_logs 
    WHERE user_id = ? AND log_date = ?
    """, (user_id, today))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result else 0

# ------------------------------------------
# BOT VA AI SOZLAMALARI
# ------------------------------------------
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

class ProfileForm(StatesGroup):
    gender = State()
    age = State()
    height = State()
    weight = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Erkak 👨"), types.KeyboardButton(text="Ayol 👩")]],
            resize_keyboard=True
        )
        await message.answer(
            "Assalomu alaykum! **Caloraa AI** botiga xush kelibsiz.\n\n"
            "Kunlik me'yoringizni aniqlash uchun jinsingizni tanlang:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await state.set_state(ProfileForm.gender)
    else:
        norma = user[5]
        today_cal = get_today_calories(message.from_user.id)
        await message.answer(
            f"Xush kelibsiz! 👋\n\n"
            f"🎯 Kunlik norma: **{norma} kcal**\n"
            f"🍽 Bugun yeyildi: **{today_cal} kcal**\n\n"
            "📸 Taom rasmini yuboring yoki matn ko'rinishida yozing!",
            parse_mode="Markdown"
        )

@dp.message(ProfileForm.gender)
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Yoshingizni kiriting (Masalan: 22):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(ProfileForm.age)

@dp.message(ProfileForm.age)
async def process_age(message: types.Message, state: FSMContext):
    await state.update_data(age=int(message.text))
    await message.answer("Bo'yingizni sm da kiriting (Masalan: 175):")
    await state.set_state(ProfileForm.height)

@dp.message(ProfileForm.height)
async def process_height(message: types.Message, state: FSMContext):
    await state.update_data(height=int(message.text))
    await message.answer("Vazningizni kg da kiriting (Masalan: 70):")
    await state.set_state(ProfileForm.weight)

@dp.message(ProfileForm.weight)
async def process_weight(message: types.Message, state: FSMContext):
    await state.update_data(weight=float(message.text))
    user_data = await state.get_data()
    
    w, h, a = user_data['weight'], user_data['height'], user_data['age']
    bmr = (10 * w + 6.25 * h - 5 * a + 5) if "Erkak" in user_data['gender'] else (10 * w + 6.25 * h - 5 * a - 161)
    target_calories = int(bmr * 1.375)
    
    add_user(message.from_user.id, user_data['gender'], a, h, w, target_calories)
    await state.clear()
    
    await message.answer(
        f"✅ Profil saqlandi!\n\n"
        f"📊 Kunlik me'yoringiz: **{target_calories} kcal**\n\n"
        "Endi yegan ovqatingiz **rasmini** yuboring yoki **nomini yozing**!",
        parse_mode="Markdown"
    )

@dp.message(Command("bugun"))
async def cmd_today(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start bosing.")
        return
    
    target = user[5]
    consumed = get_today_calories(message.from_user.id)
    remains = target - consumed
    await message.answer(
        f"📊 **Bugungi hisobot:**\n\n"
        f"🎯 Me'yor: **{target} kcal**\n"
        f"🍽 Yeyildi: **{consumed} kcal**\n"
        f"⚡️ Qoldi: **{remains if remains > 0 else 0} kcal**",
        parse_mode="Markdown"
    )

@dp.message(F.text)
async def process_text_food(message: types.Message):
    wait_msg = await message.answer("🔍 Taom tahlil qilinmoqda...")
    prompt = f"""
    Foydalanuvchi yozgan taom: "{message.text}".
    Ushbu taomning taxminiy kaloriyasini va BJU nisbatini aniqla.
    
    Javobning eng birinchi qatorida faqat va faqat umumiy kaloriyani son ko'rinishida yoz (masalan: CALORIE: 450).
    Keyingi qatordan foydalanuvchiga O'zbek tilida chiroyli javob ber:
    🍽 **Taom:** ...
    🔥 **Kaloriya:** ... kcal
    🧪 **BJU:** Oqsil: ...g | Yog': ...g | Uglevod: ...g
    """
    try:
        # AI chaqiruvini asinxron ipga o'tkazish
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        text = response.text
        
        if "CALORIE:" in text:
            cal_line = text.split("\n")[0]
            cal_val = int(''.join(filter(str.isdigit, cal_line)))
            clean_text = "\n".join(text.split("\n")[1:])
            add_food_log(message.from_user.id, message.text, cal_val)
        else:
            clean_text = text

        await wait_msg.delete()
        await message.answer(clean_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Xatolik: {e}")
        await wait_msg.edit_text(f"⚠️ Xatolik yuz berdi: {e}")

@dp.message(F.photo)
async def process_photo_food(message: types.Message):
    wait_msg = await message.answer("📸 Rasm tahlil qilinmoqda (AI Vision)...")
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = await bot.download_file(file_info.file_path)
        
        image_part = {"mime_type": "image/jpeg", "data": photo_bytes.read()}
        prompt = """
        Rasmdagi taomni aniqla (O'zbek va xalqaro taomlar).
        Javobning eng birinchi qatorida faqat va faqat umumiy kaloriyani son ko'rinishida yoz (masalan: CALORIE: 550).
        Keyingi qatordan foydalanuvchiga O'zbek tilida javob ber:
        🍽 **Taom:** ...
        🔥 **Kaloriya:** ... kcal
        🧪 **BJU:** Oqsil: ...g | Yog': ...g | Uglevod: ...g
        """
        response = await asyncio.to_thread(ai_model.generate_content, [prompt, image_part])
        text = response.text
        
        if "CALORIE:" in text:
            cal_line = text.split("\n")[0]
            cal_val = int(''.join(filter(str.isdigit, cal_line)))
            clean_text = "\n".join(text.split("\n")[1:])
            add_food_log(message.from_user.id, "Rasmli taom", cal_val)
        else:
            clean_text = text

        await wait_msg.delete()
        await message.answer(clean_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Xatolik: {e}")
        await wait_msg.edit_text(f"⚠️ Rasmni tahlil qilishda xatolik: {e}")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
