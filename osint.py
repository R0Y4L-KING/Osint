# ============ FILE KA NAAM: osint_bot.py ============

import logging
from aiohttp import web
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
import requests
import json
from datetime import datetime
import asyncio
import random
import string
import re
import os

# ============ CONFIGURATION ============
# Environment variables se read karo (Render pe env vars set karo)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "5350926991").split(",") if x.strip()]
API_URL = os.environ.get("API_URL", "https://dark-info.site/test/api.php?key=Demo&num={}")
API_KEY = os.environ.get("API_KEY", "Demo")



async def safe_edit(query, text, reply_markup=None, parse_mode='Markdown'):
    """Safely edit message - ignore 'not modified' errors."""
    try:
        await safe_edit(query, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        if "not modified" in str(e).lower():
            pass
        else:
            try:
                await safe_edit(query, text, reply_markup=reply_markup)
            except:
                pass


def start_keepalive_server():
    """Render Web Service ko port chahiye, isliye ek simple HTTP server chalate hain."""
    async def health(request):
        return web.Response(text="Bot is running! Developed by @ModAppsKing")
    
    app_web = web.Application()
    app_web.router.add_get("/", health)
    app_web.router.add_get("/health", health)
    
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app_web, host="0.0.0.0", port=port, print=lambda *a: None)


def run_keepalive_in_thread():
    """Keepalive server ko alag thread me chalao."""
    server_thread = threading.Thread(target=start_keepalive_server, daemon=True)
    server_thread.start()


def init_db():
    if os.path.exists('osint_bot.db'):
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        try:
            c.execute("SELECT phone_number FROM searches LIMIT 1")
        except sqlite3.OperationalError:
            conn.close()
            os.remove('osint_bot.db')
            print("Old database deleted, creating new one...")
        else:
            conn.close()
    
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        credits INTEGER DEFAULT 5, 
        is_banned BOOLEAN DEFAULT FALSE, 
        referred_by INTEGER, 
        joined_date TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, 
        phone_number TEXT, 
        result_data TEXT, 
        search_date TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY, 
        credits INTEGER, 
        used_by INTEGER, 
        is_used BOOLEAN DEFAULT FALSE, 
        created_by INTEGER, 
        created_date TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )''')
    
    for admin_id in ADMIN_IDS:
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
    
    conn.commit()
    conn.close()
    print("Database setup complete!")

def add_credits(user_id, amount):
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    print(f"Added {amount} credits to user {user_id}")

def deduct_credit(user_id):
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0] > 0:
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET credits = credits - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        print(f"Deducted 1 credit from user {user_id}. Remaining: {result[0]-1}")
        return True
    print(f"Failed to deduct credit from user {user_id}. Credits: {result[0] if result else 0}")
    return False

def get_user_credits(user_id):
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    credits = result[0] if result else 0
    print(f"User {user_id} has {credits} credits")
    return credits

def get_all_users():
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned = FALSE")
    users = c.fetchall()
    conn.close()
    return [user[0] for user in users]

def generate_redeem_code(credits, admin_id):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO redeem_codes (code, credits, created_by, created_date) VALUES (?, ?, ?, ?)",
             (code, credits, admin_id, datetime.now()))
    conn.commit()
    conn.close()
    print(f"Generated code: {code} for {credits} credits")
    return code

def redeem_code(user_id, code):
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("SELECT credits, is_used FROM redeem_codes WHERE code = ?", (code,))
    result = c.fetchone()
    
    if result:
        credits = result[0]
        is_used = result[1]
        
        if not is_used:
            c.execute("UPDATE redeem_codes SET is_used = TRUE, used_by = ? WHERE code = ?", (user_id, code))
            c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (credits, user_id))
            conn.commit()
            conn.close()
            print(f"User {user_id} redeemed code {code} for {credits} credits")
            return credits
        else:
            print(f"Code {code} already used")
    else:
        print(f"Code {code} not found")
    
    conn.close()
    return None

def normalize_phone(phone):
    # Remove +, spaces, dashes, brackets
    cleaned = re.sub(r'[\s+\-()]', '', phone)
    # Case 1: 12 digits starting with 91 (e.g. 919997378455)
    if re.match(r'^91[6-9]\d{9}$', cleaned):
        return cleaned
    # Case 2: 10 digits (e.g. 9997378455)
    if re.match(r'^[6-9]\d{9}$', cleaned):
        return '91' + cleaned
    # Case 3: 11 digits starting with 0 (e.g. 09997378455)
    if re.match(r'^0[6-9]\d{9}$', cleaned):
        return '91' + cleaned[1:]
    return None

def format_api_response(raw_text):
    """Parse the API text response and format it into clean structured blocks."""
    try:
        lines = [ln.strip() for ln in raw_text.split('\n') if ln.strip()]
        if not lines:
            return None
        
        # Identify section markers
        sections = []
        current_section = None
        current_lines = []
        
        for ln in lines:
            lower = ln.lower()
            if 'main' in lower and 'details' in lower:
                if current_section:
                    sections.append((current_section, current_lines))
                current_section = 'main'
                current_lines = []
            elif 'source-2' in lower or 'source2' in lower:
                if current_section:
                    sections.append((current_section, current_lines))
                current_section = 'source2'
                current_lines = []
            elif 'source-3' in lower or 'source3' in lower:
                if current_section:
                    sections.append((current_section, current_lines))
                current_section = 'source3'
                current_lines = []
            elif current_section is None:
                # Header line before first section marker
                continue
            else:
                current_lines.append(ln)
        
        if current_section:
            sections.append((current_section, current_lines))
        
        if not sections:
            return None
        
        output_parts = []
        
        section_emojis = {
            'main': '📋',
            'source2': '🔗',
            'source3': '📎',
        }
        section_names = {
            'main': 'MAIN DETAILS',
            'source2': 'SOURCE 2',
            'source3': 'SOURCE 3',
        }
        
        for sec_name, sec_lines in sections:
            emoji = section_emojis.get(sec_name, '📄')
            display = section_names.get(sec_name, sec_name.upper())
            
            if sec_name == 'main':
                # Split into individual records. A new record starts at "Phone:" (not Phone2/3..)
                records = []
                current_record = []
                
                for ln in sec_lines:
                    # New record starts with "Phone:" exactly (not Phone2, Phone3 etc)
                    if re.match(r'^Phone\s*:', ln):
                        if current_record:
                            records.append(current_record)
                        current_record = [ln]
                    else:
                        if current_record:
                            current_record.append(ln)
                        else:
                            current_record = [ln]
                
                if current_record:
                    records.append(current_record)
                
                output_parts.append(f"\n{emoji} *{display}* ({len(records)} record{'s' if len(records) != 1 else ''} found)\n")
                
                for i, rec in enumerate(records, 1):
                    output_parts.append(f"\n┌─ *Record #{i}* ─────────────")
                    for field in rec:
                        # Format field nicely: "Phone: value" -> "📞 Phone: value"
                        if field.startswith('Phone') or field.startswith('Mobilephone'):
                            field = '📞 ' + field
                        elif field.startswith('Adres'):
                            field = '🏠 ' + field
                        elif field.startswith('Fullname'):
                            field = '👤 ' + field
                        elif field.startswith('Fathername'):
                            field = '👨 ' + field
                        elif field.startswith('Documentnumber'):
                            field = '📄 ' + field
                        elif field.startswith('Region'):
                            field = '📍 ' + field
                        elif field.startswith('Registrationdate'):
                            field = '📅 ' + field
                        output_parts.append(f"│ {field}")
                    output_parts.append("└────────────────────────────")
            
            else:
                # source2 / source3 - show as-is with section header
                output_parts.append(f"\n{emoji} *{display}*\n")
                for ln in sec_lines:
                    if ln.startswith('Mobilephone'):
                        ln = '📞 ' + ln
                    elif ln.startswith('Registrationdate'):
                        ln = '📅 ' + ln
                    output_parts.append(f"• {ln}")
        
        result = '\n'.join(output_parts)
        return result
    except Exception:
        return None


async def search_number(phone, update, context):
    msg = await update.message.reply_text("🔍 **Searching...**\n⏳ Please wait", parse_mode='Markdown')
    
    frames = ["🔍", "🔄", "⏳", "📡", "⚡", "✨", "🎯", "💫"]
    
    for i in range(5):
        await asyncio.sleep(0.5)
        try:
            await msg.edit_text(f"{frames[i % 8]} **Processing Target Number**\n📞 `{phone}`\n{'.' * ((i % 3) + 1)}", parse_mode='Markdown')
        except:
            pass
    
    try:
        url = API_URL.format(phone)
        response = requests.get(url, timeout=20)
        
        if response.status_code == 200:
            raw = response.text.strip()
            if not raw:
                await msg.edit_text("⚠️ **API returned empty response!**\nTry again later or check number.", parse_mode='Markdown')
                return
            
            data = None
            
            # Try parsing as JSON directly
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                pass
            
            # If not JSON, try extracting JSON embedded inside HTML
            if data is None:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        pass
            
            # If still no JSON, extract text from HTML
            if data is None and '<html' in raw.lower():
                # Remove script and style tags
                text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                # Replace <br>, </p>, </div>, </tr>, </li> with newlines
                text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
                text = re.sub(r'</(?:p|div|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
                # Remove all remaining HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Clean up each line
                lines = [ln.strip() for ln in text.split('\n')]
                lines = [ln for ln in lines if ln]
                raw_text = '\n'.join(lines)
                
                if not raw_text:
                    await msg.edit_text("⚠️ **API returned empty HTML page!**\n\nKey may be expired or invalid.\nCheck API key in code.", parse_mode='Markdown')
                    return
                
                # Try to structure the response into nice formatted blocks
                formatted = format_api_response(raw_text)
                
                if formatted:
                    # Split into multiple messages if needed (Telegram 4096 char limit)
                    chunks = [formatted[i:i+3900] for i in range(0, len(formatted), 3900)]
                    first = True
                    for chunk in chunks:
                        if first:
                            await msg.edit_text(chunk, parse_mode='Markdown')
                            first = False
                        else:
                            await update.message.reply_text(chunk, parse_mode='Markdown')
                else:
                    # Fallback: raw text in code block
                    chunks = [raw_text[i:i+3900] for i in range(0, len(raw_text), 3900)]
                    first = True
                    for chunk in chunks:
                        if first:
                            await msg.edit_text(f"📋 **API Response:**\n\n`{chunk}`", parse_mode='Markdown')
                            first = False
                        else:
                            await update.message.reply_text(f"`{chunk}`", parse_mode='Markdown')
                return
            
            if data is None:
                await msg.edit_text(f"⚠️ **Could not parse API response!**\n\nRaw (first 1000 chars):\n`{raw[:1000]}`", parse_mode='Markdown')
                return
            
            if not isinstance(data, dict):
                await msg.edit_text(f"⚠️ **Unexpected API response format!**\n\n`{str(data)[:1000]}`", parse_mode='Markdown')
                return
            
            if 'developer' in data:
                data['developer'] = "@ModAppsKing"
            
            conn = sqlite3.connect('osint_bot.db')
            c = conn.cursor()
            c.execute("INSERT INTO searches (user_id, phone_number, result_data, search_date) VALUES (?, ?, ?, ?)",
                     (update.effective_user.id, phone, json.dumps(data), datetime.now()))
            conn.commit()
            conn.close()
            
            json_output = json.dumps(data, indent=2, ensure_ascii=False)
            
            if len(json_output) > 4096:
                await msg.edit_text(f"```json\n{json_output[:3000]}\n```", parse_mode='Markdown')
                await update.message.reply_text(f"```json\n{json_output[3000:6000]}\n```", parse_mode='Markdown')
            else:
                await msg.edit_text(f"```json\n{json_output}\n```", parse_mode='Markdown')
        else:
            await msg.edit_text(f"⚠️ **API Error:** Status {response.status_code}\n\nResponse: `{response.text[:500]}`", parse_mode='Markdown')
            
    except requests.exceptions.Timeout:
        await msg.edit_text("⚠️ **Connection Timeout!**\nTry again later.", parse_mode='Markdown')
    except requests.exceptions.ConnectionError:
        await msg.edit_text("⚠️ **Connection Error!**\nCheck internet or try again.", parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"⚠️ **Error:** {str(e)}", parse_mode='Markdown')

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_user_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📞 NUMBER TO INFO", callback_data='search')],
        [InlineKeyboardButton("💰 MY CREDITS", callback_data='credits')],
        [InlineKeyboardButton("👥 REFERRAL LINK", callback_data='referral')],
        [InlineKeyboardButton("🎫 REDEEM CODE", callback_data='redeem')],
        [InlineKeyboardButton("📜 MY HISTORY", callback_data='my_history')]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    name = (update.effective_user.first_name or "User")[:15]
    welcome_msg = (
        "🌟 *OSINT PHONE NUMBER BOT* 🌟\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome: *{name}*\n"
        f"💰 Your Credits: *{credits}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Features:*\n"
        "• 10 digit number search (1 credit)\n"
        "• Start with 5 free credits\n"
        "• Refer friends = +5 credits\n"
        "• Redeem codes = free credits\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 Developed by: @ModAppsKing"
    )
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == 'search':
        await safe_edit(query, "📞 **Send 10 digit number**\n\nExamples:\n`8084798673`\n`7991436925`\n`9116224238`\n\n⚠️ No +91 or country code needed\n\n💡 Each search costs 1 credit", parse_mode='Markdown')
        context.user_data['waiting_for_number'] = True
    
    elif query.data == 'credits':
        credits = get_user_credits(user_id)
        await safe_edit(query, f"💰 **Your Credits:** `{credits}`\n\n💡 **How to earn:**\n• Referral: +5 credits\n• Redeem codes: +? credits", parse_mode='Markdown')
    
    elif query.data == 'referral':
        ref_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
        await safe_edit(query, f"👥 **Referral Link**\n\n`{ref_link}`\n\nShare this link with friends!\nYou get 5 credits per referral!", parse_mode='Markdown')
    
    elif query.data == 'redeem':
        await safe_edit(query, "🎫 **Enter Redeem Code**\n\nExample: `ABCD123XYZ`\n\nSend the code you received from admin.", parse_mode='Markdown')
        context.user_data['waiting_for_redeem'] = True
    
    elif query.data == 'my_history':
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("SELECT phone_number, search_date FROM searches WHERE user_id = ? ORDER BY search_date DESC LIMIT 10", (user_id,))
        history = c.fetchall()
        conn.close()
        
        if history:
            text = "📜 **Your Search History**\n\n"
            for phone, date in history[:8]:
                text += f"📞 `{phone}` - {date[:19]}\n"
            await safe_edit(query, text, parse_mode='Markdown')
        else:
            await safe_edit(query, "❌ No search history found!", parse_mode='Markdown')
    
    elif query.data == 'admin' and user_id in ADMIN_IDS:
        keyboard = [
            [InlineKeyboardButton("🎫 GENERATE CODE", callback_data='admin_gen_code')],
            [InlineKeyboardButton("📢 BROADCAST", callback_data='admin_broadcast')],
            [InlineKeyboardButton("👥 ALL USERS", callback_data='admin_users')],
            [InlineKeyboardButton("💰 SEND CREDITS TO ALL", callback_data='admin_send_all')],
            [InlineKeyboardButton("🔍 USER HISTORY", callback_data='admin_user_history')],
            [InlineKeyboardButton("🚫 BAN USER", callback_data='admin_ban')],
            [InlineKeyboardButton("✅ UNBAN USER", callback_data='admin_unban')],
            [InlineKeyboardButton("📊 STATS", callback_data='admin_stats')],
            [InlineKeyboardButton("➕ ADD CREDITS", callback_data='admin_add_credits')],
            [InlineKeyboardButton("🔙 BACK", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(query, "⚙️ **ADMIN PANEL**", reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == 'admin_gen_code' and user_id in ADMIN_IDS:
        await safe_edit(query, "🎫 **Generate Code**\n\nCommand: `/gencode 10`\nExample: `/gencode 25`", parse_mode='Markdown')
    
    elif query.data == 'admin_broadcast' and user_id in ADMIN_IDS:
        await safe_edit(query, "📢 **BROADCAST MODE**\n\nSend the message you want to broadcast to all users.\n\n⚠️ Message will be sent to ALL users!", parse_mode='Markdown')
        context.user_data['broadcast_mode'] = True
    
    elif query.data == 'admin_users' and user_id in ADMIN_IDS:
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, credits, is_banned FROM users ORDER BY joined_date DESC LIMIT 15")
        users = c.fetchall()
        conn.close()
        
        if users:
            text = "👥 **Recent Users**\n\n"
            for user in users:
                status = "🚫 BANNED" if user[3] else "✅ ACTIVE"
                text += f"🆔 `{user[0]}` | {user[2]} credits | {status}\n"
            await safe_edit(query, text, parse_mode='Markdown')
        else:
            await safe_edit(query, "No users found!", parse_mode='Markdown')
    
    elif query.data == 'admin_send_all' and user_id in ADMIN_IDS:
        await safe_edit(query, "💰 **Send Credits to All Users**\n\nCommand: `/sendall credits`\nExample: `/sendall 5`", parse_mode='Markdown')
    
    elif query.data == 'admin_user_history' and user_id in ADMIN_IDS:
        await safe_edit(query, "🔍 **User History**\n\nCommand: `/userhistory user_id`", parse_mode='Markdown')
    
    elif query.data == 'admin_ban' and user_id in ADMIN_IDS:
        await safe_edit(query, "🚫 **Ban User**\n\nCommand: `/ban user_id`", parse_mode='Markdown')
    
    elif query.data == 'admin_unban' and user_id in ADMIN_IDS:
        await safe_edit(query, "✅ **Unban User**\n\nCommand: `/unban user_id`", parse_mode='Markdown')
    
    elif query.data == 'admin_add_credits' and user_id in ADMIN_IDS:
        await safe_edit(query, "➕ **Add Credits**\n\nCommand: `/addcredits user_id credits`\nExample: `/addcredits 8162909171 10`", parse_mode='Markdown')
    
    elif query.data == 'admin_stats' and user_id in ADMIN_IDS:
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
        banned_users = c.fetchone()[0]
        c.execute("SELECT SUM(credits) FROM users")
        total_credits = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM searches")
        total_searches = c.fetchone()[0]
        conn.close()
        
        text = f"📊 **Bot Statistics**\n\n👥 Total Users: {total_users}\n🚫 Banned: {banned_users}\n💰 Total Credits: {total_credits}\n🔍 Total Searches: {total_searches}"
        await safe_edit(query, text, parse_mode='Markdown')
    
    elif query.data == 'back_to_menu':
        await show_menu(query, user_id)

async def show_menu(query, user_id):
    credits = get_user_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📞 NUMBER TO INFO", callback_data='search')],
        [InlineKeyboardButton("💰 MY CREDITS", callback_data='credits')],
        [InlineKeyboardButton("👥 REFERRAL LINK", callback_data='referral')],
        [InlineKeyboardButton("🎫 REDEEM CODE", callback_data='redeem')],
        [InlineKeyboardButton("📜 MY HISTORY", callback_data='my_history')]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await safe_edit(query, f"🌟 **MAIN MENU**\n\n💰 Credits: {credits}", reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user is banned
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        await update.message.reply_text("❌ **You are banned!**", parse_mode='Markdown')
        return
    
    # BROADCAST MODE
    if context.user_data.get('broadcast_mode'):
        if user_id in ADMIN_IDS:
            users = get_all_users()
            success_count = 0
            fail_count = 0
            
            broadcast_msg = update.message.text
            status_msg = await update.message.reply_text(f"📢 **Broadcasting...**\n\nTotal Users: {len(users)}", parse_mode='Markdown')
            
            for user in users:
                try:
                    await context.bot.send_message(
                        user, 
                        f"📢 **📢 ANNOUNCEMENT 📢**\n\n{broadcast_msg}\n\n━━━━━━━━━━━━━━━━━━━━\n👨‍💻 **Developed by:** @ModAppsKing\n━━━━━━━━━━━━━━━━━━━━",
                        parse_mode='Markdown'
                    )
                    success_count += 1
                    await asyncio.sleep(0.05)
                except Exception as e:
                    fail_count += 1
                    print(f"Failed to send to {user}: {e}")
            
            await status_msg.edit_text(
                f"✅ **Broadcast Complete!**\n\n"
                f"📨 Sent to: `{success_count}` users\n"
                f"❌ Failed: `{fail_count}` users\n"
                f"👥 Total: `{len(users)}` users",
                parse_mode='Markdown'
            )
            context.user_data['broadcast_mode'] = False
        else:
            await update.message.reply_text("❌ **You are not authorized to use broadcast!**", parse_mode='Markdown')
            context.user_data['broadcast_mode'] = False
        return
    
    # WAITING FOR NUMBER
    if context.user_data.get('waiting_for_number'):
        phone = update.message.text.strip()
        
        normalized = normalize_phone(phone)
        if normalized:
            credits = get_user_credits(user_id)
            if credits > 0:
                if deduct_credit(user_id):
                    await search_number(normalized, update, context)
                else:
                    await update.message.reply_text("❌ Failed to deduct credit!", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ **No credits left!**\n\nUse referral or redeem code.", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ **Invalid number!**\n\nAccepted formats:\n• 10 digit: `8084798673`\n• With 91: `918084798673`\n• With +91: `+918084798673`\n• With 0: `08084798673`", parse_mode='Markdown')
        
        context.user_data['waiting_for_number'] = False
        return
    
    # WAITING FOR REDEEM CODE
    if context.user_data.get('waiting_for_redeem'):
        code = update.message.text.strip().upper()
        credits = redeem_code(user_id, code)
        
        if credits:
            await update.message.reply_text(f"✅ **Redeem Successful!**\n\nYou received `{credits}` credits!\n\n💰 Your total credits: `{get_user_credits(user_id)}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ **Invalid or Used Code!**\n\nPlease check the code and try again.", parse_mode='Markdown')
        
        context.user_data['waiting_for_redeem'] = False
        return

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    
    conn = sqlite3.connect('osint_bot.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    existing_user = c.fetchone()
    
    if not existing_user:
        referred_by = None
        if context.args and len(context.args) > 0 and context.args[0].startswith('ref_'):
            try:
                referred_by = int(context.args[0].split('_')[1])
                if referred_by != user_id:
                    add_credits(referred_by, 5)
                    await context.bot.send_message(
                        referred_by, 
                        f"🎉 **New Referral!**\n\n@{username} joined using your link!\nYou got **5 credits**!",
                        parse_mode='Markdown'
                    )
            except:
                pass
        
        c.execute("INSERT INTO users (user_id, username, referred_by, joined_date) VALUES (?, ?, ?, ?)",
                 (user_id, username, referred_by, datetime.now()))
        conn.commit()
        
    conn.close()
    await menu(update, context)

# ============ ADMIN COMMANDS - FIXED ============
async def generate_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!", parse_mode='Markdown')
        return
    
    try:
        credits = int(context.args[0])
        code = generate_redeem_code(credits, update.effective_user.id)
        await update.message.reply_text(
            f"✅ **Redeem Code Generated!**\n\n"
            f"📝 **Code:** `{code}`\n"
            f"💰 **Credits:** `{credits}`\n\n"
            f"Share this code with users!",
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ **Usage:** `/gencode credits`\n**Example:** `/gencode 10`", parse_mode='Markdown')

async def add_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        add_credits(user_id, amount)
        new_credits = get_user_credits(user_id)
        await update.message.reply_text(
            f"✅ **Credits Added!**\n\n"
            f"👤 **User:** `{user_id}`\n"
            f"➕ **Added:** `{amount}` credits\n"
            f"💰 **Total Credits:** `{new_credits}`",
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ **Usage:** `/addcredits user_id credits`\n**Example:** `/addcredits 8162909171 10`", parse_mode='Markdown')

async def send_all_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!", parse_mode='Markdown')
        return
    
    try:
        amount = int(context.args[0])
        users = get_all_users()
        
        status_msg = await update.message.reply_text(f"💰 **Sending {amount} credits to all users...**\n\n👥 Total Users: {len(users)}", parse_mode='Markdown')
        
        count = 0
        for user_id in users:
            add_credits(user_id, amount)
            count += 1
            await asyncio.sleep(0.01)
        
        await status_msg.edit_text(
            f"✅ **Success!**\n\n"
            f"💰 Sent `{amount}` credits to `{count}` users\n"
            f"👥 Total users updated: `{count}`",
            parse_mode='Markdown'
        )
        
    except:
        await update.message.reply_text("❌ **Usage:** `/sendall credits`\n**Example:** `/sendall 5`", parse_mode='Markdown')

async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = TRUE WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🚫 **User Banned!**\n\nUser `{user_id}` has been banned from using the bot.", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ **Usage:** `/ban user_id`\n**Example:** `/ban 123456789`", parse_mode='Markdown')

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = FALSE WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ **User Unbanned!**\n\nUser `{user_id}` has been unbanned.", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ **Usage:** `/unban user_id`\n**Example:** `/unban 123456789`", parse_mode='Markdown')

async def user_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('osint_bot.db')
        c = conn.cursor()
        c.execute("SELECT phone_number, search_date FROM searches WHERE user_id = ? ORDER BY search_date DESC LIMIT 10", (user_id,))
        history = c.fetchall()
        conn.close()
        
        if history:
            text = f"📜 **Search History for User {user_id}**\n\n"
            for phone, date in history:
                text += f"📞 `{phone}` - {date[:19]}\n"
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ No search history found for user `{user_id}`", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ **Usage:** `/userhistory user_id`\n**Example:** `/userhistory 8162909171`", parse_mode='Markdown')

def main():
    print("=" * 50)
    print("Initializing database...")
    init_db()
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN environment variable not set!")
        print("Set it in Render Dashboard > Environment")
        return
    
    # Keepalive HTTP server for Render port binding
    print("Starting keepalive HTTP server...")
    run_keepalive_in_thread()
    
    print("Starting OSINT Bot...")
    print(f"Bot Token: {BOT_TOKEN[:15]}...")
    print(f"Admin IDs: {ADMIN_IDS}")
    print("=" * 50)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # User commands
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("menu", menu))
        
        # Admin commands
        app.add_handler(CommandHandler("gencode", generate_code_command))
        app.add_handler(CommandHandler("addcredits", add_credits_command))
        app.add_handler(CommandHandler("sendall", send_all_credits_command))
        app.add_handler(CommandHandler("ban", ban_user_command))
        app.add_handler(CommandHandler("unban", unban_user_command))
        app.add_handler(CommandHandler("userhistory", user_history_command))
        
        # Handlers
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("✅ Bot is running! Developed by @ModAppsKing")
        print("=" * 50)
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your BOT_TOKEN!")

if __name__ == "__main__":
    main()