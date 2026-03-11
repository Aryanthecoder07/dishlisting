import logging
import os
import urllib.parse
import requests
import io
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# ============================================
# STEP 1: VALIDATE + CORRECT DISH NAME
# ============================================
def validate_and_correct_dish(user_input: str):
    """
    Uses AI to:
    1. Check if input is a valid food/dish name
    2. Auto-correct spelling mistakes
    3. Return clean standardized dish name
    """
    prompt = (
        f"The user typed: '{user_input}'\n\n"
        "Your job:\n"
        "1. Check if this is a real food dish or ingredient name\n"
        "2. If YES: fix any spelling mistakes and return the correct dish name\n"
        "3. If NO: return INVALID\n\n"
        "Examples:\n"
        "'gjar halwa'     → Gajar Halwa\n"
        "'chiken biryni'  → Chicken Biryani\n"
        "'pzza'           → Pizza\n"
        "'hello'          → INVALID\n"
        "'asdfgh'         → INVALID\n"
        "'my name is ali' → INVALID\n"
        "'book a flight'  → INVALID\n"
        "'dal makhni'     → Dal Makhani\n\n"
        "OUTPUT RULES:\n"
        "- If valid: return ONLY the corrected dish name, nothing else\n"
        "- If invalid: return ONLY the word INVALID, nothing else\n"
        "- No explanations, no punctuation, no extra text"
    )

    headers = {"Authorization": f"Bearer {POLLINATIONS_API_KEY}"}
    payload = {
        "model": "gemini-fast",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(
            "https://gen.pollinations.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        result = response.json()['choices'][0]['message']['content'].strip()
        
        # Clean any accidental markdown or quotes
        result = result.replace("*", "").replace('"', "").replace("'", "").strip()

        if result.upper() == "INVALID":
            return None, None
        
        # Check if AI corrected the name
        corrected = result != user_input
        return result, corrected

    except Exception as e:
        logging.error(f"Validation Error: {e}")
        # If validation fails, pass original input through
        return user_input, False


# ============================================
# STEP 2: GET AI LISTING
# ============================================
def get_ai_listing(dish_name: str):
    """Fetch bilingual text and metaprompt from Gemini."""
    prompt = (
        f"You are a professional food copywriter and photographer.\n"
        f"Create a premium marketplace listing for: '{dish_name}'\n\n"

        "EN: Write a 40-word English description.\n"
        "- Sensory words (taste, texture, aroma)\n"
        "- Cover: ingredients → appearance → taste\n"
        "- Premium, appetizing, restaurant quality tone\n"
        "- Do NOT start with Indulge or Savor\n\n"

        "BN: Write the same in natural fluent Bengali (বাংলা).\n"
        "- NOT a direct translation, use Bengali food culture tone\n"
        "- Same emotion and appetite appeal as English\n"
        "- Exactly 40 words\n\n"

        "META: Write a 50-word Flux photography prompt.\n"
        "- Dish name, plating, lighting, lens, aperture\n"
        "- Background, props, garnish, serving vessel\n"
        "- End with: 8K, hyperrealistic, food photography, bokeh\n\n"

        "OUTPUT FORMAT (strictly follow):\n"
        "EN: [text]\n"
        "BN: [text]\n"
        "META: [text]\n"
        "No extra text. No markdown. No quotes."
    )

    headers = {"Authorization": f"Bearer {POLLINATIONS_API_KEY}"}
    payload = {
        "model": "gemini-fast",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(
            "https://gen.pollinations.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
        res_text = response.json()['choices'][0]['message']['content']
        en = res_text.split("EN:")[1].split("BN:")[0].strip()
        bn = res_text.split("BN:")[1].split("META:")[0].strip()
        meta = res_text.split("META:")[1].strip()
        return en, bn, meta

    except Exception as e:
        logging.error(f"Listing Error: {e}")
        return (
            f"Delicious {dish_name}",
            f"সুস্বাদু {dish_name}",
            f"High-end food photo of {dish_name}"
        )


# ============================================
# BOT HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Royal Bengal AI Agent Active!*\n\n"
        "Send me any dish name to generate a professional listing.\n\n"
        "Examples:\n"
        "• Gajar Halwa\n"
        "• Chicken Biryani\n"
        "• Butter Naan\n"
        "• Rasmalai",
        parse_mode='Markdown'
    )


async def handle_dish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    # ── Step 1: Validate and correct dish name ──
    status_msg = await update.message.reply_text("🔍 Checking dish name...")

    dish, was_corrected = validate_and_correct_dish(user_input)

    # ── Not a valid dish ──
    if dish is None:
        await status_msg.edit_text(
            "❌ *That doesn't look like a dish name.*\n\n"
            "Please send a valid food or dish name.\n\n"
            "Examples:\n"
            "• Gajar Halwa\n"
            "• Chicken Biryani\n"
            "• Paneer Tikka",
            parse_mode='Markdown'
        )
        return

    # ── Notify if name was auto-corrected ──
    if was_corrected:
        await status_msg.edit_text(
            f"✏️ Auto-corrected: *{user_input}* → *{dish}*\n\n"
            f"⏳ Generating listing...",
            parse_mode='Markdown'
        )
    else:
        await status_msg.edit_text(f"⏳ Processing *{dish}*...", parse_mode='Markdown')

    # ── Step 2: Get listing content ──
    en, bn, meta = get_ai_listing(dish)

    # ── Step 3: Send text listing ──
    await status_msg.edit_text(
        f"📝 *Listing for {dish}*\n\n"
        f"🇬🇧 *English:*\n{en}\n\n"
        f"🇧🇩 *Bengali:*\n{bn}",
        parse_mode='Markdown'
    )

    # ── Step 4: Generate and send image ──
    encoded_meta = urllib.parse.quote(meta)
    image_url = (
        f"https://gen.pollinations.ai/image/{encoded_meta}"
        f"?model=flux&width=1024&height=1024&nologo=true&key={POLLINATIONS_API_KEY}"
    )

    try:
        img_response = requests.get(image_url, timeout=40)
        if img_response.status_code == 200:
            image_file = io.BytesIO(img_response.content)
            image_file.name = "dish.jpg"
            await update.message.reply_photo(
                photo=image_file,
                caption=f"📸 *{dish}*",
                parse_mode='Markdown',
                read_timeout=60,
                write_timeout=60
            )
        else:
            await update.message.reply_text("⚠️ Image generation failed.")

    except Exception as e:
        logging.error(f"Image Error: {e}")
        await update.message.reply_text("❌ Image timed out. Please try again.")


# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .build()
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_dish))

    print("Bot is live and monitoring...")
    application.run_polling()
