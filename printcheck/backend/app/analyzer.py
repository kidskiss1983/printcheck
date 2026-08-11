from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageFile, UnidentifiedImageError


# 允許 Pillow 載入截斷圖片，但仍然會透過 load() 驗證圖片內容。
ImageFile.LOAD_TRUNCATED_IMAGES = False


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

MAX_FILE_SIZE = 50 * 1024 * 1024


def mm_to_inch(mm: float) -> float:
    """毫米轉英吋。"""
    return mm / 25.4


def safe_float(value: Any) -> float | None:
    """安全地將數值轉成正浮點數。"""
    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        return number if number > 0 else None

    except (TypeError, ValueError):
        return None


def detect_color_space(image: Image.Image) -> tuple[str, str]:
    """
    判斷圖片色彩空間。

    回傳：
        (color_space, pillow_mode)
    """
    mode = image.mode

    if mode == "CMYK":
        return "CMYK", mode

    if mode in {"RGB", "RGBA"}:
        return "RGB", mode

    if mode in {"L", "LA", "1"}:
        return "Grayscale", mode

    if mode in {"P", "PA"}:
        return "Indexed / Palette", mode

    return "Other", mode


def get_dpi(image: Image.Image) -> tuple[float | None, float | None]:
    """
    安全取得圖片 DPI metadata。

    Pillow 常見格式：
        (x_dpi, y_dpi)

    某些圖片可能只有單一數值或不正常資料，
    因此這裡統一安全處理。
    """
    dpi = image.info.get("dpi")

    if dpi is None:
        return None, None

    if isinstance(dpi, (tuple, list)):
        if len(dpi) >= 2:
            return safe_float(dpi[0]), safe_float(dpi[1])

        if len(dpi) == 1:
            value = safe_float(dpi[0])
            return value, value

        return None, None

    value = safe_float(dpi)

    return value, value


def get_bits_per_channel(image: Image.Image) -> int:
    """依 Pillow mode 推測每通道位元深度。"""
    mode = image.mode

    return {
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
        "I": 32,
        "F": 32,
    }.get(mode, 8)


def validate_positive_number(
    value: float,
    name: str,
) -> None:
    """驗證必須是有限且大於 0 的數值。"""
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} 必須是大於 0 的有效數值。")


def validate_non_negative_number(
    value: float,
    name: str,
) -> None:
    """驗證必須是有限且大於等於 0 的數值。"""
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} 必須是大於等於 0 的有效數值。")


def analyze_image(
    raw: bytes,
    filename: str,
    target_width_mm: float = 210,
    target_height_mm: float = 297,
    bleed_mm: float = 3,
    min_dpi: float = 300,
) -> dict[str, Any]:
    """
    分析印刷圖片。

    主要檢查：
    - 檔案格式
    - 檔案大小
    - 圖片尺寸
    - 色彩模式
    - DPI metadata
    - 實際有效印刷 DPI
    - ICC Profile
    - 出血需求
    """

    # ---------------------------------------------------------
    # 基本輸入驗證
    # ---------------------------------------------------------

    if not filename:
        raise ValueError("沒有提供檔案名稱。")

    if not isinstance(raw, bytes):
        raise ValueError("無效的圖片資料。")

    if not raw:
        raise ValueError("上傳的檔案是空的。")

    if len(raw) > MAX_FILE_SIZE:
        raise ValueError("檔案超過 50 MB 上限。")

    validate_positive_number(target_width_mm, "成品寬度")
    validate_positive_number(target_height_mm, "成品高度")
    validate_non_negative_number(bleed_mm, "出血")
    validate_positive_number(min_dpi, "最低 DPI")

    # ---------------------------------------------------------
    # 檔案格式
    # ---------------------------------------------------------

    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))

        raise ValueError(
            f"不支援的檔案格式：{suffix or 'unknown'}。"
            f" 支援格式：{supported}"
        )

    # ---------------------------------------------------------
    # 開啟圖片
    # ---------------------------------------------------------

    try:
        image = Image.open(BytesIO(raw))

        # load() 會實際解碼圖片，可抓出部分損壞檔案。
        image.load()

    except UnidentifiedImageError as exc:
        raise ValueError(
            "無法辨識圖片檔案。請確認檔案沒有損壞，"
            "且副檔名與實際圖片格式一致。"
        ) from exc

    except OSError as exc:
        raise ValueError(
            "圖片檔案無法讀取，可能已損壞或格式不完整。"
        ) from exc

    except Exception as exc:
        raise ValueError(
            "讀取圖片時發生錯誤。"
        ) from exc

    # ---------------------------------------------------------
    # 基本圖片資訊
    # ---------------------------------------------------------

    width_px, height_px = image.size

    if width_px <= 0 or height_px <= 0:
        raise ValueError("圖片尺寸無效。")

    color_space, mode = detect_color_space(image)

    x_dpi, y_dpi = get_dpi(image)

    icc_profile = image.info.get("icc_profile")
    has_icc = bool(icc_profile)

    bits_per_channel = get_bits_per_channel(image)

    # ---------------------------------------------------------
    # 根據 metadata DPI 計算圖片原始列印尺寸
    # ---------------------------------------------------------

    actual_width_mm = (
        width_px / x_dpi * 25.4
        if x_dpi
        else None
    )

    actual_height_mm = (
        height_px / y_dpi * 25.4
        if y_dpi
        else None
    )

    # ---------------------------------------------------------
    # 成品尺寸 + 出血
    # ---------------------------------------------------------

    final_width_mm = target_width_mm + bleed_mm * 2
    final_height_mm = target_height_mm + bleed_mm * 2

    final_width_inch = mm_to_inch(final_width_mm)
    final_height_inch = mm_to_inch(final_height_mm)

    # 最低要求畫素
    required_width_px = final_width_inch * min_dpi
    required_height_px = final_height_inch * min_dpi

    # ---------------------------------------------------------
    # 有效印刷 DPI
    #
    # 這裡才是真正判斷「圖片畫素是否足夠」的核心。
    #
    # 即使圖片沒有 DPI metadata，
    # 仍然可以根據：
    #
    #   畫素 ÷ 實際印刷尺寸
    #
    # 算出有效 DPI。
    # ---------------------------------------------------------

    effective_dpi_x = (
        width_px / final_width_inch
        if final_width_inch > 0
        else None
    )

    effective_dpi_y = (
        height_px / final_height_inch
        if final_height_inch > 0
        else None
    )

    effective_dpi = None

    if effective_dpi_x is not None and effective_dpi_y is not None:
        effective_dpi = min(
            effective_dpi_x,
            effective_dpi_y,
        )

    # ---------------------------------------------------------
    # 檢查結果
    # ---------------------------------------------------------

    checks: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # 1. DPI metadata
    #
    # 注意：
    # 沒有 DPI metadata 不再直接判定為 warning。
    #
    # 因為真正重要的是有效印刷 DPI。
    # ---------------------------------------------------------

    if x_dpi and y_dpi:
        metadata_dpi_ok = (
            x_dpi >= min_dpi
            and y_dpi >= min_dpi
        )

        checks.append(
            {
                "key": "metadata_dpi",
                "label": "DPI Metadata",
                "status": "pass" if metadata_dpi_ok else "info",
                "message": (
                    f"{x_dpi:.0f} × {y_dpi:.0f} DPI"
                    if metadata_dpi_ok
                    else (
                        f"{x_dpi:.0f} × {y_dpi:.0f} DPI，"
                        f"低於設定值 {min_dpi:.0f} DPI；"
                        "但實際印刷品質請以有效 DPI 判斷。"
                    )
                ),
            }
        )

    else:
        checks.append(
            {
                "key": "metadata_dpi",
                "label": "DPI Metadata",
                "status": "info",
                "message": (
                    "檔案沒有提供 DPI/PPI metadata；"
                    "將依圖片畫素與指定成品尺寸計算有效 DPI。"
                ),
            }
        )

    # ---------------------------------------------------------
    # 2. 色彩模式
    # ---------------------------------------------------------

    color_ok = color_space == "CMYK"

    if color_ok:
        color_message = "CMYK，符合一般傳統印刷流程。"
        color_status = "pass"

    elif color_space == "RGB":
        color_message = (
            "RGB；若送傳統印刷，通常建議先確認印刷廠是否接受 RGB，"
            "必要時再進行 CMYK 轉換。"
        )
        color_status = "warning"

    elif color_space == "Grayscale":
        color_message = (
            f"灰階（{mode}）；是否適合印刷取決於印刷規格。"
        )
        color_status = "warning"

    elif color_space == "Indexed / Palette":
        color_message = (
            f"索引色（{mode}）；送印前建議確認色彩模式。"
        )
        color_status = "warning"

    else:
        color_message = (
            f"非標準印刷色彩模式：{color_space}（{mode}）。"
        )
        color_status = "warning"

    checks.append(
        {
            "key": "color",
            "label": "色彩模式",
            "status": color_status,
            "message": color_message,
        }
    )

    # ---------------------------------------------------------
    # 3. 有效印刷解析度
    # ---------------------------------------------------------

    if effective_dpi is None:
        resolution_status = "fail"
        resolution_message = "無法計算有效印刷 DPI。"

    elif effective_dpi >= min_dpi:
        resolution_status = "pass"
        resolution_message = (
            f"有效解析度約 {effective_dpi:.0f} DPI，"
            f"達到設定值 {min_dpi:.0f} DPI。"
        )

    elif effective_dpi >= min_dpi * 0.8333:
        # 約 250 DPI @ 300 DPI
        resolution_status = "warning"
        resolution_message = (
            f"有效解析度約 {effective_dpi:.0f} DPI，"
            f"低於建議 {min_dpi:.0f} DPI，但仍可能適用於部分印刷用途。"
        )

    else:
        resolution_status = "fail"
        resolution_message = (
            f"有效解析度約 {effective_dpi:.0f} DPI，"
            f"明顯低於建議 {min_dpi:.0f} DPI。"
        )

    checks.append(
        {
            "key": "print_resolution",
            "label": "有效印刷解析度",
            "status": resolution_status,
            "message": resolution_message,
        }
    )

    # ---------------------------------------------------------
    # 4. ICC Profile
    # ---------------------------------------------------------

    if has_icc:
        icc_status = "pass"
        icc_message = "已嵌入 ICC Profile。"

    else:
        icc_status = "warning"
        icc_message = (
            "未偵測到 ICC Profile；正式印刷前建議確認色彩管理設定。"
        )

    checks.append(
        {
            "key": "icc",
            "label": "ICC Profile",
            "status": icc_status,
            "message": icc_message,
        }
    )

    # ---------------------------------------------------------
    # 5. 出血 / 最低畫素
    # ---------------------------------------------------------

    bleed_required_width_px = required_width_px
    bleed_required_height_px = required_height_px

    bleed_ok = (
        width_px >= bleed_required_width_px
        and height_px >= bleed_required_height_px
    )

    if bleed_ok:
        bleed_status = "pass"
        bleed_message = (
            "圖片畫素足以涵蓋指定成品尺寸＋出血。"
        )

    else:
        bleed_status = "fail"
        bleed_message = (
            f"目前 {width_px} × {height_px} px；"
            f"至少需要約 "
            f"{bleed_required_width_px:.0f} × "
            f"{bleed_required_height_px:.0f} px "
            f"才能達到 {min_dpi:.0f} DPI。"
        )

    checks.append(
        {
            "key": "bleed",
            "label": "成品尺寸＋出血畫素",
            "status": bleed_status,
            "message": bleed_message,
        }
    )

    # ---------------------------------------------------------
    # 整體結果
    #
    # info 不影響 overall。
    # warning 代表需要注意。
    # fail 代表未達最低要求。
    # ---------------------------------------------------------

    has_fail = any(
        check["status"] == "fail"
        for check in checks
    )

    has_warning = any(
        check["status"] == "warning"
        for check in checks
    )

    if has_fail:
        overall = "fail"
    elif has_warning:
        overall = "warning"
    else:
        overall = "pass"

    # ---------------------------------------------------------
    # 回傳結果
    # ---------------------------------------------------------

    return {
        "filename": filename,
        "file_size_bytes": len(raw),
        "file_size_mb": round(
            len(raw) / 1024 / 1024,
            2,
        ),
        "format": image.format or suffix.replace(".", "").upper(),

        "width_px": width_px,
        "height_px": height_px,
        "pixels": width_px * height_px,

        "mode": mode,
        "color_space": color_space,
        "bits_per_channel": bits_per_channel,

        "has_icc_profile": has_icc,
        "icc_profile_bytes": (
            len(icc_profile)
            if icc_profile
            else 0
        ),

        "dpi": {
            "x": round(x_dpi, 2) if x_dpi else None,
            "y": round(y_dpi, 2) if y_dpi else None,
        },

        "metadata_print_size_mm": {
            "width": (
                round(actual_width_mm, 2)
                if actual_width_mm
                else None
            ),
            "height": (
                round(actual_height_mm, 2)
                if actual_height_mm
                else None
            ),
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

        "effective_dpi_for_target": (
            round(effective_dpi, 2)
            if effective_dpi is not None
            else None
        ),

        "checks": checks,
        "overall": overall,
    }
