export function cleanupLyrics(raw: string): { metaLines: string[]; body: string } {
  const lines = raw
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  const meta: string[] = [];
  const body: string[] = [];

  const metaRe = /^(词|曲|编曲|原唱|演唱|作词|作曲|制作|OP|SP|词：|曲：|编曲：)/;
  for (const l of lines) {
    if (body.length === 0 && (metaRe.test(l) || l.includes(" - "))) {
      meta.push(l);
      continue;
    }
    body.push(l);
  }
  return { metaLines: meta, body: body.join("\n") };
}

export type LyricLine = {
  id: string;
  text: string;
  startMeasure: number;
  endMeasure: number;
};

export function splitLineAt(text: string, idx: number): [string, string] {
  const a = text.slice(0, idx).trim();
  const b = text.slice(idx).trim();
  return [a, b];
}

export function distributeAcrossMeasures(text: string, measures: number): string[] {
  const s = text.trim();
  if (measures <= 1) return [s];
  if (!s) return new Array(measures).fill("");

  const chars = Array.from(s);
  const per = Math.ceil(chars.length / measures);
  const out: string[] = [];
  for (let i = 0; i < measures; i++) {
    out.push(chars.slice(i * per, (i + 1) * per).join("").trim());
  }
  return out;
}

