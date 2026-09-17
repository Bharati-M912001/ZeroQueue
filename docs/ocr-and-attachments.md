# Attachments and OCR

Customers can attach an **image**, a **video**, or an **invoice/document**
(pdf, txt) to any chat message. ZeroQueue reads the file and uses the
extracted text as part of the question - so a customer can show an
invoice instead of typing an order number.

## What works with ZERO setup

- `.txt` / `.md` files - read directly.
- Digital PDFs (invoices exported from any billing tool) - read with
  pypdf, already in requirements.txt.

## Images and scanned PDFs: install Tesseract once (free, 2 minutes)

1. Download the Windows installer from
   https://github.com/UB-Mannheim/tesseract/wiki (the 64-bit .exe).
2. Run it, keep defaults. It installs to `C:\Program Files\Tesseract-OCR`.
3. If the chat says "Tesseract is not installed", add this line to your
   `.env`:
   `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

## Videos

OpenCV (in requirements.txt) samples up to 5 frames and OCRs each one;
duplicate lines are removed. Nothing else to install.

## Optional: Groq vision instead of Tesseract

If you set `OCR_PROVIDER=groq` (and MOCK_MODE=false with a Groq key),
images are read by the free Groq vision model instead of local OCR.
Better on messy invoices; needs internet. Tesseract is the default
because it works offline and costs nothing.

## Try it

1. Run the backend and the page.
2. Attach `docs/samples/invoice-sample.txt` and ask "Can I return this?" -
   the answer uses the policy AND the order on the invoice.
3. For an image demo: `python scripts/make_sample_invoice_image.py`
   creates `docs/samples/sample-invoice.png`; attach it (needs Tesseract).
