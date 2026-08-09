"""
FlirtyoU - @Flirtyoubot v2 PREMIUM STARS EDITION
"""

import os
import re
import random
import hashlib
import sqlite3
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, filters, PreCheckoutQueryHandler
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "flirtyou.db"

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        coins INTEGER DEFAULT 100,
        spice_level TEXT DEFAULT 'medium',
        language TEXT DEFAULT 'english',
        chat_mode INTEGER DEFAULT 0,
        chat_name TEXT DEFAULT 'Mimi',
        daily_sub INTEGER DEFAULT 0,
        total_flirts INTEGER DEFAULT 0,
        is_premium INTEGER DEFAULT 0,
        premium_until TEXT,
        chat_used_today INTEGER DEFAULT 0,
        last_chat_date TEXT,
        created_at TEXT
    )""")
    try: c.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN premium_until TEXT")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN chat_used_today INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN last_chat_date TEXT")
    except: pass
    c.execute("CREATE TABLE IF NOT EXISTS anon_chats (user1 INTEGER, user2 INTEGER, active INTEGER DEFAULT 1, PRIMARY KEY (user1, user2))")
    c.execute("CREATE TABLE IF NOT EXISTS crushes (id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, to_username TEXT, message TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def ensure_user(update: Update):
    u = update.effective_user
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, first_name, coins, created_at) VALUES (?,?,?,?,?)",
                    (u.id, u.username or "", u.first_name or "", 100, datetime.now().isoformat()))
        conn.commit()
    else:
        cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (u.username or "", u.first_name or "", u.id))
        conn.commit()
    conn.close()

def add_coins(user_id, amount):
    conn = db()
    conn.execute("UPDATE users SET coins = coins + ?, total_flirts = total_flirts + 1 WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def set_user_field(user_id, field, value):
    conn = db()
    conn.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()

def is_premium_user(user_row):
    if not user_row: return False
    if user_row["is_premium"] == 1:
        if user_row["premium_until"]:
            try:
                until = datetime.fromisoformat(user_row["premium_until"])
                if datetime.now() < until: return True
                else:
                    set_user_field(user_row["user_id"], "is_premium", 0)
                    return False
            except: return True
        return True
    return False

FLIRT_LINES = {
    "cute": ["You look like my favorite notification 😊","Are you tired? You've been running through my mind all day","I was going to say hi but your smile already said it all","You + Me = my favorite plan"],
    "smooth": ["Are you WiFi? Because I'm really feeling a connection","Do you have a map? I just got lost in your eyes","Your vibe is like 5G - rare and super fast at stealing my attention","Is your name Google? You have everything I've been searching for"],
    "funny": ["Are you a magician? Because whenever I look at you, everyone else disappears... and so does my rizz","I'm not a photographer but I can picture us together","Are you a loan? Cause you got my interest","If you were a vegetable you'd be a cute-cumber"],
    "savage": ["You must be tired of being this fine with no appointment?","I don't need a pickup line, your ex already fumbled, I just need to pick up where he fell off","You bad, but I'm worse - we match","On a scale of 1-10 you're a 9, I'm the 1 you need"],
    "naija": ["Girl you be like MTN pulse, you dey make my heart dey do gbim gbim","You fine pass Lagos traffic when NEPA take light for night","Abeg no be only jollof dey sweet, you sef sweet die","You be like fuel for my gen, without you I no fit function","See as you fine, you be like iPhone 16 wey never comot","If beauty be crime, you for dey Kirikiri for life imprisonment","You too fine, make I no go mistakenly fall in love for here"],
    "spicy": ["You look like trouble, and I'm trying to get into some 😏","You must be cold, cause you've been on my mind and it's getting hot in here","Your energy is addictive and I'm not looking for rehab","Let's skip the small talk and go straight to flirting"]
}
COMPLIMENTS = {
    "girl": ["Your smile is literally my favorite notification today ✨","You have that main character energy, can't ignore","You fine no be small, your mirror must be proud of you","The way you carry yourself? 10/10 rizz queen"],
    "boy": ["You got that calm rizz that makes everyone look twice","Sharp guy, clean vibe, you get sense plus steeze","Your energy screams boss, I like that","You look like the guy that fixes problems and hearts"],
    "general": ["You have an amazing vibe, don't ever dim it","You're literally the reason someone checks their phone and smiles","Your aura is 10/10 today"]
}
TRUTHS = ["When was your last kiss and who was it? 😏","What's your biggest turn-on?","Have you ever had a crush on a friend? Who?","What's the most flirty text you ever sent?","Who in this group would you date?","What's your love language?"]
DARES = ["Send a voice note saying 'I miss you' to your crush","Change your bio to 'Taken by @Flirtyoubot 😏' for 10 mins","DM someone 'Hey, you crossed my mind' right now","Send your last selfie to your crush with 😏","Call your crush and say you had a dream about them"]
WYR = ["Would you rather have a cute partner or a funny partner?","Would you rather kiss your crush or have your crush kiss you first?","Would you rather date someone 5 years older or 2 years younger?","Would you rather get caught stalking your crush or get left on read?","Would you rather be rizzless for a year or broke for a month?"]
BIO_TEMPLATES = ["Sarcasm + good vibes + {interest} lover. Let's see if you can keep up 😏 | {city}","CEO of bad decisions but good conversations. {interest} addict. Your next favorite notification","6ft of chaos with soft heart. I like {interest}, late night drives and people who can actually flirt back","Not here for games, except truth or dare. {interest} & good energy only ✨"]
OPENERS = ["Okay quick question: {interest} + me + you = perfect date or disaster? 😏","You look like you have great taste... saw you like {interest}, you just earned my first message","Not gonna lie, your profile stopped my scrolling. Are you this interesting in person too?","Be honest, how many pickup lines have you gotten today? I promise mine is different","You + {interest}? That's dangerous combo. I'm intrigued"]

def ai_flirty_reply(prompt, system="You are FlirtyoU, playful, teasing, sweet Nigerian-flavored wingman. Keep it PG-13, fun, witty, not explicit. Max 2 sentences."):
    if not OPENAI_API_KEY:
        return random.choice(FLIRT_LINES["smooth"] + FLIRT_LINES["naija"])
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":system},{"role":"user","content":prompt}], max_tokens=150)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI error {e}")
        return random.choice(FLIRT_LINES["smooth"])

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Get Line", callback_data="get_flirt"), InlineKeyboardButton("🇳🇬 Naija Rizz", callback_data="get_naija")],
        [InlineKeyboardButton("💬 AI Chat", callback_data="toggle_chat"), InlineKeyboardButton("❤️ Secret Crush", callback_data="crush_start")],
        [InlineKeyboardButton("🎲 Games", callback_data="games"), InlineKeyboardButton("💘 Love Calc", callback_data="love_start")],
        [InlineKeyboardButton("🕵️ Anon Flirt", callback_data="anon_find"), InlineKeyboardButton("💎 Premium", callback_data="premium_show")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

def share_keyboard(line):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Next", callback_data="get_flirt"), InlineKeyboardButton("🔥 Spicier", callback_data="get_spicy")],
        [InlineKeyboardButton("📤 Share", switch_inline_query=line[:30])],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
    ])

anon_queue = []

def is_in_anon(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM anon_chats WHERE (user1=? OR user2=?) AND active=1", (user_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row

def get_anon_partner(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM anon_chats WHERE (user1=? OR user2=?) AND active=1", (user_id, user_id))
    row = cur.fetchone()
    conn.close()
    if not row: return None
    return row["user2"] if row["user1"]==user_id else row["user1"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    user = update.effective_user
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0].replace("ref_",""))
            if ref_id != user.id:
                add_coins(ref_id, 50)
                try: await context.bot.send_message(ref_id, f"🎉 Someone joined via your link! +50 Coins 💰")
                except: pass
        except: pass
    text = f"Hey {user.first_name} 😏\n\nI'm *FlirtyoU* — your personal rizz plug.\n🔥 /flirt\n🇳🇬 /pickup naija\n💎 /premium - Unlimited AI chat\n\nInvite: t.me/{context.bot.username}?start=ref_{user.id}\n"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    await update.message.reply_text("🏠 *Menu*", parse_mode="Markdown", reply_markup=main_keyboard())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Commands: /flirt /pickup /compliment /rizz /bio /opener /reply /translate /love /crush /anon /chat /truth /dare /wyr /daily /coins /leaderboard /premium")

async def flirt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    cat = context.args[0].lower() if context.args else "smooth"
    if cat not in FLIRT_LINES: cat = "smooth"
    user = get_user(update.effective_user.id)
    if user and user["spice_level"]=="spicy" and not is_premium_user(user):
        await update.message.reply_text("🌶️ Spicy is Premium only! /premium 💎\nHere's medium:")
        cat = "smooth"
    line = random.choice(FLIRT_LINES[cat])
    add_coins(update.effective_user.id, 5)
    await update.message.reply_text(f"🔥 *{cat.upper()}*:\n\n{line}", parse_mode="Markdown", reply_markup=share_keyboard(line))

async def pickup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await flirt_cmd(update, context)

async def compliment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    cat = context.args[0].lower() if context.args else "general"
    if cat not in COMPLIMENTS: cat = "general"
    line = random.choice(COMPLIMENTS[cat])
    add_coins(update.effective_user.id, 3)
    await update.message.reply_text(f"✨ {line}", reply_markup=share_keyboard(line))

async def rizz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /rizz your line")
        context.user_data["awaiting_rizz"] = True
        return
    score = min(98, max(15, len(text)*2 + random.randint(-5,15)))
    feedback = ai_flirty_reply(f"Rate rizz: '{text}' and improve. Fun.")
    await update.message.reply_text(f"📊 *{score}%*\n{feedback}", parse_mode="Markdown")
    if score>80: add_coins(update.effective_user.id, 10)

async def bio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("😂 Funny", callback_data="bio_funny"), InlineKeyboardButton("😏 Smooth", callback_data="bio_smooth")],[InlineKeyboardButton("🥺 Cute", callback_data="bio_cute"), InlineKeyboardButton("😎 Savage", callback_data="bio_savage")]])
    await update.message.reply_text("Vibe?", reply_markup=kb)

async def opener_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    interest = " ".join(context.args) if context.args else "good vibes"
    opener = random.choice(OPENERS).format(interest=interest)
    ai_v = ai_flirty_reply(f"DM opener for {interest}. 1 line flirty.")
    await update.message.reply_text(f"💬 Opener for {interest}:\n\n1. {opener}\n2. {ai_v}", parse_mode="Markdown")

async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    their_msg = " ".join(context.args)
    if not their_msg:
        await update.message.reply_text("Usage: /reply she said I'm busy")
        return
    gen = ai_flirty_reply(f"They said: '{their_msg}'. Give 3 flirty replies.")
    await update.message.reply_text(f"🔥 {gen}", parse_mode="Markdown")

async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = " ".join(context.args)
    if not txt:
        await update.message.reply_text("Usage: /translate good morning")
        return
    flirty = ai_flirty_reply(f"Rewrite flirty: '{txt}'")
    await update.message.reply_text(f"😏 {flirty}")

async def love_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("Usage: /love @john @sarah")
        return
    a,b = context.args[0], context.args[1]
    score = int(hashlib.md5((a+b).lower().encode()).hexdigest(),16) % 61 + 30
    await update.message.reply_text(f"💘 {a} + {b} = {score}% 🔥", parse_mode="Markdown")

async def coins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    prem = "💎 Premium" if is_premium_user(row) else "Free"
    await update.message.reply_text(f"💰 {row['coins']} Coins\nFlirts: {row['total_flirts']}\nPlan: {prem}", parse_mode="Markdown")

async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT first_name, total_flirts FROM users ORDER BY total_flirts DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    txt = "👑 *Top:*\n"
    for i,r in enumerate(rows,1): txt+=f"{i}. {r['first_name']} - {r['total_flirts']}\n"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def truth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"😏 {random.choice(TRUTHS)}")
async def dare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"😈 {random.choice(DARES)}")
async def wyr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🤔 {random.choice(WYR)}")
async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    row = get_user(update.effective_user.id)
    new_val = 0 if row["daily_sub"] else 1
    set_user_field(update.effective_user.id, "daily_sub", new_val)
    await update.message.reply_text(f"Daily: {'ON' if new_val else 'OFF'}")
async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Soft 🥺", callback_data="set_spice_soft"), InlineKeyboardButton("Medium 😏", callback_data="set_spice_medium"), InlineKeyboardButton("Spicy 🌶️", callback_data="set_spice_spicy")],
        [InlineKeyboardButton("English", callback_data="set_lang_english"), InlineKeyboardButton("Pidgin 🇳🇬", callback_data="set_lang_pidgin")]
    ])
    await update.message.reply_text("⚙️ Settings:", reply_markup=kb)

async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    row = get_user(update.effective_user.id)
    if is_premium_user(row):
        await update.message.reply_text(f"💎 Premium until {row['premium_until']} 🔥")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 1 Month - 99 Stars ⭐", callback_data="buy_month")],
        [InlineKeyboardButton("🔥 3 Months - 199 Stars ⭐", callback_data="buy_3month")],
        [InlineKeyboardButton("🚀 Lifetime - 499 Stars ⭐", callback_data="buy_lifetime")]
    ])
    await update.message.reply_text("💎 *Premium* 💎\n\nFree: 10 AI chats/day, soft/medium only\nPremium:\n✅ Unlimited AI chat\n✅ Spicy + Naija dirty\n✅ Unlimited anon\n✅ 500 coins\n\nPay with Telegram Stars:", parse_mode="Markdown", reply_markup=kb)

async def send_stars_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, months: int, stars: int, title: str):
    payload = f"premium_{months}month_{update.effective_user.id}"
    await context.bot.send_invoice(
        chat_id=update.effective_chat_id,
        title=title,
        description=f"Unlock {title}",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(title, stars)],
        start_parameter="premium"
    )

async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    uid = update.effective_user.id
    payload = payment.invoice_payload
    months = 1
    if "3month" in payload: months = 3
    elif "lifetime" in payload: months = 120
    until = datetime.now() + timedelta(days=30*months)
    conn = db()
    conn.execute("UPDATE users SET is_premium=1, premium_until=?, coins=coins+500 WHERE user_id=?", (until.isoformat(), uid))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🎉 Premium until {until.strftime('%d %b %Y')}! +500 Coins!", parse_mode="Markdown", reply_markup=main_keyboard())
    if ADMIN_ID:
        try: await context.bot.send_message(ADMIN_ID, f"💰 New Premium: {uid} paid {payment.total_amount} Stars for {months}m")
        except: pass

async def crush_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💌 Send crush username like @sarah")
    context.user_data["awaiting_crush_user"] = True

async def anon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    uid = update.effective_user.id
    if is_in_anon(uid):
        await update.message.reply_text("Already in anon. /stop to leave.")
        return
    if uid in anon_queue:
        await update.message.reply_text("Searching...")
        return
    if anon_queue:
        partner = anon_queue.pop(0)
        if partner == uid:
            anon_queue.append(uid)
            await update.message.reply_text("Searching...")
            return
        conn = db()
        conn.execute("INSERT INTO anon_chats (user1,user2) VALUES (?,?)", (uid, partner))
        conn.commit()
        conn.close()
        await update.message.reply_text("🔥 Matched! /stop to leave")
        try: await context.bot.send_message(partner, "🔥 Matched! /stop to leave")
        except: pass
    else:
        anon_queue.append(uid)
        await update.message.reply_text("🕵️ Searching...")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    global anon_queue
    if uid in anon_queue:
        anon_queue.remove(uid)
        await update.message.reply_text("Stopped.")
        return
    partner = get_anon_partner(uid)
    if partner:
        conn = db()
        conn.execute("DELETE FROM anon_chats WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)", (uid,partner,partner,uid))
        conn.commit()
        conn.close()
        await update.message.reply_text("Left chat. /anon for new")
        try: await context.bot.send_message(partner, "Partner left. /anon for new")
        except: pass
    else:
        await update.message.reply_text("You no dey any chat")

async def chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    row = get_user(update.effective_user.id)
    new_mode = 0 if row["chat_mode"] else 1
    set_user_field(update.effective_user.id, "chat_mode", new_mode)
    await update.message.reply_text(f"💬 Chat {'ON' if new_mode else 'OFF'}")

async def roleplay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("☕ Coffee", callback_data="rp_coffee"), InlineKeyboardButton("📱 DM", callback_data="rp_dm")],[InlineKeyboardButton("🌙 Night", callback_data="rp_night")]])
    await update.message.reply_text("🎭 Choose:", reply_markup=kb)

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    if data == "get_flirt":
        line = random.choice(FLIRT_LINES["smooth"])
        await query.message.reply_text(f"🔥 {line}", reply_markup=share_keyboard(line))
        add_coins(uid,5)
    elif data == "get_naija":
        line = random.choice(FLIRT_LINES["naija"])
        await query.message.reply_text(f"🇳🇬 {line}", reply_markup=share_keyboard(line))
        add_coins(uid,5)
    elif data == "get_spicy":
        row = get_user(uid)
        if not is_premium_user(row):
            await query.message.reply_text("🌶️ Premium only! /premium 💎")
            return
        line = random.choice(FLIRT_LINES["spicy"])
        await query.message.reply_text(f"🌶️ {line}", reply_markup=share_keyboard(line))
    elif data == "menu":
        await query.message.reply_text("🏠 Menu", reply_markup=main_keyboard())
    elif data.startswith("set_spice_"):
        level = data.split("_")[-1]
        row = get_user(uid)
        if level=="spicy" and not is_premium_user(row):
            await query.message.reply_text("Spicy needs Premium 💎")
            return
        set_user_field(uid, "spice_level", level)
        await query.message.reply_text(f"Spice: {level}")
    elif data.startswith("set_lang_"):
        lang = data.split("_")[-1]
        set_user_field(uid, "language", lang)
        await query.message.reply_text(f"Lang: {lang}")
    elif data.startswith("bio_"):
        vibe = data.split("_")[1]
        template = random.choice(BIO_TEMPLATES).format(interest="music", city="Lagos")
        extra = ai_flirty_reply(f"{vibe} bio for Lagos, music")
        await query.message.reply_text(f"📝 {template}\n{extra}")
    elif data == "toggle_chat":
        await chat_cmd(update, context)
    elif data == "crush_start":
        await query.message.reply_text("Send @username")
        context.user_data["awaiting_crush_user"] = True
    elif data == "premium_show":
        await premium_cmd(update, context)
    elif data == "buy_month":
        await send_stars_invoice(update, context, 1, 99, "Premium 1 Month")
    elif data == "buy_3month":
        await send_stars_invoice(update, context, 3, 199, "Premium 3 Months")
    elif data == "buy_lifetime":
        await send_stars_invoice(update, context, 120, 499, "Premium Lifetime")
    elif data == "games":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Truth", callback_data="game_truth"), InlineKeyboardButton("Dare", callback_data="game_dare")]])
        await query.message.reply_text("Pick:", reply_markup=kb)
    elif data == "game_truth":
        await query.message.reply_text(f"😏 {random.choice(TRUTHS)}")
    elif data == "game_dare":
        await query.message.reply_text(f"😈 {random.choice(DARES)}")
    elif data.startswith("rp_"):
        resp = ai_flirty_reply(f"Roleplay {data} PG-13 flirty")
        await query.message.reply_text(resp)
        set_user_field(uid, "chat_mode", 1)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    uid = update.effective_user.id
    text = update.message.text or ""
    partner = get_anon_partner(uid)
    if partner:
        if text.startswith("/"): return
        try: await context.bot.send_message(partner, f"🕵️ Anon: {text}")
        except: await update.message.reply_text("Partner offline")
        return
    if context.user_data.get("awaiting_crush_user"):
        m = re.search(r"@?(\w+)", text)
        if m:
            crush_user = m.group(0)
            if not crush_user.startswith("@"): crush_user = "@"+crush_user
            context.user_data["crush_target"] = crush_user
            context.user_data["awaiting_crush_user"] = False
            context.user_data["awaiting_crush_msg"] = True
            await update.message.reply_text(f"Got {crush_user}. Now secret message:")
        return
    if context.user_data.get("awaiting_crush_msg"):
        target = context.user_data.get("crush_target")
        conn = db()
        conn.execute("INSERT INTO crushes (from_id, to_username, message, created_at) VALUES (?,?,?,?)", (uid, target, text, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username=?", (target.replace("@",""),))
        row = cur.fetchone()
        conn.close()
        if row:
            try:
                await context.bot.send_message(row["user_id"], f"💌 Crush: \"{text}\" via @Flirtyoubot - /crush to reply")
                await update.message.reply_text(f"✅ Delivered to {target}!")
            except: await update.message.reply_text("Saved but user not started bot")
        else:
            await update.message.reply_text(f"Saved! Tell {target} to start bot")
        context.user_data["awaiting_crush_msg"] = False
        return
    if context.user_data.get("awaiting_rizz"):
        context.user_data["awaiting_rizz"] = False
        score = min(98, max(15, len(text)*2 + random.randint(-5,15)))
        feedback = ai_flirty_reply(f"Rate rizz: '{text}'")
        await update.message.reply_text(f"📊 {score}% {feedback}")
        return
    row = get_user(uid)
    if row and row["chat_mode"]:
        if text.startswith("/"): return
        today = datetime.now().date().isoformat()
        if row["last_chat_date"] != today:
            set_user_field(uid, "chat_used_today", 0)
            set_user_field(uid, "last_chat_date", today)
            row = get_user(uid)
        if not is_premium_user(row) and row["chat_used_today"] >= 10:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Unlock - 99 Stars", callback_data="buy_month")]])
            await update.message.reply_text("Free limit 10/day reached. Upgrade!", reply_markup=kb)
            return
        conn = db()
        conn.execute("UPDATE users SET chat_used_today=chat_used_today+1 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        resp = ai_flirty_reply(text, system=f"You are {row['chat_name'] or 'Mimi'}, flirty Nigerian AI, PG-13 short.")
        await update.message.reply_text(resp)
        return
    if len(text) > 2 and not text.startswith("/"):
        await update.message.reply_text("Use /flirt or /menu", reply_markup=main_keyboard())

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID: return
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM users")
    total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM users WHERE is_premium=1")
    prem = cur.fetchone()["c"]
    conn.close()
    await update.message.reply_text(f"Users: {total} Premium: {prem} Queue: {len(anon_queue)}")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID: return
    msg = " ".join(context.args)
    if not msg: return
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()
    sent=0
    for u in users:
        try:
            await context.bot.send_message(u["user_id"], f"📢 {msg}")
            sent+=1
        except: pass
    await update.message.reply_text(f"Sent {sent}")

async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE daily_sub=1")
    users = cur.fetchall()
    conn.close()
    line = random.choice(FLIRT_LINES["smooth"] + FLIRT_LINES["naija"])
    for u in users:
        try: await context.bot.send_message(u["user_id"], f"☀️ Daily: {line}", reply_markup=main_keyboard())
        except: pass

def main():
    init_db()
    if not BOT_TOKEN:
        print("Set BOT_TOKEN")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("flirt", flirt_cmd))
    app.add_handler(CommandHandler("pickup", pickup_cmd))
    app.add_handler(CommandHandler("compliment", compliment_cmd))
    app.add_handler(CommandHandler("rizz", rizz_cmd))
    app.add_handler(CommandHandler("bio", bio_cmd))
    app.add_handler(CommandHandler("opener", opener_cmd))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("translate", translate_cmd))
    app.add_handler(CommandHandler("love", love_cmd))
    app.add_handler(CommandHandler("coins", coins_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("truth", truth_cmd))
    app.add_handler(CommandHandler("dare", dare_cmd))
    app.add_handler(CommandHandler("wyr", wyr_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("crush", crush_cmd))
    app.add_handler(CommandHandler("anon", anon_cmd))
    app.add_handler(CommandHandler("match", anon_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("chat", chat_cmd))
    app.add_handler(CommandHandler("roleplay", roleplay_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.job_queue.run_repeating(daily_job, interval=86400, first=10)
    print("🔥 FlirtyoU v2 PREMIUM STARS running...")
    app.run_polling()

if __name__ == "__main__":
    main()
