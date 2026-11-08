"""PII guard with a switchable detector (config: pii.detector = regex | luna | both).

regex = L1 rung of the privacy ladder: local, deterministic, strong on structured Vietnamese IDs,
        blind to names and addresses. Regexes need validation against official formats before production.
luna  = L0 rung: the hosted model flags PII in the transcript. It shows the policy flow but is NOT a
        privacy barrier, because the page image has already gone to the same provider.
Presidio (container) replaces `regex` later behind the same interface.
"""
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from . import llm

CTX = 40  # characters of left context searched for keywords


@dataclass(frozen=True)
class Entity:
    type: str
    text: str


# Phone candidates are loose; _valid_phone() rejects financial figures such as "059.692 8.130".
_PHONE_GROUPS = {(4, 3, 3), (3, 3, 4), (3, 4, 3)}


def _valid_phone(s: str) -> bool:
    body = s[3:] if s.startswith("+84") else s
    lead_zero = not s.startswith("+84")
    seps = re.findall(r"[ .-]", body)
    if len(set(seps)) > 1:
        return False
    digits = re.sub(r"\D", "", body)
    if lead_zero and not (len(digits) == 10 and digits[0] == "0" and digits[1] in "35789"):
        return False
    if not lead_zero:
        digits = digits.lstrip("0")
        if not (len(digits) == 9 and digits[0] in "35789"):
            return False
        return True  # +84 numbers: separators vary too much to constrain
    if seps:
        groups = tuple(len(g) for g in re.split(r"[ .-]", body))
        return groups in _PHONE_GROUPS
    return True


PATTERNS = {
    "VN_CCCD": (re.compile(r"(?<!\d)\d{12}(?!\d)"), re.compile(r"cccd|căn cước|số định danh", re.I)),
    "VN_CMND": (re.compile(r"(?<!\d)\d{9}(?!\d)"), re.compile(r"cmnd|chứng minh", re.I)),
    "VN_PHONE": (re.compile(r"(?<![\d.,])(?:\+84|0)(?:[ .-]?\d){9}(?!\d|[.,]\d)"), None),
    "EMAIL": (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
}


def detect_regex(text: str, entities) -> list:
    found = []
    for etype in entities:
        pat, ctx = PATTERNS[etype]
        for m in pat.finditer(text):
            if ctx is not None and not ctx.search(text[max(0, m.start() - CTX):m.start()]):
                continue
            if etype == "VN_PHONE" and not _valid_phone(m.group()):
                continue
            found.append(Entity(etype, m.group()))
    return found


class _Hit(BaseModel):
    type: Literal["PERSON", "ID_NUMBER", "PHONE", "EMAIL", "ADDRESS"]
    text: str


class _Hits(BaseModel):
    entities: list[_Hit]


def detect_luna(text: str, cfg, usage, audit, doc_id) -> list:
    instr = ("Find personal data of natural persons in the document text: names of individuals, ID numbers "
             "(CCCD/CMND/passport), phone numbers, email addresses, home addresses. Do NOT list company names, "
             "company tax codes, company addresses or amounts. Copy each 'text' exactly as it appears.")
    hits = llm.call(cfg.model, instr, _Hits, text=text, usage=usage, audit=audit, doc_id=doc_id, step="pii_guard")
    return [Entity(h.type, h.text) for h in hits.entities if h.text and h.text in text]


def detect(text: str, cfg, usage, audit, doc_id) -> list:
    mode = cfg.pii.detector
    found = []
    if mode in ("regex", "both"):
        found += detect_regex(text, cfg.pii.entities)
    if mode in ("luna", "both"):
        found += detect_luna(text, cfg, usage, audit, doc_id)
    return sorted(set(found), key=lambda e: (e.type, e.text))


def mask(text: str, entities: list):
    """Replace each distinct entity with <TYPE_n>. Returns (masked_text, {token: original})."""
    mapping, counts = {}, {}
    for e in sorted(entities, key=lambda e: -len(e.text)):
        counts[e.type] = counts.get(e.type, 0) + 1
        token = f"<{e.type}_{counts[e.type]}>"
        mapping[token] = e.text
        text = text.replace(e.text, token)
    return text, mapping
