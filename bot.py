import logging
import os
from datetime import datetime

try:
    from zoneinfo import ZoneInfo

    TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
except Exception:
    TASHKENT_TZ = None

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import db
from parser import ParseError, parse_entry

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

XABAR_START = (
    "Assalomu alaykum! Men sizning moliyaviy kotibingizman.\n\n"
    "Hozircha oddiy matn orqali kirim/chiqim yozib borishimiz mumkin:\n"
    "  kirim 3 million Ish haqi\n"
    "  chiqim 50 ming Taksi\n\n"
    "Oxirgi yozuvlaringizni ko'rish uchun /royxat buyrug'ini yuboring."
)

XABAR_YORDAM = (
    "Yozuv qo'shish uchun quyidagi shaklda yozing:\n"
    "  kirim <summa> <tavsif>\n"
    "  chiqim <summa> <tavsif>\n\n"
    "Misollar:\n"
    "  chiqim 50 ming taksi\n"
    "  kirim 3 million ish haqi\n"
    "  chiqim 20000 nonushta"
)


def bugungi_sana() -> str:
    now = datetime.now(TASHKENT_TZ) if TASHKENT_TZ else datetime.now()
    return now.strftime("%Y-%m-%d")


def summani_formatlash(summa: float) -> str:
    return f"{summa:,.0f}".replace(",", " ")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(XABAR_START)


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(XABAR_YORDAM)


async def royxat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    yozuvlar = db.get_recent_transactions(user_id, limit=5)
    if not yozuvlar:
        await update.message.reply_text("Hali hech qanday yozuv yo'q.")
        return

    qatorlar = ["Oxirgi yozuvlar:"]
    for y in yozuvlar:
        belgi = "+" if y["tur"] == "kirim" else "-"
        qatorlar.append(
            f"#{y['id']} | {y['sana']} | {belgi}{summani_formatlash(y['summa'])} so'm | {y['tavsif']}"
        )
    await update.message.reply_text("\n".join(qatorlar))


async def matn_qabul_qilish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    try:
        yozuv = parse_entry(text)
    except ParseError as e:
        await update.message.reply_text(f"Tushunmadim: {e}\n\n{XABAR_YORDAM}")
        return

    sana = bugungi_sana()
    db.add_transaction(user_id, sana, yozuv.tur, yozuv.summa, yozuv.tavsif)

    tur_sozi = "Kirim" if yozuv.tur == "kirim" else "Chiqim"
    await update.message.reply_text(
        f"✅ {tur_sozi} qo'shildi: {summani_formatlash(yozuv.summa)} so'm — {yozuv.tavsif} ({sana})"
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN topilmadi. .env faylini tekshiring.")

    db.init_db()

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", yordam))
    application.add_handler(CommandHandler("royxat", royxat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_qabul_qilish))

    logger.info("Bot ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()
