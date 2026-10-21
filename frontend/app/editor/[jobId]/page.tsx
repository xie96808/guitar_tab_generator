"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalysisResult, JobState } from "../../../lib/api";
import { createDraft, editScore, getJobResult, getJobState, uploadDraftFile } from "../../../lib/api";
import { exportGp, mountScore, type TabScore } from "../../../lib/tabScore";

function getToken(jobId: string): string | null {
  return sessionStorage.getItem(`job_token:${jobId}`);
}

function saveBytes(bytes: Uint8Array, filename: string) {
  const copy = Uint8Array.from(bytes);
  const blob = new Blob([copy.buffer], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function downloadEditedGp5(score: TabScore, filename: string) {
  const resp = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/export/gp5`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score })
  });
  if (!resp.ok) throw new Error(await resp.text());
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function EditorPage({ params }: { params: { jobId: string } }) {
  const jobId = params.jobId;
  const isNew = jobId === "new";
  const [token, setToken] = useState<string | null>(isNew ? "local" : null);
  const [state, setState] = useState<JobState | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [score, setScore] = useState<TabScore | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jianpu, setJianpu] = useState("key C\ntime 4/4\n1 2 3 5 | 6 5 3 2");
  const [chords, setChords] = useState("Em G | C D");
  const [ascii, setAscii] = useState("e|--0--3--|\nB|--1-----|\nG|--------|\nD|--------|\nA|--------|\nE|--------|");
  const [fret, setFret] = useState("3");
  const [stringNumber, setStringNumber] = useState("1");
  const [duration, setDuration] = useState("1");
  const [dotted, setDotted] = useState(false);
  const [tempo, setTempo] = useState("120");
  const [numerator, setNumerator] = useState("4");
  const [denominator, setDenominator] = useState("4");
  const [keyName, setKeyName] = useState("C");
  const [dynamic, setDynamic] = useState("f");
  const [chordName, setChordName] = useState("Em");
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isNew) setToken(getToken(jobId));
  }, [isNew, jobId]);

  useEffect(() => {
    if (isNew || token == null || token === "local") return;
    const token2 = token;
    let alive = true;
    async function poll() {
      try {
        const next = await getJobState(jobId, token2);
        if (!alive) return;
        setState(next);
        if (next.status === "completed") {
          const job = await getJobResult(jobId, token2);
          if (!alive) return;
          setResult(job);
          setScore(job.score as TabScore);
          alive = false;
        }
        if (next.status === "failed") setError(next.error || "Job failed");
      } catch (err: unknown) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    }
    poll();
    const id = setInterval(() => {
      if (alive) poll();
    }, 1200);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [isNew, jobId, token]);

  useEffect(() => {
    const element = sheetRef.current;
    if (!element || !score) return;
    const api = mountScore(element, score);
    return () => api.destroy();
  }, [score]);

  async function runEdit(edit: Record<string, unknown>) {
    if (!score) return;
    const next = await editScore(score, edit);
    setScore(next);
  }

  async function loadKind(kind: string, text = "") {
    setError(null);
    try {
      setScore(await createDraft(kind, text, "quarter"));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  if (!isNew && !token) {
    return (
      <div className="card">
        <h1>编辑器</h1>
        <p className="muted">找不到 job token。回到首页重新生成，或打开空白谱。</p>
        <a className="btn secondary" href="/editor/new">
          空白谱 / 文本初稿
        </a>
      </div>
    );
  }

  const title = score?.title || result?.meta.title || "tab";

  return (
    <div>
      <div className="card">
        <h1>{score ? title : "编辑吉他谱"}</h1>
        <p className="muted">{score ? `${score.timeSignature} · ${score.tempo} BPM` : state?.message || "先生成初稿，再在这页上改。"}</p>
        <div className="row">
          <button className="btn secondary" type="button" onClick={() => loadKind("blank")}>
            空白谱
          </button>
          <button className="btn secondary" type="button" onClick={() => loadKind("jianpu", jianpu)}>
            生成简谱
          </button>
          <button className="btn secondary" type="button" onClick={() => loadKind("chords", chords)}>
            生成和弦
          </button>
          <button className="btn secondary" type="button" onClick={() => loadKind("ascii", ascii)}>
            生成文本六线
          </button>
        </div>
        <label>
          简谱
          <textarea value={jianpu} onChange={(event) => setJianpu(event.target.value)} rows={3} />
        </label>
        <label>
          和弦
          <textarea value={chords} onChange={(event) => setChords(event.target.value)} rows={2} />
        </label>
        <label>
          文本六线
          <textarea value={ascii} onChange={(event) => setAscii(event.target.value)} rows={6} />
        </label>
        <label>
          MIDI / Guitar Pro / MusicXML
          <input
            type="file"
            accept=".mid,.midi,.gp,.gp5,.xml,.musicxml"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              try {
                setScore(await uploadDraftFile(file));
              } catch (err: unknown) {
                setError(err instanceof Error ? err.message : String(err));
              }
            }}
          />
        </label>
        {error ? <pre className="mono">{error}</pre> : null}
      </div>
      {score ? (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="row">
            <button className="btn" type="button" onClick={() => saveBytes(exportGp(score), `${title}.gp`)}>
              下载 .gp
            </button>
            <button className="btn secondary" type="button" onClick={() => downloadEditedGp5(score, `${title}.gp5`)}>
              下载 .gp5
            </button>
          </div>
          <div className="row">
            <label>
              品位
              <input aria-label="品位" value={fret} onChange={(event) => setFret(event.target.value)} />
            </label>
            <label>
              弦号
              <input aria-label="弦号" value={stringNumber} onChange={(event) => setStringNumber(event.target.value)} />
            </label>
            <label>
              时值
              <input aria-label="时值" value={duration} onChange={(event) => setDuration(event.target.value)} />
            </label>
            <label>
              附点
              <input type="checkbox" checked={dotted} onChange={(event) => setDotted(event.target.checked)} />
            </label>
            <button
              className="btn"
              type="button"
              onClick={() => runEdit({ op: "set_fret", bar: 0, beat: 0, note: 0, fret: Number(fret) })}
            >
              应用品位
            </button>
            <button
              className="btn secondary"
              type="button"
              onClick={() => runEdit({ op: "set_string", bar: 0, beat: 0, note: 0, string: Number(stringNumber) })}
            >
              应用弦号
            </button>
            <button
              className="btn secondary"
              type="button"
              onClick={() =>
                runEdit({ op: "set_duration", bar: 0, beat: 0, duration: Number(duration), dotted })
              }
            >
              应用时值
            </button>
          </div>
          <div className="row">
            <label>
              速度
              <input aria-label="速度" value={tempo} onChange={(event) => setTempo(event.target.value)} />
            </label>
            <label>
              拍号分子
              <input aria-label="拍号分子" value={numerator} onChange={(event) => setNumerator(event.target.value)} />
            </label>
            <label>
              拍号分母
              <input aria-label="拍号分母" value={denominator} onChange={(event) => setDenominator(event.target.value)} />
            </label>
            <label>
              调号
              <input aria-label="调号" value={keyName} onChange={(event) => setKeyName(event.target.value)} />
            </label>
            <label>
              力度
              <select aria-label="力度" value={dynamic} onChange={(event) => setDynamic(event.target.value)}>
                <option value="p">p</option>
                <option value="mf">mf</option>
                <option value="f">f</option>
              </select>
            </label>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_tempo", tempo: Number(tempo) })}>
              应用速度
            </button>
            <button
              className="btn secondary"
              type="button"
              onClick={() =>
                runEdit({ op: "set_time_signature", numerator: Number(numerator), denominator: Number(denominator) })
              }
            >
              应用拍号
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_key", key: keyName })}>
              应用调号
            </button>
            <button
              className="btn secondary"
              type="button"
              onClick={() => runEdit({ op: "set_dynamic", bar: 0, beat: 0, note: 0, dynamic })}
            >
              应用力度
            </button>
          </div>
          <div className="row">
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_rest", bar: 0, beat: 0 })}>
              休止符
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_tie", bar: 0, beat: 0, note: 0 })}>
              延音线
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_hammer", bar: 0, beat: 0, note: 0 })}>
              击弦
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_pull", bar: 0, beat: 0, note: 0 })}>
              勾弦
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_slide", bar: 0, beat: 0, note: 0 })}>
              滑音
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_bend", bar: 0, beat: 0, note: 0, semitones: 1 })}>
              推弦
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_vibrato", bar: 0, beat: 0, note: 0 })}>
              颤音
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_palm_mute", bar: 0, beat: 0, note: 0 })}>
              闷音
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_dead", bar: 0, beat: 0, note: 0 })}>
              死音
            </button>
            <label>
              和弦名
              <input aria-label="和弦名" value={chordName} onChange={(event) => setChordName(event.target.value)} />
            </label>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_chord", bar: 0, beat: 0, name: chordName })}>
              应用和弦名
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "set_repeat", start: 0, end: 0, count: 2 })}>
              反复记号
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "add_note", bar: 0, beat: 0, string: 1, fret: 0 })}>
              加音
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "delete_note", bar: 0, beat: 0, note: 0 })}>
              删音
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "quantize", grid: 0.5 })}>
              量化
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "delete_bar", bar: 0 })}>
              删除小节
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "copy_bar", bar: 0 })}>
              复制小节
            </button>
            <button className="btn secondary" type="button" onClick={() => runEdit({ op: "transpose", semitones: 2 })}>
              移调
            </button>
          </div>
        </div>
      ) : null}
      <div className="card tab-sheet" style={{ marginTop: 12 }} data-tab-sheet="" ref={sheetRef} />
    </div>
  );
}
