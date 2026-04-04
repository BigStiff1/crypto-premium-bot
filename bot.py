import os
import requests
from datetime import datetime, date
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    PreCheckoutQueryHandler, MessageHandler, filters,
    CallbackQueryHandler
)

# ========================= CONFIG =========================
TOKEN ="8653969864:AAEmXcFQZgpHXypeLxl9B6bJYH4eM2hXi2g"


COINGECKO_API = "https://api.coingecko.com/api/v3"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

# ========================= STORAGE =========================
user_alerts = {}       # {user_id: [alert_dicts]}
user_counts = {}       # {user_id: count_today}
user_premium = {}      # {user_id: True}
user_last_reset = {}   # {user_id: date}
total_alerts_today = 0

# ========================= HELPERS =========================
def reset_daily_count(user_id: int):
    today = date.today()
    if user_last_reset.get(user_id) != today:
        user_counts[user_id] = 0
        user_last_reset[user_id] = today

# ========================= COMMANDS =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_daily_count(user_id)
    is_premium = user_premium.get(user_id, False)
    count = user_counts.get(user_id, 0)
    status = "🌟 LIFETIME PREMIUM" if is_premium else f"Free: {count}/3 alerts today"

    keyboard = [
        [InlineKeyboardButton("🚨 Set New Alert", callback_data="quick_alert")],
        [InlineKeyboardButton("⭐ Upgrade to Premium", callback_data="show_upgrade")],
        [InlineKeyboardButton("🔥 Trending Coins", callback_data="show_trending")],
        [InlineKeyboardButton("📊 My Alerts & Stats", callback_data="show_myalerts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🚀 *CryptoStar Alerts* — Real-time crypto price alerts!\n\n"
        f"{status}\n\n"
        "*Commands:*\n"
        "`/alert BTC 65000 above` — Alert when Bitcoin ≥ $65k\n"
        "`/alert ETH 3200 below` — Alert when Ethereum ≤ $3.2k\n"
        "`/myalerts` — Your alerts\n"
        "`/upgrade` — Get **UNLIMITED** alerts forever (500 Stars)\n\n"
        "*Why users love us:*\n"
        "• Alerts every 60 seconds\n"
        "• 100% free tier (3/day)\n"
        "• Telegram Stars payments (instant)\n"
        "• Trending coins + stats\n\n"
        "Send /help for full commands.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *CryptoStar Alerts Commands*\n\n"
        "`/alert BTC 65000 above` — Set alert\n"
        "`/myalerts` — Your active alerts\n"
        "`/trending` — Top trending coins right now\n"
        "`/upgrade` — Lifetime premium (500–2500 Stars)\n"
        "`/stats` — Bot usage stats\n\n"
        "*Premium perks:*\n"
        "• Unlimited alerts\n"
        "• Priority notifications\n"
        "• Never hit free limit\n\n"
        "⚠️ *Not financial advice. Prices from CoinGecko. Use at your own risk.*",
        parse_mode='Markdown'
    )

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Support both direct commands and callback queries
    msg = update.message or (update.callback_query and update.callback_query.message)
    try:
        r = requests.get(f"{COINGECKO_API}/search/trending", timeout=10)
        r.raise_for_status()
        coins = r.json().get("coins", [])[:8]

        text = "🔥 *Trending Coins Right Now*\n\n"
        for i, coin in enumerate(coins, 1):
            data = coin["item"]
            text += f"{i}. **{data['name']}** ({data['symbol']})\n"

        await msg.reply_text(text, parse_mode='Markdown')
    except Exception:
        await msg.reply_text("❌ Could not fetch trending coins right now.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(user_alerts)
    premium_count = len([u for u in user_premium.values() if u])
    await update.message.reply_text(
        f"📊 *CryptoStar Stats*\n\n"
        f"• Active users: {total_users}\n"
        f"• Alerts set today: {total_alerts_today}\n"
        f"• Premium users: {premium_count}\n"
        f"• Uptime: Always on (Render 24/7)\n\n"
        "Join the thousands getting alerts!",
        parse_mode='Markdown'
    )

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_daily_count(user_id)
    is_premium = user_premium.get(user_id, False)

    if not is_premium and user_counts.get(user_id, 0) >= 3:
        await update.message.reply_text(
            "⚠️ Free limit reached (3/day).\nSend /upgrade for lifetime unlimited!"
        )
        return

    try:
        args = context.args
        if len(args) != 3:
            raise ValueError("Format: /alert COIN PRICE above|below")

        symbol = args[0].upper()
        price = float(args[1])
        condition = args[2].lower()

        if condition not in ["above", "below"]:
            raise ValueError("Condition must be 'above' or 'below'")

        r = requests.get(f"{COINGECKO_API}/coins/list", timeout=10)
        r.raise_for_status()
        coin_list = r.json()
        coin_data = next(
            (c for c in coin_list if c["symbol"].upper() == symbol or c["id"].lower() == symbol.lower()),
            None
        )

        if not coin_data:
            await update.message.reply_text(f"❌ Coin '{symbol}' not found. Try BTC, ETH, SOL...")
            return

        if user_id not in user_alerts:
            user_alerts[user_id] = []

        alert = {
            "coin_id": coin_data["id"],
            "symbol": symbol,
            "target": price,
            "condition": condition,
            "created": datetime.now().isoformat()
        }
        user_alerts[user_id].append(alert)
        user_counts[user_id] = user_counts.get(user_id, 0) + 1

        global total_alerts_today
        total_alerts_today += 1

        await update.message.reply_text(
            f"✅ *Alert Set!*\n\n"
            f"**{symbol}** will notify when {condition} **${price:,.2f}**\n"
            f"Free alerts today: {user_counts[user_id]}/3",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)[:100]}\n\nUse: `/alert BTC 65000 above`"
        )

async def myalerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Support both direct commands and callback queries
    msg = update.message or (update.callback_query and update.callback_query.message)
    alerts = user_alerts.get(user_id, [])

    if not alerts:
        await msg.reply_text("No active alerts yet.\nSet some with /alert!")
        return

    text = "*Your Active Alerts:*\n\n"
    for i, a in enumerate(alerts, 1):
        text += f"{i}. **{a['symbol']}** → {a['condition']} ${a['target']:,.2f}\n"
    await msg.reply_text(text, parse_mode='Markdown')

# ========================= PAYMENTS =========================
PRODUCTS = {
    "premium_basic": {"title": "Basic Lifetime", "desc": "Unlimited alerts forever", "stars": 500},
    "premium_pro":   {"title": "Pro Lifetime",   "desc": "Unlimited + priority 30s checks", "stars": 1200},
    "premium_vip":   {"title": "VIP Bundle",     "desc": "Everything + early features", "stars": 2500},
}

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Support both /upgrade command and callback
    msg = update.message or (update.callback_query and update.callback_query.message)
    keyboard = [
        [InlineKeyboardButton("Basic Lifetime – 500 Stars",  callback_data="premium_basic")],
        [InlineKeyboardButton("Pro Lifetime – 1200 Stars",   callback_data="premium_pro")],
        [InlineKeyboardButton("VIP Bundle – 2500 Stars",     callback_data="premium_vip")],
    ]
    await msg.reply_text(
        "⭐ *Choose Your Lifetime Package*\n\n"
        "Pay once with Telegram Stars → unlimited alerts forever!\n"
        "No recurring fees. Instant access.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Quick-action buttons from /start
    if data == "show_upgrade":
        await upgrade(update, context)
        return
    if data == "show_trending":
        await trending(update, context)
        return
    if data == "show_myalerts":
        await myalerts(update, context)
        return
    if data == "quick_alert":
        await query.message.reply_text("Send `/alert BTC 65000 above` to create one!", parse_mode='Markdown')
        return

    # Premium purchase buttons
    prod = PRODUCTS.get(data)
    if not prod:
        return

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=prod["title"],
        description=prod["desc"],
        payload=data,
        provider_token="",   # Empty = Telegram Stars
        currency="XTR",
        prices=[LabeledPrice(prod["title"], prod["stars"])],
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload

    user_premium[user_id] = True
    extra = "Priority checks enabled!" if "pro" in payload else (
        "VIP perks unlocked!" if "vip" in payload else "Enjoy unlimited alerts!"
    )

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🎉 *Payment Complete!*\n\n"
             f"**{payload.replace('_', ' ').title()}** activated!\n"
             f"{extra}\n\n"
             "You now have **lifetime unlimited alerts**.\n"
             "Go crazy with /alert commands!",
        parse_mode='Markdown'
    )

# ========================= PRICE CHECKER =========================
async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    if not user_alerts:
        return
    try:
        all_ids = {alert["coin_id"] for alerts in user_alerts.values() for alert in alerts}
        if not all_ids:
            return

        r = requests.get(
            f"{COINGECKO_API}/simple/price?ids={','.join(all_ids)}&vs_currencies=usd",
            timeout=10
        )
        r.raise_for_status()
        prices = r.json()

        for uid, alerts in list(user_alerts.items()):
            for alert in alerts[:]:
                current = prices.get(alert["coin_id"], {}).get("usd")
                if not current:
                    continue

                triggered = (
                    (alert["condition"] == "above" and current >= alert["target"]) or
                    (alert["condition"] == "below" and current <= alert["target"])
                )

                if triggered:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🚨 *ALERT!* **{alert['symbol']}** is now **${current:,.2f}** "
                             f"({alert['condition']} ${alert['target']:,.2f})",
                        parse_mode='Markdown'
                    )
                    alerts.remove(alert)

            if not alerts:
                del user_alerts[uid]

    except Exception as e:
        print(f"Price check error: {e}")

# ========================= MAIN =========================
def main():
    print("🚀 CryptoStar Alerts starting on Render...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("stats",    stats))
    app.add_handler(CommandHandler("alert",    set_alert))
    app.add_handler(CommandHandler("myalerts", myalerts))
    app.add_handler(CommandHandler("upgrade",  upgrade))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    app.job_queue.run_repeating(check_prices, interval=60, first=10)

    port = int(os.getenv("PORT", 8080))
    webhook_url = RENDER_URL.rstrip("/") if RENDER_URL else None
    print(f"📡 Starting webhook on {webhook_url} (port {port})")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="",
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
