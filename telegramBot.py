import asyncio
import logging
import time
from binance.client import Client
from scanner import scan_market  # sync function, called via async wrapper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = 'your_telegram_bot_token_here'
CHAT_ID = 'your_chat_id_here'

BINANCE_API_KEY = 'your_binance_api_key_here'
BINANCE_API_SECRET = 'your_binance_api_secret_here'

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

last_scan_results = []
last_scan_time = 0
SCAN_INTERVAL = 300  # seconds


def get_gpt_decision(data):
    return "buy" if data["score"] >= 8 else "don’t buy"


async def buy_order_async(symbol):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, buy_order, symbol)


def buy_order(symbol):
    try:
        order = client.create_order(
            symbol=symbol,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quantity=100
        )
        return f"✅ Order sent: {order['symbol']} - {order['side']}"
    except Exception as e:
        logger.error(f"Buy order error: {e}")
        return f"❌ Order error: {e}"


async def get_scan_results(force_refresh=False):
    global last_scan_results, last_scan_time
    now = time.time()

    if force_refresh or (now - last_scan_time > SCAN_INTERVAL) or not last_scan_results:
        logger.info("Performing new scan...")
        loop = asyncio.get_running_loop()
        last_scan_results = await loop.run_in_executor(None, scan_market)
        last_scan_time = now
    else:
        logger.info("Fetching scan results from cache...")

    return last_scan_results


async def scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/scan command triggered.")
    try:
        results = await get_scan_results()
        filtered = [c for c in results if c['score'] >= 8]

        if not filtered:
            await update.message.reply_text("🔍 No strong signal detected at the moment.")
            return

        for coin in filtered[:5]:
            decision = get_gpt_decision(coin)
            message = (
                f"*{coin['symbol']}* | Score: {round(coin['score'], 2)} | Decision: *{decision.upper()}*\n"
                f"RSI: {coin['rsi']} | MACD: {coin['macd']}\n"
                f"/detail {coin['symbol']} — for technical details"
            )
            keyboard = [
                [
                    InlineKeyboardButton("✅ Buy", callback_data=f"{coin['symbol']}_buy"),
                    InlineKeyboardButton("❌ Don't Buy", callback_data=f"{coin['symbol']}_dontbuy"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"/scan error: {e}")
        await update.message.reply_text(f"⚠️ An error occurred: {e}")


async def detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Please provide the coin symbol: /detail BTCUSDT")
        return

    symbol = context.args[0].upper()
    logger.info(f"/detail command: {symbol}")
    try:
        results = await get_scan_results()
        coin = next((c for c in results if c['symbol'] == symbol), None)

        if not coin:
            await update.message.reply_text(f"No data found for {symbol}.")
            return

        details = (
            f"*{coin['symbol']} Technical Details*\n"
            f"Score: {round(coin['score'], 2)}\n"
            f"RSI: {coin['rsi']}\nMACD: {coin['macd']} (Signal: {coin['macd_signal']})\n"
            f"EMA50: {coin['ema50']} | EMA200: {coin['ema200']}\n"
            f"Support: {coin['support']} | Resistance: {coin['resistance']}\n"
            f"ATR: {coin['atr']}\n"
            f"Fib Levels: 0: {coin['fib_0']}, 23.6: {coin['fib_23_6']}, 38.2: {coin['fib_38_2']}, 50: {coin['fib_50']}\n"
            f"Momentum: {coin['momentum']}\n"
            f"OBV: {coin['obv']}\n"
        )
        await update.message.reply_text(details, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"/detail error: {e}")
        await update.message.reply_text(f"⚠️ An error occurred: {e}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        data = query.data.split("_")
        if len(data) != 2:
            await query.edit_message_text("❌ Invalid input received, action cancelled.")
            return

        symbol, action = data

        if action == 'buy':
            message = await buy_order_async(symbol)
            await query.edit_message_text(message, parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ {symbol} action cancelled.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Button response error: {e}")
        await query.edit_message_text(f"⚠️ An error occurred: {e}")


async def auto_gpt_decision(context):
    try:
        results = await get_scan_results()
        filtered = [c for c in results if c['score'] >= 8]

        for coin in filtered[:3]:
            decision = get_gpt_decision(coin)
            keyboard = [[
                InlineKeyboardButton("✅ Buy", callback_data=f"{coin['symbol']}_buy"),
                InlineKeyboardButton("❌ Don't Buy", callback_data=f"{coin['symbol']}_dontbuy")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message = (
                f"Suggested action for *{coin['symbol']}*: *{decision.upper()}*\n"
                f"Score: {coin['score']} | RSI: {coin['rsi']} | MACD: {coin['macd']}"
            )
            await context.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Auto decision error: {e}")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🚀 *Commands:* \n"
        "/scan — Lists coins with strong signals (max 5)\n"
        "/detail SYMBOL — Shows technical details of a coin\n"
        "/help — Shows help info\n\n"
        "Use BUY / DON'T BUY buttons to take action."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("scan", scan_handler))
    app.add_handler(CommandHandler("detail", detail_handler))
    app.add_handler(CommandHandler("help", help_handler))

    app.add_handler(CallbackQueryHandler(button_callback))

    app.job_queue.run_repeating(auto_gpt_decision, interval=3600, first=10)

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
