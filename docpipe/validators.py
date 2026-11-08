"""Deterministic checks. A wrong digit should fail loudly instead of passing silently.

Statement labels differ between VAS ("Tổng cộng tài sản", "Nguồn vốn") and IFRS-style
statements ("TỔNG TÀI SẢN", "NỢ PHẢI TRẢ VÀ VỐN CHỦ SỞ HỮU"), so labels are matched by pattern.
"""
import re

import pymupdf

from .models import Check, PageExtraction

NUM = re.compile(r"\(?-?\d[\d.,]*\)?")
LEADING = re.compile(r"^(?:[A-ZIVX]+\.|\d+\.|\([a-z0-9]+\))\s*")  # "A. ", "I. ", "1. "

PATTERNS = {
    "total_assets": re.compile(r"^tổng( cộng)? tài sản$"),
    "current_assets": re.compile(r"^tài sản (ngắn hạn|lưu động)"),
    "noncurrent_assets": re.compile(r"^tài sản (dài hạn|cố định)"),
    "liabilities": re.compile(r"^nợ phải trả$"),
    "equity": re.compile(r"^vốn chủ sở hữu$"),
    "total_le": re.compile(r"^(tổng( cộng)? (nguồn vốn|nợ phải trả và vốn chủ sở hữu)|nợ phải trả và vốn chủ sở hữu)$"),
    "bs_cash": re.compile(r"^tiền và (các khoản )?tương đương tiền$"),
    "revenue": re.compile(r"^doanh thu( thuần)?( về bán hàng và cung cấp dịch vụ)?$"),
    "cogs": re.compile(r"^giá vốn hàng bán"),
    "gross_profit": re.compile(r"^lợi nhuận gộp"),
    "pbt": re.compile(r"^(tổng )?lợi nhuận (kế toán )?trước thuế"),
    "tax": re.compile(r"^(chi phí |lợi ích |thu nhập )?thuế (thu nhập doanh nghiệp|tndn)( hiện hành| hoãn lại)?$"),
    "net_profit": re.compile(r"^lợi nhuận (thuần|sau thuế)( thu nhập doanh nghiệp| tndn)?$"),
    "cash_open": re.compile(r"^tiền và (các khoản )?tương đương tiền đầu"),
    "cash_close": re.compile(r"^tiền và (các khoản )?tương đương tiền cuối"),
    "cash_net": re.compile(r"^(lưu chuyển )?tiền thuần trong (năm|kỳ)|^lưu chuyển tiền thuần trong"),
    "cfo": re.compile(r"^(lưu chuyển )?tiền thuần (thu |chi )?(từ|cho) hoạt động kinh doanh"),
    "cfi": re.compile(r"^(lưu chuyển )?tiền thuần (thu |chi )?(từ|cho) hoạt động đầu tư"),
    "cff": re.compile(r"^(lưu chuyển )?tiền thuần (thu |chi )?(từ|cho) hoạt động tài chính"),
}
UNITS = re.compile(r"(triệu|nghìn|ngàn|tỷ|vnd|đồng|vnđ)", re.I)


def norm(label: str) -> str:
    s = LEADING.sub("", label.strip()).lower()
    # VAS labels carry the line-code formula, e.g. "TỔNG TÀI SẢN (270 = 100 + 200)"; drop it, even if truncated
    s = re.sub(r"(\s*\([^)]*\)?)+\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip(" :")


def find(items, key):
    pat = PATTERNS[key]
    for it in items:
        if pat.match(norm(it.label)):
            return it
    return None


def text_numbers(page_text: str) -> set:
    """Digit strings of every number printed in the page text layer."""
    out = set()
    for tok in NUM.findall(page_text):
        digits = re.sub(r"\D", "", tok)
        if digits:
            out.add(digits.lstrip("0") or "0")
    return out


def is_critical(label: str) -> bool:
    n = norm(label)
    return any(p.match(n) for p in PATTERNS.values())


def support(pages: dict, doc: pymupdf.Document):
    """(ratio, unsupported) for extracted numbers vs the page text layer; None when there is no text layer.

    unsupported is a list of (page, label, value, critical).
    """
    total = 0
    unsupported = []
    for i, ex in pages.items():
        text = doc[i - 1].get_text()
        if len(text.strip()) <= 50:
            return None
        nums = text_numbers(text)
        for it in ex.items:
            for v in (it.current, it.prior):
                if v is None:
                    continue
                total += 1
                digits = str(int(abs(v))).lstrip("0")
                if digits and digits not in nums:
                    unsupported.append((i, it.label, v, is_critical(it.label)))
    return ((total - len(unsupported)) / total if total else None), unsupported


def run(pages: dict, doc: pymupdf.Document, vcfg) -> list:
    checks = []
    bs = [it for ex in pages.values() if ex.page_type == "balance_sheet" for it in ex.items]
    tol = vcfg.balance_tolerance

    # units present on every statement page
    bad = [i for i, ex in pages.items() if not UNITS.search(ex.unit or "")]
    checks.append(Check(name="unit_present", status="fail" if bad else "pass",
                        detail=f"pages without a recognisable unit: {bad}" if bad else ""))

    # the same unit across the statements of one document
    units = {ex.unit.strip().lower() for ex in pages.values()}
    checks.append(Check(name="unit_consistent", status="pass" if len(units) <= 1 else "fail",
                        detail="" if len(units) <= 1 else f"units seen: {sorted(units)}"))

    if not bs:
        checks.append(Check(name="balance_sheet_found", status="fail", detail="no balance-sheet page extracted"))
    else:
        ta, tle = find(bs, "total_assets"), find(bs, "total_le")
        li, eq = find(bs, "liabilities"), find(bs, "equity")
        ca, nca = find(bs, "current_assets"), find(bs, "noncurrent_assets")
        for col in ("current", "prior"):
            def v(it):
                return getattr(it, col) if it else None
            a = v(ta)
            right = v(tle)
            if right is None and v(li) is not None and v(eq) is not None:
                right = v(li) + v(eq)
            if a is None or right is None:
                checks.append(Check(name=f"assets_eq_liab_equity[{col}]", status="skip",
                                    detail="total assets or total sources not found"))
            else:
                diff = abs(a - right)
                checks.append(Check(name=f"assets_eq_liab_equity[{col}]", status="pass" if diff <= tol else "fail",
                                    detail=f"assets={a:,.0f} sources={right:,.0f} diff={diff:,.0f}"))
            if a is not None and v(ca) is not None and v(nca) is not None:
                diff = abs(a - (v(ca) + v(nca)))
                checks.append(Check(name=f"current_plus_noncurrent[{col}]", status="pass" if diff <= tol else "fail",
                                    detail=f"diff={diff:,.0f}"))

    checks += statement_checks(pages, bs, tol)

    # every value must be printed on the page (fabrication check); key totals must all be supported
    res = support(pages, doc)
    if res is None or res[0] is None:
        checks.append(Check(name="text_support", status="skip", detail="no text layer (scan)"))
    else:
        ratio, bad = res
        ok = len(bad) <= vcfg.max_unsupported
        detail = f"{ratio:.1%} of extracted numbers appear in the page text"
        if bad:
            detail += "; unsupported: " + ", ".join(f"p{p} {l[:30]}={v:,.0f}" for p, l, v, _ in bad[:4])
        checks.append(Check(name="text_support", status="pass" if ok else "fail", detail=detail))
    return checks


def _fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").replace("đ", "d").replace("Đ", "D"))
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in s if not unicodedata.combining(c)).lower()))


def classification_evidence(meta, text: str) -> list:
    """Deterministic checks for documents without statement tables, where arithmetic validators do not apply:
    the classifier's evidence quote and the company name must both be found in the document text (accent-folded),
    so a hallucinated label or company cannot be auto-filed on the model's self-reported confidence alone."""
    body = _fold(text)
    words_in_body = set(body.split())
    ev = _fold(meta.evidence)
    if len(ev) < 6:
        c1 = Check(name="classification_evidence", status="fail", detail="no evidence quote returned")
    else:
        words = ev.split()
        # tolerate small OCR/quote differences: the exact quote, or 80% of its words present in the text
        hit = ev in body or sum(w in words_in_body for w in words) / len(words) >= 0.8
        c1 = Check(name="classification_evidence", status="pass" if hit else "fail",
                   detail=f"evidence quote {'found' if hit else 'NOT found'} in text: {meta.evidence[:80]!r}")
    name = re.sub(r"\b(cong ty|co phan|tnhh|trach nhiem huu han|ctcp|tap doan|ngan hang|thuong mai)\b", " ", _fold(meta.company))
    core = [w for w in name.split() if len(w) > 1]
    found = sum(w in words_in_body for w in core)
    ok = bool(core) and found / len(core) >= 0.8
    c2 = Check(name="company_in_text", status="pass" if ok else "fail",
               detail=f"{found}/{len(core)} words of {meta.company!r} found in the text")
    return [c1, c2]


def confidence(checks: list, meta_conf: float) -> float:
    """Signals, not the model's self-report: any failed check halves confidence."""
    c = meta_conf
    for k in checks:
        if k.status == "fail":
            c *= 0.5
    return round(c, 3)


def _eq(name, lhs, rhs, tol, text):
    if lhs is None or rhs is None:
        return Check(name=name, status="skip", detail="required line items not found")
    diff = abs(lhs - rhs)
    return Check(name=name, status="pass" if diff <= tol else "fail", detail=f"{text} lhs={lhs:,.0f} rhs={rhs:,.0f} diff={diff:,.0f}")


def statement_checks(pages: dict, bs_items: list, tol: float) -> list:
    """Income-statement and cash-flow arithmetic, plus the cash tie-out to the balance sheet.

    Each check skips (not fails) when its line items cannot be found, because label sets differ by issuer.
    """
    out = []
    inc = [it for ex in pages.values() if ex.page_type == "income_statement" for it in ex.items]
    # Segment or notes pages can also be typed as income statements; profit and tax must come from the same page.
    main_inc = next((ex.items for ex in pages.values() if ex.page_type == "income_statement"
                     and find(ex.items, "pbt") and find(ex.items, "net_profit")), None)
    cf = [it for ex in pages.values() if ex.page_type == "cash_flow" for it in ex.items]
    for col in ("current", "prior"):
        def val(items, key):
            it = find(items, key)
            return getattr(it, col) if it else None
        if inc:
            rev, cogs, gp = val(inc, "revenue"), val(inc, "cogs"), val(inc, "gross_profit")
            out.append(_eq(f"gross_profit[{col}]", gp, None if rev is None or cogs is None else abs(rev) - abs(cogs), tol,
                           "gross profit = revenue - cost of sales"))
            pbt, net = (val(main_inc, "pbt"), val(main_inc, "net_profit")) if main_inc else (None, None)
            tax_items = [it for it in (main_inc or []) if PATTERNS["tax"].match(norm(it.label))
                         and getattr(it, col) is not None]
            # Banks print current + deferred AND their total; summing all three double-counts. Prefer the total line
            # (no 'hiện hành'/'hoãn lại' suffix) when present, else sum the components.
            totals = [it for it in tax_items if not re.search(r"(hiện hành|hoãn lại)$", norm(it.label))]
            taxes = [getattr(it, col) for it in (totals if totals and len(tax_items) > 1 else tax_items)]
            rhs = None
            if pbt is not None and taxes:
                # printed sign differs by issuer (expense positive in VAS, negative in IFRS-style): accept either
                rhs = min((pbt - sum(taxes), pbt + sum(taxes)), key=lambda r: abs(r - net) if net is not None else 0)
            out.append(_eq(f"net_profit[{col}]", net, rhs, tol, "net profit = profit before tax - tax"))
        if cf:
            opn, close, net = val(cf, "cash_open"), val(cf, "cash_close"), val(cf, "cash_net")
            fx = sum(getattr(it, col) or 0 for it in cf
                     if re.search(r"^(ảnh hưởng của thay đổi tỷ giá|chênh lệch quy đổi)", norm(it.label)))
            out.append(_eq(f"cash_roll_forward[{col}]", close, None if opn is None or net is None else opn + net + fx, tol,
                           "closing cash = opening + net change + FX"))
            parts = [val(cf, k) for k in ("cfo", "cfi", "cff")]
            out.append(_eq(f"cash_net_change[{col}]", net, None if None in parts else sum(parts), tol,
                           "net change = operating + investing + financing"))
            if bs_items:
                out.append(_eq(f"cash_ties_to_balance_sheet[{col}]", close, val(bs_items, "bs_cash"), tol,
                               "closing cash = balance-sheet cash"))
    return out


def agreement(p1: dict, p2: dict) -> Check:
    """Two independent reads of the same pages must yield the same multiset of values (label-free, so
    spelling differences between passes do not matter). Used where no text layer can confirm the numbers."""
    from collections import Counter

    def bag(ex):
        return Counter(int(abs(v)) for it in ex.items for v in (it.current, it.prior) if v is not None)

    bad, total = [], 0
    for i, a in p1.items():
        if i not in p2:
            continue
        ca, cb = bag(a), bag(p2[i])
        total += sum(ca.values())
        for v in (ca - cb):
            bad.append((i, v, "pass1 only"))
        for v in (cb - ca):
            bad.append((i, v, "pass2 only"))
    detail = f"{len(bad)} disagreeing values over {total}"
    if bad:
        detail += ": " + ", ".join(f"p{i} {v:,} ({w})" for i, v, w in bad[:5])
    return Check(name="two_pass_agreement", status="fail" if bad else "pass", detail=detail)
