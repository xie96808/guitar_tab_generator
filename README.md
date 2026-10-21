# guitar_tab_generator

Web app for drafting a guitar score, editing it in the browser, and exporting Guitar Pro files.

## What you can do

- Upload WAV, MP3, or M4A. A clean single-guitar recording becomes a rough staff-and-tab draft.
- Start from a blank score, numbered notation (简谱), chord-and-strum text, ASCII tab, MIDI, Guitar Pro, or MusicXML.
- Edit frets, strings, durations, tempo, meter, key, dynamics, and techniques on the same page.
- Download `.gp` and `.gp5`.

Full-mix transcription is not accurate. Treat audio output as a draft and correct it in the editor.

## Run locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

MP3 and M4A decoding uses `ffmpeg` on your PATH.

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000" npm run dev
```

Open `http://localhost:3000`. A blank or text draft is at `http://localhost:3000/editor/new`.
