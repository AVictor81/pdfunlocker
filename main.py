from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import pikepdf
from io import BytesIO
import re
import fitz  # PyMuPDF

app = FastAPI()

# Словарь соответствия компаний и сокращений
COMPANY_MAP = {
    "SOLAR GENERATION POWER LLC": "SG",
    "ECO ENERGY POWER LLC": "Eco",
    "ENERGOEFFECT POWER LLC": "EF",
    "SOLIS POTENTIA HOLDING LLC": "SPH",
    "TERAWATT POWER LLC": "SPH",
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
    "RUSSIAN RUBLES": "RUR",
}

def extract_text_and_pdf_bytes(file_bytes: bytes, passwords: list[str]) -> tuple[str, bytes]:
    # 1) Пробуем все пароли
    for pwd in passwords:
        try:
            with pikepdf.open(BytesIO(file_bytes), password=pwd) as pdf:
                buf = BytesIO()
                pdf.save(buf)
                unlocked = buf.getvalue()
                doc = fitz.open(stream=unlocked, filetype="pdf")
                txt = "\n".join(page.get_text() for page in doc)
                doc.close()
                return txt, unlocked
        except Exception:
            continue

    # 2) Если ни один пароль не подошёл — открываем «как есть»
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        txt = "\n".join(page.get_text() for page in doc)
        doc.close()
        return txt, file_bytes
    except Exception:
        return "", b""

def parse_info(text: str) -> dict:
    best = len(text)
    company_code = currency_code = None
    ut = text.upper()

    for name, code in COMPANY_MAP.items():
        idx = ut.find(name)
        if 0 <= idx < best:
            best = idx
            company_code = code

    m = re.search(r"Currency\s*[:\-]?\s*([A-Za-z ]+)", text, flags=re.IGNORECASE)
    if m:
        cur = m.group(1).strip().upper()
        currency_code = CURRENCY_MAP.get(cur, cur)

    return {
        "company": company_code or "",
        "currency": currency_code or "",
    }

@app.post("/extract-info")
async def extract_info(
    file: UploadFile = File(...),
    passwords: str = Form(None)
):
    fb = await file.read()
    pw_list = [p.strip() for p in passwords.split(",")] if passwords else []

    text, pdf_bytes = extract_text_and_pdf_bytes(fb, pw_list)
    if not pdf_bytes:
        return JSONResponse(status_code=400, content={"error": "Failed to open PDF with provided passwords."})

    info = parse_info(text)

    # Возвращаем распароленный PDF вместе с нужными заголовками
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "x-company-code": info["company"],
            "x-currency-code": info["currency"],
        }
    )

