import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import * as alphaTab from "@coderline/alphatab";

import { exportGp, notesFromGp, playedBeats, renderScoreSvg, scoreToAlphaTex, type TabScore } from "./tabScore";

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  fs.readFileSync(path.resolve(here, "../../scores/fixture.score.json"), "utf8")
) as TabScore;

function sorted(beats: ReturnType<typeof playedBeats>) {
  return beats.map((beat) => ({
    duration: beat.duration,
    notes: [...beat.notes].sort((a, b) => a.string - b.string)
  }));
}

test("alphaTab SVG shows fixture fret numerals and .gp reloads the same notes", () => {
  const svg = renderScoreSvg(fixture);
  const texts = [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map((match) =>
    match[1].replace(/&#\d+;/g, "").trim()
  );
  assert.ok(texts.includes("0"), `open-string 0 missing from ${texts.join(",")}`);
  assert.ok(
    texts.some((text) => Number(text) >= 3),
    `fret >= 3 missing from ${texts.join(",")}`
  );
  assert.match(svg, /&#57424;/, "treble clef glyph missing");
  assert.ok((svg.match(/&#57476;/g) || []).length >= 2, "4/4 time signature glyphs missing");
  assert.match(svg, /&#58658;/, "eighth-note flag glyph missing");

  const gp = exportGp(fixture);
  assert.equal(Buffer.from(gp.subarray(0, 2)).toString("utf8"), "PK");
  const expected = sorted(playedBeats(fixture));
  const loaded = sorted(notesFromGp(gp));
  assert.deepEqual(loaded, expected);
  assert.equal(loaded[1].duration * 2, loaded[0].duration);
});

test("alphaTex keeps dotted rests key dynamics and techniques", () => {
  const score = {
    ...fixture,
    keySignature: "G",
    tracks: [
      {
        ...fixture.tracks[0],
        bars: [
          {
            repeatStart: true,
            repeatEnd: 2,
            beats: [
              {
                duration: 1.5,
                chord: "Em",
                notes: [
                  {
                    string: 3,
                    fret: 0,
                    duration: 1.5,
                    dynamic: "p",
                    hammer: true,
                    pull: false,
                    slide: true,
                    bend: true,
                    vibrato: true,
                    palmMute: true,
                    dead: true,
                    tie: true
                  }
                ]
              },
              { duration: 1, rest: true, notes: [] },
              {
                duration: 1,
                notes: [{ string: 2, fret: 1, duration: 1, dynamic: "mf" }]
              },
              {
                duration: 1,
                notes: [{ string: 1, fret: 3, duration: 1, dynamic: "f" }]
              }
            ]
          }
        ]
      }
    ]
  } as TabScore;
  const tex = scoreToAlphaTex(score);
  assert.match(tex, /\{h sl be bend 0 0 12 1 v pm x t d dy p ch Em\}/);
  assert.match(tex, /dy mf/);
  assert.match(tex, /dy f/);
  assert.match(tex, /\\ks \(g major\)/);
  assert.match(tex, /:4 r/);
  assert.match(tex, /\\ro/);
  assert.match(tex, /\\rc 2/);
  const loaded = alphaTab.importer.ScoreLoader.loadAlphaTex(tex);
  assert.equal(loaded.tracks[0].staves[0].bars[0].keySignature, 1);
  const svg = renderScoreSvg(score);
  assert.match(svg, /&#58656;/, "piano dynamic missing");
  assert.match(svg, /&#57954;/, "G major sharp missing");
  assert.doesNotMatch(tex, /:3 /);
  assert.doesNotMatch(tex, /undefined/);
});

test("repeat close stays on the same bar and does not add a measure", () => {
  const score = {
    ...fixture,
    tracks: [
      {
        ...fixture.tracks[0],
        bars: [
          {
            repeatStart: true,
            repeatEnd: 2,
            beats: [{ duration: 1, notes: [{ string: 6, fret: 0, duration: 1 }] }]
          },
          {
            beats: [{ duration: 1, notes: [{ string: 1, fret: 3, duration: 1 }] }]
          }
        ]
      }
    ]
  } as TabScore;
  const tex = scoreToAlphaTex(score);
  assert.match(tex, /\\ro \\rc 2 :4 0\.6 \| :4 3\.1/);
  const loaded = alphaTab.importer.ScoreLoader.loadAlphaTex(tex);
  assert.equal(loaded.masterBars.length, 2);
  assert.equal(loaded.masterBars[0].isRepeatStart, true);
  assert.equal(loaded.masterBars[0].repeatCount, 2);
  assert.equal(loaded.tracks[0].staves[0].bars[1].voices[0].beats[0].notes[0].fret, 3);
});

test("alphaTab reads a Guitar Pro file and MusicXML", () => {
  const gp = execFileSync(
    path.resolve(here, "../../backend/.venv/bin/python"),
    [
      "-c",
      "from app.tab.drafts import parse_jianpu; from app.tab.gp5 import score_to_gp5_bytes; import sys; sys.stdout.buffer.write(score_to_gp5_bytes(parse_jianpu('key C\\ntime 4/4\\n1 3\\n')))"
    ],
    { cwd: path.resolve(here, "../../backend") }
  );
  const gpScore = alphaTab.importer.ScoreLoader.loadScoreFromBytes(gp);
  const gpPitches = gpScore.tracks[0].staves[0].bars[0].voices[0].beats.flatMap((beat) =>
    beat.notes.map((note) => note.realValue)
  );
  assert.deepEqual(gpPitches, [60, 64]);

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Guitar</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>1</divisions></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
    <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
  </measure></part>
</score-partwise>`;
  const xmlScore = alphaTab.importer.ScoreLoader.loadScoreFromBytes(new TextEncoder().encode(xml));
  const xmlPitches = xmlScore.tracks[0].staves[0].bars[0].voices[0].beats.flatMap((beat) =>
    beat.notes.map((note) => note.realValue)
  );
  assert.deepEqual(xmlPitches, [60, 64]);
});

test("editor sheet downloads .gp and .gp5 and drops the chord chart", () => {
  const page = fs.readFileSync(path.resolve(here, "../app/editor/[jobId]/page.tsx"), "utf8");
  const api = fs.readFileSync(path.resolve(here, "api.ts"), "utf8");
  assert.match(page, /下载 \.gp/);
  assert.match(page, /下载 \.gp5/);
  assert.match(page, /\/api\/export\/gp5/);
  assert.match(api, /\/export\/gp5/);
  const tab = fs.readFileSync(path.resolve(here, "tabScore.ts"), "utf8");
  assert.match(page, /mountScore/);
  assert.match(page, /exportGp/);
  assert.match(page, /应用品位/);
  assert.match(page, /editScore/);
  assert.match(page, /生成简谱/);
  assert.match(tab, /ScoreTab/);
  assert.match(tab, /fontDirectory = "\/font\/"/);
  assert.equal(page.includes("window.print"), false);
  assert.equal(page.includes("renderChordSvg"), false);
  assert.equal(page.includes("hit_mask"), false);
  assert.equal(page.includes("chordDiagrams"), false);
  assert.equal(page.includes("节奏型"), false);
});
