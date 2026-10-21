export type ChordShape = {
  name: string;
  // frets for strings 6..1; null = mute
  frets: Array<number | null>;
  baseFret?: number; // 1-based
};

const SHAPES: Record<string, ChordShape> = {
  C: { name: "C", frets: [null, 3, 2, 0, 1, 0] },
  G: { name: "G", frets: [3, 2, 0, 0, 0, 3] },
  D: { name: "D", frets: [null, null, 0, 2, 3, 2] },
  A: { name: "A", frets: [null, 0, 2, 2, 2, 0] },
  E: { name: "E", frets: [0, 2, 2, 1, 0, 0] },
  Am: { name: "Am", frets: [null, 0, 2, 2, 1, 0] },
  Em: { name: "Em", frets: [0, 2, 2, 0, 0, 0] },
  Dm: { name: "Dm", frets: [null, null, 0, 2, 3, 1] },
  F: { name: "F", frets: [1, 3, 3, 2, 1, 1] },

  // Common barre shapes for D key examples
  Bm: { name: "Bm", frets: [null, 2, 4, 4, 3, 2], baseFret: 1 },
  "F#m": { name: "F#m", frets: [2, 4, 4, 2, 2, 2], baseFret: 1 },
  Gmaj7: { name: "Gmaj7", frets: [3, 2, 0, 0, 0, 2] }
};

export function normalizeChordSymbol(sym: string): string {
  const s = sym.trim();
  if (!s) return s;
  // Basic normalization: "F# m" -> "F#m", "A min" -> "Am"
  return s.replace(/\s+/g, "").replace(/min$/i, "m");
}

export function getChordShape(sym: string): ChordShape | null {
  const k = normalizeChordSymbol(sym);
  return SHAPES[k] || null;
}

export function renderChordSvg(sym: string, size = 84): string | null {
  const shape = getChordShape(sym);
  if (!shape) return null;
  const frets = shape.frets;
  const base = shape.baseFret || 1;
  const w = size;
  const h = Math.round(size * 1.1);
  const pad = 10;
  const gridTop = 18;
  const gridLeft = pad;
  const gridW = w - pad * 2;
  const gridH = h - gridTop - pad;
  const strings = 6;
  const fretCount = 5;
  const dx = gridW / (strings - 1);
  const dy = gridH / fretCount;

  const stringX = (s: number) => gridLeft + s * dx; // s:0..5 corresponds to strings 6..1
  const fretY = (f: number) => gridTop + f * dy;

  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">`;
  svg += `<text x="${w / 2}" y="12" text-anchor="middle" font-family="ui-monospace, Menlo, monospace" font-size="12">${shape.name}</text>`;

  // nut / base fret
  const nutY = gridTop;
  svg += `<rect x="${gridLeft}" y="${nutY - 2}" width="${gridW}" height="${base === 1 ? 4 : 1}" fill="#111827" />`;
  if (base !== 1) {
    svg += `<text x="${gridLeft - 2}" y="${gridTop + 12}" text-anchor="end" font-family="ui-monospace, Menlo, monospace" font-size="10">${base}fr</text>`;
  }

  // strings
  for (let s = 0; s < strings; s++) {
    const x = stringX(s);
    svg += `<line x1="${x}" y1="${gridTop}" x2="${x}" y2="${gridTop + gridH}" stroke="#111827" stroke-width="1" />`;
  }
  // frets
  for (let f = 0; f <= fretCount; f++) {
    const y = fretY(f);
    svg += `<line x1="${gridLeft}" y1="${y}" x2="${gridLeft + gridW}" y2="${y}" stroke="#111827" stroke-width="1" />`;
  }

  // markers
  for (let s = 0; s < strings; s++) {
    const fret = frets[s];
    const x = stringX(s);
    if (fret === null) {
      svg += `<text x="${x}" y="${gridTop - 6}" text-anchor="middle" font-family="ui-monospace, Menlo, monospace" font-size="10">x</text>`;
      continue;
    }
    if (fret === 0) {
      svg += `<text x="${x}" y="${gridTop - 6}" text-anchor="middle" font-family="ui-monospace, Menlo, monospace" font-size="10">o</text>`;
      continue;
    }
    const fretRel = fret - base;
    const cy = gridTop + (fretRel + 0.5) * dy;
    svg += `<circle cx="${x}" cy="${cy}" r="${Math.max(3, dx * 0.16)}" fill="#111827" />`;
  }

  svg += `</svg>`;
  return svg;
}

