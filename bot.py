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
from parser import ParseError, parse_debt_add, parse_debt_close, parse_entry, qarz_xabarimi, summani_ajratish

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

XABAR_START = (
    "Assalomu alaykum! Men sizning moliyaviy kotibingizman.\n\n"
    "Hozircha oddiy matn orqali kirim/chiqim va qarzlarni yozib borishimiz mumkin:\n"
    "  kirim 3 million Ish haqi\n"
    "  chiqim 50 ming Taksi\n"
    "  qarz berdim Aliyev 500 ming 2 oydan keyin\n\n"
    "To'liq yo'riqnoma uchun /help, oxirgi yozuvlar uchun /royxat buyrug'ini yuboring."
)

XABAR_YORDAM = (
    "📝 Kirim/chiqim yozish:\n"
    "  kirim <summa> <tavsif>\n"
    "  chiqim <summa> <tavsif>\n"
    "Misollar: 'chiqim 50 ming taksi', 'kirim 3 million ish haqi'\n\n"
    "🤝 Qarz yozish (ism bitta so'z bo'lsin):\n"
    "  qarz berdim <ism> <summa> [muddat]   — kimgadir qarz berdingiz\n"
    "  qarz oldim <ism> <summa> [muddat]    — kimdandir qarz oldingiz\n"
    "  qarz yopildi <ism>                   — shu ism bilan ochiq qarzni yopadi\n"
    "Misollar: 'qarz berdim Aliyev 500 ming 2 oydan keyin', 'qarz yopildi Aliyev'\n\n"
    "✏️ Xato yozuvni tuzatish:\n"
    "  /tahrirlash <ID> <yangi_summa>   — /royxat'da ko'rsatilgan ID bo'yicha\n"
    "Misol: /tahrirlash 3 300000\n\n"
    "📊 Boshqa buyruqlar: /balans, /qarzlar, /hisobot, /hisobot <oy_nomi>, /royxat"
)

OY_NOMLARI = {
    "yanvar": 1,
    "fevral": 2,
    "mart": 3,
    "aprel": 4,
    "may": 5,
    "iyun": 6,
    "iyul": 7,
    "avgust": 8,
    "sentabr": 9,
    "sentyabr": 9,
    "oktabr": 10,
    "oktyabr": 10,
    "noyabr": 11,
    "dekabr": 12,
}


def oy_oraligi(yil: int, oy: int) -> tuple[str, str]:
    """[boshlanish, tugash) — sana_gacha shu sanani o'z ichiga olmaydi."""
    boshlanish = f"{yil:04d}-{oy:02d}-01"
    if oy == 12:
        tugash = f"{yil + 1:04d}-01-01"
    else:
        tugash = f"{yil:04d}-{oy + 1:02d}-01"
    return boshlanish, tugash


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
        qatorlar.append(
            f"{y['id']}. {y['tur']} {summani_formatlash(y['summa'])} {y['tavsif']}"
        )
    qatorlar.append("\nXato bo'lsa: /tahrirlash <ID> <yangi_summa>")
    await update.message.reply_text("\n".join(qatorlar))


async def tahrirlash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2 or not args[0].isdigit():
        await update.message.reply_text(
            "Format: /tahrirlash <ID> <yangi_summa>\nMasalan: /tahrirlash 3 300000"
        )
        return

    transaction_id = int(args[0])
    try:
        yangi_summa, _ = summani_ajratish(args[1:])
    except ParseError:
        await update.message.reply_text(
            "Summa noto'g'ri. Masalan: /tahrirlash 3 300000"
        )
        return

    user_id = update.effective_user.id
    muvaffaqiyatli = db.update_transaction_summa(user_id, transaction_id, yangi_summa)

    if not muvaffaqiyatli:
        await update.message.reply_text("Bunday raqamli yozuv topilmadi.")
        return

    await update.message.reply_text(
        f"✅ {transaction_id}-yozuv {summani_formatlash(yangi_summa)} so'mga tuzatildi."
    )


async def balans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    jami_kirim, jami_chiqim = db.get_totals(user_id)
    joriy_balans = jami_kirim - jami_chiqim
    await update.message.reply_text(f"💰 Joriy balans: {summani_formatlash(joriy_balans)} so'm")


async def qarzlar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    mendan_qarzdorlar = db.get_debts(user_id, "mendan_qarzdor")
    men_qarzdor_bolgan = db.get_debts(user_id, "men_qarzdorman")

    def qatorga_aylantirish(yozuvlar):
        if not yozuvlar:
            return ["  — yo'q —"]
        natija = []
        for q in yozuvlar:
            muddat = f", muddat: {q['muddat']}" if q["muddat"] else ""
            natija.append(f"  {q['ism']} — {summani_formatlash(q['summa'])} so'm{muddat}")
        return natija

    qatorlar = ["🤝 Sizga qarzdorlar:"]
    qatorlar += qatorga_aylantirish(mendan_qarzdorlar)
    qatorlar.append("")
    qatorlar.append("📌 Siz qarzdor bo'lgan joylar:")
    qatorlar += qatorga_aylantirish(men_qarzdor_bolgan)

    await update.message.reply_text("\n".join(qatorlar))


async def hisobot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sarlavha = "barcha vaqt uchun"
    sana_dan = None
    sana_gacha = None

    if context.args:
        oy_nomi = " ".join(context.args).strip().lower()
        oy_raqami = OY_NOMLARI.get(oy_nomi)
        if oy_raqami is None:
            await update.message.reply_text(
                "Noma'lum oy nomi. Masalan: /hisobot avgust"
            )
            return
        yil = datetime.now(TASHKENT_TZ).year if TASHKENT_TZ else datetime.now().year
        sana_dan, sana_gacha = oy_oraligi(yil, oy_raqami)
        sarlavha = f"{oy_nomi} {yil}"

    jami_kirim, jami_chiqim = db.get_totals(user_id=update.effective_user.id, sana_dan=sana_dan, sana_gacha=sana_gacha)
    sof_balans = jami_kirim - jami_chiqim

    await update.message.reply_text(
        f"📊 Hisobot ({sarlavha}):\n"
        f"Jami kirim: {summani_formatlash(jami_kirim)} so'm\n"
        f"Jami chiqim: {summani_formatlash(jami_chiqim)} so'm\n"
        f"Sof balans: {summani_formatlash(sof_balans)} so'm"
    )


async def qarz_xabarini_qayta_ishlash(update: Update, user_id: int, text: str) -> None:
    tokens = text.strip().split()
    ikkinchi_soz = tokens[1].lower() if len(tokens) > 1 else ""

    if ikkinchi_soz == "yopildi":
        try:
            ism = parse_debt_close(text)
        except ParseError as e:
            await update.message.reply_text(f"Tushunmadim: {e}\n\n{XABAR_YORDAM}")
            return

        yopildimi = db.qarzni_yopish(user_id, ism)
        if yopildimi:
            await update.message.reply_text(f"✅ '{ism}' bilan bog'liq qarz yopildi (to'landi deb belgilandi).")
        else:
            await update.message.reply_text(f"'{ism}' nomi bilan ochiq qarz topilmadi.")
        return

    try:
        yozuv = parse_debt_add(text)
    except ParseError as e:
        await update.message.reply_text(f"Tushunmadim: {e}\n\n{XABAR_YORDAM}")
        return

    sana = bugungi_sana()
    db.add_debt(user_id, yozuv.tur, yozuv.ism, yozuv.summa, sana, yozuv.muddat)

    tur_matni = "sizga qarzdor bo'ldi" if yozuv.tur == "mendan_qarzdor" else "siz qarzdor bo'ldingiz"
    muddat_matni = f", muddat: {yozuv.muddat}" if yozuv.muddat else ""
    await update.message.reply_text(
        f"✅ Qarz qo'shildi: {yozuv.ism} — {tur_matni}: {summani_formatlash(yozuv.summa)} so'm{muddat_matni}"
    )


async def matn_qabul_qilish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    if qarz_xabarimi(text):
        await qarz_xabarini_qayta_ishlash(update, user_id, text)
        return

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
    application.add_handler(CommandHandler("balans", balans))
    application.add_handler(CommandHandler("qarzlar", qarzlar))
    application.add_handler(CommandHandler("hisobot", hisobot))
    application.add_handler(CommandHandler("tahrirlash", tahrirlash))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_qabul_qilish))

    logger.info("Bot ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()
