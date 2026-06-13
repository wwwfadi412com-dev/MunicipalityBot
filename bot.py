import telebot
from PIL import Image
import os
import json
import threading
from flask import Flask

# ================= إعدادات السيرفر الوهمي =================
app = Flask(__name__)

@app.route('/')
def home():
    return "بوت إدارة المنطقة يعمل بنجاح! ✅"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ================= الإعدادات الرئيسية =================
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_ID = 8558896048 # ضع الـ ID الخاص فيك هنا
FRAMES_DIR = 'frames'
ADMIN_FRAMES_DIR = 'admin_frames'
DB_FILE = 'database.json'

bot = telebot.TeleBot(TOKEN)

# ================= قاعدة البيانات =================
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

municipalities_db = load_db()

# ================= قراءة المجالس تلقائياً =================
COUNCILS = {}
if os.path.exists(FRAMES_DIR):
    files = sorted([f for f in os.listdir(FRAMES_DIR) if f.endswith('.png')])
    for index, filename in enumerate(files, start=1):
        council_name = os.path.splitext(filename)[0]
        COUNCILS[str(index)] = {"name": council_name, "file": filename}
else:
    print("⚠️ خطأ: مجلد frames غير موجود!")

# تخزين حالة المستخدم (ليش يختار إطار إدارة ولا مجلس)
user_sessions = {}

# ================= أوامر البوت =================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    
    if user_id == str(ADMIN_ID):
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("👑 إطارات إدارة المنطقة", callback_data="mode_admin"))
        markup.add(telebot.types.InlineKeyboardButton("🏛️ إطارات رؤساء المجالس", callback_data="mode_council"))
        bot.reply_to(message, "👑 أهلاً بك يا مدير المنطقة!\nاختر نوع الإطار الذي تريد استخدامه:", reply_markup=markup)
        return
    
    if user_id in municipalities_db:
        council_id = municipalities_db[user_id]
        council_name = COUNCILS.get(council_id, {}).get("name", "غير معروف")
        bot.reply_to(message, f"🏛️ أهلاً بك في بوت {council_name}\nأرسل الصورة الخام الآن ليتم وضع الإطار عليها.")
    else:
        bot.reply_to(message, "🚫 عذراً، ليس لديك صلاحية استخدام هذا البوت.")

# عند اختيار نوع الإطار (للمدير فقط)
@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def handle_mode_selection(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    
    mode = call.data.split('_')[1] # admin أو council
    user_sessions[str(call.from_user.id)] = {"mode": mode, "council_id": None}
    
    # عرض قائمة المجالس للاختيار
    markup = telebot.types.InlineKeyboardMarkup()
    for idx, data in COUNCILS.items():
        markup.add(telebot.types.InlineKeyboardButton(data['name'], callback_data=f"select_{idx}"))
        
    mode_text = "👑 إطارات إدارة المنطقة" if mode == "admin" else "🏛️ إطارات المجالس"
    bot.edit_message_text(f"اخترت: {mode_text}\n\nالآن اختر المجلس/البلدة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# عند اختيار المجلس (للمدير فقط)
@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_council_selection(call):
    user_id = str(call.from_user.id)
    if user_id != str(ADMIN_ID) or user_id not in user_sessions:
        return
        
    council_id = call.data.split('_')[1]
    user_sessions[user_id]["council_id"] = council_id
    
    council_name = COUNCILS[council_id]["name"]
    mode_text = "👑 إطار إدارة المنطقة" if user_sessions[user_id]["mode"] == "admin" else "🏛️ إطار المجلس"
    
    bot.edit_message_text(f"✅ تم الاختيار بنجاح!\n\nالمجلس: {council_name}\nنوع الإطار: {mode_text}\n\nأرسل الصورة الخام الآن.", call.message.chat.id, call.message.message_id)

# أمر إضافة رؤساء البلديات
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
            bot.reply_to(message, "❌ رقم المجلس غير صحيح.")
    except:
        bot.reply_to(message, "⚠️ استخدم:\n/add [ID_رئيس_البلدية] [رقم_المجلس]")

# أمر عرض قائمة المجالس
@bot.message_handler(commands=['councils'])
def list_councils(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    response = "📋 **قائمة المجالس وأرقامها:**\n\n"
    for idx, data in COUNCILS.items():
        response += f"`{idx}` - {data['name']}\n"
    bot.reply_to(message, response, parse_mode="Markdown")

# معالجة الصور
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = str(message.from_user.id)
    
    # 1. معالجة صورة المدير
    if user_id == str(ADMIN_ID):
        if user_id not in user_sessions or user_sessions[user_id]["council_id"] is None:
            bot.reply_to(message, "⚠️ يرجى اختيار نوع الإطار والمجلس أولاً عبر /start")
            return
            
        session = user_sessions[user_id]
        council_id = session["council_id"]
        mode = session["mode"]
        
        # تحديد المجلد بناءً على الاختيار
        if mode == "admin":
            frames_directory = ADMIN_FRAMES_DIR
            caption_text = "✅ تفضل، الصورة جاهزة بإطار إدارة المنطقة"
        else:
            frames_directory = FRAMES_DIR
            caption_text = "✅ تفضل، الصورة جاهزة بإطار المجلس"
            
        council_data = COUNCILS.get(council_id)
        
    # 2. معالجة صورة رئيس البلدية
    elif user_id in municipalities_db:
        council_id = municipalities_db[user_id]
        council_data = COUNCILS.get(council_id)
        frames_directory = FRAMES_DIR
        caption_text = f"✅ تفضل، الصورة جاهزة بإطار {council_data['name']}"
        mode = "council"
        
    else:
        return # شخص غريب

    bot.reply_to(message, "⏳ جاري معالجة الصورة...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        input_path = f"temp_{user_id}.jpg"
        output_path = f"out_{user_id}.png"
        
        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        base_image = Image.open(input_path).convert("RGBA")
        
        # تحديد مسار الإطار
        frame_path = os.path.join(frames_directory, council_data["file"])
        
        if os.path.exists(frame_path):
            frame = Image.open(frame_path).convert("RGBA")
            frame = frame.resize(base_image.size, Image.Resampling.LANCZOS)
            final_image = Image.alpha_composite(base_image, frame)
            final_image.convert("RGB").save(output_path, "PNG")
        else:
            error_msg = "❌ خطأ: إطار المجلس غير موجود." if mode == "council" else "❌ خطأ: إطار إدارة المنطقة غير موجود."
            bot.reply_to(message, error_msg)
            os.remove(input_path)
            return
            
        with open(output_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption_text)
            
        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.reply_to(message, f"⚠️ حدث خطأ: {e}")

# ================= التشغيل =================
if __name__ == '__main__':
    threading.Thread(target=run_web).start()
    print("🤖 بوت إدارة المنطقة الاحترافي يعمل بنجاح...")
    bot.polling(none_stop=True)
