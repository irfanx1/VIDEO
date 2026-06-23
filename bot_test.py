# ═══════════════════════════════════════════════════════════════════
# 🤖 MANGA VIDEO AUTOMATION BOT - COMPLETE + DEBUG VERSION
# ═══════════════════════════════════════════════════════════════════

import os
import sys
import random
import sqlite3
import asyncio
import shutil
import time
import json
import zipfile
import re
import psutil
import platform
import logging
from datetime import datetime, timedelta
from pathlib import Path
from pyrogram.enums import ChatType
from typing import Dict, List, Optional
from concurrent.futures import ProcessPoolExecutor
import warnings

warnings.filterwarnings('ignore')

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

# 💉 MONKEY PATCH FOR MOVIEPY PIL 10.x ISSUE
if hasattr(Image, 'Resampling'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from pdf2image import convert_from_path
from google import genai
import edge_tts
from moviepy.editor import *

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    Message, CallbackQuery, InputMediaPhoto
)

# Safe pyromod import
try:
    from pyromod import listen
    PYROMOD_AVAILABLE = True
except:
    PYROMOD_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════
# 🔧 LOGGING SETUP (DEBUG MODE)
# ═══════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# 🔧 BOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

API_ID = 39407537
API_HASH = "5bd2e83dd1227da3f38c966d1d46d9ae"
BOT_TOKEN = "8540781290:AAH2LcuDU6_bvfDV9RpmzkNhwX6ga572gIM"
DEVELOPER_ID = 8180269769

UPDATE_CHANNEL = "https://t.me/auto_uploading"
SUPPORT_GROUP = "https://t.me/Auto_uploading_support_group"
DEVELOPER_URL = "https://t.me/SubaruXnatsuki"
GEMINI_API_KEY = "AQ.Ab8RN6LF0_h6uR798yBz4P5FOq2-SrFx8hdiLuqSgcH1uUG9Rw"

# ═══════════════════════════════════════════════════════════════════
# 🎯 VPS RESOURCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

CPU_CORES = os.cpu_count()
TOTAL_RAM = psutil.virtual_memory().total / (1024**3)
MAX_WORKERS = max(1, CPU_CORES - 1)

executor = ProcessPoolExecutor(max_workers=MAX_WORKERS)

# ═══════════════════════════════════════════════════════════════════
# 🎛️ GROUP MODE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

GROUP_MODE = True
TARGET_GROUP_ID = -1002238896583

# ═══════════════════════════════════════════════════════════════════
# 📊 QUEUE & TASK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

MAX_QUEUE_SIZE = 15
MAX_PAGES_LIMIT = 5000

processing_queue = []
user_active_tasks = {}
CANCEL_TASKS = {}

app = Client("manga_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ═══════════════════════════════════════════════════════════════════
# 🖼️ IMAGE PLACEHOLDERS
# ═══════════════════════════════════════════════════════════════════

IMAGES = {
    "start": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=Welcome+To+Manga+Bot"],
    "settings": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=Settings"],
    "quality": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=Quality"],
    "voice": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=Voice"],
    "bgm": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=BGM"],
    "blur": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=Blur"],
    "about": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=About"],
    "dashboard": ["https://dummyimage.com/800x400/2b2b2b/ffffff.jpg&text=Dashboard"]
}

def get_random_image(category: str) -> str:
    return random.choice(IMAGES.get(category, IMAGES["start"]))

# ═══════════════════════════════════════════════════════════════════
# 🗄️ DATABASE (FIXED)
# ═══════════════════════════════════════════════════════════════════

DB_PATH = "manga_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        quality TEXT DEFAULT '360p',
        voice TEXT DEFAULT 'hi-IN-SwaraNeural',
        bgm_volume INTEGER DEFAULT 20,
        blur_radius INTEGER DEFAULT 9,
        youtube_connected INTEGER DEFAULT 0,
        custom_bgm_file_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ban_history (
        user_id INTEGER PRIMARY KEY,
        strike_count INTEGER DEFAULT 0,
        last_strike_time TIMESTAMP,
        ban_until TIMESTAMP,
        banned INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        is_premium INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

init_db()

def add_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
              (user_id, username or "Unknown", first_name or "User"))
    conn.commit()
    conn.close()

def get_user_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_banned_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM ban_history WHERE banned=1")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_user_settings(user_id: int) -> Dict:
    """Get user settings with proper error handling"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    
    if not row:
        # Insert default settings
        c.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM user_settings WHERE user_id=?", (user_id,))
        row = c.fetchone()
    
    conn.close()
    
    # Safe unpacking with default values
    try:
        return {
            "quality": row[1] if len(row) > 1 else '360p',
            "voice": row[2] if len(row) > 2 else 'hi-IN-SwaraNeural',
            "bgm_volume": row[3] if len(row) > 3 else 20,
            "blur_radius": row[4] if len(row) > 4 else 9,
            "youtube_connected": row[5] if len(row) > 5 else 0,
            "custom_bgm_file_id": row[6] if len(row) > 6 else None
        }
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return {
            "quality": '360p',
            "voice": 'hi-IN-SwaraNeural',
            "bgm_volume": 20,
            "blur_radius": 9,
            "youtube_connected": 0,
            "custom_bgm_file_id": None
        }

def update_user_setting(user_id: int, key: str, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE user_settings SET {key}=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()

def reset_user_settings(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""UPDATE user_settings SET quality='360p', voice='hi-IN-SwaraNeural',
        bgm_volume=20, blur_radius=9, youtube_connected=0, custom_bgm_file_id=NULL WHERE user_id=?""", (user_id,))
    conn.commit()
    conn.close()

def check_ban_status(user_id: int) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM ban_history WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"banned": False, "strike_count": 0}
    if row[4]:
        ban_until = datetime.fromisoformat(row[4])
        if datetime.now() < ban_until:
            return {"banned": True, "ban_until": ban_until, "strike_count": row[1]}
        else:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE ban_history SET banned=0, ban_until=NULL WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
    return {"banned": False, "strike_count": row[1] if row else 0}

def add_strike(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT strike_count FROM ban_history WHERE user_id=?", (user_id,))
    row = c.fetchone()
    now = datetime.now()
    if not row:
        c.execute("INSERT INTO ban_history (user_id, strike_count, last_strike_time) VALUES (?, 1, ?)",
                  (user_id, now.isoformat()))
        conn.commit()
        conn.close()
        return 1
    new_count = row[0] + 1
    if new_count >= 2:
        ban_until = now + timedelta(hours=50)
        c.execute("UPDATE ban_history SET strike_count=?, last_strike_time=?, banned=1, ban_until=? WHERE user_id=?",
                  (new_count, now.isoformat(), ban_until.isoformat(), user_id))
    else:
        c.execute("UPDATE ban_history SET strike_count=?, last_strike_time=? WHERE user_id=?",
                  (new_count, now.isoformat(), user_id))
    conn.commit()
    conn.close()
    return new_count

# ═══════════════════════════════════════════════════════════════════
# ⚙️ QUALITY PRESETS
# ═══════════════════════════════════════════════════════════════════

QUALITY_PRESETS = {
    "360p": {"label": "360p super fast", "resolution": (640, 360), "fps": 30, "bitrate": "1500k"},
    "480p": {"label": "480p very fast", "resolution": (854, 480), "fps": 30, "bitrate": "2000k"},
    "540p": {"label": "540p fast", "resolution": (960, 540), "fps": 30, "bitrate": "2500k"},
    "720p": {"label": "720p normal", "resolution": (1280, 720), "fps": 48, "bitrate": "3000k"},
    "1080p": {"label": "1080p slow", "resolution": (1920, 1080), "fps": 48, "bitrate": "6000k"},
    "4K": {"label": "4K very slow", "resolution": (3840, 2160), "fps": 60, "bitrate": "12000k"}
}

VOICE_PRESETS = {
    "female": {"label": "👩 ғᴇᴍᴀʟᴇ (ᴄᴜᴛɪᴇ) ", "code": "hi-IN-SwaraNeural"},
    "male": {"label": "👨 ᴍᴀʟᴇ (sʜᴜᴜʜʜ!)", "code": "hi-IN-MadhurNeural"}
}

# ═══════════════════════════════════════════════════════════════════
# 🎨 KEYBOARDS
# ═══════════════════════════════════════════════════════════════════

def start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Update Channel", url=UPDATE_CHANNEL),
         InlineKeyboardButton("💬 Support Group", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("👨‍💻 Developer", url=DEVELOPER_URL)]
    ])

def settings_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Quality", callback_data="quality"),
         InlineKeyboardButton("🗣️ Voice", callback_data="voice")],
        [InlineKeyboardButton("🎵 BGM", callback_data="bgm"),
         InlineKeyboardButton("🌫️ Blur", callback_data="blur")],
        [InlineKeyboardButton("🔄 Reset to Default", callback_data="reset_settings")],
        [InlineKeyboardButton("📺 YouTube Upload", callback_data="youtube")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="start")]
    ])

def quality_keyboard():
    buttons = []
    row = []
    for key, val in QUALITY_PRESETS.items():
        row.append(InlineKeyboardButton(val["label"], callback_data=f"set_quality_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])
    return InlineKeyboardMarkup(buttons)

def voice_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(VOICE_PRESETS["female"]["label"], callback_data="set_voice_female"),
         InlineKeyboardButton(VOICE_PRESETS["male"]["label"], callback_data="set_voice_male")],
        [InlineKeyboardButton("🤖 Custom Voice", callback_data="custom_voice")],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
    ])

def bgm_keyboard():
    buttons = []
    row = []
    for vol in range(5, 100, 5):
        row.append(InlineKeyboardButton(f"{vol}%", callback_data=f"set_bgm_{vol}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("➕ Custom BGM", callback_data="custom_bgm"),
                    InlineKeyboardButton("🗑️ Delete BGM", callback_data="delete_bgm")])
    buttons.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])
    return InlineKeyboardMarkup(buttons)

def blur_keyboard():
    buttons = []
    row = []
    for radius in range(3, 51, 2):
        row.append(InlineKeyboardButton(str(radius), callback_data=f"set_blur_{radius}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])
    return InlineKeyboardMarkup(buttons)

def confirm_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Start Processing", callback_data=f"confirm_yes_{user_id}"),
         InlineKeyboardButton("❌ No, Cancel", callback_data=f"confirm_no_{user_id}")]
    ])

def progress_keyboard(user_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{user_id}"),
        InlineKeyboardButton("❌ Cancel Task", callback_data=f"cancel_{user_id}")
    ]])

# ═══════════════════════════════════════════════════════════════════
# 🚦 ACCESS CONTROL
# ═══════════════════════════════════════════════════════════════════

def is_owner(user_id: int) -> bool:
    return user_id == DEVELOPER_ID

def can_process_in_this_chat(message: Message) -> bool:
    user_id = message.from_user.id
    
    if is_owner(user_id):
        logger.info(f"✅ Owner {user_id} - Access granted")
        return True
    
    if GROUP_MODE:
        allowed = message.chat.type != ChatType.PRIVATE and message.chat.id == TARGET_GROUP_ID
        logger.info(f"🔍 GROUP check: {message.chat.id} vs {TARGET_GROUP_ID} = {allowed}")
        return allowed
    else:
        allowed = message.chat.type == ChatType.PRIVATE
        logger.info(f"🔍 DM check: {message.chat.type} = {allowed}")
        return allowed

# ═══════════════════════════════════════════════════════════════════
# 🔍 DEBUG MESSAGE LOGGER
# ═══════════════════════════════════════════════════════════════════

@app.on_message(group=-1)
async def debug_message_logger(client, message: Message):
    try:
        user_id = message.from_user.id if message.from_user else "Unknown"
        username = message.from_user.username if message.from_user else "Unknown"
        chat_id = message.chat.id
        chat_type = message.chat.type
        text = message.text[:50] if message.text else "[No text]"
        
        logger.info(f"""
━━━━━━━━━━━━━━━━━━━━━━
📨 NEW MESSAGE
━━━━━━━━━━━━━━━━━━━━━━
👤 User: {user_id}
🏷️  @{username}
💬 Chat: {chat_id}
📂 Type: {chat_type}
✉️  Text: {text}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
        """)
    except Exception as e:
        logger.error(f"❌ Error logging: {e}")

# ═══════════════════════════════════════════════════════════════════
# 💬 COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    logger.info(f"🔵 /start from user {message.from_user.id}")
    
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    ban_status = check_ban_status(user_id)
    if ban_status["banned"] and not is_owner(user_id):
        logger.warning(f"⚠️ User {user_id} banned")
        await message.reply_text(
            f"🚫 **You are banned!**\n\n"
            f"⏰ Ban expires: {ban_status['ban_until'].strftime('%d %b %Y, %I:%M %p')}"
        )
        return
    
    can_process = can_process_in_this_chat(message)
    
    caption = f"Hello {message.from_user.first_name}! 👋\n\n"
    caption += "🎬 **Manga to Video Bot!**\n\n"
    
    caption += "📖 **Quick Start:**\n"
    caption += "1️⃣ Send ZIP/PDF file\n"
    caption += "2️⃣ Reply with `/manga`\n"
    caption += "3️⃣ Click Yes to start\n"
    caption += "4️⃣ Video is ready! 🎉\n\n"
    
    caption += "⚙️ **Bot Commands:**\n"
    caption += "• **/manga** - Start process\n"
    caption += "• **/help** - Full guide\n"
    caption += "• **/ping** - Check status\n\n"
    
    caption += "✨ **Powered by @RJGamer07**"
    
    logger.info(f"✅ Sending response to {user_id}")
    await message.reply_photo(
        photo=get_random_image("start"),
        caption=caption,
        reply_markup=start_keyboard()
    )


@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    logger.info(f"🔵 /help from {message.from_user.id}")
    
    help_text = f"""
📖 **COMPLETE BOT GUIDE**

╔════════════════════╗
║ 🎬 WHAT IT DOES?   ║
╚════════════════════╝
✨ Manga/Comic to Video:
• Samvadini script generation
• Clean text removal
• Hindi TTS voiceover
• Background music
• High-quality export

━━━━━━━━━━━━━━━━━━━━━━

╔════════════════════╗
║ 📂 HOW TO USE?     ║
╚════════════════════╝
**Method 1 (Best):**
1. Upload ZIP/PDF file
2. Reply with **/manga**
3. Click "Yes" & Done!

**Method 2:**
1. Send **/manga** command
2. Bot asks for file
3. Upload file & Done!

━━━━━━━━━━━━━━━━━━━━━━

╔════════════════════╗
║ 📜 RULES & POLICY  ║
╚════════════════════╝
• Only Manga/Comics.
• No spamming allowed.
• Don't DM the bot.
🚫 NSFW: 2 strikes=BAN!

━━━━━━━━━━━━━━━━━━━━━━

╔════════════════════╗
║ ⚙️ CONFIG & LIMITS ║
╚════════════════════╝
🎥 Quality: 360p - 4K
🗣️ Voice: Male/Female
📊 Normal: 25 pages/req
👑 Owner: NO LIMITS!

━━━━━━━━━━━━━━━━━━━━━━

╔════════════════════╗
║ 📋 BOT COMMANDS    ║
╚════════════════════╝
**/start** - Start the bot
**/help** - Show this guide
**/manga** - Start process
**/ping** - Check status
**/dashboard** - Dev Stats #owner_cammand

━━━━━━━━━━━━━━━━━━━━━━
💬 Support: {SUPPORT_GROUP}
📢 Updates: {UPDATE_CHANNEL}
👨‍💻 Dev: @RJGamer07
    """
    await message.reply_text(help_text)

@app.on_message(filters.command("ping"))
async def ping_command(client, message: Message):
    logger.info(f"🔵 /ping from {message.from_user.id}")
    
    start = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = time.time()
    ping = (end - start) * 1000
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    uptime = time.time() - app.start_time
    uptime_str = str(timedelta(seconds=int(uptime)))
    
    text = f"""
🏓 **PONG!**

━━━━━━━━━━━━━━━━━━━━━
📡 **CONNECTION**
━━━━━━━━━━━━━━━━━━━━━
⚡ Ping: `{ping:.2f} ms`
⏰ Uptime: `{uptime_str}`
🐍 Python: `{platform.python_version()}`

━━━━━━━━━━━━━━━━━━━━━
💻 **SYSTEM STATUS**
━━━━━━━━━━━━━━━━━━━━━
🧠 RAM: `{ram.used/1024**3:.1f}GB / {ram.total/1024**3:.1f}GB ({ram.percent}%)`
💿 Disk: `{disk.used/1024**3:.1f}GB / {disk.total/1024**3:.1f}GB ({disk.percent}%)`
⚡ CPU: `{cpu}%`

━━━━━━━━━━━━━━━━━━━━━
📊 **QUEUE STATUS**
━━━━━━━━━━━━━━━━━━━━━
📋 Queue: `{len(processing_queue)}/{MAX_QUEUE_SIZE}`
🔄 Active: `{len(user_active_tasks)}`
👥 Users: `{get_user_count()}`

━━━━━━━━━━━━━━━━━━━━━
✨ **Bot by @RJGamer07**
    """
    await msg.edit_text(text)

@app.on_message(filters.command("dashboard") & filters.user(DEVELOPER_ID))
async def dashboard_command(client, message: Message):
    logger.info(f"🔵 /dashboard from owner")
    
    start = time.time()
    
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    end = time.time()
    ping = (end - start) * 1000
    
    total_users = get_user_count()
    banned_users = get_banned_count()
    
    uptime = time.time() - app.start_time
    uptime_str = str(timedelta(seconds=int(uptime)))
    
    active_downloads = len(user_active_tasks)
    idle_workers = MAX_WORKERS - active_downloads
    
    text = f"""
╔═════════════════╗
║  🎌 **DASHBOARD** ║
╚═════════════════╝

━━━━━━━━━━━━━━━━━━━━━━
📡 **CONNECTION**
━━━━━━━━━━━━━━━━━━━━━━
🏓 Ping: `{ping:.2f} ms`
🐍 Python: `{platform.python_version()}`
⏰ Uptime: `{uptime_str}`

━━━━━━━━━━━━━━━━━━━━━━
💻 **SYSTEM RESOURCES**
━━━━━━━━━━━━━━━━━━━━━━
🧠 RAM: `{ram.used/1024**3:.1f}GB / {ram.total/1024**3:.1f}GB ({ram.percent}%)`
💿 Disk: `{disk.used/1024**3:.1f}GB / {disk.total/1024**3:.1f}GB ({disk.percent}%)`
⚡ CPU: `{cpu}%`

━━━━━━━━━━━━━━━━━━━━━━
👷 **WORKERS**
━━━━━━━━━━━━━━━━━━━━━━
📦 Total Cores: `{CPU_CORES}`
⚙️ Max Workers: `{MAX_WORKERS}`
🟢 Working: `{active_downloads}`
⚪ Idle: `{idle_workers}`

━━━━━━━━━━━━━━━━━━━━━━
📊 **QUEUE**
━━━━━━━━━━━━━━━━━━━━━━
📋 Queue: `{len(processing_queue)}/{MAX_QUEUE_SIZE}`
📥 Active Tasks: `{len(user_active_tasks)}`

━━━━━━━━━━━━━━━━━━━━━━
👥 **USERS**
━━━━━━━━━━━━━━━━━━━━━━
👤 Total: `{total_users}`
🚫 Banned: `{banned_users}`

━━━━━━━━━━━━━━━━━━━━━━
📺 **BOT CONFIG**
━━━━━━━━━━━━━━━━━━━━━━
🎯 Mode: `{'GROUP ONLY' if GROUP_MODE else 'DM ONLY'}`
🆔 Target Group: `{TARGET_GROUP_ID if GROUP_MODE else 'N/A'}`
📄 Max Pages: `{MAX_PAGES_LIMIT}`
🔄 Queue Size: `{MAX_QUEUE_SIZE}`

━━━━━━━━━━━━━━━━━━━━━━
👑 Owner: {DEVELOPER_ID}
━━━━━━━━━━━━━━━━━━━━━━
    """
    
    await message.reply_photo(
        photo=get_random_image("dashboard"),
        caption=text
    )

@app.on_message(filters.command("getgroupid") & filters.user(DEVELOPER_ID))
async def get_group_id_command(client, message: Message):
    logger.info(f"🔵 /getgroupid from owner")
    
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title if hasattr(message.chat, 'title') else "Private"
    
    text = f"""
🆔 **CHAT INFORMATION**

**Chat ID:** `{chat_id}`
**Chat Type:** `{chat_type}`
**Chat Title:** `{chat_title}`

━━━━━━━━━━━━━━━━━━━━━━

**Current Config:**
• Mode: `{'GROUP' if GROUP_MODE else 'DM'}`
• Target Group ID: `{TARGET_GROUP_ID}`

━━━━━━━━━━━━━━━━━━━━━━

**Agar ye group ID set karna hai:**
1. `bot.py` mein line 81:
   `TARGET_GROUP_ID = {chat_id}`
2. Bot restart karo
    """
    await message.reply_text(text)

@app.on_message(filters.command("id") & filters.user(DEVELOPER_ID))
async def get_file_id(client, message: Message):
    if message.reply_to_message and message.reply_to_message.photo:
        file_id = message.reply_to_message.photo.file_id
        await message.reply_text(f"📸 **Photo File ID:**\n\n`{file_id}`")
    else:
        await message.reply_text("❌ Reply to a photo with /id command!")

# ═══════════════════════════════════════════════════════════════════
# 📁 /MANGA COMMAND
# ═══════════════════════════════════════════════════════════════════

user_file_data = {}

@app.on_message(filters.command("manga"))
async def manga_command(client, message: Message):
    logger.info(f"🔵 /manga from user {message.from_user.id} in chat {message.chat.id}")
    
    user_id = message.from_user.id
    
    if not can_process_in_this_chat(message):
        logger.warning(f"❌ /manga blocked: User {user_id} not in allowed chat")
        if GROUP_MODE:
            await message.reply_text(
                f"❌ **Processing sirf authorized group mein!**\n\n"
                f"📢 Join: {SUPPORT_GROUP}\n"
                f"🆔 Current: `{message.chat.id}`\n"
                f"🎯 Required: `{TARGET_GROUP_ID}`\n\n"
                f"👑 Owner: Anywhere allowed!"
            )
        else:
            await message.reply_text(
                f"❌ **Processing only in DM!**\n\n"
                f"👑 Owner: Anywhere allowed!"
            )
        return
    
    logger.info(f"✅ /manga access granted for user {user_id}")
    
    if not is_owner(user_id):
        ban_status = check_ban_status(user_id)
        if ban_status["banned"]:
            logger.warning(f"❌ User {user_id} is banned")
            await message.reply_text(
                f"🚫 **Banned!**\n\n"
                f"⏰ Khatam: {ban_status['ban_until'].strftime('%d %b %Y, %I:%M %p')}"
            )
            return
        
        if len(processing_queue) >= MAX_QUEUE_SIZE:
            logger.warning(f"❌ Queue full ({len(processing_queue)}/{MAX_QUEUE_SIZE})")
            await message.reply_text(
                f"⚠️ **Queue Full!**\n\n"
                f"📊 {len(processing_queue)}/{MAX_QUEUE_SIZE}\n"
                f"⏰ Wait karo."
            )
            return
        
        if user_id in user_active_tasks:
            logger.warning(f"❌ User {user_id} already has active task")
            await message.reply_text(
                "⚠️ **Ek task pehle se chal raha!**\n\n"
                "❌ Cancel karo ya wait karo."
            )
            return
    
    if message.reply_to_message and message.reply_to_message.document:
        logger.info(f"📎 File detected in reply")
        file_msg = message.reply_to_message
        file_name = file_msg.document.file_name
        
        if not (file_name.endswith('.zip') or file_name.endswith('.pdf')):
            logger.warning(f"❌ Invalid file type: {file_name}")
            await message.reply_text("❌ **Sirf ZIP ya PDF!**")
            return
        
        logger.info(f"✅ Valid file: {file_name}")
        confirm_msg = await message.reply_text(
        f"📂 **File:** **{file_name}**\n"
        f"📊 **Size:** **{file_msg.document.file_size / (1024*1024):.2f} MB**\n\n"
        f"🎬 **Do you want to convert this to a video?**",
         reply_markup=confirm_keyboard(user_id)
)
        
        user_file_data[user_id] = {"file_message": file_msg, "confirm_message": confirm_msg}
        logger.info(f"✅ Confirmation sent to user {user_id}")
    
    else:
        if not PYROMOD_AVAILABLE:
            logger.error("❌ Pyromod not available")
            await message.reply_text(
                "❌ **Pyromod not available!**\n\n"
                "📂 File bhejo aur reply mein `/manga` likho."
            )
            return
        
        logger.info(f"⏳ Waiting for file from user {user_id}")
        ask_msg = await message.reply_text("📂 **ZIP/PDF bhejo...**\n\n⏳ 120 sec")
        
        try:
            file_msg: Message = await app.listen(user_id, timeout=120, filters=filters.document)
            
            file_name = file_msg.document.file_name
            if not (file_name.endswith('.zip') or file_name.endswith('.pdf')):
                logger.warning(f"❌ Invalid file: {file_name}")
                await file_msg.reply_text("❌ **Sirf ZIP/PDF!**")
                return
            
            logger.info(f"✅ File received: {file_name}")
            await ask_msg.delete()
            
            confirm_msg = await file_msg.reply_text(
                f"📂 **File:** `{file_name}`\n"
                f"📊 Size: `{file_msg.document.file_size / (1024*1024):.2f} MB`\n\n"
                f"🎬 **Convert karu?**",
                reply_markup=confirm_keyboard(user_id)
            )
            
            user_file_data[user_id] = {"file_message": file_msg, "confirm_message": confirm_msg}
        
        except asyncio.TimeoutError:
            logger.warning(f"⏰ File upload timeout for user {user_id}")
            await ask_msg.edit_text("⏰ **Timeout!** Dobara `/manga` bhejo.")

# ═══════════════════════════════════════════════════════════════════
# 📞 CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════════

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    
    logger.info(f"🔘 Callback: {user_id} → {data}")
    
    # ═══ CONFIRMATION ═══
    if data.startswith("confirm_yes_"):
        logger.info(f"✅ User {user_id} confirmed processing")
        target_user = int(data.split("_")[2])
        if user_id != target_user:
            await callback.answer("❌ Tumhara nahi!", show_alert=True)
            return
        
        if user_id not in user_file_data:
            await callback.answer("❌ Data lost!", show_alert=True)
            return
        
        file_msg = user_file_data[user_id]["file_message"]
        confirm_msg = user_file_data[user_id]["confirm_message"]
        
        await confirm_msg.delete()
        
        status_msg = await file_msg.reply_text("📥 **Downloading...**")
        
        try:
            logger.info(f"📥 Downloading file for user {user_id}")
            file_path = await file_msg.download()
            logger.info(f"✅ File downloaded: {file_path}")
            
            await status_msg.edit_text("✅ **Downloaded!** Processing...")
            
            CANCEL_TASKS[user_id] = False
            user_active_tasks[user_id] = {"file_path": file_path, "start_time": time.time()}
            processing_queue.append(user_id)
            
            logger.info(f"🎬 Starting processing for user {user_id}")
            await process_manga_video(client, file_msg, user_id, file_path, status_msg)
        
        except Exception as e:
            logger.error(f"❌ Processing error for user {user_id}: {e}")
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        
        finally:
            if user_id in user_file_data:
                del user_file_data[user_id]
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
            if user_id in processing_queue:
                processing_queue.remove(user_id)
    
    elif data.startswith("confirm_no_"):
        logger.info(f"❌ User {user_id} cancelled")
        target_user = int(data.split("_")[2])
        if user_id != target_user:
            await callback.answer("❌ Tumhara nahi!", show_alert=True)
            return
        
        if user_id in user_file_data:
            await user_file_data[user_id]["confirm_message"].delete()
            del user_file_data[user_id]
        
        await callback.answer("❌ Cancelled!", show_alert=True)
    
    # ═══ SETTINGS ═══
    elif data == "start":
        caption = f"Namaste {callback.from_user.first_name}! 👋\n\n"
        caption += "🎬 **Main Manga/Comic ko YouTube Video mein convert karta hoon!**\n\n"
        caption += "📖 **Kaise use karein:**\n"
        caption += "1️⃣ ZIP ya PDF file bhejo\n"
        caption += "2️⃣ File ko reply mein `/manga` command use karo\n"
        caption += "3️⃣ Confirmation button dabao\n"
        caption += "4️⃣ Video ready! 🎉\n\n"
        caption += "⚙️ **Commands:**\n"
        caption += "• `/manga` - Video processing\n"
        caption += "• `/ping` - Bot status\n"
        caption += "• `/help` - Complete guide\n\n"
        caption += "✨ **Powered By @RJGamer07**"
        
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("start"), caption=caption),
            reply_markup=start_keyboard()
        )
    
    elif data == "settings":
        settings = get_user_settings(user_id)
        quality_label = QUALITY_PRESETS[settings["quality"]]["label"]
        gender = "{F}" if "Swara" in settings["voice"] else "{M}"
        caption = (
            "⚙️ **YOUR CURRENT SETTINGS** ⚙️\n\n"
            f"🎥 Quality: `{quality_label}`\n"
            f"🗣️ Voice: `{settings['voice']}` {gender}\n"
            f"🎵 BGM: `{settings['bgm_volume']}%`\n"
            f"🌫️ Blur: `{settings['blur_radius']}`\n"
            f"📺 YouTube: `{'Connected' if settings['youtube_connected'] else 'Not Connected'}`\n\n"
            "👇 **Select option to change:**"
        )
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("settings"), caption=caption),
            reply_markup=settings_keyboard()
        )
    
    elif data == "quality":
        settings = get_user_settings(user_id)
        current = QUALITY_PRESETS[settings["quality"]]["label"]
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("quality"), caption=f"🎥 **Select Video Quality:**\n\nCurrent: `{current}`"),
            reply_markup=quality_keyboard()
        )
    
    elif data.startswith("set_quality_"):
        quality = data.replace("set_quality_", "")
        update_user_setting(user_id, "quality", quality)
        logger.info(f"⚙️ User {user_id} changed quality to {quality}")
        await callback.answer(f"✅ {QUALITY_PRESETS[quality]['label']}", show_alert=True)
        await callback_handler(client, CallbackQuery(id=callback.id, from_user=callback.from_user, message=callback.message, data="settings"))
    
    elif data == "voice":
        settings = get_user_settings(user_id)
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("voice"), caption=f"🗣️ **Select Narration Voice:**\n\nCurrent: `{settings['voice']}`"),
            reply_markup=voice_keyboard()
        )
    
    elif data.startswith("set_voice_"):
        voice_type = data.replace("set_voice_", "")
        voice_code = VOICE_PRESETS[voice_type]["code"]
        update_user_setting(user_id, "voice", voice_code)
        logger.info(f"⚙️ User {user_id} changed voice to {voice_code}")
        await callback.answer(f"✅ {VOICE_PRESETS[voice_type]['label']}", show_alert=True)
        await callback_handler(client, CallbackQuery(id=callback.id, from_user=callback.from_user, message=callback.message, data="settings"))
    
    elif data == "custom_voice":
        await callback.answer("Feature coming soon!", show_alert=True)
    
    elif data == "bgm":
        settings = get_user_settings(user_id)
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("bgm"), caption=f"🎵 **Select Background Music Volume:**\n\nCurrent: `{settings['bgm_volume']}%`"),
            reply_markup=bgm_keyboard()
        )
    
    elif data.startswith("set_bgm_"):
        volume = int(data.replace("set_bgm_", ""))
        update_user_setting(user_id, "bgm_volume", volume)
        await callback.answer(f"✅ BGM: {volume}%", show_alert=True)
        await callback_handler(client, CallbackQuery(id=callback.id, from_user=callback.from_user, message=callback.message, data="settings"))
    
    elif data == "custom_bgm":
        await callback.answer("Feature coming soon!", show_alert=True)
    
    elif data == "delete_bgm":
        update_user_setting(user_id, "custom_bgm_file_id", None)
        await callback.answer("🗑️ Deleted!", show_alert=True)
    
    elif data == "blur":
        settings = get_user_settings(user_id)
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("blur"), caption=f"🌫️ **Select Background Blur Radius:**\n\nCurrent: `{settings['blur_radius']}` (Default: 9)"),
            reply_markup=blur_keyboard()
        )
    
    elif data.startswith("set_blur_"):
        radius = int(data.replace("set_blur_", ""))
        update_user_setting(user_id, "blur_radius", radius)
        await callback.answer(f"✅ Blur: {radius}", show_alert=True)
        await callback_handler(client, CallbackQuery(id=callback.id, from_user=callback.from_user, message=callback.message, data="settings"))
    
    elif data == "reset_settings":
        reset_user_settings(user_id)
        logger.info(f"🔄 User {user_id} reset settings")
        await callback.answer("✅ Settings reset!", show_alert=True)
        await callback_handler(client, CallbackQuery(id=callback.id, from_user=callback.from_user, message=callback.message, data="settings"))
    
    elif data == "youtube":
        await callback.answer("YouTube upload feature limited users ke liye!", show_alert=True)
    
    elif data == "about":
        about_text = (
            "╔════════════════════╗\n"
            "║ ℹ️ **ABOUT** ║\n"
            "╚════════════════════╝\n\n"
            "🤖 **Manga Video Bot**\n"
            "🎬 Manga/Comics → YouTube\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ **FEATURES**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "• AI script (Gemini-3.5-flash)\n"
            "• Professional text removal\n"
            "• Hindi voiceover (TTS)\n"
            "• Quality: 360p - 4K\n"
            "• BGM & Blur effects\n"
            "• Real-time progress\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👨‍💻 **Developer:** @RJGamer07\n"
            f"📢 **Updates:** @auto_uploading\n"
            f"💬 **Support:** @Auto_uploading_support_group\n\n"
            f"🖥️ **VPS:** **{CPU_CORES}** cores, **{TOTAL_RAM:.1f}GB** RAM\n\n"
            "✨ **Version:** 1.9.4.3"
        )
        await callback.message.edit_media(
            InputMediaPhoto(media=get_random_image("about"), caption=about_text),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="start")]])
        )

    
    elif data.startswith("refresh_"):
        await callback.answer("🔄 Refreshed!", show_alert=False)
    
    elif data.startswith("cancel_"):
        target_user = int(data.replace("cancel_", ""))
        if user_id != target_user:
            await callback.answer("❌ Tumhara nahi!", show_alert=True)
            return
        
        logger.info(f"❌ User {user_id} cancelled task")
        CANCEL_TASKS[user_id] = True
        
        user_work_dir = f"user_data/{user_id}"
        if os.path.exists(user_work_dir):
            shutil.rmtree(user_work_dir)
        
        if user_id in user_active_tasks:
            del user_active_tasks[user_id]
        
        if user_id in processing_queue:
            processing_queue.remove(user_id)
        
        await callback.message.edit_text(
            "❌ **Cancelled!**\n\nFiles deleted.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="start")]])
        )
        await callback.answer("✅ Cancelled!", show_alert=True)

# ═══════════════════════════════════════════════════════════════════
# 🎬 PROCESSING FUNCTIONS (COMPLETE - AS PER ORIGINAL CODE)
# ═══════════════════════════════════════════════════════════════════

def extract_media(file_path, output_folder):
    logger.info(f"📦 Extracting media from: {file_path}")
    
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    image_paths = []
    
    if file_path.endswith('.zip'):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(output_folder)
        
        for root, dirs, files in os.walk(output_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    src = os.path.join(root, file)
                    dst = os.path.join(output_folder, file)
                    if src != dst:
                        shutil.move(src, dst)
                    image_paths.append(dst)
    
    elif file_path.endswith('.pdf'):
        pages = convert_from_path(file_path, 200)
        for i, page in enumerate(pages):
            img_path = os.path.join(output_folder, f"page_{i+1:03d}.jpg")
            page.save(img_path, 'JPEG')
            image_paths.append(img_path)
    
    logger.info(f"✅ Extracted {len(image_paths)} images")
    return sorted(image_paths)

async def generate_manga_script_async(image_folder, user_id):
    logger.info(f"🤖 Generating AI script for user {user_id}")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    image_files = sorted([f for f in os.listdir(image_folder)
                         if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
    
    if not image_files:
        logger.error("❌ No images found")
        return None
    
    image_paths = [os.path.join(image_folder, f) for f in image_files]
    pil_images = [Image.open(img) for img in image_paths]
    
    prompt = """
You are an expert YouTube Manga/Comic Explainer AI. I am providing you with pages from a Manga/Comic chapter.

    **CRITICAL CONTENT FILTERS & RULES:**
    1. **INTERNET VERIFICATION:** Use your Google Search tool to find the ACTUAL character names, their current aliases (e.g., if a character changed their name), and the chapter context.
    2. **ATTACKS vs NAMES (CRITICAL):** Manga pages often have huge text for ATTACK NAMES (e.g., 'BUTTERFLY HEEL DROP', 'TIGER FIST'). DO NOT confuse these with character names! Explain them as attacks done by the character.
    3. **UNKNOWN/CHANGING CHARACTERS:** If you don't know a character's name, DO NOT guess wrong names. Describe them by their physical appearance instead (e.g., 'तितली के पंखों वाला मॉन्स्टर').
    4. **NSFW Detection:** Analyze if this manga contains extreme explicit adult/NSFW content. If YES, return ONLY: {{"nsfw_detected": true}}
    5. **Ecchi/Borderline Pages:** Do not skip borderline pages, explain them using funny, safe, family-friendly Hindi language. We cannot skip panels because it breaks video sync.
    6. **Tone & Narration Style:** The tone should be highly energetic and engaging, narrated by a confident {narrator_gender}.
       - **DO NOT** use unnatural repetitive phrases like "मैं देख रहा हूँ" or "मैं बता रही हूँ" for every action. Tell the story directly and naturally.
    7. **Language:** Write in Hindi (Devanagari script), but use common English anime words in Hindi script (e.g., 'मैजिक', 'अटैक').

    **Output Format:**
    Return EXACTLY as a JSON object:
    {{
      "nsfw_detected": false,
      "title": "Catchy YouTube video title in Hindi (max 100 characters)",
      "description": "Engaging 2-line description in Hindi for YouTube",
      "chapter_summary": "A 2-line brief about what happens in these pages.",
      "script": [
        {{
          "page_number": 1,
          "filename": "exact_image_filename.jpg",
          "narration_hindi": "इस पेज पर जो एक्शन हो रहा है, उसका नेचुरल एक्सप्लेनेशन..."
        }}
      ]
    }}
    """

    contents = [prompt] + pil_images
    
    try:
        response = client.models.generate_content(model='gemini-3.5-flash', contents=contents)
        raw_text = response.text.strip()
        
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3]
        
        script_data = json.loads(raw_text)
        
        if script_data.get("nsfw_detected", False):
            logger.warning("⚠️ NSFW content detected")
            return {"nsfw_detected": True}
        
        if 'title' not in script_data:
            script_data['title'] = "Manga Video"
        if 'description' not in script_data:
            script_data['description'] = "Amazing manga chapter!"
        
        logger.info(f"✅ Script generated with {len(script_data.get('script', []))} panels")
        return script_data
    
    except Exception as e:
        logger.error(f"❌ Gemini Error: {e}")
        return None

def clean_text_for_tts(text):
    text = re.sub(r'\.{2,}', ' ', text)
    text = re.sub(r',+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

async def generate_audio_fixed(script_data, output_folder, voice):
    logger.info(f"🎤 Generating audio with voice: {voice}")
    
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    audio_data = []
    
    for panel in script_data['script']:
        page_num = panel['page_number']
        text = panel.get('narration_hindi', panel.get('narration', ''))
        text = clean_text_for_tts(text)
        
        audio_file = os.path.join(output_folder, f"audio_{page_num:03d}.mp3")
        
        # ← ADD RETRY LOGIC
        max_retries = 3
        for attempt in range(max_retries):
            try:
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(audio_file)
                await asyncio.sleep(0.5)  # Small delay between requests
                break  # Success, exit retry loop
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ TTS failed after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"⚠️ TTS attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(2)  # Wait before retry
        
        audio_data.append({"page_number": page_num, "audio_path": audio_file})
    
    logger.info(f"✅ Generated {len(audio_data)} audio clips")
    return audio_data

def create_video_sync(script_data, audio_data, cleaned_folder, cleaned_files, output_path, user_settings):
    logger.info(f"🎬 Rendering video...")
    
    quality = user_settings["quality"]
    blur_radius = user_settings["blur_radius"]
    
    W, H = QUALITY_PRESETS[quality]["resolution"]
    fps = QUALITY_PRESETS[quality]["fps"]
    bitrate = QUALITY_PRESETS[quality]["bitrate"]
    
    AUDIO_GAP = 0.15
    FADE_TIME = 0.15
    
    video_clips = []
    
    for i, item in enumerate(script_data['script']):
        if i >= len(cleaned_files):
            continue
        
        cleaned_filename = cleaned_files[i]
        img_path = os.path.join(cleaned_folder, cleaned_filename)
        
        if not os.path.exists(img_path):
            continue
        
        audio_path = audio_data[i]['audio_path']
        audio_clip = AudioFileClip(audio_path)
        vid_duration = audio_clip.duration + AUDIO_GAP
        
        # Background with blur
        bg_img = Image.open(img_path).convert('RGB')
        bg_resized = bg_img.resize((W, H))
        enhancer = ImageEnhance.Brightness(bg_resized)
        bg_dark = enhancer.enhance(0.65)
        bg_blur = bg_dark.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        bg_array = np.array(bg_blur)
        bg_clip = ImageClip(bg_array).set_duration(vid_duration)
        
        # Foreground with scroll effect
        fg_img = Image.open(img_path).convert('RGB')
        fg_array = np.array(fg_img)
        fg_clip = ImageClip(fg_array)
        
        center_width = int(W * 0.6)
        
        if fg_clip.h / fg_clip.w > H / W:
            fg_clip = fg_clip.resize(width=center_width)
            max_y = max(0, fg_clip.h - H)
            
            if max_y > 0:
                def pos_tall(t, my=max_y, vd=vid_duration):
                    progress = t / vd
                    y = -int(my * progress)
                    return ('center', y)
                fg_clip = fg_clip.set_position(pos_tall)
            else:
                fg_clip = fg_clip.set_position('center')
        else:
            fg_clip = fg_clip.resize(height=int(H * 0.8))
            max_x = max(0, fg_clip.w - center_width)
            
            if max_x > 0:
                def pos_wide(t, mx=max_x, vd=vid_duration):
                    progress = t / vd
                    x = -int(mx * progress)
                    return (x + (W - center_width)//2, 'center')
                fg_clip = fg_clip.set_position(pos_wide)
            else:
                fg_clip = fg_clip.set_position('center')
        
        fg_clip = fg_clip.set_duration(vid_duration)
        
        panel_clip = CompositeVideoClip([bg_clip, fg_clip]).set_duration(vid_duration)
        panel_clip = panel_clip.set_audio(audio_clip)
        
        if i > 0:
            panel_clip = panel_clip.crossfadein(FADE_TIME)
        
        video_clips.append(panel_clip)
        logger.info(f"✅ Rendered panel {i+1}/{len(cleaned_files)}")
    
    final_video = concatenate_videoclips(video_clips, padding=-FADE_TIME, method="compose")
    
    logger.info(f"💾 Writing video file...")
    final_video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate=bitrate,
        threads=MAX_WORKERS,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    )
    
    final_video.close()
    logger.info(f"✅ Video created: {output_path}")

async def process_manga_video(client, message: Message, user_id: int, file_path: str, status_msg: Message):
    logger.info(f"🎬 Starting FULL processing for user {user_id}")
    
    user_settings = get_user_settings(user_id)
    user_work_dir = f"user_data/{user_id}"
    
    if os.path.exists(user_work_dir):
        shutil.rmtree(user_work_dir)
    os.makedirs(user_work_dir, exist_ok=True)
    
    start_time = time.time()
    
    try:
        # STEP 1: Extract
        if CANCEL_TASKS.get(user_id, False):
            logger.warning(f"❌ Task cancelled by user {user_id}")
            return
        
        logger.info(f"📦 STEP 1: Extracting...")
        await status_msg.edit_text(
            "⏳ **Extracting Files...**\n\n[░░░░░░░░░░] 5%",
            reply_markup=progress_keyboard(user_id)
        )
        
        extracted_folder = os.path.join(user_work_dir, "extracted")
        loop = asyncio.get_event_loop()
        image_paths = await loop.run_in_executor(executor, extract_media, file_path, extracted_folder)
        
        if not image_paths:
            logger.error("❌ No images found")
            await status_msg.edit_text("❌ **No images found!**")
            return
        
        # Page limit check
        if user_id != DEVELOPER_ID and len(image_paths) > MAX_PAGES_LIMIT:
            logger.warning(f"❌ Page limit exceeded: {len(image_paths)} > {MAX_PAGES_LIMIT}")
            await status_msg.edit_text(
                f"❌ **Max {MAX_PAGES_LIMIT} pages!**\n\n"
                f"Your file: {len(image_paths)} pages"
            )
            shutil.rmtree(user_work_dir)
            return
        
        # STEP 2: AI Script
        if CANCEL_TASKS.get(user_id, False):
            return
        
        logger.info(f"🤖 STEP 2: Generating AI script...")
        await status_msg.edit_text(
            "⏳ **Generating AI Script...**\n\n[██░░░░░░░░] 20%",
            reply_markup=progress_keyboard(user_id)
        )
        
        script_data = await generate_manga_script_async(extracted_folder, user_id)
        
        if not script_data:
            logger.error("❌ Script generation failed")
            await status_msg.edit_text("❌ **Script generation failed!**")
            return
        
        if script_data.get("nsfw_detected", False):
            strike_count = add_strike(user_id)
            logger.warning(f"⚠️ NSFW detected! Strike {strike_count} for user {user_id}")
            if strike_count >= 2:
                await status_msg.edit_text("🚫 **50 HOURS BAN!**\n\nNSFW content (2 strikes)")
            else:
                await status_msg.edit_text("⚠️ **WARNING! Strike 1**\n\nNSFW detected.")
            shutil.rmtree(user_work_dir)
            return
        
        # STEP 3: Text Removal (Simulated - copy files)
        if CANCEL_TASKS.get(user_id, False):
            return
        
        logger.info(f"🧹 STEP 3: Cleaning panels... Beta")
        await status_msg.edit_text(
            "⏳ **Cleaning Panels (AI)...**\n\n[████░░░░░░░] 40%",
            reply_markup=progress_keyboard(user_id)
        )
        
        cleaned_folder = os.path.join(extracted_folder, "cleaned")
        os.makedirs(cleaned_folder, exist_ok=True)
        
        cleaned_files = []
        for img_file in sorted(os.listdir(extracted_folder)):
            if img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                src = os.path.join(extracted_folder, img_file)
                name, ext = os.path.splitext(img_file)
                dst_name = f"{name}_clean{ext}"
                dst = os.path.join(cleaned_folder, dst_name)
                shutil.copy(src, dst)
                cleaned_files.append(dst_name)
        
        # STEP 4: Audio Generation
        if CANCEL_TASKS.get(user_id, False):
            return
        
        logger.info(f"🎤 STEP 4: Generating audio...")
        await status_msg.edit_text(
            "⏳ **Generating Hindi Voiceover...**\n\n[██████░░░░] 60%",
            reply_markup=progress_keyboard(user_id)
        )
        
        audio_folder = os.path.join(user_work_dir, "audio")
        audio_data = await generate_audio_fixed(script_data, audio_folder, user_settings["voice"])
        
        # STEP 5: Video Rendering
        if CANCEL_TASKS.get(user_id, False):
            return
        
        logger.info(f"🎬 STEP 5: Rendering video...")
        await status_msg.edit_text(
            "⏳ **Rendering Video (this may take time)...**\n\n[███████░░░] 70%",
            reply_markup=progress_keyboard(user_id)
        )
        
        output_video = os.path.join(user_work_dir, f"output_{user_id}.mp4")
        
        await loop.run_in_executor(
            executor,
            create_video_sync,
            script_data,
            audio_data,
            cleaned_folder,
            cleaned_files,
            output_video,
            user_settings
        )
        
        # STEP 6: Upload
        if CANCEL_TASKS.get(user_id, False):
            return
        
        logger.info(f"📤 STEP 6: Uploading video...")
        await status_msg.edit_text(
            "⏳ **Uploading Video...**\n\n[█████████░] 90%",
            reply_markup=progress_keyboard(user_id)
        )
        
        total_time = int(time.time() - start_time)
        minutes = total_time // 60
        seconds = total_time % 60
        
        video_clip = VideoFileClip(output_video)
        duration = int(video_clip.duration)
        vid_minutes = duration // 60
        vid_seconds = duration % 60
        video_clip.close()
        
        caption = (
            f"🎬 **Chapter:** {script_data.get('chapter_summary', 'Manga Video')}\n"
            f"⏱️ **Duration:** {vid_minutes}:{vid_seconds:02d} min\n"
            f"⚙️ **Quality:** {QUALITY_PRESETS[user_settings['quality']]['label']}\n"
            f"⏳ **Processing Time:** {minutes}:{seconds:02d} min\n\n"
        )
        
        if 'title' in script_data:
            caption += f"**Title:** {script_data['title']}\n\n"
        
        if 'description' in script_data:
            caption += f"**Description:** {script_data['description']}\n\n"
        
        caption += "✨ **Developed by @RJGamer07**"
        
        logger.info(f"📤 Uploading video for user {user_id}")
        await message.reply_video(
            video=output_video,
            caption=caption,
            supports_streaming=True,
            width=QUALITY_PRESETS[user_settings['quality']]['resolution'][0],
            height=QUALITY_PRESETS[user_settings['quality']]['resolution'][1]
        )
        
        logger.info(f"✅ Processing complete for user {user_id}! Time: {minutes}m {seconds}s")
        
        await asyncio.sleep(2)
        await status_msg.delete()
        
        shutil.rmtree(user_work_dir)
        
        if user_id in CANCEL_TASKS:
            del CANCEL_TASKS[user_id]
    
    except Exception as e:
        logger.error(f"❌ Processing error for user {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ **Error:**\n\n`{str(e)}`")
        if os.path.exists(user_work_dir):
            shutil.rmtree(user_work_dir)

# ═══════════════════════════════════════════════════════════════════
# 🚀 BOT START
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.start_time = time.time()
    print("\n" + "="*70)
    print("🤖 MANGA VIDEO BOT - COMPLETE + DEBUG EDITION v4.0")
    print("="*70)
    print(f"💻 CPU: {CPU_CORES} cores")
    print(f"🧠 RAM: {TOTAL_RAM:.2f} GB")
    print(f"⚙️  Workers: {MAX_WORKERS}")
    print("="*70)
    print(f"🎯 Mode: {'GROUP ONLY' if GROUP_MODE else 'DM ONLY'}")
    if GROUP_MODE:
        print(f"🆔 Target Group: {TARGET_GROUP_ID}")
    print(f"📄 Max Pages: {MAX_PAGES_LIMIT}")
    print(f"🔄 Queue: {MAX_QUEUE_SIZE}")
    print("="*70)
    print("🚀 Bot is LIVE and listening for messages!")
    print("="*70 + "\n")
    
    app.run()
