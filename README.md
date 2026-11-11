# PrintCheck — 印刷檔案預檢網站

一個可直接部署的印刷檔案預檢工具，包含：

- React/Vite 前端
- Python FastAPI 後端
- JPG / JPEG / PNG / TIFF / WEBP 圖片上傳
- PDF 向量刀模初步檢查
- 寬高畫素分析
- DPI / PPI 分析
- RGB / CMYK / Grayscale 判斷
- ICC Profile 判斷
- 位元深度與檔案大小
- 依指定印刷尺寸與最低 DPI 判斷是否適合送印
- JSON API
- Docker 部署

## 貼紙刀模檢查（第一階段）

目前新增 PDF 向量路徑檢查：可擷取 PDF 向量線段、曲線、矩形與四邊形，並檢查開放路徑、自我交叉、路徑重疊／相交、路徑間距、短線段及距 PDF 頁面邊界的距離。可依圖層名稱關鍵字（CutContour、Cut Line、Dieline、Die Cut、Thru-cut、Kiss Cut、刀模、裁切）或自訂線條顏色標示已確認刀模；其餘向量路徑會列為疑似，避免只憑顏色誤判。

API：`POST /api/analyze-dieline`，Form Data：`file`、`min_gap_mm`（預設 2）、`edge_clearance_mm`（預設 3）、`min_segment_mm`（預設 0.5）、`cut_color`（選填，格式 `#RRGGBB`）。

**限制：**目前是 PDF 向量幾何的初步檢查，不等同完整印前檢查。PyMuPDF 對 PDF 專色 Separation／DeviceN 名稱及不同軟體輸出的圖層資訊不一定都能完整提供；未可靠取得的專色不會自動視為已確認。掃描圖、點陣化刀模不會被當成向量路徑。AI／EPS／SVG 尚未納入這一階段，建議先由 Illustrator 匯出含向量路徑的 PDF 再檢查。

## 專案結構

```text
printcheck/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py
│  │  └─ analyzer.py
│  ├─ requirements.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx
│  │  ├─ main.jsx
│  │  └─ style.css
│  ├─ index.html
│  ├─ package.json
│  ├─ vite.config.js
│  └─ Dockerfile
├─ docker-compose.yml
└─ README.md
```

## 本機啟動

### 1. 後端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

後端 API：
http://localhost:8000

### 2. 前端

另開終端：

```bash
cd frontend
npm install
npm run dev
```

前端：
http://localhost:5173

Vite 會將 `/api` 代理到 FastAPI。

## Docker

```bash
docker compose up --build
```

前端：
http://localhost:5173

## API

`POST /api/analyze`

Form Data：

- `file`
- `target_width_mm`
- `target_height_mm`
- `bleed_mm`
- `min_dpi`

例如 A4：

- width = 210
- height = 297
- bleed = 3
- min_dpi = 300

## 注意

DPI 是檔案 metadata 中的 PPI/DPI 資訊。如果檔案沒有嵌入 DPI，系統會標示「未提供」，不會假裝推算。

「可以送印」只代表通過本工具目前設定的基本檢查，並不等於完整印前製作檢查。真正商業印刷還可能需要檢查 PDF/X、字型、透明度、總墨量、專色、出血、裁切標記等。
