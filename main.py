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
    "EURO": "EUR",
    "UAE DIRHAM": "AED",
    "QATARI RIYAL": "QAR",
    "SWISS FRANCS": "CHF"
}

def extract_text_from_pdf(file_bytes: bytes, password: str | None = None) -> str:
    try:
        if password:
            with pikepdf.open(BytesIO(file_bytes), password=password) as pdf:
                output = BytesIO()
                pdf.save(output)
                output.seek(0)
                doc = fitz.open(stream=output.read(), filetype="pdf")
        else:
            doc = fitz.open(stream=file_bytes, filetype="pdf")

        full_text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return full_text

    except Exception as e:
        return f"ERROR: {str(e)}"


def parse_info(text: str):
    company_full = company_code = account = period = currency_code = None

    for name, code in COMPANY_MAP.items():
        if name in text:
            company_full = name
            company_code = code
            break

    account_match = re.search(r"40817\d{11}", text)
    if account_match:
        account = account_match.group(0)

    period_match = re.search(r"\b(0[1-9]|1[0-2])\.20\d{2}\b", text)
    if period_match:
        period = period_match.group(0)

    currency_match = re.search(r"Currency\s*[:\-]?\s*([A-Z ]+)", text)
    if currency_match:
        currency_name = currency_match.group(1).strip()
        currency_code = CURRENCY_MAP.get(currency_name, currency_name)

    return {
        "company": company_code,
        "account": account,
        "period": period,
        "currency": currency_code,
        "raw": text[:500]
    }


@app.post("/extract-info")
async def extract_info(file: UploadFile = File(...), password: str = Form(None)):
    file_bytes = await file.read()
    text = extract_text_from_pdf(file_bytes, password=password)

    if text.startswith("ERROR:"):
        return JSONResponse(status_code=400, content={"error": text})

    info = parse_info(text)
    return info
