import re


def validate_currency_code(code: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{3}", code or ""))
