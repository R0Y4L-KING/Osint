# ============================================================
# TELEGRAM API BOT
# Direct API URLs + Multi Channel Force Subscribe
# ============================================================
#
# INSTALL:
# pip install python-telegram-bot aiohttp
#
# RUN:
# python bot.py
# ============================================================

import re
import json
import aiohttp

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# ============================================================
# 1. BOT TOKEN
# ============================================================

BOT_TOKEN = "king ko nhi milta"


# ============================================================
# 2. FORCE SUB CHANNEL USERNAMES
# ============================================================
# YAHAN APNE CHANNEL USERNAMES DALO
#
# Example:
# "@mychannel"
#
# Bot ko channels me admin rakho taaki membership check kar sake.
# ============================================================

FORCE_CHANNELS = [
    "@altaf_upgraded",
    "@altafmodschannel",
]


# ============================================================
# 3. DIRECT API URLS
# ============================================================
#
# {value} automatically user ke input se replace hoga.
#
# Example:
# https://example.com/api/vehicle?number={value}
#
# API ko authorized/public-safe information hi return karni chahiye.
# ============================================================

NUMBER_API_URL = (
    "https://nmdllpezcocquamhgpmb.supabase.co/functions/v1/lookup?number={value}"
)

TG_API_URL = (
    "https://tg2num-botadminshere.vercel.app/?id={value}"
)

AADHAAR_API_URL = (
    "https://dark-info.site/familyinfo/api.php?key=JSON-4325&aadhar={value}"
)

VEHICLE_API_URL = (
    "https://revangevichelinfo.vercel.app/api/rc?number={value}"
)


# ============================================================
# 4. MAIN KEYBOARD
# ============================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [
            "📱 NUMBER INFO",
            "👤 TG INFO"
        ],
        [
            "🪪 AADHAAR VERIFY",
            "🚗 VEHICLE INFO"
        ],
    ],
    resize_keyboard=True,
)


# ============================================================
# 5. CREDIT FIELDS — YEH FIELDS RESPONSE SE HATA DI JAYENGE
# ============================================================

CREDIT_FIELDS = {
    "credit",
    "used_today",
    "daily_limit",
    "valid_days",
    "expires_on",
    "ok",
    "status",
    "success",
    "raw_response",
}


# ============================================================
# 6. FIELD EMOJI MAPPING
# ============================================================

FIELD_EMOJI = {
    "phone": "📞",
    "phone2": "📞",
    "phone3": "📞",
    "phone4": "📞",
    "phone5": "📞",
    "adres": "🏠",
    "adres2": "🏠",
    "adres3": "🏠",
    "documentnumber": "📄",
    "fullname": "👤",
    "fathername": "👨",
    "region": "📍",
    "tg_id": "🆔",
    "country": "🌍",
    "country_code": "🌐",
    "number": "📞",
    "provider": "📡",
    "indianstate": "🗺️",
    "mobileoperator": "📡",
    "query": "🔍",
    "name": "👤",
    "father_name": "👨",
    "address": "🏠",
    "address2": "🏠",
    "address3": "🏠",
    "vehicle_number": "🚗",
    "owner_name": "👤",
    "model": "🚗",
    "rc_status": "📋",
    "registration_date": "📅",
    "engine_number": "🔧",
    "chassis_number": "🔧",
    "fuel_type": "⛽",
    "insurance": "🛡️",
    "insurance_validity": "🛡️",
    "fitness_validity": "✅",
    "permit_validity": "✅",
    "state": "🗺️",
    "rto": "🏛️",
    "aadhaar": "🪪",
    "dob": "🎂",
    "gender": "⚧",
    "email": "📧",
}


def get_emoji(key):
    """Field key ke liye emoji return karo."""
    return FIELD_EMOJI.get(key.lower(), "🔹")


def pretty_key(key):
    """Field key ko readable format me convert karo."""
    return key.replace("_", " ").title()


# ============================================================
# 7. STRIP CREDIT FIELDS — recursively remove credit/usage info
# ============================================================

def strip_credit_fields(data):
    """Response data se credit/usage fields recursively hata do."""
    if isinstance(data, dict):
        return {
            k: strip_credit_fields(v)
            for k, v in data.items()
            if k.lower() not in CREDIT_FIELDS
        }
    if isinstance(data, list):
        return [strip_credit_fields(item) for item in data]
    return data


# ============================================================
# 8. FORMAT HELPERS
# ============================================================

def format_record_box(record, record_num=None):
    """Ek record dict ko box-drawing format me render karo."""
    lines = []

    if record_num is not None:
        lines.append(f"┌─ Record #{record_num} ─────────────")
    else:
        lines.append("┌────────────────────────────")

    for key, value in record.items():
        emoji = get_emoji(key)
        pk = pretty_key(key)
        if isinstance(value, dict):
            lines.append(f"│ {emoji} {pk}:")
            for sub_k, sub_v in value.items():
                sub_emoji = get_emoji(sub_k)
                lines.append(f"│   {sub_emoji} {pretty_key(sub_k)}: {sub_v}")
        elif isinstance(value, list):
            lines.append(f"│ {emoji} {pk}:")
            for idx, item in enumerate(value, 1):
                if isinstance(item, dict):
                    for sub_k, sub_v in item.items():
                        sub_emoji = get_emoji(sub_k)
                        lines.append(f"│   {sub_emoji} {pretty_key(sub_k)}: {sub_v}")
                else:
                    lines.append(f"│   • {item}")
        else:
            lines.append(f"│ {emoji} {pk}: {value}")

    lines.append("└────────────────────────────")
    return "\n".join(lines)


def format_kv_bullets(data, indent=0):
    """Dict ko bullet-point format me render karo."""
    lines = []
    pad = "  " * indent
    for key, value in data.items():
        emoji = get_emoji(key)
        pk = pretty_key(key)
        if isinstance(value, dict):
            lines.append(f"{pad}{emoji} {pk}:")
            lines.append(format_kv_bullets(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{pad}{emoji} {pk}:")
            for item in value:
                if isinstance(item, dict):
                    for sub_k, sub_v in item.items():
                        sub_emoji = get_emoji(sub_k)
                        lines.append(f"{pad}  • {pretty_key(sub_k)}: {sub_v}")
                else:
                    lines.append(f"{pad}  • {item}")
        else:
            lines.append(f"{pad}• {pk}: {value}")
    return "\n".join(lines)


def extract_records(data):
    """Response data se records list nikalo (agar hai to)."""
    # Direct list
    if isinstance(data, list):
        dict_items = [r for r in data if isinstance(r, dict)]
        if dict_items:
            return dict_items
        return None

    if not isinstance(data, dict):
        return None

    # Common keys jisme records ho sakte hain
    for key in ("records", "data", "results", "result", "items", "list"):
        val = data.get(key)
        if isinstance(val, list):
            dict_items = [r for r in val if isinstance(r, dict)]
            if dict_items:
                return dict_items
        if isinstance(val, dict):
            # Nested — ek level aur check karo
            for sub_key in ("records", "data", "results", "result", "items", "list"):
                sub_val = val.get(sub_key)
                if isinstance(sub_val, list):
                    dict_items = [r for r in sub_val if isinstance(r, dict)]
                    if dict_items:
                        return dict_items

    return None


def format_response(result, mode=None):
    """API response ko clean format me convert karo.

    - Credit/usage fields hata do
    - Box-drawing style records
    - Bullet-point KV for simple data
    """

    # --- ERROR CASE ---
    if not result.get("ok"):
        error = result.get("error", "Unknown error")
        details = result.get("details", "")
        msg = f"❌ {error}"
        if details:
            msg += f"\n📝 {details}"
        return msg

    data = result.get("result", {})
    data = strip_credit_fields(data)

    # Agar data empty ho gaya sab strip hone ke baad
    if not data or (isinstance(data, dict) and not data):
        return "❌ No data found."

    # ========================================================
    # TELEGRAM MODE
    # ========================================================
    if mode == "telegram":
        # TG API: result.result me actual data hota hai
        inner = data.get("result", data)
        if isinstance(inner, dict) and inner:
            header = "👤 TELEGRAM INFO\n\n"
            body = format_kv_bullets(inner)
            return f"<pre>{header}{body}</pre>"
        if isinstance(inner, str) and inner:
            return f"<pre>👤 TELEGRAM INFO\n\n• Result: {inner}</pre>"
        return "❌ No Telegram data found."

    # ========================================================
    # NUMBER MODE
    # ========================================================
    if mode == "number":
        records = extract_records(data)
        if records:
            count = len(records)
            header = (
                f"📋 MAIN DETAILS ({count} "
                f"record{'s' if count != 1 else ''} found)\n\n"
            )
            body = "\n\n".join(
                format_record_box(r, i + 1) for i, r in enumerate(records)
            )
            return f"<pre>{header}{body}</pre>"

        # Single record dict
        if isinstance(data, dict) and data:
            return f"<pre>📋 NUMBER INFO\n\n{format_kv_bullets(data)}</pre>"

        return "❌ No data found."

    # ========================================================
    # AADHAAR MODE
    # ========================================================
    if mode == "aadhaar":
        records = extract_records(data)
        if records:
            count = len(records)
            header = (
                f"🪪 AADHAAR DETAILS ({count} "
                f"record{'s' if count != 1 else ''} found)\n\n"
            )
            body = "\n\n".join(
                format_record_box(r, i + 1) for i, r in enumerate(records)
            )
            return f"<pre>{header}{body}</pre>"

        if isinstance(data, dict) and data:
            return f"<pre>🪪 AADHAAR DETAILS\n\n{format_kv_bullets(data)}</pre>"

        return "❌ No data found."

    # ========================================================
    # VEHICLE MODE
    # ========================================================
    if mode == "vehicle":
        records = extract_records(data)
        if records:
            count = len(records)
            header = (
                f"🚗 VEHICLE DETAILS ({count} "
                f"record{'s' if count != 1 else ''} found)\n\n"
            )
            body = "\n\n".join(
                format_record_box(r, i + 1) for i, r in enumerate(records)
            )
            return f"<pre>{header}{body}</pre>"

        if isinstance(data, dict) and data:
            return f"<pre>🚗 VEHICLE DETAILS\n\n{format_kv_bullets(data)}</pre>"

        return "❌ No data found."

    # ========================================================
    # FALLBACK — generic clean format
    # ========================================================
    if isinstance(data, dict) and data:
        return f"<pre>{format_kv_bullets(data)}</pre>"
    if isinstance(data, list) and data:
        dict_items = [r for r in data if isinstance(r, dict)]
        if dict_items:
            body = "\n\n".join(
                format_record_box(r, i + 1) for i, r in enumerate(dict_items)
            )
            return f"<pre>{body}</pre>"
        return f"<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>"

    return f"<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>"


# ============================================================
# 9. VALIDATION
# ============================================================

def valid_phone(value):

    value = value.strip()

    return bool(
        re.fullmatch(
            r"\+?[0-9]{7,15}",
            value
        )
    )


def valid_telegram_id(value):

    value = value.strip()

    return bool(
        re.fullmatch(
            r"-?[0-9]{5,20}",
            value
        )
    )


def valid_aadhaar(value):

    value = re.sub(
        r"\D",
        "",
        value
    )

    return len(value) == 12


def valid_vehicle(value):

    value = (
        value
        .upper()
        .replace(" ", "")
        .replace("-", "")
    )

    return bool(
        re.fullmatch(
            r"[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{3,4}",
            value
        )
    )


# ============================================================
# 10. API REQUEST
# ============================================================

async def call_api(api_url, value):

    if not api_url:

        return {
            "ok": False,
            "error": "API URL is not configured"
        }

    endpoint = api_url.replace(
        "{value}",
        value
    )

    try:

        timeout = aiohttp.ClientTimeout(
            total=15
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                endpoint
            ) as response:

                status = response.status

                content_type = (
                    response.headers
                    .get(
                        "content-type",
                        ""
                    )
                )

                if "application/json" in content_type:

                    data = await response.json()

                else:

                    text = await response.text()

                    try:

                        data = json.loads(text)

                    except Exception:

                        data = {
                            "raw_response": text
                        }

                return {
                    "ok": status < 400,
                    "status": status,
                    "result": data
                }

    except aiohttp.ClientError as error:

        return {
            "ok": False,
            "error": "API connection failed",
            "details": str(error)
        }

    except Exception as error:

        return {
            "ok": False,
            "error": "Unexpected error",
            "details": str(error)
        }


# ============================================================
# 11. CHECK CHANNEL MEMBERSHIP
# ============================================================

async def get_missing_channels(
    bot,
    user_id
):

    missing = []

    for channel in FORCE_CHANNELS:

        try:

            member = await bot.get_chat_member(
                chat_id=channel,
                user_id=user_id
            )

            if member.status not in (
                "member",
                "administrator",
                "creator",
            ):

                missing.append(channel)

        except Exception:

            missing.append(channel)

    return missing


# ============================================================
# 12. FORCE SUB CHECK
# ============================================================

async def force_sub(update):

    if not FORCE_CHANNELS:
        return True

    user_id = update.effective_user.id

    missing = await get_missing_channels(
        update.get_bot(),
        user_id
    )

    if not missing:
        return True

    buttons = []

    for channel in missing:

        username = channel.lstrip("@")

        buttons.append(
            [
                InlineKeyboardButton(
                    f"📢 JOIN {channel}",
                    url=f"https://t.me/{username}"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "✅ VERIFY",
                callback_data="verify_subscription"
            )
        ]
    )

    await update.effective_message.reply_text(
        "🔐 ACCESS LOCKED\n\n"
        "Bot use karne ke liye pehle "
        "required channels join karo.\n\n"
        "Join karne ke baad VERIFY dabao.",
        reply_markup=InlineKeyboardMarkup(
            buttons
        )
    )

    return False


# ============================================================
# 13. START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await force_sub(update):
        return

    context.user_data.clear()

    await update.message.reply_text(
        "🤖 BOT READY\n\n"
        "Neeche se option select karo:",
        reply_markup=MAIN_KEYBOARD
    )


# ============================================================
# 14. VERIFY BUTTON
# ============================================================

async def verify_subscription(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    missing = await get_missing_channels(
        context.bot,
        user_id
    )

    if missing:

        await query.message.reply_text(
            "❌ Verification failed.\n\n"
            "Sabhi required channels join karke "
            "VERIFY dobara press karo."
        )

        return

    await query.message.reply_text(
        "✅ VERIFIED SUCCESSFULLY!\n\n"
        "Ab bot use kar sakte ho.",
        reply_markup=MAIN_KEYBOARD
    )


# ============================================================
# 15. MESSAGE HANDLER
# ============================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not await force_sub(update):
        return

    text = update.message.text.strip()


    # --------------------------------------------------------
    # NUMBER BUTTON
    # --------------------------------------------------------

    if text == "📱 NUMBER INFO":

        context.user_data["mode"] = "number"

        await update.message.reply_text(
            "📱 Number send karo:"
        )

        return


    # --------------------------------------------------------
    # TELEGRAM BUTTON
    # --------------------------------------------------------

    if text == "👤 TG INFO":

        context.user_data["mode"] = "telegram"

        await update.message.reply_text(
            "👤 Telegram numeric ID send karo:"
        )

        return


    # --------------------------------------------------------
    # AADHAAR BUTTON
    # --------------------------------------------------------

    if text == "🪪 AADHAAR VERIFY":

        context.user_data["mode"] = "aadhaar"

        await update.message.reply_text(
            "🪪 12-digit Aadhaar number "
            "authorized verification ke liye send karo:"
        )

        return


    # --------------------------------------------------------
    # VEHICLE BUTTON
    # --------------------------------------------------------

    if text == "🚗 VEHICLE INFO":

        context.user_data["mode"] = "vehicle"

        await update.message.reply_text(
            "🚗 Vehicle registration number send karo:"
        )

        return


    # --------------------------------------------------------
    # GET CURRENT MODE
    # --------------------------------------------------------

    mode = context.user_data.get(
        "mode"
    )

    if not mode:

        await update.message.reply_text(
            "⬇️ Pehle koi option select karo.",
            reply_markup=MAIN_KEYBOARD
        )

        return


    # ========================================================
    # NUMBER
    # ========================================================

    if mode == "number":

        if not valid_phone(text):

            await update.message.reply_text(
                "❌ Invalid phone number."
            )

            return

        result = await call_api(
            NUMBER_API_URL,
            text
        )


    # ========================================================
    # TELEGRAM
    # ========================================================

    elif mode == "telegram":

        if not valid_telegram_id(text):

            await update.message.reply_text(
                "❌ Invalid Telegram ID."
            )

            return

        result = await call_api(
            TG_API_URL,
            text
        )


    # ========================================================
    # AADHAAR
    # ========================================================

    elif mode == "aadhaar":

        if not valid_aadhaar(text):

            await update.message.reply_text(
                "❌ Aadhaar must contain 12 digits."
            )

            return

        result = await call_api(
            AADHAAR_API_URL,
            text
        )


    # ========================================================
    # VEHICLE
    # ========================================================

    elif mode == "vehicle":

        if not valid_vehicle(text):

            await update.message.reply_text(
                "❌ Invalid vehicle registration number."
            )

            return

        result = await call_api(
            VEHICLE_API_URL,
            text
        )


    else:

        result = {
            "ok": False,
            "error": "Invalid mode"
        }


    # ========================================================
    # SEND FORMATTED RESPONSE
    # ========================================================

    output = format_response(result, mode)

    # Telegram message size protection
    if len(output) <= 4000:

        await update.message.reply_text(
            output,
            parse_mode="HTML"
        )

    else:

        # Bade response ko multiple messages me bhejo
        chunks = []
        current = ""

        for line in output.split("\n"):

            if len(current) + len(line) + 1 > 3900:

                if current:

                    chunks.append(current)

                current = line

            else:

                if current:

                    current += "\n" + line

                else:

                    current = line

        if current:

            chunks.append(current)

        for chunk in chunks:

            try:

                await update.message.reply_text(
                    chunk,
                    parse_mode="HTML"
                )

            except Exception:

                await update.message.reply_text(
                    chunk
                )


    # Reset mode
    context.user_data.pop(
        "mode",
        None
    )


# ============================================================
# 16. ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context
):

    print(
        "ERROR:",
        repr(context.error)
    )


# ============================================================
# 17. RUN BOT
# ============================================================

def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE"
    ):

        raise RuntimeError(
            "BOT_TOKEN code me set karo."
        )


    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )


    # /start
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    # VERIFY button
    app.add_handler(
        CallbackQueryHandler(
            verify_subscription,
            pattern="^verify_subscription$"
        )
    )


    # Normal messages/buttons
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )


    app.add_error_handler(
        error_handler
    )


    print(
        "🤖 Bot started successfully..."
    )


    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
