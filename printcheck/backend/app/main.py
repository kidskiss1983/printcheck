from __future__ import annotations

import math

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analyzer import MAX_FILE_SIZE, analyze_image


app = FastAPI(
    title="PrintCheck API",
    version="1.1.0",
    description="印刷檔案預檢 API",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# 基本 API
# ---------------------------------------------------------


@app.get("/")
def root():
    return {
        "name": "PrintCheck API",
        "version": "1.1.0",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "PrintCheck API",
    }


# ---------------------------------------------------------
# 圖片分析
# ---------------------------------------------------------


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    target_width_mm: float = Form(210),
    target_height_mm: float = Form(297),
    bleed_mm: float = Form(3),
    min_dpi: float = Form(300),
):
    # -----------------------------------------------------
    # 檔案名稱
    # -----------------------------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="沒有檔案名稱。",
        )

    # -----------------------------------------------------
    # 數值驗證
    # -----------------------------------------------------

    if (
        not math.isfinite(target_width_mm)
        or target_width_mm <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail="成品寬度必須是大於 0 的有效數值。",
        )

    if (
        not math.isfinite(target_height_mm)
        or target_height_mm <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail="成品高度必須是大於 0 的有效數值。",
        )

    if (
        not math.isfinite(bleed_mm)
        or bleed_mm < 0
    ):
        raise HTTPException(
            status_code=400,
            detail="出血必須是大於等於 0 的有效數值。",
        )

    if (
        not math.isfinite(min_dpi)
        or min_dpi <= 0
    ):
        raise HTTPException(
            status_code=400,
            detail="最低 DPI 必須是大於 0 的有效數值。",
        )

    # -----------------------------------------------------
    # 讀取檔案
    #
    # 多讀 1 byte。
    #
    # 如果超過 50 MB，就可以立即拒絕，
    # 不必讓 analyzer 再處理。
    # -----------------------------------------------------

    try:
        raw = await file.read(MAX_FILE_SIZE + 1)

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="無法讀取上傳檔案。",
        ) from exc

    if not raw:
        raise HTTPException(
            status_code=400,
            detail="上傳的檔案是空的。",
        )

    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="檔案超過 50 MB 上限。",
        )

    # -----------------------------------------------------
    # 執行圖片分析
    # -----------------------------------------------------

    try:
        result = analyze_image(
            raw=raw,
            filename=file.filename,
            target_width_mm=target_width_mm,
            target_height_mm=target_height_mm,
            bleed_mm=bleed_mm,
            min_dpi=min_dpi,
        )

        return JSONResponse(
            content=result,
            status_code=200,
        )

    except ValueError as exc:
        # 使用者上傳的檔案或參數有問題
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        # 不把 Python 內部 traceback / 系統資訊直接暴露給使用者。
        raise HTTPException(
            status_code=500,
            detail="分析檔案時發生未預期錯誤，請稍後再試。",
        ) from exc
