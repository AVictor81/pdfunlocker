from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
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
    "SOLIS POTENTIA HOLDING LLC": "SPH"
}

# Словарь соответствия валют
CURRENCY_MAP = {
    "US DOLLARS": "USD",
    "US Dollar": "USD",
    "EURO": "EUR",
    "UAE DIRHAM": "AED",
    "ARAB EMIRATES DIRHAMS": "AED",
    "QATARI RIYAL": "QAR",
    "SWISS FRANCS": "CHF",
    "CHINESE YUAN RENMINBI": "CNY",
    "RUSSIAN RUBLES": "RUR"
}

def extract_text_from_pdf(file_bytes: bytes, passwords: list[str]) -> str:
    # Пробуем все пароли сначала
    for password in passwords:
        try:
            with pikepdf.open(BytesIO(file_bytes), password=password) as pdf:
                output = BytesIO()
                pdf.save(output)
                output.seek(0)
                doc = fitz.open(stream=output.read(), filetype="pdf")
                full_text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return full_text
        except Exception:
            continue

    # Если пароли не помогли — пробуем без пароля в явном виде
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return full_text
    except Exception:
        return "ERROR: Failed to open PDF with provided passwords"


def parse_info(text: str):
    company_full = company_code = currency_code = None
    best_position = len(text)

    for name, code in COMPANY_MAP.items():
        pos = text.find(name)
        if 0 <= pos < best_position:
            best_position = pos
            company_full = name
            company_code = code

    currency_match = re.search(r"Currency\s*[:\-]?\s*([A-Z ]+)", text)
    if currency_match:
        currency_name = currency_match.group(1).strip()
        currency_code = CURRENCY_MAP.get(currency_name, currency_name)

    return {
        "company": company_code,
        "currency": currency_code,
        "raw": text[:500]
    }


@app.post("/extract-info")
async def extract_info(file: UploadFile = File(...), passwords: str = Form(None)):
    file_bytes = await file.read()
    password_list = [p.strip() for p in passwords.split(",")] if passwords else []
    text = extract_text_from_pdf(file_bytes, password_list)

    if text.startswith("ERROR:"):
        return JSONResponse(status_code=400, content={"error": text})

    info = parse_info(text)
    return info