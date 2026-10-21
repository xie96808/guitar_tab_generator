import * as alphaTab from "@coderline/alphatab";

export type TabNote = {
  string: number;
  fret: number;
  duration: number;
  dynamic?: string;
  tie?: boolean;
  dead?: boolean;
  hammer?: boolean;
  pull?: boolean;
  slide?: boolean;
  bend?: boolean;
  vibrato?: boolean;
  palmMute?: boolean;
};

export type TabBeat = {
  duration: number;
  rest?: boolean;
  chord?: string | null;
  notes: TabNote[];
};

export type TabBar = {
  repeatStart?: boolean;
  repeatEnd?: number;
  beats: TabBeat[];
};

export type TabTrack = {
  name: string;
  tuning: number[];
  bars: TabBar[];
};

export type TabScore = {
  title: string;
  tempo: number;
  timeSignature: string;
  keySignature?: string;
  tracks: TabTrack[];
};

export type PlayedBeat = {
  duration: number;
  notes: Array<{ string: number; fret: number }>;
};

function texDuration(quarters: number): { token: string; dotted: boolean } {
  const known: Array<[number, number, boolean]> = [
    [4, 1, false],
    [3, 2, true],
    [2, 2, false],
    [1.5, 4, true],
    [1, 4, false],
    [0.75, 8, true],
    [0.5, 8, false],
    [0.25, 16, false]
  ];
  for (const [value, denom, dotted] of known) {
    if (Math.abs(quarters - value) < 1e-6) return { token: `:${denom}`, dotted };
  }
  return { token: `:${Math.max(1, Math.round(4 / quarters))}`, dotted: false };
}

function keyTex(key: string | undefined): string {
  if (!key) return "";
  const minor = key.endsWith("m");
  const letter = (minor ? key.slice(0, -1) : key).toLowerCase();
  return `\\ks (${letter} ${minor ? "minor" : "major"})`;
}

function noteTags(note: TabNote): string[] {
  const tags: string[] = [];
  if (note.hammer || note.pull) tags.push("h");
  if (note.slide) tags.push("sl");
  if (note.bend) tags.push("be bend 0 0 12 1");
  if (note.vibrato) tags.push("v");
  if (note.palmMute) tags.push("pm");
  if (note.dead) tags.push("x");
  if (note.tie) tags.push("t");
  return tags;
}

function beatTex(beat: TabBeat): string {
  const { token, dotted } = texDuration(beat.duration);
  const beatTags: string[] = [];
  if (dotted) beatTags.push("d");
  const dynamic = beat.notes.find((note) => note.dynamic)?.dynamic;
  if (dynamic) beatTags.push(`dy ${dynamic}`);
  if (beat.chord) beatTags.push(`ch ${beat.chord}`);
  if (beat.rest || beat.notes.length === 0) {
    const brace = beatTags.length ? `{${beatTags.join(" ")}}` : "";
    return `${token} r${brace}`;
  }
  const sounded = beat.notes.map((note, index) => {
    const tags = index === 0 ? [...noteTags(note), ...beatTags] : noteTags(note);
    const brace = tags.length ? `{${tags.join(" ")}}` : "";
    return `${note.fret}.${note.string}${brace}`;
  });
  const cluster = sounded.length > 1 ? `(${sounded.join(" ")})` : sounded[0];
  return `${token} ${cluster}`;
}

export function scoreToAlphaTex(score: TabScore): string {
  const track = score.tracks[0];
  const [numerator, denominator] = score.timeSignature.split("/");
  const bars = track.bars.map((bar, index) => {
    const head = [
      index === 0 ? keyTex(score.keySignature) : "",
      bar.repeatStart ? "\\ro" : "",
      bar.repeatEnd && bar.repeatEnd > 0 ? `\\rc ${bar.repeatEnd}` : ""
    ].filter(Boolean);
    return `${head.join(" ")} ${bar.beats.map(beatTex).join(" ")}`.trim();
  });
  return [
    `\\title "${score.title}"`,
    `\\tempo ${score.tempo}`,
    `\\ts ${numerator} ${denominator}`,
    ".",
    `\\track "${track.name}"`,
    "\\staff {score tabs}",
    bars.join(" | ")
  ].join("\n");
}

function tabSettings(): alphaTab.Settings {
  const settings = new alphaTab.Settings();
  settings.core.engine = "svg";
  settings.core.useWorkers = false;
  settings.core.enableLazyLoading = false;
  settings.core.logLevel = alphaTab.LogLevel.None;
  settings.display.staveProfile = alphaTab.StaveProfile.ScoreTab;
  settings.player.playerMode = alphaTab.PlayerMode.Disabled;
  return settings;
}

function loadScore(score: TabScore): alphaTab.model.Score {
  return alphaTab.importer.ScoreLoader.loadAlphaTex(scoreToAlphaTex(score));
}

export function mountScore(element: HTMLElement, score: TabScore): { destroy(): void } {
  element.replaceChildren();
  const settings = tabSettings();
  settings.core.fontDirectory = "/font/";
  const api = new alphaTab.AlphaTabApi(element, settings);
  api.tex(scoreToAlphaTex(score));
  return api;
}

export function renderScoreSvg(score: TabScore): string {
  const parsed = loadScore(score);
  const settings = tabSettings();
  const renderer = new alphaTab.rendering.ScoreRenderer(settings);
  renderer.width = 980;
  const chunks: string[] = [];
  renderer.partialRenderFinished.on((event) => {
    if (typeof event.renderResult === "string") chunks.push(event.renderResult);
  });
  renderer.renderScore(parsed, [0]);
  renderer.destroy();
  if (!chunks.length) throw new Error("alphaTab did not render an SVG");
  return chunks.join("");
}

export function exportGp(score: TabScore): Uint8Array {
  const parsed = loadScore(score);
  return new alphaTab.exporter.Gp7Exporter().export(parsed, tabSettings());
}

export function notesFromGp(bytes: Uint8Array): PlayedBeat[] {
  const parsed = alphaTab.importer.ScoreLoader.loadScoreFromBytes(bytes);
  const stringCount = parsed.tracks[0].staves[0].tuning.length;
  const beats: PlayedBeat[] = [];
  for (const bar of parsed.tracks[0].staves[0].bars) {
    for (const beat of bar.voices[0].beats) {
      if (!beat.notes.length) continue;
      beats.push({
        duration: 4 / Number(beat.duration),
        notes: beat.notes.map((note) => ({
          string: stringCount + 1 - note.string,
          fret: note.fret
        }))
      });
    }
  }
  return beats;
}

export function playedBeats(score: TabScore): PlayedBeat[] {
  return score.tracks[0].bars.flatMap((bar) =>
    bar.beats.map((beat) => ({
      duration: beat.duration,
      notes: beat.notes.map((note) => ({ string: note.string, fret: note.fret }))
    }))
  );
}
