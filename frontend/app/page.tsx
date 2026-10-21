"use client";

import { useMemo, useState } from "react";
import { createJob } from "../lib/api";

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileHint = useMemo(() => {
    if (!file) return "建议先上传 WAV（后端无 ffmpeg 时最稳）";
    const mb = file.size / (1024 * 1024);
    const suffix = file.name.toLowerCase().endsWith(".wav") ? "" : "（当前后端只稳定支持 .wav）";
    const sizeWarn = mb > 50 ? "（可能超过后端默认 50MB 上限）" : "";
    return `${file.name} (${mb.toFixed(1)} MB) ${suffix}${sizeWarn}`;
  }, [file]);

  async function onSubmit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const { job_id, job_token } = await createJob(file);
      sessionStorage.setItem(`job_token:${job_id}`, job_token);
      window.location.href = `/editor/${job_id}`;
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="row">
      <div className="card" style={{ flex: "1 1 520px" }}>
        <h1>吉他六线谱</h1>
        <p className="muted">上传 WAV、MP3 或 M4A 得到初稿，或从空白谱、简谱、和弦开始，然后在网页上改到能导出。</p>
        <p>
          <a className="btn secondary" href="/editor/new">
            空白谱 / 文本初稿
          </a>
        </p>
        <div className="no-print">
          <label>
            音频文件（≤5分钟）
            <input
              type="file"
              accept="audio/*"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={busy}
            />
          </label>
          <p className="muted">{fileHint}</p>
          <button className="btn" onClick={onSubmit} disabled={!file || busy}>
            {busy ? "上传中…" : "开始生成"}
          </button>
          {error ? (
            <pre className="card mono" style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>
              {error}
            </pre>
          ) : null}
        </div>
      </div>
      <div className="card" style={{ flex: "1 1 360px" }}>
        <h2>输入说明</h2>
        <ul>
          <li>音频接受 WAV、MP3、M4A。干净的单吉他效果最好。</li>
          <li>编辑页用同一份乐谱数据画出六线谱，并可下载 .gp 与 .gp5。</li>
          <li>从音频逐音识别还没做，谱面上的音是可弹的六线谱，不是和弦扫弦表。</li>
        </ul>
      </div>
    </div>
  );
}
