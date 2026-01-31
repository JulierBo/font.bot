import telebot
import re
import unicodedata
import time
import json
import os
from telebot.types import ChatPermissions

def parse_time(text):
    text = text.strip().lower()

    if text.endswith("s"):
        return int(text[:-1])
    if text.endswith("m"):
        return int(text[:-1]) * 60
    if text.endswith("h"):
        return int(text[:-1]) * 3600
    if text.endswith("d"):
        return int(text[:-1]) * 86400

    return int(text)


TOKEN = "8137226690:AAGjtMCYhlHHZm3eVAZiaXbM9i2JFZu5PgY"
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

ADMIN_IDS = [8197491717]
DATA_FILE = "data.json"

# ======================
# Load / Save
# ======================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "mute_time": 30,
        "strikes": {},
        "extra_words": []
    }

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load_data()

# ======================
# Base banned patterns
# ======================
BASE_PATTERNS = [
    r"b[\W_]*i[\W_]*o",
    r"j[\W_]*o[\W_]*i[\W_]*n",
    r"t[\W_]*\.?[\W_]*m[\W_]*e",
    r"http[s]?",
    r"www\.",
    r"link",
    r"ဂျိုင်း",
    r"ဘိုင်[\W_]*အို",
]

def normalize(text):
    return unicodedata.normalize("NFKC", text).lower()

def is_admin(chat_id, user_id):
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except:
        return False

def build_patterns():
    patterns = BASE_PATTERNS[:]
    for w in data.get("extra_words", []):
        letters = r"[\W_]*".join(map(re.escape, w))
        patterns.append(letters)
    return patterns

def contains_banned(text):
    text = normalize(text)
    for p in build_patterns():
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

def strike_key(chat_id, user_id):
    return f"{chat_id}:{user_id}"

def mention(user):
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

# ======================
# /help command
# ======================
@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.reply_to(
        message,
        "📘 <b>Group Guard Bot Help</b>\n\n"
        "🚫 <b>ပိတ်ပင်ထားသော အရာများ</b>\n"
        "• ဘိုင်အို (bio)\n"
        "• ဂျိုင်း (join)\n"
        "• လင့် (link)\n"
        "• Admin ထည့်သွင်းထားသော စကားလုံးများ\n\n"
        "⚠️ ၃ ကြိမ် ပြုလုပ်ပါက Auto Mute\n\n"
        "🛠 <b>Admin Commands</b>\n"
        "/setmute 60 – mute အချိန်ပြောင်း\n"
        "/addword spam – စကားလုံးထည့်\n"
        "/delword spam – စကားလုံးဖျက်\n"
        "/help – ဒီစာမျက်နှာ"
    )

# ======================
# Admin Commands
# ======================
@bot.message_handler(commands=["setmute"])
def set_mute(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        raw = message.text.split()[1]
        sec = parse_time(raw)

        data["mute_time"] = sec
        save_data()

        bot.reply_to(
            message,
            f"✅ <b>Mute time updated</b>\n"
            f"⏱ {raw} ({sec} seconds)"
        )
    except:
        bot.reply_to(
            message,
            "❌ Usage:\n"
            "/setmute 30s\n"
            "/setmute 5m\n"
            "/setmute 2h\n"
            "/setmute 1d"
        )


@bot.message_handler(commands=["addword"])
def add_word(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        word = message.text.split(" ", 1)[1].strip().lower()
        if word not in data["extra_words"]:
            data["extra_words"].append(word)
            save_data()
            bot.reply_to(message, f"✅ Added: <b>{word}</b>")
        else:
            bot.reply_to(message, "⚠️ Word already exists")
    except:
        bot.reply_to(message, "❌ Usage: /addword spam")

@bot.message_handler(commands=["delword"])
def del_word(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        word = message.text.split(" ", 1)[1].strip().lower()
        if word in data["extra_words"]:
            data["extra_words"].remove(word)
            save_data()
            bot.reply_to(message, f"🗑 Removed: <b>{word}</b>")
        else:
            bot.reply_to(message, "⚠️ Word not found")
    except:
        bot.reply_to(message, "❌ Usage: /delword spam")

# ======================
# Message Guard
# ======================
@bot.message_handler(content_types=["text"])
def guard(message):
    if message.chat.type not in ["group", "supergroup"]:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    if is_admin(chat_id, user_id):
        return

    if not contains_banned(message.text):
        return

    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass

    key = strike_key(chat_id, user_id)
    data["strikes"][key] = data["strikes"].get(key, 0) + 1
    save_data()

    strikes = data["strikes"][key]
    mute_time = data["mute_time"]

    if strikes >= 3:
        until = int(time.time()) + mute_time
        bot.restrict_chat_member(
            chat_id,
            user_id,
            until_date=until,
            permissions=ChatPermissions(can_send_messages=False)
        )

        bot.send_message(
            chat_id,
            f"🔇 <b>Auto Mute</b>\n\n"
            f"👤 {mention(message.from_user)}\n"
            f"👥 <b>{message.chat.title}</b>\n\n"
            f"🚫 ဒီ group မှာ ပိတ်ပင်ထားသော စာသားများ ပို့ထားသဖြင့်\n"
            f"⏱ <b>{mute_time} seconds</b> mute လုပ်လိုက်ပါသည်။"
        )

        data["strikes"][key] = 0
        save_data()
    else:
        bot.send_message(
            chat_id,
            f"⚠️ <b>သတိပေးချက် ({strikes}/3)</b>\n\n"
            f"👤 {mention(message.from_user)}\n"
            f"👥 <b>{message.chat.title}</b>\n\n"
            f"🚫 ဒီ group မှာ\n"
            f"( ဘိုင်အို / ဂျိုင်း / လင့် )\n"
            f"ဆိုင်ရာ စာသားများ ပို့ခြင်းကို ခွင့်မပြုပါ။\n\n"
            f"🔁 ၃ ကြိမ် ပြုလုပ်ပါက\n"
            f"⏱ Auto mute ဖြစ်ပါမည်။"
        )

print("Bot running...")
bot.infinity_polling()
