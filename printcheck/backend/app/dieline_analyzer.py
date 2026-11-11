from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import fitz
from shapely.geometry import LineString, Polygon
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
    all_shapes = []
    total_paths = 0
    configured_color = cut_color.strip().upper() if cut_color else None
    if configured_color and not re.fullmatch(r"#[0-9A-F]{6}", configured_color):
        doc.close()
        raise ValueError("自訂刀模顏色請使用 #RRGGBB 格式。")

    for page_index, page in enumerate(doc):
        page_rect = page.rect
        drawings = page.get_drawings()
        page_shapes = []
        for drawing_index, drawing in enumerate(drawings):
            if len(page_shapes) >= 1500:
                doc.close()
                raise ValueError("單頁向量路徑超過 1,500 條，為避免分析時間過長，請先簡化 PDF 或分頁檢查。")
            pts = _drawing_points(drawing)
            if len(pts) < 2:
                continue
            total_paths += 1
            line = LineString(pts)
            if line.length <= 0:
                continue
            closed = bool(drawing.get("closePath")) or _distance(pts[0], pts[-1]) <= 0.75
            layer = drawing.get("layer")
            color_hex = _rgb_hex(drawing.get("color"))
            layer_text = str(layer or "")
            name_match = bool(CUT_NAME_RE.search(layer_text))
            color_match = bool(configured_color and color_hex and color_hex.upper() == configured_color)
            # PDF.js / PyMuPDF drawing records do not reliably expose Separation names.
            classification = "confirmed" if (name_match or color_match) else "suspected"
            polygon = None
            if closed and len(pts) >= 4:
                try:
                    polygon = Polygon(pts)
                except Exception:
                    polygon = None
            bounds = [round(v * pt_to_mm, 2) for v in line.bounds]
            lengths = [_distance(pts[i], pts[i+1]) * pt_to_mm for i in range(len(pts)-1)]
            shape = {
                "page": page_index + 1,
                "path_index": drawing_index + 1,
                "layer": layer_text or None,
                "color": color_hex,
                "classification": classification,
                "closed": closed,
                "geometry_type": "closed" if closed else "open",
                "length_mm": round(line.length * pt_to_mm, 2),
                "bounds_mm": bounds,
                "min_segment_mm": round(min(lengths), 3) if lengths else None,
                "_geom": line,
                "_line": line,
                "_polygon": polygon,
                "_lengths": lengths,
            }
            page_shapes.append(shape)
            all_shapes.append(shape)

        issues = []
        for shape in page_shapes:
            if not shape["closed"]:
                issues.append({"code": "open_path", "severity": "warning", "page": page_index + 1,
                               "path": shape["path_index"], "message": f"路徑 {shape['path_index']} 未封閉，請確認是否為完整刀模。"})
            if shape["_lengths"] and min(shape["_lengths"]) < min_segment_mm:
                issues.append({"code": "short_segment", "severity": "warning", "page": page_index + 1,
                               "path": shape["path_index"], "message": f"路徑 {shape['path_index']} 含有短於 {min_segment_mm:g} mm 的線段。"})
            if not shape["_line"].is_simple:
                issues.append({"code": "self_intersection", "severity": "fail", "page": page_index + 1,
                               "path": shape["path_index"], "message": f"路徑 {shape['path_index']} 有自我交叉。"})
            if shape["closed"] and shape["_polygon"] is not None and not shape["_polygon"].is_valid:
                issues.append({"code": "invalid_polygon", "severity": "fail", "page": page_index + 1,
                               "path": shape["path_index"], "message": f"路徑 {shape['path_index']} 的封閉形狀不合法。"})
            # distance to PDF page edge, measured using bounding box
            x0, y0, x1, y1 = shape["_line"].bounds
            edge_pt = min(x0-page_rect.x0, y0-page_rect.y0, page_rect.x1-x1, page_rect.y1-y1)
            edge_mm = edge_pt * pt_to_mm
            if edge_mm < edge_clearance_mm:
                issues.append({"code": "edge_clearance", "severity": "warning", "page": page_index + 1,
                               "path": shape["path_index"], "message": f"路徑距離 PDF 頁面邊界約 {max(0,edge_mm):.2f} mm，小於設定的 {edge_clearance_mm:g} mm。"})
        # pairwise spacing / overlap
        for i in range(len(page_shapes)):
            for j in range(i+1, len(page_shapes)):
                a, b = page_shapes[i], page_shapes[j]
                dist_mm = a["_line"].distance(b["_line"]) * pt_to_mm
                if a["_line"].equals(b["_line"]):
                    issues.append({"code": "duplicate_path", "severity": "warning", "page": page_index + 1,
                                   "path": a["path_index"], "other_path": b["path_index"],
                                   "message": f"路徑 {a['path_index']} 與 {b['path_index']} 完全重複。"})
                elif a["_line"].intersects(b["_line"]) or dist_mm <= 0.01:
                    issues.append({"code": "overlap", "severity": "fail", "page": page_index + 1,
                                   "path": a["path_index"], "other_path": b["path_index"],
                                   "message": f"路徑 {a['path_index']} 與 {b['path_index']} 重疊或相交。"})
                elif dist_mm < min_gap_mm:
                    issues.append({"code": "small_gap", "severity": "warning", "page": page_index + 1,
                                   "path": a["path_index"], "other_path": b["path_index"],
                                   "message": f"路徑 {a['path_index']} 與 {b['path_index']} 間距約 {dist_mm:.2f} mm，小於 {min_gap_mm:g} mm。"})
        page_results.append({
            "page": page_index + 1,
            "width_mm": round(page_rect.width * pt_to_mm, 2),
            "height_mm": round(page_rect.height * pt_to_mm, 2),
            "vector_path_count": len(page_shapes),
            "issues": issues,
        })
        findings.extend(issues)

    if total_paths == 0:
        findings.append({
            "code": "no_vector_paths",
            "severity": "warning",
            "page": 1,
            "message": "PDF 中未擷取到可分析的向量路徑；若刀模是點陣圖片或已點陣化，無法用此功能辨識。",
        })

    confirmed = sum(1 for s in all_shapes if s["classification"] == "confirmed")
    suspected = len(all_shapes) - confirmed
    for shape in all_shapes:
        shape.pop("_geom", None)
        shape.pop("_line", None)
        shape.pop("_polygon", None)
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
        "classification_note": "目前以圖層名稱或使用者指定顏色作為確認依據；PDF 專色名稱需視檔案內部結構而定，未能可靠讀取者不會自動判定為已確認。",
        "settings": {"min_gap_mm": min_gap_mm, "edge_clearance_mm": edge_clearance_mm, "min_segment_mm": min_segment_mm, "cut_color": configured_color},
        "pages": page_results,
        "paths": all_shapes,
        "findings": findings,
        "summary": {"fail": fail_count, "warning": warning_count},
        "overall": overall,
    }
