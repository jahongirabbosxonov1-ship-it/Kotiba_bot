import re
from dataclasses import dataclass

TUR_KALITLARI = {
    "kirim": "kirim",
    "kirdi": "kirim",
    "chiqim": "chiqim",
    "xarajat": "chiqim",
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


class ParseError(Exception):
    pass


def _sonmi(token: str) -> bool:
    return bool(SON_REGEX.match(token.replace(" ", "")))


def parse_entry(text: str) -> ParsedEntry:
    tokens = text.strip().split()
    if len(tokens) < 2:
        raise ParseError("Xabar juda qisqa")

    tur_kalit = tokens[0].lower()
    tur = TUR_KALITLARI.get(tur_kalit)
    if tur is None:
        raise ParseError(f"Noma'lum tur: '{tokens[0]}'. 'kirim' yoki 'chiqim' bilan boshlang.")

    qolgan = tokens[1:]
    if not qolgan or not _sonmi(qolgan[0]):
        raise ParseError("Summa topilmadi. Masalan: 'chiqim 50 ming taksi'")

    summa = float(qolgan[0].replace(",", "."))
    qolgan = qolgan[1:]

    if qolgan and qolgan[0].lower() in KOPAYTIRUVCHILAR:
        summa *= KOPAYTIRUVCHILAR[qolgan[0].lower()]
        qolgan = qolgan[1:]

    if qolgan and qolgan[0].lower() in BIRLIK_SOZLAR:
        qolgan = qolgan[1:]

    tavsif = " ".join(qolgan).strip() or "-"

    return ParsedEntry(tur=tur, summa=summa, tavsif=tavsif)
