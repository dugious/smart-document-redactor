"""Conservative English/US structured detectors; no network validation."""
from dataclasses import dataclass
import re
from smart_redactor.detection.email import detect_email

TYPES = ('EMAIL', 'PHONE', 'CREDIT_CARD', 'ADDRESS', 'PERSON')
PRIORITY = {'CREDIT_CARD': 0, 'EMAIL': 1, 'PHONE': 2, 'ADDRESS': 3, 'PERSON': 4}


@dataclass(frozen=True)
class Candidate:
    type: str
    start: int
    end: int
    text: str
    source: str = 'regex'
    confidence: float | None = None


def luhn(value: str) -> bool:
    if not re.fullmatch(r'[0-9 -]+', value):
        return False
    digits = [int(c) for c in value if c.isascii() and c.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        doubled = digit * 2 if i % 2 else digit
        total += doubled - 9 if doubled > 9 else doubled
    return total % 10 == 0


CARD = re.compile(r'(?<![\w+.-])(?:[0-9][ -]?){12,18}[0-9](?![\w-])')
# Explicit separators required. Bare 10-digit numbers are not classified as phones.
PHONE = re.compile(r'(?<![\w+.-])(?:\+?1[ .-])?(?:\([2-9][0-9]{2}\)[ ]?|[2-9][0-9]{2}[ .-])[2-9][0-9]{2}[ .-][0-9]{4}(?:[ ]?(?:ext\.?|x)[ ]?[0-9]{1,6})?(?![\w-])', re.IGNORECASE)
ADDRESS = re.compile(r'(?<![\w.])\b[0-9]{1,6}[ ]+(?:[A-Z][A-Za-z\'-]*[ ]+){1,4}(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Ln\.?|Drive|Dr\.?|Boulevard|Blvd\.?|Court|Ct\.?)(?![A-Za-z])(?:[ ,]+(?:Apt|Suite|Unit)[ .#]*[A-Za-z0-9-]+)?')


def resolve_overlaps(candidates: list[Candidate]) -> list[Candidate]:
    """Priority, longer span, earlier start, then type; half-open adjacency allowed.

    Resolve all types BEFORE filtering user categories so disabling cards cannot
    reinterpret part of a validated card as a phone. Never merge regions.
    """
    accepted = []
    for candidate in sorted(candidates, key=lambda c: (PRIORITY[c.type], -(c.end-c.start), c.start, c.type, c.text)):
        if not any(candidate.start < other.end and other.start < candidate.end for other in accepted):
            accepted.append(candidate)
    return sorted(accepted, key=lambda c: (c.start, c.end, c.type))


def detect_structured(text: str) -> list[Candidate]:
    candidates = [Candidate('EMAIL', start, end, value) for start, end, value in detect_email(text)]
    candidates.extend(Candidate('CREDIT_CARD', m.start(), m.end(), m.group()) for m in CARD.finditer(text) if luhn(m.group()))
    candidates.extend(Candidate('PHONE', m.start(), m.end(), m.group()) for m in PHONE.finditer(text))
    candidates.extend(Candidate('ADDRESS', m.start(), m.end(), m.group()) for m in ADDRESS.finditer(text))
    return resolve_overlaps(candidates)
