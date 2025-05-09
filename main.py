from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import pikepdf
from io import BytesIO
import re
import fitz  # PyMuPDF
import base64

app = FastAPI()

# Словарь соответствия компаний и сокращений
COMPANY_MAP = {
    "SOLAR GENERATION POWER LLC": "SG",
    "ECO ENERGY POWER LLC": "Eco",
    "ENERGOEFFECT POWER LLC": "EF",
    "SOLIS POTENTIA HOLDING LLC": "SPH",
    "Terawatt power LLC": "SPH"
}

# Словарь соответствия валют
CURRENCY_MAP = {
    "US DOLLARS": "USD",
    "US DOLLAR": "USD",
    "EURO": "EUR",
    "UAE DIRHAM": "AED",
    "ARAB EMIRATES DIRHAMS": "AED",
    "QAR": "QAR",
    "QATARI RIYAL": "QAR",
    "SWISS FRANCS": "CHF",
    "CHINESE YUAN RENMINBI": "CNY",
    "RUSSIAN RUBLES": "RUR"
}


def extract_text_and_unlocked_pdf(file_bytes: bytes, passwords: list[str]) -> tuple[str, bytes]:
    for password in passwords:
        try:
            with pikepdf.open(BytesIO(file_bytes), password=password) as pdf:
                output = BytesIO()
                pdf.save(output)
                unlocked_pdf = output.getvalue()
                doc = fitz.open(stream=unlocked_pdf, filetype="pdf")
                full_text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return full_text, unlocked_pdf
        except Exception:
            continue

    # Если не удалось снять защиту — пробуем открыть как обычный PDF
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return full_text, file_bytes
    except Exception:
        return "ERROR: Failed to open PDF with provided passwords", b""


def parse_info(text: str):
    company_full = company_code = currency_code = None
    best_position = len(text)
    upper_text = text.upper()

    for name, code in COMPANY_MAP.items():
        pos = upper_text.find(name.upper())
        if 0 <= pos < best_position:
            best_position = pos
            company_full = name
            company_code = code

    currency_match = re.search(r"Currency\s*[:\-]?\s*([A-Za-z ]+)", text)
    if currency_match:
        currency_name = currency_match.group(1).strip().upper()
        currency_code = CURRENCY_MAP.get(currency_name, currency_name)

    return {
        "company": company_code,
        "currency": currency_code,
        "raw": text[:500]
    }


@app.post("/extract-info")
async def extract_info(file: UploadFile = File(...)):
    contents = await file.read()

    passwords = ["1234", "12345", "0000", "1111", ""]

    text, unlocked_pdf = extract_text_and_unlocked_pdf(contents, passwords)

    if not unlocked_pdf:
        raise HTTPException(status_code=400, detail="Failed to unlock PDF with provided passwords.")

    parsed = parse_info(text)

    pdf_base64 = base64.b64encode(unlocked_pdf).decode("utf-8")

    return {
    "company": company,
    "currency": currency,
    "pdf_base64": pdf_base64,
    "raw": extracted_text[:1000]  # можно больше, если нужно
}
