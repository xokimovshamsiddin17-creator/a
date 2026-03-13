import telebot
import yt_dlp
import os
import json
import re
import requests
from datetime import datetime
from telebot import types
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = telebot.TeleBot(API_KEY)

# --- Ensure Directories ---
for folder in ["data", "step", "temp"]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- Helper Functions ---
def read_file(path, default=""):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return default
    return default

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def append_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(content + "\n")

def is_admin(user_id):
    admins = read_file("data/admins.txt").splitlines()
    return str(user_id) == str(ADMIN_ID) or str(user_id) in [a.strip() for a in admins]

# --- Core Downloader Engine ---
def download_instagram_media(url):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'extract_flat': False, # We need links, but not necessarily files
        'force_generic_extractor': False,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'logtostderr': False,
        'skip_download': True, # Crucial for speed: don't download the file locally
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info once
            info = ydl.extract_info(url, download=False)
            if not info:
                return {'success': False, 'error': 'No info found'}
                
            media_results = []
            
            # Handle Carousel/Playlist
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        media_results.append({
                            'url': entry.get('url'),
                            'type': 'video' if entry.get('ext') == 'mp4' else 'image'
                        })
            else:
                media_results.append({
                    'url': info.get('url'),
                    'type': 'video' if info.get('ext') == 'mp4' else 'image'
                })
            
            return {
                'success': True,
                'media': [m for m in media_results if m['url']],
                'title': info.get('title', 'Instagram Media')
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# --- Keyboards ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Statistika")
    if is_admin(ADMIN_ID): # Placeholder for simplicity
        markup.row("👨🏻‍💻 Boshqaruv paneli")
    return markup

def get_admin_panel():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📈 Statistika", "📝 Habar yuborish")
    markup.row("📢 Kanallar", "🔐 Blok tizimi")
    markup.row("◀️ Ortga")
    return markup

# --- Handlers ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.from_user.id
    cid = message.chat.id
    
    # Save user to stats
    stats = read_file("data/statistika.txt")
    if str(uid) not in stats:
        append_file("data/statistika.txt", str(uid))
        
    welcome_text = (
        "<b>🌟 Xush kelibsiz!</b>\n\n"
        "Men Instagramdan video va rasmlarni yuklab beruvchi botman.\n\n"
        "🔗 <i>Menga Reels yoki Post havolasini yuboring...</i>"
    )
    bot.send_message(cid, welcome_text, parse_mode='HTML', reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text == "◀️ Ortga")
def back_main(message):
    start_handler(message)

# --- Simple Admin Features ---
@bot.message_handler(func=lambda m: m.text == "📊 Statistika" or m.text == "📈 Statistika")
def stats_msg(message):
    stats = read_file("data/statistika.txt").splitlines()
    count = len([s for s in stats if s.strip()])
    bot.send_message(message.chat.id, f"<b>👥 Foydalanuvchilar:</b> {count} ta", parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "👨🏻‍💻 Boshqaruv paneli")
def admin_panel_msg(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "<b>⚙ Admin panel:</b>", parse_mode='HTML', reply_markup=get_admin_panel())

# --- Instagram Handler ---
@bot.message_handler(func=lambda m: "instagram.com" in m.text)
def handle_instagram(message):
    cid = message.chat.id
    text = message.text
    
    # Extract URL using regex
    match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories|reels)/[\w\-]+)', text)
    if not match:
        return
        
    url = match.group(1)
    wait_msg = bot.send_message(cid, "<b>💎 Yuklanmoqda...</b>", parse_mode='HTML')
    
    result = download_instagram_media(url)
    
    try:
        bot.delete_message(cid, wait_msg.message_id)
    except:
        pass
        
    if result['success']:
        media_list = result['media']
        caption = f"<b>✅ Yuklab olindi!</b>\n\n<blockquote>🔗 {url}</blockquote>"
        
        # Send first 2 media items (common for carousels)
        for i, item in enumerate(media_list[:2]):
            try:
                if item['type'] == 'video':
                    bot.send_video(cid, item['url'], caption=caption if i == 0 else None, parse_mode='HTML')
                else:
                    bot.send_photo(cid, item['url'], caption=caption if i == 0 else None, parse_mode='HTML')
            except Exception as e:
                # If direct URL sending fails, the bot could try downloading and uploading,
                # but for simplicity and speed, we provide the link as fallback.
                bot.send_message(cid, f"<b>⚠️ Media yuborishda muammo bo'ldi.</b>\n<a href='{item['url']}'>🔗 Mana bu yerda ko'rishingiz mumkin</a>", parse_mode='HTML')
    else:
        bot.send_message(cid, "<b>❌ Xatolik yuz berdi!</b>\nIltimos, havola to'g'ri ekanligini tekshiring.", parse_mode='HTML')

# --- Start Bot ---
if __name__ == "__main__":
    print("Bot is running with yt-dlp...")
    bot.infinity_polling()
