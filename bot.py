import telebot
from PIL import Image
import os
import json
import threading
from flask import Flask

# ================= إعدادات السيرفر الوهمي (عشان Render ما يعلق) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "بوت إدارة المنطقة يعمل بنجاح! ✅"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ================= الإعدادات الرئيسية للبوت =================
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 8558896048  # استبدل هذا برقم الـ ID الخاص فيك يا مدير المنطقة
FRAMES_DIR = 'frames'
DB_FILE = 'database.json'

bot = telebot.TeleBot(TOKEN)

# ================= قاعدة البيانات (لحفظ الصلاحيات) =================
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

municipalities_db = load_db()

# ================= قراءة المجالس تلقائياً من الملفات =================
COUNCILS = {}
if os.path.exists(FRAMES_DIR):
    files = sorted([f for f in os.listdir(FRAMES_DIR) if f.endswith('.png')])
    for index, filename in enumerate(files, start=1):
        council_name = os.path.splitext(filename)[0]
        COUNCILS[str(index)] = {"name": council_name, "file": filename}
else:
    print("⚠️ خطأ: مجلد frames غير موجود!")

# ================= أوامر البوت =================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    
    if user_id == str(ADMIN_ID):
        bot.reply_to(message, "👑 أهلاً بك يا مدير المنطقة في لوحة التحكم.\n\n"
                              "لإضافة رئيس بلدية، أرسل الأمر:\n"
                              "`/add [ID_رئيس_البلدية] [رقم_المجلس]`\n\n"
                              "لمشاهدة أرقام المجالس، أرسل:\n`/councils`", parse_mode="Markdown")
        return
    
    if user_id in municipalities_db:
        council_id = municipalities_db[user_id]
        council_name = COUNCILS.get(council_id, {}).get("name", "غير معروف")
        bot.reply_to(message, f"🏛️ أهلاً بك في بوت {council_name}\nأرسل الصورة الخام الآن ليتم وضع الإطار عليها.")
    else:
        bot.reply_to(message, "🚫 عذراً، ليس لديك صلاحية استخدام هذا البوت.\nتواصل مع إدارة المنطقة.")

@bot.message_handler(commands=['councils'])
def list_councils(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    response = "📋 **قائمة المجالس وأرقامها:**\n\n"
    for idx, data in COUNCILS.items():
        response += f"`{idx}` - {data['name']}\n"
        
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_user(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        parts = message.text.split()
        user_id = str(parts[1])
        council_id = parts[2]
        
        if council_id in COUNCILS:
            municipalities_db[user_id] = council_id
            save_db(municipalities_db)
            council_name = COUNCILS[council_id]["name"]
            bot.reply_to(message, f"✅ تم إعطاء صلاحية ({council_name}) للمستخدم `{user_id}` بنجاح.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ رقم المجلس غير صحيح. أرسل /councils لمعرفة الأرقام.")
    except:
        bot.reply_to(message, "⚠️ خطأ في الصيغة. استخدم:\n/add [ID_رئيس_البلدية] [رقم_المجلس]")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = str(message.from_user.id)
    
    if user_id not in municipalities_db:
        if user_id != str(ADMIN_ID):
            return
        else:
            bot.reply_to(message, "يا مدير، حسابك للإدارة فقط. أرسل الصور من حسابات رؤساء المجالس.")
            return

    council_id = municipalities_db[user_id]
    council_data = COUNCILS.get(council_id)
    
    if not council_data:
        bot.reply_to(message, "خطأ في النظام، تواصل مع المدير.")
        return

    bot.reply_to(message, "⏳ جاري معالجة الصورة...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        input_path = f"temp_{user_id}.jpg"
        output_path = f"out_{user_id}.png"
        
        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        base_image = Image.open(input_path).convert("RGBA")
        
        frame_path = os.path.join(FRAMES_DIR, council_data["file"])
        if os.path.exists(frame_path):
            frame = Image.open(frame_path).convert("RGBA")
            frame = frame.resize(base_image.size, Image.Resampling.LANCZOS)
            final_image = Image.alpha_composite(base_image, frame)
            final_image.convert("RGB").save(output_path, "PNG")
        else:
            bot.reply_to(message, "❌ خطأ: ملف الإطار غير موجود.")
            os.remove(input_path)
            return
            
        with open(output_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=f"✅ تفضل، الصورة جاهزة بإطار {council_data['name']}")
            
        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.reply_to(message, f"⚠️ حدث خطأ: {e}")

# ================= تشغيل البوت والسيرفر معاً =================
if __name__ == '__main__':
    # تشغيل السيرفر الوهمي في Thread (مسار منفصل) عشان ما يعلق البوت
    threading.Thread(target=run_web).start()
    
    print("🤖 بوت إدارة المنطقة الاحترافي يعمل بنجاح...")
    # تشغيل بوت تلغرام
    bot.polling(none_stop=True)
