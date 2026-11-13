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



function DielineOverall({ status }) {
  const map = {
    pass: ["pass", "幾何檢查通過（仍需人工確認）"],
    warning: ["warning", "有項目需要確認"],
    fail: ["fail", "發現幾何異常"]
  };
  const [cls, text] = map[status] || map.warning;
  return (
    <div className={`overall ${cls}`}>
      <div className="overall-mark">{status === "pass" ? "✓" : "!"}</div>
      <div>
        <div className="overall-label">刀模幾何檢查結果</div>
        <div className="overall-title">{text}</div>
      </div>
    </div>
  );
}

export default function App() {
  // 圖片印刷檢查：獨立狀態
const imageInputRef = useRef(null);
const [imageFile, setImageFile] = useState(null);
const [imageDragging, setImageDragging] = useState(false);
const [imageLoading, setImageLoading] = useState(false);
const [imageError, setImageError] = useState("");

// 刀模檢查：獨立狀態
const dielineInputRef = useRef(null);
const [dielineFile, setDielineFile] = useState(null);
const [dielineDragging, setDielineDragging] = useState(false);
const [dielineLoading, setDielineLoading] = useState(false);
const [dielineError, setDielineError] = useState("");
const [result, setResult] = useState(null);
  const [dielineResult, setDielineResult] = useState(null);
  const [previewPage, setPreviewPage] = useState(1);
  
function downloadDielinePreview() {
  const preview = dielineResult?.previews?.[previewPage - 1];
  const pageData = dielineResult?.pages?.find(
    page => page.page === previewPage
  );

  if (!preview?.image) return;

  const img = new Image();

  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = preview.width;
    canvas.height = preview.height;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    (pageData?.issue_markers || []).forEach(marker => {
      ctx.beginPath();
      ctx.arc(marker.x, marker.y, 9, 0, Math.PI * 2);
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ff3030";
      ctx.fillStyle = "rgba(255, 0, 0, 0.08)";
      ctx.fill();
      ctx.stroke();
    });

    const link = document.createElement("a");
    link.download = `PDF_刀模檢查_第${previewPage}頁.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  };

  img.src = preview.image;
}

  const [dielineSettings, setDielineSettings] = useState({ minGap: 2, edgeClearance: 3, minSegment: 0.5, cutColor: "" });


  const [settings, setSettings] = useState({
    width: 210,
    height: 297,
    bleed: 3,
    dpi: 300
  });

   
// 圖片印刷檢查：選取檔案
function chooseImageFile(selected) {
  if (!selected) return;
  setImageFile(selected);
  setResult(null);
  setImageError("");
}

// 刀模檢查：選取 PDF
function chooseDielineFile(selected) {
  if (!selected) return;

  if (!selected.name.toLowerCase().endsWith(".pdf")) {
    setDielineError("目前刀模向量檢查只接受 PDF 檔案。");
    return;
  }

  setDielineFile(selected);
  setDielineResult(null);
  setDielineError("");
}

// 圖片區域拖曳上傳
function onImageDrop(e) {
  e.preventDefault();
  setImageDragging(false);
  chooseImageFile(e.dataTransfer.files?.[0]);
}

// 刀模區域拖曳上傳
function onDielineDrop(e) {
  e.preventDefault();
  setDielineDragging(false);
  chooseDielineFile(e.dataTransfer.files?.[0]);
}

  // 圖片印刷檢查
  async function analyzeImage() {
    if (!imageFile) {
      setImageError("請先選擇圖片檔案。");
      return;
    }

    setImageLoading(true);
    setImageError("");
    setResult(null);

    const body = new FormData();
    body.append("file", imageFile);
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
        throw new Error(data.detail || "圖片分析失敗");
      }

      setResult(data);
    } catch (err) {
      setImageError(err.message || "無法連線到後端服務。");
    } finally {
      setImageLoading(false);
    }
  }

  // PDF 刀模檢查
  async function analyzeDieline() {
    if (!dielineFile) {
      setDielineError("請先選擇 PDF 檔案。");
      return;
    }

    setDielineLoading(true);
    setDielineError("");
    setDielineResult(null);

    const body = new FormData();
    body.append("file", dielineFile);
    body.append("min_gap_mm", dielineSettings.minGap);
    body.append("edge_clearance_mm", dielineSettings.edgeClearance);
    body.append("min_segment_mm", dielineSettings.minSegment);
    body.append("cut_color", dielineSettings.cutColor);

    try {
      const response = await fetch(`${API_BASE}/api/analyze-dieline`, {
        method: "POST",
        body
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "刀模分析失敗");
      }

      setDielineResult(data);
    } catch (err) {
      setDielineError(err.message || "無法連線到後端服務。");
    } finally {
      setDielineLoading(false);
    }
  }

  function updateSetting(key, value) {
    setSettings(prev => ({ ...prev, [key]: Number(value) }));
  }

  function updateDielineSetting(key, value) {
    setDielineSettings(prev => ({ ...prev, [key]: key === "cutColor" ? value : Number(value) }));
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
              分析圖片畫素、DPI、RGB / CMYK、ICC Profile，並初步檢查 PDF 貼紙刀模向量路徑，
              協助找出可能造成印刷問題的地方。
            </p>
          </div>
        </section>

        <section className="workspace">
          <div className="panel settings-panel">
            <div className="panel-title">
              <h2>① 檔案與印刷設定</h2>
              <span>STEP 1</span>
            </div>

           
{/* 第一區：圖片印刷檢查 */}
<div className="inspection-section image-inspection-section">
  <h2>圖片印刷檢查</h2>
  <p>檢查圖片尺寸、色彩模式、DPI 與出血設定。</p>

  <div
    className={`dropzone ${imageDragging ? "dragging" : ""}`}
    onClick={() => imageInputRef.current?.click()}
    onDragOver={(e) => {
      e.preventDefault();
      setImageDragging(true);
    }}
    onDragLeave={() => setImageDragging(false)}
    onDrop={onImageDrop}
  >
    <input
      ref={imageInputRef}
      type="file"
      accept=".jpg,.jpeg,.png,.tif,.tiff,.webp"
      hidden
      onChange={(e) => {
        chooseImageFile(e.target.files?.[0]);
        e.target.value = "";
      }}
    />
    <div className="upload-icon">↑</div>
    <strong>{imageFile ? imageFile.name : "拖曳圖片到這裡"}</strong>
    <span>
      {imageFile
        ? `${(imageFile.size / 1024 / 1024).toFixed(2)} MB`
        : "或點擊選擇圖片"}
    </span>
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

  {imageError && <div className="error">{imageError}</div>}

  <button
  className="analyze-button"
  onClick={analyzeImage}
  disabled={imageLoading || !imageFile}
>
  {imageLoading ? "圖片分析中…" : "開始圖片印刷檢查 →"}
</button>

{!result && !imageLoading && (
  <div className="empty">
    <div className="empty-symbol">◎</div>
    <h3>等待圖片分析</h3>
    <p>上傳圖片並按下「開始圖片印刷檢查」後，分析結果會顯示在這裡。</p>
  </div>
)}

{imageLoading && (
  <div className="empty">
    <div className="spinner"></div>
    <h3>正在分析圖片…</h3>
    <p>正在讀取圖片 metadata 與印刷解析度。</p>
  </div>
)}
</div>

{/* 第二區：PDF 刀模檢查 */}
<div className="inspection-section dieline-inspection-section">
  <h2>PDF 刀模檢查</h2>
  <p>檢查 PDF 向量刀模路徑、間距與幾何異常。</p>

  <div
    className={`dropzone ${dielineDragging ? "dragging" : ""}`}
    onClick={() => dielineInputRef.current?.click()}
    onDragOver={(e) => {
      e.preventDefault();
      setDielineDragging(true);
    }}
    onDragLeave={() => setDielineDragging(false)}
    onDrop={onDielineDrop}
  >
    <input
      ref={dielineInputRef}
      type="file"
      accept=".pdf"
      hidden
      onChange={(e) => {
        chooseDielineFile(e.target.files?.[0]);
        e.target.value = "";
      }}
    />
    <div className="upload-icon">↑</div>
    <strong>{dielineFile ? dielineFile.name : "拖曳 PDF 到這裡"}</strong>
    <span>
      {dielineFile
        ? `${(dielineFile.size / 1024 / 1024).toFixed(2)} MB`
        : "或點擊選擇 PDF"}
    </span>
    <small>PDF 向量刀模檔案，最大 50 MB</small>
  </div>

<div className="dieline-settings">
  <h3>貼紙刀模檢查設定</h3>
  <p>圖層名稱含 CutContour、Dieline、Die Cut 等關鍵字，或符合自訂顏色的路徑，會列為已確認；其他向量路徑列為疑似。</p>

  <div className="settings-grid">
  <label>
    <span>刀模最小間距 mm</span>
    <input
      type="number"
      min="0.1"
      step="0.1"
      value={dielineSettings.minGap}
      onChange={e => updateDielineSetting("minGap", e.target.value)}
    />
  </label>

  <label>
    <span>距頁面邊界 mm</span>
    <input
      type="number"
      min="0"
      step="0.1"
      value={dielineSettings.edgeClearance}
      onChange={e => updateDielineSetting("edgeClearance", e.target.value)}
    />
  </label>

  <label>
    <span>最短線段 mm</span>
    <input
      type="number"
      min="0.1"
      step="0.1"
      value={dielineSettings.minSegment}
      onChange={e => updateDielineSetting("minSegment", e.target.value)}
    />
  </label>

  <label>
    <span>刀模線條顏色</span>
    <input
      type="text"
      value={dielineSettings.cutColor}
      onChange={e => updateDielineSetting("cutColor", e.target.value)}
      placeholder="例如 #FF00FF"
    />
  </label>
</div>

  {dielineError && <div className="error">{dielineError}</div>}

<button
  className="analyze-button"
  onClick={analyzeDieline}
  disabled={dielineLoading || !dielineFile}
>
  {dielineLoading ? "刀模分析中…" : "開始 PDF 刀模檢查 →"}
</button>

{!dielineResult && !dielineLoading && (
  <div className="empty">
    <div className="empty-symbol">◎</div>
    <h3>等待刀模分析</h3>
    <p>上傳 PDF 並按下「開始 PDF 刀模檢查」後，分析結果會顯示在這裡。</p>
  </div>
)}

{dielineLoading && (
  <div className="empty">
    <div className="spinner"></div>
    <h3>正在分析 PDF 刀模…</h3>
    <p>正在讀取 PDF 向量路徑與幾何資訊。</p>
  </div>
)}

</div>
</div>     
           

          </div>

<div className="panel result-panel dieline-result-panel">
  <div className="panel-title">
    <h2>PDF 刀模檢查結果</h2>
    <span>刀模分析</span>
  </div>
          {dielineResult && (
              <div className="result">
                <DielineOverall status={dielineResult.overall} />
                <div className="metrics">
                  <div className="metric"><span>PDF 頁數</span><strong>{dielineResult.page_count}</strong></div>
                  <div className="metric"><span>向量路徑</span><strong>{dielineResult.vector_path_count}</strong></div>
                  <div className="metric"><span>已確認刀模</span><strong className="good">{dielineResult.confirmed_dielines}</strong></div>
                  <div className="metric"><span>疑似刀模</span><strong className="attention">{dielineResult.suspected_dielines}</strong></div>
                </div>
                <div className="dieline-note">{dielineResult.classification_note}</div>
                                {dielineResult.previews?.length > 0 && (
                  <div className="pdf-preview">
                    <h3 className="checks-title">PDF 預覽與異常位置</h3>

                    
<div className="pdf-preview-toolbar">
  <button
    type="button"
    disabled={previewPage <= 1}
    onClick={() => setPreviewPage(p => p - 1)}
  >
    上一頁
  </button>

  <span>
    第 {previewPage} 頁 / 共 {dielineResult.previews.length} 頁
  </span>

  <button
    type="button"
    disabled={previewPage >= dielineResult.previews.length}
    onClick={() => setPreviewPage(p => p + 1)}
  >
    下一頁
  </button>

  <button
    type="button"
    onClick={downloadDielinePreview}
  >
    下載含紅圈 PNG
  </button>
</div>

                    <div className="pdf-preview-image">
  {(() => {
    const preview = dielineResult.previews[previewPage - 1];
    const pageData = dielineResult.pages.find(
      page => page.page === previewPage
    );

    return (
      <div className="pdf-preview-canvas">
        <img
          src={preview?.image}
          alt={`PDF 第 ${previewPage} 頁預覽`}
        />

        {pageData?.issue_markers?.map((marker, index) => (
          <span
            key={`${marker.path}-${index}`}
            className="pdf-issue-marker"
            title={`異常路徑 ${marker.path}`}
            style={{
              left: `${marker.x / (preview?.width || 1) * 100}%`,
              top: `${marker.y / (preview?.height || 1) * 100}%`,
            }}
          />
        ))}
      </div>
    );
  })()}
</div>
                  </div>
                )}
                <h3 className="checks-title">刀模異常檢查</h3>
                {dielineResult.findings.length === 0 ? (
                  <div className="check"><StatusIcon status="pass" /><div><strong>未發現設定範圍內的幾何異常</strong><p>仍請人工確認刀模路徑是否符合實際加工需求。</p></div></div>
                ) : (
                  <div className="checks">
                    {dielineResult.findings.map((finding, index) => (
                      <div className="check" key={`${finding.code}-${index}`}>
                        <StatusIcon status={finding.severity === "fail" ? "fail" : "warning"} />
                        <div><strong>{finding.code} · 第 {finding.page} 頁</strong><p>{finding.message}</p></div>
                      </div>
                    ))}
                  </div>
                )}
                <h3 className="checks-title">向量路徑清單</h3>
                <div className="path-list">
                  {dielineResult.paths.map(path => (
                    <div className="path-row" key={`${path.page}-${path.path_index}`}>
                      <div><strong>第 {path.page} 頁 · 路徑 {path.path_index}</strong><small>{path.layer || "未命名圖層"} · {path.color || "未提供線條顏色"}</small></div>
                      <span className={path.classification === "confirmed" ? "path-confirmed" : "path-suspected"}>{path.classification === "confirmed" ? "已確認" : "疑似"}</span>
                      <span>{path.closed ? "封閉" : "開放"} · {path.length_mm} mm</span>
                    </div>
                  ))}
                  {dielineResult.paths.length === 0 && <p className="dieline-note">未擷取到可分析的向量路徑。若刀模已被點陣化，請提供含向量刀模的 PDF。</p>}
                </div>
                <h3 className="checks-title">各頁面摘要</h3>
                {dielineResult.pages.map(page => (
                  <div className="page-summary" key={page.page}>
                    <strong>第 {page.page} 頁</strong>
                    <span>{page.width_mm} × {page.height_mm} mm</span>
                    <span>{page.vector_path_count} 條向量路徑</span>
                  </div>
                ))}
              </div>
            )}
          </div>
<div className="panel result-panel image-result-panel">
          <div className="panel-title">
            <h2>圖片印刷檢查結果</h2>
            <span>圖片分析</span>
          </div>
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
          PrintCheck v1.1 · 圖片印前預檢與 PDF 刀模初步檢查
        </footer>
      </main>
    </div>
  );
}
