export type JobStatus = "queued" | "running" | "completed" | "failed";

export type JobState = {
  job_id: string;
  status: JobStatus;
  progress: number;
  message?: string | null;
  error?: string | null;
};

export type TabNote = {
  string: number;
  fret: number;
  duration: number;
};

export type TabScore = {
  title: string;
  tempo: number;
  timeSignature: string;
  tracks: Array<{
    name: string;
    tuning: number[];
    bars: Array<{
      beats: Array<{
        duration: number;
        notes: TabNote[];
      }>;
    }>;
  }>;
};

export type AnalysisResult = {
  meta: {
    title: string;
    bpm: number;
    time_signature: string;
    key?: string;
    key_confidence?: number;
    suggested_capo?: any;
    limitations?: string[];
  };
  score: TabScore;
  timeline: {
    beat_times: number[];
    onset_times: number[];
    measures: Array<{
      index: number;
      start_time: number;
      end_time: number;
      beats_per_bar: number;
    }>;
  };
  sections: Array<{ id: string; name: string; start_measure: number; end_measure: number }>;
  chords: Array<{ beat_index: number; chord: string; confidence: number }>;
  rhythm_patterns: Array<{
    section_id: string;
    subdivisions_per_bar: number;
    hit_mask: number[];
    accent: number[];
    style: string;
    suggested_du: string[];
  }>;
  lyrics?: any;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function createJob(file: File): Promise<{ job_id: string; job_token: string }> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: form });
  if (!resp.ok) {
    throw new Error(await resp.text());
  }
  return resp.json();
}

export async function getJobState(jobId: string, token: string): Promise<JobState> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`, { headers: { "X-Job-Token": token } });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

export async function getJobResult(jobId: string, token: string): Promise<AnalysisResult> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/result`, { headers: { "X-Job-Token": token } });
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

export async function createDraft(kind: string, text = "", strum = "quarter"): Promise<TabScore> {
  const resp = await fetch(`${API_BASE}/api/drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, text, strum })
  });
  if (!resp.ok) throw new Error(await resp.text());
  const body = await resp.json();
  return body.score;
}

export async function uploadDraftFile(file: File): Promise<TabScore> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(`${API_BASE}/api/drafts/file`, { method: "POST", body: form });
  if (!resp.ok) throw new Error(await resp.text());
  const body = await resp.json();
  return body.score;
}

export async function editScore(score: TabScore, edit: Record<string, unknown>): Promise<TabScore> {
  const resp = await fetch(`${API_BASE}/api/score/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score, edit })
  });
  if (!resp.ok) throw new Error(await resp.text());
  const body = await resp.json();
  return body.score;
}

export async function downloadScoreGp5(score: TabScore, filename: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/export/gp5`, {
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

export async function downloadGp5(jobId: string, token: string, filename: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/export/gp5`, { headers: { "X-Job-Token": token } });
  if (!resp.ok) throw new Error(await resp.text());
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
