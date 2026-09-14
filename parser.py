import re
from dataclasses import dataclass

TUR_KALITLARI = {
    "kirim": "kirim",
    "kirdi": "kirim",
    "chiqim": "chiqim",
    "xarajat": "chiqim",
}

QARZ_FELLARI = {
    "berdim": "mendan_qarzdor",
    "oldim": "men_qarzdorman",
}

KOPAYTIRUVCHILAR = {
    "ming": 1_000,
    "mln": 1_000_000,
    "million": 1_000_000,
}

BIRLIK_SOZLAR = {"so'm", "som", "sum", "uzs"}

SON_REGEX = re.compile(r"^\d+([.,]\d+)?$")


@dataclass
class ParsedEntry:
    tur: str
    summa: float
    tavsif: str


@dataclass
class ParsedDebt:
    tur: str  # 'mendan_qarzdor' (u sizga qarzdor) yoki 'men_qarzdorman' (siz qarzdorsiz)
    ism: str
    summa: float
    muddat: str | None


class ParseError(Exception):
    pass


def _sonmi(token: str) -> bool:
    return bool(SON_REGEX.match(token.replace(" ", "")))


def summani_ajratish(tokens: list[str]) -> tuple[float, list[str]]:
    """tokens boshida summa (va ixtiyoriy ko'paytiruvchi/birlik) bo'lishi kerak.
    (summa, qolgan_tokenlar) qaytaradi yoki ParseError ko'taradi."""
    if not tokens or not _sonmi(tokens[0]):
        raise ParseError("Summa topilmadi.")

    summa = float(tokens[0].replace(",", "."))
    qolgan = tokens[1:]

    if qolgan and qolgan[0].lower() in KOPAYTIRUVCHILAR:
        summa *= KOPAYTIRUVCHILAR[qolgan[0].lower()]
        qolgan = qolgan[1:]

    if qolgan and qolgan[0].lower() in BIRLIK_SOZLAR:
        qolgan = qolgan[1:]

    return summa, qolgan


def parse_entry(text: str) -> ParsedEntry:
    tokens = text.strip().split()
    if len(tokens) < 2:
        raise ParseError("Xabar juda qisqa")

    tur_kalit = tokens[0].lower()
    tur = TUR_KALITLARI.get(tur_kalit)
    if tur is None:
        raise ParseError(f"Noma'lum tur: '{tokens[0]}'. 'kirim' yoki 'chiqim' bilan boshlang.")

    try:
        summa, qolgan = summani_ajratish(tokens[1:])
    except ParseError:
        raise ParseError("Summa topilmadi. Masalan: 'chiqim 50 ming taksi'")

    tavsif = " ".join(qolgan).strip() or "-"

    return ParsedEntry(tur=tur, summa=summa, tavsif=tavsif)


def qarz_xabarimi(text: str) -> bool:
    tokens = text.strip().split()
    return bool(tokens) and tokens[0].lower() == "qarz"


def parse_debt_add(text: str) -> ParsedDebt:
    tokens = text.strip().split()
    if len(tokens) < 4 or tokens[0].lower() != "qarz":
        raise ParseError(
            "Format: 'qarz berdim <ism> <summa> [muddat]' yoki 'qarz oldim <ism> <summa> [muddat]'"
        )

    tur = QARZ_FELLARI.get(tokens[1].lower())
    if tur is None:
        raise ParseError("'qarz berdim' yoki 'qarz oldim' deb yozing.")

    ism = tokens[2]

    try:
        summa, qolgan = summani_ajratish(tokens[3:])
    except ParseError:
        raise ParseError("Summa topilmadi. Masalan: 'qarz berdim Aliyev 500 ming 2 oydan keyin'")

    muddat = " ".join(qolgan).strip() or None

    return ParsedDebt(tur=tur, ism=ism, summa=summa, muddat=muddat)


def parse_debt_close(text: str) -> str:
    tokens = text.strip().split()
    if len(tokens) < 3 or tokens[0].lower() != "qarz" or tokens[1].lower() != "yopildi":
        raise ParseError("Format: 'qarz yopildi <ism>'")

    ism = " ".join(tokens[2:]).strip()
    if not ism:
        raise ParseError("Ism ko'rsatilmadi. Masalan: 'qarz yopildi Aliyev'")

    return ism
