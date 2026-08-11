import { useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "";

function StatusIcon({ status }) {
  if (status === "pass") return <span className="status-icon pass">✓</span>;
  if (status === "fail") return <span className="status-icon fail">!</span>;
  return <span className="status-icon warning">!</span>;
}

function Overall({ status }) {
  const map = {
    pass: ["pass", "可以送印"],
    warning: ["warning", "建議確認"],
    fail: ["fail", "不建議直接送印"]
  };
  const [cls, text] = map[status] || map.warning;
  return (
    <div className={`overall ${cls}`}>
      <div className="overall-mark">{status === "pass" ? "✓" : "!"}</div>
      <div>
        <div className="overall-label">預檢結果</div>
        <div className="overall-title">{text}</div>
      </div>
    </div>
  );
}

export default function App() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [settings, setSettings] = useState({
    width: 210,
    height: 297,
    bleed: 3,
    dpi: 300
  });

  function chooseFile(selected) {
    if (!selected) return;
    setFile(selected);
    setResult(null);
    setError("");
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    chooseFile(e.dataTransfer.files?.[0]);
  }

  async function analyze() {
    if (!file) {
      setError("請先選擇圖片檔案。");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const body = new FormData();
    body.append("file", file);
    body.append("target_width_mm", settings.width);
    body.append("target_height_mm", settings.height);
    body.append("bleed_mm", settings.bleed);
    body.append("min_dpi", settings.dpi);

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        body
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "分析失敗");
      }

      setResult(data);
    } catch (err) {
      setError(err.message || "無法連線到後端服務。");
    } finally {
      setLoading(false);
    }
  }

  function updateSetting(key, value) {
    setSettings(prev => ({ ...prev, [key]: Number(value) }));
  }

  const colorClass = result?.color_space === "CMYK" ? "good" : "attention";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="logo">P</div>
          <div>
            <strong>PrintCheck</strong>
            <span>印刷檔案預檢工具</span>
          </div>
        </div>
        <div className="api-badge">PRINT PREFLIGHT</div>
      </header>

      <main className="container">
        <section className="hero">
          <div>
            <p className="eyebrow">PREPRESS CHECK</p>
            <h1>送印前，先把檔案檢查一次。</h1>
            <p className="subtitle">
              分析畫素、DPI、RGB / CMYK、ICC Profile 與指定成品尺寸，
              快速找出可能造成印刷問題的地方。
            </p>
          </div>
        </section>

        <section className="workspace">
          <div className="panel settings-panel">
            <div className="panel-title">
              <h2>① 檔案與印刷設定</h2>
              <span>STEP 1</span>
            </div>

            <div
              className={`dropzone ${dragging ? "dragging" : ""}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.tif,.tiff,.webp"
                hidden
                onChange={(e) => chooseFile(e.target.files?.[0])}
              />
              <div className="upload-icon">↑</div>
              <strong>{file ? file.name : "拖曳圖片到這裡"}</strong>
              <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "或點擊選擇檔案"}</span>
              <small>JPG / PNG / TIFF / WEBP，最大 50 MB</small>
            </div>

            <div className="settings-grid">
              <label>
                <span>成品寬度 mm</span>
                <input type="number" value={settings.width} onChange={e => updateSetting("width", e.target.value)} />
              </label>
              <label>
                <span>成品高度 mm</span>
                <input type="number" value={settings.height} onChange={e => updateSetting("height", e.target.value)} />
              </label>
              <label>
                <span>四邊出血 mm</span>
                <input type="number" value={settings.bleed} onChange={e => updateSetting("bleed", e.target.value)} />
              </label>
              <label>
                <span>最低 DPI</span>
                <input type="number" value={settings.dpi} onChange={e => updateSetting("dpi", e.target.value)} />
              </label>
            </div>

            <button className="analyze-button" onClick={analyze} disabled={loading || !file}>
              {loading ? "分析中…" : "開始檢查檔案 →"}
            </button>

            {error && <div className="error">{error}</div>}
          </div>

          <div className="panel result-panel">
            <div className="panel-title">
              <h2>② 檢查結果</h2>
              <span>STEP 2</span>
            </div>

            {!result && !loading && (
              <div className="empty">
                <div className="empty-symbol">◎</div>
                <h3>等待檔案分析</h3>
                <p>上傳檔案並按下「開始檢查檔案」後，分析結果會顯示在這裡。</p>
              </div>
            )}

            {loading && (
              <div className="empty">
                <div className="spinner"></div>
                <h3>正在分析檔案…</h3>
                <p>正在讀取圖片 metadata 與印刷解析度。</p>
              </div>
            )}

            {result && (
              <div className="result">
                <Overall status={result.overall} />

                <div className="metrics">
                  <div className="metric">
                    <span>畫素</span>
                    <strong>{result.width_px.toLocaleString()} × {result.height_px.toLocaleString()}</strong>
                    <small>{result.pixels.toLocaleString()} pixels</small>
                  </div>
                  <div className="metric">
                    <span>色彩模式</span>
                    <strong className={colorClass}>{result.color_space}</strong>
                    <small>{result.mode}</small>
                  </div>
                  <div className="metric">
                    <span>檔案 DPI</span>
                    <strong>
                      {result.dpi.x && result.dpi.y
                        ? `${result.dpi.x} × ${result.dpi.y}`
                        : "未提供"}
                    </strong>
                    <small>PPI / DPI metadata</small>
                  </div>
                  <div className="metric">
                    <span>有效印刷 DPI</span>
                    <strong>{result.effective_dpi_for_target || "—"}</strong>
                    <small>依指定成品＋出血計算</small>
                  </div>
                </div>

                <div className="detail-grid">
                  <div>
                    <span>格式</span>
                    <b>{result.format}</b>
                  </div>
                  <div>
                    <span>檔案大小</span>
                    <b>{result.file_size_mb} MB</b>
                  </div>
                  <div>
                    <span>位元深度</span>
                    <b>{result.bits_per_channel} bit / channel</b>
                  </div>
                  <div>
                    <span>ICC Profile</span>
                    <b>{result.has_icc_profile ? "已嵌入" : "未偵測"}</b>
                  </div>
                </div>

                <h3 className="checks-title">Preflight 檢查</h3>

                <div className="checks">
                  {result.checks.map(check => (
                    <div className="check" key={check.key}>
                      <StatusIcon status={check.status} />
                      <div>
                        <strong>{check.label}</strong>
                        <p>{check.message}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="required">
                  <strong>目前設定需要的最低畫素</strong>
                  <span>
                    {result.target.required_pixels.width.toLocaleString()} ×{" "}
                    {result.target.required_pixels.height.toLocaleString()} px
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>

        <footer>
          PrintCheck v1.0 · 基礎圖片印前預檢工具
        </footer>
      </main>
    </div>
  );
}
