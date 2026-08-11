from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024


def mm_to_inch(mm: float) -> float:
    return mm / 25.4


def safe_float(value: Any) -> float | None:
    try:
        value = float(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def detect_color_space(image: Image.Image) -> tuple[str, str]:
    mode = image.mode

    if mode == "CMYK":
        return "CMYK", "CMYK"

    if mode in {"RGB", "RGBA"}:
        return "RGB", "RGB"

    if mode in {"L", "LA", "1"}:
        return "Grayscale", mode

    if mode in {"P", "PA"}:
        return "Indexed / Palette", mode

    return "Other", mode


def analyze_image(
    raw: bytes,
    filename: str,
    target_width_mm: float = 210,
    target_height_mm: float = 297,
    bleed_mm: float = 3,
    min_dpi: float = 300,
) -> dict[str, Any]:

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支援的檔案格式：{suffix or 'unknown'}。"
            f"支援：{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if len(raw) > MAX_FILE_SIZE:
        raise ValueError("檔案超過 50 MB 上限。")

    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except UnidentifiedImageError as exc:
        raise ValueError("無法辨識圖片檔案。") from exc

    width_px, height_px = image.size
    color_space, mode = detect_color_space(image)

    dpi = image.info.get("dpi")
    x_dpi = safe_float(dpi[0] if isinstance(dpi, tuple) else dpi)
    y_dpi = safe_float(dpi[1] if isinstance(dpi, tuple) else dpi)

    icc_profile = image.info.get("icc_profile")
    has_icc = bool(icc_profile)

    bits_per_channel = {
        "1": 1,
        "L": 8,
        "LA": 8,
        "P": 8,
        "PA": 8,
        "RGB": 8,
        "RGBA": 8,
        "CMYK": 8,
        "I;16": 16,
        "I;16L": 16,
        "I;16B": 16,
    }.get(mode, 8)

    actual_width_mm = (
        width_px / x_dpi * 25.4 if x_dpi else None
    )
    actual_height_mm = (
        height_px / y_dpi * 25.4 if y_dpi else None
    )

    # 在指定成品尺寸下，計算圖片實際可達的 DPI。
    required_width_px = (target_width_mm + bleed_mm * 2) / 25.4 * min_dpi
    required_height_px = (target_height_mm + bleed_mm * 2) / 25.4 * min_dpi

    effective_dpi_x = (
        width_px / ((target_width_mm + bleed_mm * 2) / 25.4)
        if target_width_mm > 0
        else None
    )
    effective_dpi_y = (
        height_px / ((target_height_mm + bleed_mm * 2) / 25.4)
        if target_height_mm > 0
        else None
    )

    effective_dpi = (
        min(effective_dpi_x, effective_dpi_y)
        if effective_dpi_x and effective_dpi_y
        else None
    )

    checks = []

    if x_dpi and y_dpi:
        dpi_ok = x_dpi >= min_dpi and y_dpi >= min_dpi
        checks.append({
            "key": "metadata_dpi",
            "label": "檔案 DPI",
            "status": "pass" if dpi_ok else "warning",
            "message": (
                f"{x_dpi:.0f} × {y_dpi:.0f} DPI"
                if dpi_ok
                else f"{x_dpi:.0f} × {y_dpi:.0f} DPI，低於建議 {min_dpi:.0f} DPI"
            ),
        })
    else:
        checks.append({
            "key": "metadata_dpi",
            "label": "檔案 DPI",
            "status": "warning",
            "message": "檔案沒有提供 DPI/PPI metadata",
        })

    color_ok = color_space == "CMYK"
    checks.append({
        "key": "color",
        "label": "色彩模式",
        "status": "pass" if color_ok else "warning",
        "message": (
            "CMYK，符合一般印刷流程"
            if color_ok
            else f"{color_space}（{mode}），若送傳統印刷通常建議確認是否需要 CMYK"
        ),
    })

    resolution_ok = (
        effective_dpi is not None and effective_dpi >= min_dpi
    )
    checks.append({
        "key": "print_resolution",
        "label": "指定成品尺寸解析度",
        "status": "pass" if resolution_ok else "fail",
        "message": (
            f"有效解析度約 {effective_dpi:.0f} DPI"
            if effective_dpi is not None
            else "無法計算"
        ),
    })

    icc_status = "pass" if has_icc else "warning"
    checks.append({
        "key": "icc",
        "label": "ICC Profile",
        "status": icc_status,
        "message": "已嵌入 ICC Profile" if has_icc else "未偵測到 ICC Profile",
    })

    if bleed_mm > 0:
        bleed_required_width_px = (target_width_mm + 2 * bleed_mm) / 25.4 * min_dpi
        bleed_required_height_px = (target_height_mm + 2 * bleed_mm) / 25.4 * min_dpi
        bleed_ok = width_px >= bleed_required_width_px and height_px >= bleed_required_height_px
        checks.append({
            "key": "bleed",
            "label": "出血所需畫素",
            "status": "pass" if bleed_ok else "fail",
            "message": (
                f"至少約 {bleed_required_width_px:.0f} × {bleed_required_height_px:.0f} px"
                if not bleed_ok
                else "畫素足以涵蓋指定成品尺寸＋出血"
            ),
        })

    has_fail = any(c["status"] == "fail" for c in checks)
    has_warning = any(c["status"] == "warning" for c in checks)

    overall = "fail" if has_fail else ("warning" if has_warning else "pass")

    return {
        "filename": filename,
        "file_size_bytes": len(raw),
        "file_size_mb": round(len(raw) / 1024 / 1024, 2),
        "format": image.format or suffix.replace(".", "").upper(),
        "width_px": width_px,
        "height_px": height_px,
        "pixels": width_px * height_px,
        "mode": mode,
        "color_space": color_space,
        "bits_per_channel": bits_per_channel,
        "has_icc_profile": has_icc,
        "icc_profile_bytes": len(icc_profile) if icc_profile else 0,
        "dpi": {
            "x": round(x_dpi, 2) if x_dpi else None,
            "y": round(y_dpi, 2) if y_dpi else None,
        },
        "metadata_print_size_mm": {
            "width": round(actual_width_mm, 2) if actual_width_mm else None,
            "height": round(actual_height_mm, 2) if actual_height_mm else None,
        },
        "target": {
            "width_mm": target_width_mm,
            "height_mm": target_height_mm,
            "bleed_mm": bleed_mm,
            "min_dpi": min_dpi,
            "required_pixels": {
                "width": round(required_width_px),
                "height": round(required_height_px),
            },
        },
        "effective_dpi_for_target": round(effective_dpi, 2) if effective_dpi else None,
        "checks": checks,
        "overall": overall,
    }
