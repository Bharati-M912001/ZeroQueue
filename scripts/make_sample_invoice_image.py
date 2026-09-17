"""Create docs/samples/sample-invoice.png - a fake invoice IMAGE you can
attach in the chat to demo OCR (needs: pip install Pillow, plus the free
Tesseract install to read it back). Run from the repo root:

    python scripts/make_sample_invoice_image.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

LINES = [
    "Nivara Botanics - Tax Invoice",
    "Order: NB-1042",
    "Date: 12 Sep 2026",
    "Item: Rosehip Renewal Serum 30ml",
    "Qty: 1    Amount: Rs 1,299",
    "Shipping: Rs 0 (free over Rs 999)",
    "Status: Delivered 15 Sep 2026",
    "Payment: UPI",
]

out = Path(__file__).resolve().parents[1] / "docs" / "samples" / "sample-invoice.png"
img = Image.new("RGB", (640, 320), "white")
draw = ImageDraw.Draw(img)
y = 20
for line in LINES:
    draw.text((24, y), line, fill="black")
    y += 36
img.save(out)
print(f"Wrote {out}")
