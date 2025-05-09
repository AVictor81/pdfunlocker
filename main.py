from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse
import pikepdf
from io import BytesIO
import re
import fitz  # PyMuPDF

app = FastAPI()

COMPANY_MAP = {
    "SOLAR GENERATION POWER LLC": "SG",
    "ECO ENERGY POWER LLC": "Eco",
    "ENERGOEFFECT POWER LLC": "EF",
    "SOLIS POTENTIA HOLDING LLC": "SPH",
    "TERAWATT POWER LLC": "SPH",
}

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

    # 2) Открываем «как есть», если ни один пароль не подошёл
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        txt = "\n".join(page.get_text() for page in doc)
        doc.close()
        return txt, file_bytes
    except Exception:
        return "", b""

def parse_info(text: str) -> dict:
    best = len(text)
    company_code = ""
    currency_code = ""
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

    return {"company": company_code, "currency": currency_code}

@app.post("/extract-info")
async def extract_info(
    file: UploadFile = File(...),
    passwords: str = Form(None)
):
    fb = await file.read()
    pw_list = [p.strip() for p in passwords.split(",")] if passwords else []
    text, _ = extract_text_and_pdf_bytes(fb, pw_list)
    if not text:
        raise HTTPException(status_code=400, detail="Не удалось открыть PDF")
    info = parse_info(text)
    return JSONResponse(status_code=200, content=info)

@app.post("/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    passwords: str = Form(None)
):
    fb = await file.read()
    pw_list = [p.strip() for p in passwords.split(",")] if passwords else []
    _, pdf_bytes = extract_text_and_pdf_bytes(fb, pw_list)
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Не удалось открыть PDF")
    return Response(content=pdf_bytes, media_type="application/pdf")

