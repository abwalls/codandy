"""Best-effort scrubbing of untrusted telemetry text before it is retained.

No pattern set guarantees that every secret is removed, so normalization also withholds
whole provider sections (request data, cookies, frame variables, user identity) and
exports remain reviewable. Counts per section are kept; original values never are.
"""

import re
from collections import Counter

from app.debugging.models import RedactionCount

# Invisible and bidirectional controls can make displayed evidence differ from its content.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

_SECRET_KEY = (r"[\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key"
               r"|auth|session|cookie|credential|private[_-]?key|dsn)[\w.-]*")

# Ordered: specific formats run before generic assignments and emails.
_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE "
                               r"KEY-----|\Z)", re.DOTALL), "[redacted:private_key]"),
    ("jwt", re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"), "[redacted:jwt]"),
    ("provider_token", re.compile(
        r"\b(?:sntry[su]_[\w+/=-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_\w{30,}"
        r"|xox[abprs]-[\w-]{10,}|sk-(?:ant-|proj-)?[\w-]{20,}|sk_(?:live|test)_[A-Za-z0-9]{16,}"
        r"|AKIA[0-9A-Z]{16}|AIza[\w-]{35})"), "[redacted:token]"),
    ("url_credentials", re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]*@"),
     r"\1[redacted]@"),
    ("authorization", re.compile(r"(?i)\b(bearer|basic)\s+[\w.~+/-]+=*"), r"\1 [redacted]"),
    ("assignment", re.compile(rf"(?i)\b({_SECRET_KEY})([\"']?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&)\]}}]+)"),
     r"\1\2[redacted]"),
    ("email", re.compile(r"\b[\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[redacted:email]"),
    # Home directories identify people; the remainder of the path stays usable for binding.
    ("user_path", re.compile(r"(?i)(\b[a-z]:[\\/]+(?:users|documents and settings)[\\/]+"
                             r"|(?<![\w.])/(?:home|users)/)(?!\[user\])[^\\/\s:\"'<>|]+"),
     r"\1[user]"),
)
_CARD = re.compile(r"(?<![\d-])[3-6]\d{3}(?:[ -]?\d){9,15}(?![\d-])")


def _luhn(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


class Redactor:
    def __init__(self):
        self._counts: Counter[tuple[str, str]] = Counter()

    def text(self, value: str, section: str) -> str:
        cleaned, found = _CONTROL.subn("", value)
        self._count(section, "invisible_control", found)
        for kind, pattern, replacement in _PATTERNS:
            cleaned, found = pattern.subn(replacement, cleaned)
            self._count(section, kind, found)
        cards = 0

        def card(match: re.Match[str]) -> str:
            nonlocal cards
            digits = re.sub(r"\D", "", match.group())
            if 13 <= len(digits) <= 19 and _luhn(digits):
                cards += 1
                return "[redacted:card]"
            return match.group()

        cleaned = _CARD.sub(card, cleaned)
        self._count(section, "card_number", cards)
        return cleaned

    def _count(self, section: str, kind: str, found: int):
        if found:
            self._counts[(section, kind)] += found

    def summary(self) -> list[RedactionCount]:
        return [RedactionCount(section=section, kind=kind, count=count)
                for (section, kind), count in sorted(self._counts.items())]
