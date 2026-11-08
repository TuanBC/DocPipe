"""PII detector evaluation on SEEDED SYNTHETIC lines (no real personal data).

Compares the local regex detector (L1) with the Luna detector (L0) per entity group.
Negatives include look-alikes that real financial documents contain: long amounts, company tax
codes, company addresses, account-like numbers.
Run: uv run --group gateway python -m evals.pii_eval
"""
import json
import random
from collections import defaultdict
from pathlib import Path

from docpipe import config, llm, pii

random.seed(7)
SURNAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi"]
MIDDLE = ["Văn", "Thị", "Minh", "Quốc", "Ngọc", "Hữu"]
GIVEN = ["An", "Bình", "Châu", "Dũng", "Hà", "Khánh", "Lan", "Phúc", "Quang", "Trang"]
STREETS = ["Lê Lợi", "Nguyễn Huệ", "Trần Hưng Đạo", "Hai Bà Trưng", "Phạm Ngọc Thạch"]
DISTRICTS = ["Quận 1", "Quận Ba Đình", "Quận Hải Châu", "Quận Cầu Giấy", "Quận 3"]
CITIES = ["TP. Hồ Chí Minh", "Hà Nội", "Đà Nẵng"]
GROUP = {"VN_CCCD": "ID_NUMBER", "VN_CMND": "ID_NUMBER", "VN_PHONE": "PHONE", "EMAIL": "EMAIL",
         "ID_NUMBER": "ID_NUMBER", "PHONE": "PHONE", "PERSON": "PERSON", "ADDRESS": "ADDRESS"}


def name():
    return f"{random.choice(SURNAMES)} {random.choice(MIDDLE)} {random.choice(GIVEN)}"


def cccd():
    return "0" + "".join(random.choice("0123456789") for _ in range(11))


def phone():
    p = "0" + random.choice("35789") + "".join(random.choice("0123456789") for _ in range(8))
    style = random.choice(["plain", "space", "dot"])
    if style == "space":
        return f"{p[:4]} {p[4:7]} {p[7:]}"
    if style == "dot":
        return f"{p[:3]}.{p[3:6]}.{p[6:]}"
    return p


def email(n):
    local = "".join(c for c in n.lower() if c.isascii() and c.isalpha())
    return f"{local}{random.randint(1, 99)}@example.com"


def addr():
    return f"số {random.randint(1, 99)} {random.choice(STREETS)}, {random.choice(DISTRICTS)}, {random.choice(CITIES)}"


def positives():
    rows = []
    for _ in range(12):
        n, c, p = name(), cccd(), phone()
        rows.append((f"Người đại diện theo pháp luật: {n}, CCCD số {c}, điện thoại {p}",
                     [("PERSON", n), ("ID_NUMBER", c), ("PHONE", p)]))
    for _ in range(10):
        n = name()
        e, p = email(n), phone()
        rows.append((f"Liên hệ: {n} - {p} - {e}", [("PERSON", n), ("PHONE", p), ("EMAIL", e)]))
    for _ in range(8):
        n, a = name(), addr()
        rows.append((f"Cổ đông cá nhân {n}, địa chỉ thường trú: {a}", [("PERSON", n), ("ADDRESS", a)]))
    for _ in range(6):
        n, c = name(), cccd()
        rows.append((f"Ông/Bà {n} (số định danh cá nhân {c}) sở hữu 1.250.000 cổ phiếu", [("PERSON", n), ("ID_NUMBER", c)]))
    return rows


NEGATIVES = [
    "Tổng cộng tài sản 56.091.826 triệu đồng tại ngày 31/12/2025",
    "Doanh thu thuần 63.724.000.000.000 đồng, tăng 3,1% so với năm trước",
    "Mã số thuế: 0300588569 - Công ty Cổ phần Sữa Việt Nam",
    "Địa chỉ trụ sở chính: 10 Tân Trào, Phường Tân Phú, Quận 7, TP. Hồ Chí Minh",
    "Số dư tiền gửi 100000001234 đồng tại ngân hàng",
    "Lợi nhuận sau thuế 9.380.000 triệu đồng, 059.692 8.130 triệu đồng chi phí khác",
    "Công ty TNHH Một thành viên ABC Việt Nam, vốn điều lệ 20.899.554.450.000 đồng",
    "Báo cáo kiểm toán số 1234567890 của Công ty TNHH KPMG",
    "Hàng tồn kho 6.555.827 6.380.777 triệu đồng",
    "Phải thu khách hàng 21.354.864 23.260.089",
    "Tài sản dài hạn 19.884.372 19.491.725 triệu đồng",
    "Nợ ngắn hạn 0912345678901 đồng (mã giao dịch nội bộ)",
]


def score(name_, preds_by_line, gold_by_line):
    tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
    for line, gold in gold_by_line.items():
        pred = {(GROUP[t], x) for t, x in preds_by_line.get(line, [])}
        g = set(gold)
        for t, x in pred & g:
            tp[t] += 1
        for t, x in pred - g:
            fp[t] += 1
        for t, x in g - pred:
            fn[t] += 1
    print(f"\n{name_}")
    print(f"{'type':10} {'TP':>3} {'FP':>3} {'FN':>3} {'precision':>9} {'recall':>7}")
    res = {}
    for t in ("PERSON", "ID_NUMBER", "PHONE", "EMAIL", "ADDRESS"):
        p = tp[t] / (tp[t] + fp[t]) if tp[t] + fp[t] else None
        r = tp[t] / (tp[t] + fn[t]) if tp[t] + fn[t] else None
        res[t] = {"tp": tp[t], "fp": fp[t], "fn": fn[t], "precision": p, "recall": r}
        fmt = lambda v: "  n/a" if v is None else f"{v:.2f}"  # noqa: E731
        print(f"{t:10} {tp[t]:>3} {fp[t]:>3} {fn[t]:>3} {fmt(p):>9} {fmt(r):>7}")
    return res


def main():
    cfg = config.load()
    pos = positives()
    lines = [(t, g) for t, g in pos] + [(t, []) for t in NEGATIVES]
    random.shuffle(lines)
    gold = {t: g for t, g in lines}

    regex_preds = {t: [(e.type, e.text) for e in pii.detect_regex(t, cfg.pii.entities)] for t in gold}

    usage = llm.Usage()
    luna_preds = {}
    texts = list(gold)
    for i in range(0, len(texts), 10):
        batch = texts[i:i + 10]
        found = pii.detect_luna("\n".join(batch), cfg, usage, None, "pii_eval")
        for t in batch:
            luna_preds[t] = [(e.type, e.text) for e in found if e.text in t]
    out = {"regex": score("regex (L1, local)", regex_preds, gold), "luna": score("luna (L0, hosted)", luna_preds, gold),
           "usage": usage.as_dict(cfg.model), "lines": len(gold), "positive_lines": len(pos)}
    print("\nluna usage:", out["usage"])
    Path("data/eval").mkdir(parents=True, exist_ok=True)
    Path("data/eval/pii_eval.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
