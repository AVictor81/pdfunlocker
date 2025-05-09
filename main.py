from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import pikepdf
from io import BytesIO
import re
import fitz  # PyMuPDF

app = FastAPI()

# Справочник компаний → код
COMPANY_MAP = {
    "SOLAR GENERATION POWER LLC": "SG",
    "ECO ENERGY POWER LLC": "Eco",
    "ENERGOEFFECT POWER LLC": "EF",
    "SOLIS POTENTIA HOLDING LLC": "SPH",
    "TERAWATT POWER LLC": "SPH"
}

# Справочник валют → код
CURRENCY_MAP = {
    "US DOLLARS": "USD",
    "US DOLLAR": "USD",
    "EURO": "EUR",
    "UAE DIRHAM": "AED",
    "ARAB EMIRATES DIRHAMS": "AED",
    "QATARI RIYAL": "QAR",
    "QAR": "QAR",
    "SWISS FRANCS": "CHF",
    "CHINESE YUAN RENMINBI": "CNY",
    "RUSSIAN RUBLES": "RUR"
}

def extract_text_and_pdf(input_bytes: bytes, passwords: list[str]) -> tuple[str, bytes]:
    # Попытка открыть PDF с каждым паролем
    for pwd in passwords:
        try:
            with pikepdf.open(BytesIO(input_bytes), password=pwd) as pdf:
                tmp = BytesIO()
                pdf.save(tmp)
                data = tmp.getvalue()
                # Достаём текст из разблокированного
                doc = fitz.open(stream=data, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return text, data
        except Exception:
            continue
    # Если пароли не подошли — без пароля
    try:
        doc = fitz.open(stream=input_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text, input_bytes
    except Exception:
        return "ERROR: cannot open PDF", b""

def parse_codes(text: str) -> tuple[str, str]:
    up = text.upper()
    best_pos = len(text)
    comp_code = ""
    # Ищем компанию по первому вхождению
    for name, code in COMPANY_MAP.items():
        idx = up.find(name)
        if 0 <= idx < best_pos:
            best_pos = idx
            comp_code = code
    # Ищем валюту
    m = re.search(r"Currency\s*[:\-]?\s*([A-Za-z ]+)", text, re.IGNORECASE)
    cur_code = ""
    if m:
        nm = m.group(1).strip().upper()
        cur_code = CURRENCY_MAP.get(nm, nm)
    return comp_code, cur_code

@app.post("/extract-info")
async def extract_info(
    file: UploadFile = File(...),
    passwords: str = Form(None)
):
    file_bytes = await file.read()
    pw_list = [p.strip() for p in passwords.split(",")] if passwords else []
    text, pdf_bytes = extract_text_and_pdf(file_bytes, pw_list)

    if text.startswith("ERROR:"):
        raise HTTPException(status_code=400, detail=text)

    comp, cur = parse_codes(text)

    # Формируем заголовки, из которых Make возьмёт метаданные
    headers = {
        "Content-Disposition": f'attachment; filename="{comp}_{cur}.pdf"',
        "X-Company-Code": comp,
        "X-Currency-Code": cur
    }
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=headers
    )

