from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
import pikepdf
from io import BytesIO

app = FastAPI()

@app.post("/unlock-pdf")
async def unlock_pdf(file: UploadFile = File(...), password: str = Form(...)):
    input_pdf = await file.read()
    input_stream = BytesIO(input_pdf)

    try:
        with pikepdf.open(input_stream, password=password) as pdf:
            output_stream = BytesIO()
            pdf.save(output_stream)
            output_stream.seek(0)
            return StreamingResponse(output_stream, media_type='application/pdf', headers={
                "Content-Disposition": f"attachment; filename=unlocked_{file.filename}"
            })
    except pikepdf.PasswordError:
        return {"error": "Incorrect password or file is not encrypted"}
