from __future__ import annotations
import base64
import math
import re
from collections import Counter
from typing import Any

import fitz
from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points
from shapely.ops import unary_union


CUT_NAME_RE = re.compile(
    r"(cut.?contour|cut.?line|dieline|die.?cut|thru.?cut|kiss.?cut|刀模|裁切)",
    re.IGNORECASE,
)


def _point(p):
    return (float(p.x), float(p.y))


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _cubic(p0, p1, p2, p3, steps=16):
    result = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        result.append((x, y))
    return result


def _drawing_points(drawing):
    points = []
    for item in drawing.get("items", []):
        kind = item[0]
        if kind == "l":
            a, b = _point(item[1]), _point(item[2])
            if not points:
                points.append(a)
            elif _distance(points[-1], a) > 0.01:
                points.append(a)
            points.append(b)
        elif kind == "c":
            p0, p1, p2, p3 = map(_point, item[1:5])
            if not points:
                points.append(p0)
            elif _distance(points[-1], p0) > 0.01:
                points.append(p0)
            points.extend(_cubic(p0, p1, p2, p3))
        elif kind == "re":
            r = item[1]
            corners = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
            if points and _distance(points[-1], corners[0]) > 0.01:
                points.append(corners[0])
            elif not points:
                points.append(corners[0])
            points.extend(corners[1:])
        elif kind == "qu":
            q = item[1]
            corners = [_point(q.ul), _point(q.ur), _point(q.lr), _point(q.ll), _point(q.ul)]
            if points and _distance(points[-1], corners[0]) > 0.01:
                points.append(corners[0])
            elif not points:
                points.append(corners[0])
            points.extend(corners[1:])
    # remove adjacent duplicates
    clean = []
    for p in points:
        if not clean or _distance(clean[-1], p) > 0.01:
            clean.append(p)
    return clean


def _rgb_hex(color):
    if not color:
        return None
    try:
        return "#" + "".join(f"{round(max(0,min(1,c))*255):02X}" for c in color[:3])
    except Exception:
        return None


def analyze_pdf_dielines(
    raw: bytes,
    filename: str,
    min_gap_mm: float = 2.0,
    edge_clearance_mm: float = 3.0,
    min_segment_mm: float = 0.5,
    cut_color: str | None = None,
) -> dict[str, Any]:
    if not raw:
        raise ValueError("上傳的 PDF 是空的。")
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("檔案超過 50 MB 上限。")
    for value, label, allow_zero in [
        (min_gap_mm, "最小間距", False),
        (edge_clearance_mm, "邊界安全距離", True),
        (min_segment_mm, "最短線段", False),
    ]:
        if not math.isfinite(value) or (value < 0 if allow_zero else value <= 0):
            raise ValueError(f"{label}設定值無效。")

    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise ValueError("無法讀取 PDF，請確認檔案未損毀且有正確副檔名。") from exc

    if doc.is_encrypted:
        doc.close()
        raise ValueError("PDF 有密碼保護，請先解除密碼再上傳。")
    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF 沒有可檢查的頁面。")

    # PDF points -> mm
    pt_to_mm = 25.4 / 72
    findings = []
    page_results = []
    previews = []
    all_shapes = []
    total_paths = 0
    configured_color = cut_color.strip().upper() if cut_color else None

    if configured_color and not re.fullmatch(r"#[0-9A-F]{6}", configured_color):
        doc.close()
        raise ValueError("自訂刀模顏色請使用 #RRGGBB 格式。")

    for page_index, page in enumerate(doc):
        # 產生 PDF 頁面預覽圖
        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        preview_data = base64.b64encode(
            pix.tobytes("png")
        ).decode("utf-8")

        previews.append({
            "page": page_index + 1,
            "image": f"data:image/png;base64,{preview_data}",
            "width": pix.width,
            "height": pix.height
        })
        findings.extend(issues)

    if total_paths == 0:
        findings.append({
            "code": "no_vector_paths",
            "severity": "warning",
            "page": 1,
            "message": "PDF 中未擷取到可分析的向量路徑；若刀模是點陣圖片或已點陣化，無法用此功能辨識。",
        })

    confirmed = 0
    suspected = sum(
        page["vector_path_count"]
        for page in page_results
    )
    for shape in all_shapes:
        shape.pop("_geom", None)
        shape.pop("_line", None)
        shape.pop("_polygon", None)
        shape.pop("_area_mm2", None)
        shape.pop("_lengths", None)
    doc.close()

    fail_count = sum(1 for f in findings if f["severity"] == "fail")
    warning_count = sum(1 for f in findings if f["severity"] == "warning")
    overall = "fail" if fail_count else ("warning" if warning_count or suspected else "pass")
    return {
        "filename": filename,
        "format": "PDF",
        "page_count": len(page_results),
        "vector_path_count": total_paths,
        "confirmed_dielines": confirmed,
        "suspected_dielines": suspected,
        "classification_note": "目前依據封閉外框及相對面積篩選疑似刀模；仍可能包含文字外框或裝飾圖形，檢查結果需人工確認。",
        "settings": {"min_gap_mm": min_gap_mm, "edge_clearance_mm": edge_clearance_mm, "min_segment_mm": min_segment_mm, "cut_color": configured_color},
        "pages": page_results,
        "previews": previews,
        "paths": all_shapes,
        "findings": findings,
        "summary": {"fail": fail_count, "warning": warning_count},
        "overall": overall,
    }
