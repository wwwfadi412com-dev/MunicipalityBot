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
INITIAL_ADMIN_IDS = ['8558896048', '6504296861'] # المدراء الأساسيين (يتم إضافتهم لأول مرة فقط)
FRAMES_DIR = 'frames'
ADMIN_FRAMES_DIR = 'admin_frames'
DB_FILE = 'database.json'

bot = telebot.TeleBot(TOKEN)

# ================= قاعدة البيانات =================
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
            # دمج المدراء الأساسيين مع المدراء المخزنين لضمان عدم فقدان الصلاحيات
            admins = set(db.get("admins", []))
            for admin_id in INITIAL_ADMIN_IDS:
                admins.add(admin_id)
            db["admins"] = list(admins)
            return db
    # هيكل قاعدة البيانات الافتراضي
    return {"users": {}, "admins": INITIAL_ADMIN_IDS}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

data_db = load_db()

def is_admin(user_id):
    return str(user_id) in data_db["admins"]

# ================= قراءة المجالس تلقائياً =================
COUNCILS = {}
if os.path.exists(FRAMES_DIR):
    files = sorted([f for f in os.listdir(FRAMES_DIR) if f.endswith('.png')])
    for index, filename in enumerate(files, start=1):
        council_name = os.path.splitext(filename)[0]
        COUNCILS[str(index)] = {"name": council_name, "file": filename}
else:
    print("⚠️ خطأ: مجلد frames غير موجود!")

user_sessions = {}

# دالة لإعداد زر القائمة في تلغرام
def setup_bot_commands():
    commands = [
        telebot.types.BotCommand("start", "فتح لوحة التحكم الرئيسية")
    ]
    bot.set_my_commands(commands)

# استدعاء الدالة عند تشغيل البوت
setup_bot_commands()

# ================= دوال مساعدة للواجهة =================
def get_main_menu_markup():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("👑 إطارات إدارة المنطقة", callback_data="mode_admin"),
        telebot.types.InlineKeyboardButton("🏛️ إطارات رؤساء المجالس", callback_data="mode_council")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("➕ إضافة رئيس بلدية", callback_data="dash_add_user"),
        telebot.types.InlineKeyboardButton("🗑️ حذف رئيس بلدية", callback_data="dash_remove_user")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("📋 المستخدمون والمجالس", callback_data="dash_view_lists"),
        telebot.types.InlineKeyboardButton("⚙️ إدارة المدراء", callback_data="dash_manage_admins")
    )
    return markup

# ================= أوامر البوت والواجهة =================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    
    # لو المدير هو اللي دخل
    if is_admin(user_id):
        bot.reply_to(message, "👑 أهلاً بك في لوحة تحكم إدارة المنطقة:\nاختر ما تريد من القائمة أدناه 👇", reply_markup=get_main_menu_markup())
        return
    
    # لو رئيس بلدية مسجل
    if user_id in data_db["users"]:
        council_id = data_db["users"][user_id]
        council_name = COUNCILS.get(council_id, {}).get("name", "غير معروف")
        bot.reply_to(message, f"🏛️ أهلاً بك في بوت {council_name}\nأرسل الصورة الخام الآن ليتم وضع الإطار عليها.")
    else:
        # لو شخص غريب (ليس مدير ولا رئيس بلدية مسجل)
        user_name = message.from_user.first_name
        
        # 1. إعطاء المستخدم الـ ID حقه ليرسله للإدارة
        bot.reply_to(message, f"🚫 عذراً، ليس لديك صلاحية استخدام هذا البوت.\n\n🆔 الـ ID الخاص بحسابك هو: `{user_id}`\n\n📌 أرسل هذا الرقم لإدارة المنطقة (الأخ أبو جمال) ليتم إضافتك إلى النظام.", parse_mode="Markdown")
        
        # 2. إرسال إشعار لكل المدراء برغبة الشخص بالدخول
        for admin_id in data_db["admins"]:
            try:
                bot.send_message(admin_id, f"🔔 تنبيه: شخص جديد يحاول استخدام البوت!\n\n👤 الاسم: {user_name}\n🆔 الـ ID: `{user_id}`\n\nلإضافته اضغط /start واستخدم زر (➕ إضافة رئيس بلدية).", parse_mode="Markdown")
            except:
                pass # تجاهل الخطأ لو المدير لم يبدأ المحادثة مع البوت بعد

# ================= معالجة أزرار لوحة التحكم =================

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
def back_to_main(call):
    if not is_admin(call.from_user.id): return
    bot.edit_message_text("👑 لوحة تحكم إدارة المنطقة:\nاختر ما تريد من القائمة أدناه 👇", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_markup())

# 1. اختيار نوع الإطار
@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def handle_mode_selection(call):
    if not is_admin(call.from_user.id): return
    
    mode = call.data.split('_')[1]
    user_sessions[str(call.from_user.id)] = {"mode": mode, "council_id": None, "action": None}
    
    markup = telebot.types.InlineKeyboardMarkup()
    for idx, data in COUNCILS.items():
        markup.add(telebot.types.InlineKeyboardButton(data['name'], callback_data=f"select_{idx}"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        
    mode_text = "👑 إطارات إدارة المنطقة" if mode == "admin" else "🏛️ إطارات المجالس"
    bot.edit_message_text(f"اخترت: {mode_text}\n\nالآن اختر المجلس/البلدة 👇", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_council_selection(call):
    user_id = str(call.from_user.id)
    if not is_admin(user_id) or user_id not in user_sessions: return
        
    council_id = call.data.split('_')[1]
    user_sessions[user_id]["council_id"] = council_id
    
    council_name = COUNCILS[council_id]["name"]
    mode_text = "👑 إطار إدارة المنطقة" if user_sessions[user_id]["mode"] == "admin" else "🏛️ إطار المجلس"
    
    bot.edit_message_text(f"✅ تم الاختيار بنجاح!\n\nالمجلس: {council_name}\nنوع الإطار: {mode_text}\n\n📩 أرسل الصورة الخام الآن.", call.message.chat.id, call.message.message_id)

# 2. إضافة رئيس بلدية
@bot.callback_query_handler(func=lambda call: call.data == 'dash_add_user')
def handle_dash_add_user(call):
    if not is_admin(call.from_user.id): return
    user_sessions[str(call.from_user.id)] = {"action": "waiting_for_user_id"}
    bot.edit_message_text("➕ **إضافة رئيس بلدية جديد:**\n\nأرسل الـ ID الخاص بالمستخدم (أرقام فقط):", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# 3. حذف رئيس بلدية
@bot.callback_query_handler(func=lambda call: call.data == 'dash_remove_user')
def handle_dash_remove_user(call):
    if not is_admin(call.from_user.id): return
    if not data_db["users"]:
        bot.edit_message_text("لا يوجد رؤساء بلديات مسجلون حالياً.", call.message.chat.id, call.message.message_id)
        return
        
    markup = telebot.types.InlineKeyboardMarkup()
    for uid, council_id in data_db["users"].items():
        council_name = COUNCILS.get(council_id, {}).get("name", "غير معروف")
        markup.add(telebot.types.InlineKeyboardButton(f"❌ حذف: {council_name} ({uid})", callback_data=f"deluser_{uid}"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        
    bot.edit_message_text("🗑️ **اختر المستخدم الذي تريد حذفه:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('deluser_'))
def execute_remove_user(call):
    if not is_admin(call.from_user.id): return
    uid = call.data.split('_')[1]
    if uid in data_db["users"]:
        council_name = COUNCILS.get(data_db["users"][uid], {}).get("name", "غير معروف")
        del data_db["users"][uid]
        save_db(data_db)
        bot.edit_message_text(f"✅ تم سحب الصلاحية من المستخدم `{uid}` ({council_name}) بنجاح.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text("⚠️ هذا المستخدم غير موجود.", call.message.chat.id, call.message.message_id)

# 4. عرض القوائم
@bot.callback_query_handler(func=lambda call: call.data == 'dash_view_lists')
def handle_dash_view_lists(call):
    if not is_admin(call.from_user.id): return
    
    # قائمة المجالس
    councils_text = "📋 **أرقام المجالس:**\n\n"
    for idx, data in COUNCILS.items():
        councils_text += f"`{idx}` - {data['name']}\n"
        
    # قائمة المستخدمين
    users_text = "\n\n📋 **رؤساء البلديات المسجلون:**\n\n"
    if not data_db["users"]:
        users_text += "لا يوجد مستخدمون مسجلون حالياً.\n"
    else:
        for uid, council_id in data_db["users"].items():
            council_name = COUNCILS.get(council_id, {}).get("name", "غير معروف")
            users_text += f"👤 `{uid}` ◀️ {council_name}\n"

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    bot.edit_message_text(councils_text + users_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# 5. إدارة المدراء
@bot.callback_query_handler(func=lambda call: call.data == 'dash_manage_admins')
def handle_dash_manage_admins(call):
    if not is_admin(call.from_user.id): return
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("➕ إضافة مدير جديد", callback_data="admin_add_step1"))
    markup.add(telebot.types.InlineKeyboardButton("🗑️ حذف مدير", callback_data="admin_remove_list"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    bot.edit_message_text("⚙️ **إدارة المدراء:**\n\nيمكنك إضافة أو حذف مدراء من هنا (المدراء لديهم نفس صلاحياتك).", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_add_step1')
def handle_admin_add_step1(call):
    if not is_admin(call.from_user.id): return
    user_sessions[str(call.from_user.id)] = {"action": "waiting_for_admin_id"}
    bot.edit_message_text("➕ **إضافة مدير جديد:**\n\nأرسل الـ ID الخاص بالمدير (أرقام فقط):", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_remove_list')
def handle_admin_remove_list(call):
    if not is_admin(call.from_user.id): return
    markup = telebot.types.InlineKeyboardMarkup()
    for admin_id in data_db["admins"]:
        # منع المدير من حذف نفسه بالخطأ
        if str(admin_id) != str(call.from_user.id):
             markup.add(telebot.types.InlineKeyboardButton(f"❌ حذف: {admin_id}", callback_data=f"deladmin_{admin_id}"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="dash_manage_admins"))
    bot.edit_message_text("🗑️ **اختر المدير الذي تريد حذفه:**\n(لا يمكنك حذف نفسك)", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('deladmin_'))
def execute_remove_admin(call):
    if not is_admin(call.from_user.id): return
    admin_id = call.data.split('_')[1]
    if admin_id in data_db["admins"]:
        data_db["admins"].remove(admin_id)
        save_db(data_db)
        bot.edit_message_text(f"✅ تم حذف المدير `{admin_id}` من النظام بنجاح.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# ================= استقبال الرسائل النصية =================
@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = str(message.from_user.id)
    
    # 1. معالجة حالات الإدارة (إضافة مستخدم أو مدير)
    if is_admin(user_id):
        if user_id in user_sessions and user_sessions[user_id].get("action") == "waiting_for_user_id":
            new_id = message.text.strip()
            if not new_id.isdigit():
                bot.reply_to(message, "⚠️ الـ ID يجب أن يتكون من أرقام فقط! حاول مرة أخرى.")
                return
            
            markup = telebot.types.InlineKeyboardMarkup()
            for idx, data in COUNCILS.items():
                markup.add(telebot.types.InlineKeyboardButton(data['name'], callback_data=f"newuser_{new_id}_{idx}"))
            markup.add(telebot.types.InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
            
            bot.reply_to(message, f"تم استلام الـ ID: `{new_id}`\nالآن اختر البلدة/المجلس لهذا المستخدم 👇", reply_markup=markup, parse_mode="Markdown")
            user_sessions[user_id]["action"] = None
            return

        elif user_id in user_sessions and user_sessions[user_id].get("action") == "waiting_for_admin_id":
            new_admin_id = message.text.strip()
            if not new_admin_id.isdigit():
                bot.reply_to(message, "⚠️ الـ ID يجب أن يتكون من أرقام فقط! حاول مرة أخرى.")
                return
            
            if new_admin_id not in data_db["admins"]:
                data_db["admins"].append(new_admin_id)
                save_db(data_db)
                bot.reply_to(message, f"✅ تم إضافة المدير `{new_admin_id}` بنجاح.", parse_mode="Markdown")
            else:
                bot.reply_to(message, "⚠️ هذا المستخدم مدير بالفعل.")
            
            user_sessions[user_id]["action"] = None
            return
        
        # 🌟 إضافة جديدة: لو المدير أرسل أي كلمة ثانية، اعرض له القائمة
        else:
            bot.reply_to(message, "👑 أنت في لوحة التحكم، اختر من القائمة أدناه 👇", reply_markup=get_main_menu_markup())
            return

    # 2. معالجة رئيس البلدية (لو أرسل نص، ذكره يرسل صورة)
    if user_id in data_db["users"]:
        bot.reply_to(message, "🏛️ لمعالجة صورة، يرجى إرسال الصورة الخام مباشرة (وليس نصاً).")
        return
    
    # 3. شخص غريب
    bot.reply_to(message, "🚫 عذراً، ليس لديك صلاحية استخدام هذا البوت.\nتواصل مع إدارة المنطقة.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('newuser_'))
def save_new_user(call):
    if not is_admin(call.from_user.id): return
    parts = call.data.split('_')
    new_id = parts[1]
    council_id = parts[2]
    
    data_db["users"][new_id] = council_id
    save_db(data_db)
    council_name = COUNCILS[council_id]["name"]
    
    bot.edit_message_text(f"✅ تم إضافة المستخدم `{new_id}` بنجاح إلى صلاحية ({council_name}).", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# ================= معالجة الصور =================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = str(message.from_user.id)
    
    if is_admin(user_id):
        if user_id not in user_sessions or user_sessions[user_id].get("council_id") is None:
            bot.reply_to(message, "⚠️ يرجى اختيار نوع الإطار والمجلس أولاً من القائمة /start")
            return
            
        session = user_sessions[user_id]
        council_id = session["council_id"]
        mode = session["mode"]
        
        if mode == "admin":
            frames_directory = ADMIN_FRAMES_DIR
            caption_text = "✅ تفضل، الصورة جاهزة بإطار إدارة المنطقة"
        else:
            frames_directory = FRAMES_DIR
            caption_text = "✅ تفضل، الصورة جاهزة بإطار المجلس"
            
        council_data = COUNCILS.get(council_id)
        
    elif user_id in data_db["users"]:
        council_id = data_db["users"][user_id]
        council_data = COUNCILS.get(council_id)
        frames_directory = FRAMES_DIR
        caption_text = f"✅ تفضل، الصورة جاهزة بإطار {council_data['name']}"
        mode = "council"
        
    else:
        return

    bot.reply_to(message, "⏳ جاري معالجة الصورة...")

    input_path = f"temp_{user_id}.jpg"
    output_path = f"out_{user_id}.png"

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        base_image = Image.open(input_path).convert("RGBA")
        
        frame_path = os.path.join(frames_directory, council_data["file"])
        
        if os.path.exists(frame_path):
            frame = Image.open(frame_path).convert("RGBA")
            frame = frame.resize(base_image.size, Image.Resampling.LANCZOS)
            final_image = Image.alpha_composite(base_image, frame)
            final_image.convert("RGB").save(output_path, "PNG")
        else:
            error_msg = "❌ خطأ: إطار المجلس غير موجود." if mode == "council" else "❌ خطأ: إطار إدارة المنطقة غير موجود."
            bot.reply_to(message, error_msg)
            return
            
        with open(output_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption_text)

    except Exception as e:
        bot.reply_to(message, f"⚠️ حدث خطأ: {e}")
        
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

# ================= التشغيل =================
if __name__ == '__main__':
    threading.Thread(target=run_web).start()
    print("🤖 بوت إدارة المنطقة الاحترافي يعمل بنجاح...")
    
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"⚠️ حصل خطأ والبوت فصل: {e}")
            print("🔄 جاري إعادة تشغيل البوت بعد 5 ثواني...")
            import time
            time.sleep(5)
