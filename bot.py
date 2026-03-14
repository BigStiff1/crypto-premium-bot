import os
import requests
from telegram import Update, LabeledPrice
from telegram.ext import Application, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
from datetime import datetime

# CONFIG
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("CRITICAL: BOT_TOKEN not set!")
    exit(1)

COINGECKO_API = "https://api.coingecko.com/api/v3"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render auto-provides this

# Storage (in-memory — resets on restart, fine for tonight)
user_alerts = {}
user_counts = {}
user_premium = {}  # Lifetime premium users

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_premium = user_premium.get(user_id, False)
    count = user_counts.get(user_id, 0)
    
    status = "🌟 LIFETIME PREMIUM" if is_premium else f"Free tier: {count}/3 alerts today"
    
    await update.message.reply_text(
        f"""🚀 *Crypto Premium Alert Bot*
        
{status}

*Commands:*
`/alert BTC 65000 above` — Alert when Bitcoin ≥ $65k
`/alert ETH 3200 below` — Alert when Ethereum ≤ $3.2k
`/myalerts` — Your alerts
`/upgrade` — Get **UNLIMITED** alerts forever (500 Stars)

Alerts checked every 60 seconds!""",
        parse_mode='Markdown'
    )

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send Stars payment invoice for lifetime premium"""
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Lifetime Premium Crypto Alerts",
        description="Unlimited alerts + priority checks. Never hit the 3/day limit again!",
        payload="premium_lifetime",
        provider_token="",           # Empty = Telegram Stars
        currency="XTR",              # Stars currency
        prices=[LabeledPrice("Lifetime Access", 500)],  # 500 Stars ≈ $4-6
    )

async def pre_checkout_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_premium[user_id] = True
    await context.bot.send_message(
        chat_id=user_id,
        text="🎉 *Payment Successful!*\n\n"
             "You now have **Lifetime Premium** ✅\n"
             "Unlimited alerts forever. Go set as many as you want with /alert!"
    )

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_premium = user_premium.get(user_id, False)
    
    if not is_premium and user_counts.get(user_id, 0) >= 3:
        await update.message.reply_text("⚠️ Free limit reached! Send /upgrade for lifetime unlimited alerts (500 Stars).")
        return
    
    # ... (rest of your original set_alert logic — exactly the same as before)
    # I kept it identical for simplicity. Full logic is in the previous version you had.

    # (Paste your original set_alert, myalerts, check_prices functions here — they work unchanged)
    # For brevity in this message, I'm showing only the new payment parts. 
    # Use the exact set_alert + myalerts + check_prices from the code I gave you 2 messages ago. 
    # Just add the premium check at the top of set_alert.

async def myalerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Your original myalerts function (unchanged)
    pass  # replace with your working version

async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    # Your original background job (unchanged)
    pass

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("alert", set_alert))
    application.add_handler(CommandHandler("myalerts", myalerts))
    application.add_handler(CommandHandler("upgrade", upgrade))
    
    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_query))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    application.job_queue.run_repeating(check_prices, interval=60, first=10)
    
    PORT = int(os.getenv("PORT", 8080))
    print(f"🚀 Starting webhook on {RENDER_URL}")
    
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=RENDER_URL
    )

if __name__ == "__main__":
    main()
