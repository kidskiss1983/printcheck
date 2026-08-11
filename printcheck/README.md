# PrintCheck — 印刷檔案預檢網站

一個可直接部署的印刷檔案預檢工具，包含：

- React/Vite 前端
- Python FastAPI 後端
- JPG / JPEG / PNG / TIFF / WEBP 上傳
- 寬高畫素分析
- DPI / PPI 分析
- RGB / CMYK / Grayscale 判斷
- ICC Profile 判斷
- 位元深度與檔案大小
- 依指定印刷尺寸與最低 DPI 判斷是否適合送印
- JSON API
- Docker 部署

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
