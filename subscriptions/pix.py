import unicodedata
from binascii import crc_hqx

from django.conf import settings

PIX_KEY = "62151351000150"


def ascii_name(value, limit):
    normalized = unicodedata.normalize("NFKD", value.upper()).encode("ascii", "ignore").decode("ascii")
    return " ".join("".join(char for char in normalized if char.isalnum() or char == " ").split())[:limit].strip()


def enabled():
    return bool(ascii_name(settings.PIX_MERCHANT_CITY, 15) and ascii_name(settings.PIX_MERCHANT_NAME, 25))


def field(tag, value):
    return f"{tag}{len(value):02}{value}"


def payload(order):
    merchant = field("00", "br.gov.bcb.pix") + field("01", PIX_KEY)
    txid = order.public_id.hex[:25]
    data = "".join((
        field("00", "01"), field("26", merchant), field("52", "0000"),
        field("53", "986"), field("54", f"{order.amount:.2f}"), field("58", "BR"),
        field("59", ascii_name(settings.PIX_MERCHANT_NAME, 25)),
        field("60", ascii_name(settings.PIX_MERCHANT_CITY, 15)),
        field("62", field("05", txid)), "6304",
    ))
    return f"{data}{crc_hqx(data.encode('ascii'), 0xFFFF):04X}"
