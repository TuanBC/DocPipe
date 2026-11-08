"""Synthetic scanned test documents (fictional companies and people, no real data) for the OCR and filing paths.

Writes to data/samples/:
  dkkd_an_phat.png          business registration certificate (image, no text layer)
  hopdong_tin_dung.pdf      2-page credit contract, rendered as images inside a PDF (a "scanned" PDF)
  hoadon_minh_long.jpg      VAT invoice photo (rotated, noisy)

Run: uv run python scripts/make_samples.py
"""
import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path("data/samples")
FONT = "C:/Windows/Fonts/arial.ttf"
BOLD = "C:/Windows/Fonts/arialbd.ttf"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def page(lines, size=(1654, 2339)):
    """lines: list of (text, size, bold, align) with align in {'l','c'}; '' = blank line."""
    img = Image.new("L", size, 250)
    d = ImageDraw.Draw(img)
    y = 140
    for ln in lines:
        if ln == "":
            y += 30
            continue
        text, sz, bold, align = ln
        f = font(sz, bold)
        w = d.textlength(text, font=f)
        x = (size[0] - w) / 2 if align == "c" else 150
        d.text((x, y), text, fill=20, font=f)
        y += int(sz * 1.55)
    return img


def scanify(img, angle=0.6, seed=1):
    rnd = random.Random(seed)
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=245)
    px = img.load()
    for _ in range(img.size[0] * img.size[1] // 60):
        x, y = rnd.randrange(img.size[0]), rnd.randrange(img.size[1])
        px[x, y] = rnd.choice((90, 160, 200))
    return img.filter(ImageFilter.GaussianBlur(0.7))


def stamp(img, xy, text="CÔNG TY TNHH", r=150):
    rgb = img.convert("RGB")
    d = ImageDraw.Draw(rgb)
    x, y = xy
    d.ellipse((x - r, y - r, x + r, y + r), outline=(200, 30, 30), width=8)
    d.ellipse((x - r + 25, y - r + 25, x + r - 25, y + r - 25), outline=(200, 30, 30), width=3)
    f = font(30, True)
    d.text((x - d.textlength(text, font=f) / 2, y - 18), text, fill=(200, 30, 30), font=f)
    return rgb


def dkkd():
    L = [
        ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", 40, True, "c"),
        ("Độc lập - Tự do - Hạnh phúc", 36, True, "c"),
        "",
        ("SỞ KẾ HOẠCH VÀ ĐẦU TƯ THÀNH PHỐ HÀ NỘI", 36, True, "c"),
        ("PHÒNG ĐĂNG KÝ KINH DOANH", 34, False, "c"),
        "",
        ("GIẤY CHỨNG NHẬN ĐĂNG KÝ DOANH NGHIỆP", 48, True, "c"),
        ("CÔNG TY CỔ PHẦN", 40, True, "c"),
        ("Mã số doanh nghiệp: 0109876543", 36, False, "c"),
        ("Đăng ký lần đầu: ngày 15 tháng 03 năm 2019", 32, False, "c"),
        ("Đăng ký thay đổi lần thứ 4: ngày 08 tháng 07 năm 2025", 32, False, "c"),
        "",
        ("1. Tên công ty", 36, True, "l"),
        ("Tên công ty viết bằng tiếng Việt: CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT", 32, False, "l"),
        ("Tên công ty viết bằng tiếng nước ngoài: AN PHAT TRADING JOINT STOCK COMPANY", 32, False, "l"),
        ("Tên công ty viết tắt: AN PHAT TRADING JSC", 32, False, "l"),
        "",
        ("2. Địa chỉ trụ sở chính", 36, True, "l"),
        ("Số 12 phố Hàng Giấy (giả định), Phường Đồng Xuân, Quận Hoàn Kiếm, Hà Nội", 32, False, "l"),
        ("Điện thoại: 024 3999 0000     Email: lienhe@anphat-demo.vn", 32, False, "l"),
        "",
        ("3. Vốn điều lệ: 45.000.000.000 đồng", 36, True, "l"),
        ("Bằng chữ: Bốn mươi lăm tỷ đồng. Mệnh giá cổ phần: 10.000 đồng", 32, False, "l"),
        ("Tổng số cổ phần: 4.500.000", 32, False, "l"),
        "",
        ("4. Người đại diện theo pháp luật của công ty", 36, True, "l"),
        ("Họ và tên: NGUYỄN VĂN MẪU          Giới tính: Nam", 32, False, "l"),
        ("Chức danh: Tổng giám đốc", 32, False, "l"),
        ("Số định danh cá nhân (CCCD): 001090012345", 32, False, "l"),
        ("Điện thoại di động: 0912 345 678", 32, False, "l"),
        "",
        ("KT. TRƯỞNG PHÒNG", 32, True, "l"),
        ("PHÓ TRƯỞNG PHÒNG", 32, True, "l"),
    ]
    img = scanify(page(L), angle=0.8, seed=3)
    img = stamp(img, (1250, 2050), "PHÒNG ĐKKD")
    img.save(OUT / "dkkd_an_phat.png")


def contract():
    p1 = [
        ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", 40, True, "c"),
        ("Độc lập - Tự do - Hạnh phúc", 36, True, "c"),
        "",
        ("HỢP ĐỒNG TÍN DỤNG HẠN MỨC", 50, True, "c"),
        ("Số: 2025/HDTD/0457", 34, False, "c"),
        "",
        ("Hôm nay, ngày 20 tháng 08 năm 2025, tại Hà Nội, chúng tôi gồm:", 32, False, "l"),
        "",
        ("BÊN CHO VAY: NGÂN HÀNG TMCP DEMO VIỆT NAM - CHI NHÁNH HOÀN KIẾM", 32, True, "l"),
        ("Địa chỉ: Số 1 phố Mẫu (giả định), Quận Hoàn Kiếm, Hà Nội", 32, False, "l"),
        ("Đại diện: Ông Trần Thế Ví Dụ - Giám đốc chi nhánh", 32, False, "l"),
        "",
        ("BÊN VAY: CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT", 32, True, "l"),
        ("Mã số doanh nghiệp: 0109876543", 32, False, "l"),
        ("Đại diện: Ông Nguyễn Văn Mẫu - Tổng giám đốc", 32, False, "l"),
        "",
        ("Điều 1. Hạn mức tín dụng", 36, True, "l"),
        ("1.1. Hạn mức: 30.000.000.000 đồng (Ba mươi tỷ đồng).", 32, False, "l"),
        ("1.2. Mục đích: bổ sung vốn lưu động phục vụ hoạt động kinh doanh thương mại.", 32, False, "l"),
        ("1.3. Thời hạn duy trì hạn mức: 12 tháng kể từ ngày ký.", 32, False, "l"),
        "",
        ("Điều 2. Lãi suất và phí", 36, True, "l"),
        ("2.1. Lãi suất cho vay: 7,5%/năm, điều chỉnh 3 tháng một lần.", 32, False, "l"),
        ("2.2. Lãi suất quá hạn: 150% lãi suất trong hạn.", 32, False, "l"),
        ("2.3. Phí cam kết: 0,1% trên hạn mức chưa sử dụng.", 32, False, "l"),
    ]
    p2 = [
        ("Điều 3. Tài sản bảo đảm", 36, True, "l"),
        ("Quyền sử dụng đất và tài sản gắn liền với đất tại thửa số 88, tờ bản đồ số 12,", 32, False, "l"),
        ("theo Hợp đồng thế chấp số 2025/HDTC/0457 ký cùng ngày.", 32, False, "l"),
        "",
        ("Điều 4. Bảng tóm tắt điều kiện giải ngân", 36, True, "l"),
        ("Chỉ tiêu                              Điều kiện", 32, True, "l"),
        ("Hệ số nợ/vốn chủ sở hữu               tối đa 2,5 lần", 32, False, "l"),
        ("Doanh thu thuần năm gần nhất         tối thiểu 120.000.000.000 đồng", 32, False, "l"),
        ("Báo cáo tài chính                     đã kiểm toán năm 2024", 32, False, "l"),
        "",
        ("Điều 5. Điều khoản chung", 36, True, "l"),
        ("Hợp đồng có hiệu lực kể từ ngày ký và được lập thành 04 bản có giá trị như nhau.", 32, False, "l"),
        "",
        "",
        ("ĐẠI DIỆN BÊN CHO VAY                      ĐẠI DIỆN BÊN VAY", 34, True, "l"),
        "",
        "",
        ("Trần Thế Ví Dụ                                  Nguyễn Văn Mẫu", 32, False, "l"),
    ]
    pdf = pymupdf.open()
    for i, lines in enumerate((p1, p2)):
        img = scanify(page(lines), angle=-0.5 + i, seed=10 + i)
        if i == 1:
            img = stamp(img, (1200, 1350), "AN PHÁT")
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=80)
        pg = pdf.new_page(width=595, height=842)
        pg.insert_image(pg.rect, stream=buf.getvalue())
    pdf.save(OUT / "hopdong_tin_dung.pdf")


def invoice():
    L = [
        ("HÓA ĐƠN GIÁ TRỊ GIA TĂNG", 46, True, "c"),
        ("(VAT INVOICE)", 32, False, "c"),
        ("Ký hiệu: 1C25TML    Số: 0001284", 32, False, "c"),
        ("Ngày 05 tháng 09 năm 2025", 32, False, "c"),
        "",
        ("Đơn vị bán hàng: CÔNG TY TNHH THIẾT BỊ MINH LONG", 32, True, "l"),
        ("Mã số thuế: 0312345678", 32, False, "l"),
        ("Địa chỉ: 45 đường Ví Dụ (giả định), Quận 7, TP. Hồ Chí Minh", 32, False, "l"),
        "",
        ("Người mua hàng: CÔNG TY CỔ PHẦN THƯƠNG MẠI AN PHÁT", 32, True, "l"),
        ("Mã số thuế: 0109876543", 32, False, "l"),
        "",
        ("STT  Tên hàng hóa, dịch vụ        ĐVT   Số lượng   Đơn giá        Thành tiền", 30, True, "l"),
        ("1    Máy đóng gói tự động MP-200   Bộ    2          185.000.000    370.000.000", 30, False, "l"),
        ("2    Băng tải inox 3m             Cái   4          22.500.000     90.000.000", 30, False, "l"),
        ("3    Lắp đặt, chạy thử            Gói   1          15.000.000     15.000.000", 30, False, "l"),
        "",
        ("Cộng tiền hàng:                                              475.000.000", 30, True, "l"),
        ("Thuế suất GTGT: 10%   Tiền thuế GTGT:                         47.500.000", 30, True, "l"),
        ("Tổng cộng tiền thanh toán:                                   522.500.000", 32, True, "l"),
        ("Số tiền viết bằng chữ: Năm trăm hai mươi hai triệu năm trăm nghìn đồng.", 30, False, "l"),
    ]
    img = page(L, size=(1654, 1500))
    img = scanify(img, angle=2.2, seed=7)
    img = stamp(img, (1250, 1300), "MINH LONG", r=120)
    img.save(OUT / "hoadon_minh_long.jpg", quality=72)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    dkkd()
    contract()
    invoice()
    print("wrote", sorted(p.name for p in OUT.iterdir()))
