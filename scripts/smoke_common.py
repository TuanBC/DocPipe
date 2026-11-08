"""Shared helpers for the Luna smoke tests."""
import base64
import io

from PIL import Image, ImageDraw, ImageFont

ROWS = [
    ("BẢNG CÂN ĐỐI KẾ TOÁN", "Đơn vị: triệu đồng", ""),
    ("Chỉ tiêu", "31/12/2025", "31/12/2024"),
    ("A. Tài sản ngắn hạn", "1.250.400", "1.100.250"),
    ("B. Tài sản dài hạn", "2.349.600", "2.099.750"),
    ("TỔNG CỘNG TÀI SẢN", "3.600.000", "3.200.000"),
    ("C. Nợ phải trả", "2.100.000", "1.900.000"),
    ("D. Vốn chủ sở hữu", "1.500.000", "1.300.000"),
    ("TỔNG CỘNG NGUỒN VỐN", "3.600.000", "3.200.000"),
]

EXPECT = {"total_assets": 3600000, "total_liabilities": 2100000, "equity": 1500000, "total_assets_prior": 3200000}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["unit", "total_assets", "total_liabilities", "equity", "total_assets_prior"],
    "properties": {
        "unit": {"type": "string"},
        "total_assets": {"type": "number"},
        "total_liabilities": {"type": "number"},
        "equity": {"type": "number"},
        "total_assets_prior": {"type": "number"},
    },
}

PROMPT = "Extract the balance sheet totals as JSON. Numbers use '.' as thousands separator."


def make_image() -> bytes:
    img = Image.new("RGB", (900, 420), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(r"C:\Windows\Fonts\calibri.ttf", 26)
    fb = ImageFont.truetype(r"C:\Windows\Fonts\calibrib.ttf", 26)
    y = 20
    for i, (a, b, c) in enumerate(ROWS):
        font = fb if i in (0, 1, 4, 7) else f
        d.text((30, y), a, fill="black", font=font)
        d.text((520, y), b, fill="black", font=font)
        d.text((720, y), c, fill="black", font=font)
        y += 48
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def png_b64() -> str:
    return base64.b64encode(make_image()).decode()
