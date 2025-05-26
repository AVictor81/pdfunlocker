from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pikepdf
from io import BytesIO
import re
import fitz  # PyMuPDF
import base64

app = FastAPI(
    title="PDF Extraction Service",
    description="API for unlocking PDFs and extracting company and currency information.",
    version="1.1.0"
)

# Allow all origins for simplicity (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mapping of full company names to codes
COMPANY_MAP = {
    "SOLAR GENERATION POWER LLC": "SG",
    "ECO ENERGY POWER LLC": "Eco",
    "ENERGOEFFECT POWER LLC": "EF",
    "SOLIS POTENTIA HOLDING LLC": "SPH",
    "Terawatt power LLC": "SPH"
}

# Mapping of currency names to ISO codes
CURRENCY_MAP = {
    "US DOLLAR": "USD",
    "US DOLLARS": "USD",
    "EURO": "EUR",
    "UAE DIRHAM": "AED",
    "ARAB EMIRATES DIRHAMS": "AED",
    "QATARI RIYAL": "QAR",
    "Amount in QAR": "QAR",
    "SWISS FRANC": "CHF",
    "SWISS FRANCS": "CHF",
    "CHINESE YUAN RENMINBI": "CNY",
    "RUSSIAN RUBLE": "RUR",
    "RUSSIAN RUBLES": "RUR"
}


def extract_text_and_unlocked_pdf(file_bytes: bytes, passwords: list[str]) -> tuple[str, bytes]:
    """
    Attempt to unlock a password-protected PDF using the provided passwords,
    then extract its text. If none work, try opening it without password.
    Returns extracted text and the bytes of the (unlocked) PDF.
    """
    # Try each password
    for password in passwords:
        try:
            with pikepdf.open(BytesIO(file_bytes), password=password) as pdf:
                out = BytesIO()
                pdf.save(out)
                unlocked = out.getvalue()
                doc = fitz.open(stream=unlocked, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return text, unlocked
        except Exception:
            continue

    # Fallback: try without password
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text, file_bytes
    except Exception:
        raise ValueError("Failed to open PDF with provided passwords")


def parse_info(text: str) -> dict:
    """
    Parse the extracted text to identify the first occurring company and currency.
    Returns a dict with 'company', 'currency', and a 'raw' text excerpt.
    """
    upper = text.upper()
    best_pos = len(upper)
    found_company = None
    for full, code in COMPANY_MAP.items():
        idx = upper.find(full.upper())
        if 0 <= idx < best_pos:
            best_pos = idx
            found_company = code

    currency_match = re.search(r"Currency\s*[:\-]?\s*([A-Za-z ]+)", text)
    code = None
    if currency_match:
        name = currency_match.group(1).strip().upper()
        code = CURRENCY_MAP.get(name, name)

    return {"company": found_company, "currency": code, "raw": text[:500]}


@app.post("/extract-info")
async def extract_info(
    file: UploadFile = File(...),
    passwords: str = Form(None)
):
    """
    Unlock the uploaded PDF (using comma-separated passwords if provided),
    extract text, parse company and currency, and return results plus
    Base64-encoded unlocked PDF.
    """
    data = await file.read()
    pw_list = [p.strip() for p in passwords.split(",")] if passwords else []
    try:
        txt, pdf_bytes = extract_text_and_unlocked_pdf(data, pw_list)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    info = parse_info(txt)
    return {
        "company": info["company"],
        "currency": info["currency"],
        "raw": info["raw"],
    }


@app.post("/extract-pdf")
async def extract_pdf(
    file: UploadFile = File(...),
    passwords: str = Form(None)
):
    """
    Attempt to unlock the uploaded PDF using a list of passwords.
    Return the unlocked PDF file directly.
    """
    data = await file.read()
    pw_list = [p.strip() for p in passwords.split(",")] if passwords else []

    txt, pdf_bytes = extract_text_and_unlocked_pdf(data, pw_list)
    if txt.startswith("ERROR:"):
        return JSONResponse(status_code=400, content={"error": txt})

    output_stream = BytesIO(pdf_bytes)
    output_stream.seek(0)
    return StreamingResponse(
        output_stream,
        media_type='application/pdf',
        headers={"Content-Disposition": f"attachment; filename=unlocked_{file.filename}"}
    )