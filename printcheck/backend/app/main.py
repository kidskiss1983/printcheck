from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analyzer import analyze_image


app = FastAPI(
    title="PrintCheck API",
    version="1.0.0",
    description="印刷檔案預檢 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "PrintCheck API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    target_width_mm: float = Form(210),
    target_height_mm: float = Form(297),
    bleed_mm: float = Form(3),
    min_dpi: float = Form(300),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="沒有檔案名稱。")

    if target_width_mm <= 0 or target_height_mm <= 0:
        raise HTTPException(status_code=400, detail="成品尺寸必須大於 0。")

    if bleed_mm < 0:
        raise HTTPException(status_code=400, detail="出血不能小於 0。")

    if min_dpi <= 0:
        raise HTTPException(status_code=400, detail="最低 DPI 必須大於 0。")

    try:
        raw = await file.read()
        result = analyze_image(
            raw=raw,
            filename=file.filename,
            target_width_mm=target_width_mm,
            target_height_mm=target_height_mm,
            bleed_mm=bleed_mm,
            min_dpi=min_dpi,
        )
        return JSONResponse(result)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"分析檔案時發生錯誤：{exc}",
        ) from exc
