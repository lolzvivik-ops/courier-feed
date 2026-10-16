# STFU — iOS-UI storytelling (Remotion)

A 19.33 s vertical motion piece cut to **STFU — Yeat**. On top: the song's own words as
subtitles, each word appearing exactly when it is sung. In the middle: an iOS-style card
whose events are fired by those words, while cards change on downbeats and punch on kicks.
Everything is code (React + TypeScript + Remotion), rendered deterministically.

| bars | sung line (subtitles) | card | events (sung word → what happens) |
|---|---|---|---|
| 0–1 | pre-hook, line 1 | Messages icon | jumps on the first downbeat; 1st word → badge pops and rolls 1→47, lands on the 2nd word |
| 2–3 | pre-hook, line 2 | iMessage thread, "Do Not Answer" | 1st word → icon opens into the thread; words 2–5 → one text each; "Read 3:47 AM" on the next 808 |
| 4–5 | pre-hook, line 3 | lock screen, 3:47 | a missed call on every word (×1→×3→×5→×8→×12, the phone buzzes); the beat before the drop the Dynamic Island blooms into an incoming call and the track dips into a lowpass |
| 6–7 | lines 4–5 (over the drop) | full-screen incoming call | **the hook's first word is sung on the drop**: light→dark wipe, shake, the call takes the screen; a ring pulses out on every word; the first "Shut" → Decline, "Call Ended" |
| 8–9 | hook, lines 6–7 | Focus → Do Not Disturb | the second "shut" → DND on; the next line's words → the silenced counter rolls 12→29→47 |
| 10 | hook, line 8 | "Block Contact?" alert | 1st word → finger down; 3rd → Block Contact; 4th → "Blocked" pill |
| 11 | hook, line 9 | Messages icon | pill → icon; 1st word → badge 47; 2nd → 9, 3rd → 1, last → 0 and it pops; back to light; last frame = first frame |

The lyric text itself is not in this repository (see below).

Trigger words that set off a card event "stamp" in; the main ones take the colour of what
they trigger (green call, red decline/block/pop, indigo DND).

## Run it

```bash
npm ci
python3 -m venv .venv && .venv/bin/pip install librosa scipy soundfile matplotlib
cp /path/to/stfu.mp3 public/stfu.mp3      # not in git (copyrighted, public repo)

npm run analyze        # beats.json: tempo grid, downbeats, kicks, onsets, fragment
npm run audio          # public/generated/track.wav: the cut + pre-drop lowpass dip
npm run studio         # preview / scrub in Remotion Studio

npm run preview        # 540×960 check render
npm run render         # 1080×1920 60 fps master (H.264 CRF 15, yuv420p, bt709, AAC 320k)
npm run render:30      # 30 fps upload version (re-rendered, not decimated)
npm run render:square  # 1080×1080
```

### Subtitles (lyrics)

The lyrics are copyrighted text, so like the MP3 they stay local: `lyrics.txt` and
`src/data/lyrics.json` are gitignored. Without them the build falls back to
`src/data/lyrics.placeholder.json` (same timings, bullets instead of words).

```bash
python3 -m venv .venv-asr
.venv-asr/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.venv-asr/bin/pip install demucs faster-whisper librosa soundfile scipy

npm run separate       # Demucs htdemucs_ft → .cache/stems/vocals_ft.wav (~3 min on 4 cores)
npm run transcribe     # optional: Whisper large-v3 word timestamps, a starting point for lyrics.txt
# edit lyrics.txt: "song-seconds | line", one sung line per row ("?" at the end = unsure)
npm run lyrics         # forced alignment (MMS CTC) → word onsets → src/data/lyrics.json
```

`npm run lyrics` aligns the whole fragment in one pass (lines stay in order, `*` tokens absorb
ad-libs), re-aligns each line inside its box and keeps the more confident result per word,
then snaps every word start to the nearest vocal onset (±60 ms) of the isolated vocal.
Card events reference words by position — `W(line, word)` in `src/scenes.ts` — so correcting
a word's spelling keeps everything in sync; if a line gets more or fewer words, the build
says which cue to update. `CENSOR` in `src/config.ts` masks profanity on screen.

How the current lyric sheet was made: seven Whisper runs (large-v3 / v2 / turbo / medium on two
Demucs stems) give a consensus for the hook; where they disagree, each candidate wording was
force-aligned against the vocal and the best acoustic fit kept (`scripts/score_candidates.py`,
candidates in the local `lyrics.candidates.json`).
Lines marked `?` in `lyrics.txt` are still best guesses — check them against the official
lyrics (Spotify / Apple Music) and re-run `npm run lyrics`.

### Checks

```bash
npm run sync-report    # every event frame vs onsets: track onsets for beat events, the isolated
                       # vocal for sung words (pass: mean < 1 frame @60, max ≤ 20 ms)
npm run mix-check      # renders the mix, checks clipping and where each UI sound sits
npm run check-text     # no Cyrillic anywhere; prints every on-screen string
npm run check-static   # no stretch without motion longer than 0.5 s (on the preview render)
node scripts/render_stills.mjs --guides 1 --sheet review 0 290 484 650 840 1133   # stills + safe zones
```

`sfx` and `scripts/make_grain.py` regenerate the committed UI sounds and grain tile.
On a machine with a preinstalled Chromium set `REMOTION_BROWSER_EXECUTABLE`.

## How the timing works

- `scripts/analyze_beats.py` fits a constant grid to the track: **149.000 BPM** (librosa's
  estimate is 148.0; the integer grid scores 2.4× better than its neighbours). Hi-hats on 8ths
  make "on the beat" vs "on the and" ambiguous, so the bar phase is chosen as the one that puts
  the biggest energy jumps (the bass drop at 0:08.11) exactly on a bar line.
- The fragment needs 6 bars before the drop. The song's real bass drop (0:08.11) has only 5
  bars of intro before it, so the cut uses **bars 43→55 (69.32–88.65 s)**: the drop is the hook
  coming back at bar 49 (an exact repeat of the first hook, similarity 0.90) — and the hook's
  first word is sung right on that downbeat. 12 bars = 19.33 s.
- `src/scenes.ts` is the script: cards per bar, cues on 8ths or on sung words.
  `src/timeline.ts` resolves them from `beats.json` and `lyrics.json`; nothing is placed in
  seconds by hand. The two halves of the hook align 8.00 beats apart word for word.
- Cards "punch" (+2.5 %, ~10-frame exponential decay, shadow tightens) on kicks from `beats.json`.
- `npm run sync-report` (60 fps): 101 events, mean |Δ| 4.0 ms, max 14.1 ms; sung words alone
  mean 4.3 ms against the vocal.

## Decisions worth knowing

- **Motion blur**: `src/components/MotionBlur.tsx` instead of `<CameraMotionBlur>`. Same
  method (sub-frame renders averaged, 180° shutter, 10 samples) but layers are averaged as a
  running mean (opacity 1/k) rather than `plus-lighter` at 1/N, so static pixels stay exact
  (no banding in the soft gradient and shadows), and the shutter is centred on the frame
  (CameraMotionBlur samples ahead of it, shifting every hit ~0.7 frame early).
- **Fonts**: Inter Tight / Inter woff2 from `@fontsource` in `public/fonts` (the same files Google
  Fonts serves) via `@remotion/fonts`, so renders never depend on network access.
- **Squircles**: continuous corners from `src/lib/squircle.ts` (Figma-style corner smoothing 0.6),
  used for every card, the icon, the Dynamic Island and the morphs (icon → thread, alert → pill → icon).
- **Audio**: one decode (ffmpeg) for analysis and playback so the grid is sample-exact.
  The master decodes to +1.9 dBFS, so the cut gets a static −3.4 dB (peak −1.5 dBFS) instead
  of a limiter. 14 synthesized UI sounds (no Apple sounds, no samples) sit 20–25 dB under it.
- **Loop**: frame 0 and the last frame differ by < 1 level once the 24 fps grain is averaged out.
- **Safe zones** (TikTok 150 / 140 / 420): text axis and cards sit 10 px left of centre so card
  UI clears the right rail; `--guides 1` draws the zones.

## Layout

```
lyrics.txt        the sung lines (local only)
src/
  config.ts       AUDIO_START / AUDIO_END, sync offset, CENSOR, layouts (9:16, 1:1), levels
  scenes.ts       the script: cards, cues (beats or W(line, word)), accents, UI copy
  lyrics.ts       lyrics.json → subtitle words in timeline units
  timeline.ts     script × beats.json × lyrics → times, kicks, SFX, the dip
  data/           beats.json, lyrics.json (local), lyrics.placeholder.json
  components/     Card, Squircle, Subtitles (word reveal), MotionBlur, Backdrop (bg, grain,
                  theme wipe), Roulette (odometer digits), MessagesIcon/Badge, Floaters, Icons
  scenes/         IntroThread, LockScene, CallScene, FocusScene, BlockOutro
scripts/          analysis, stems, transcription, lyric alignment, audio prep, SFX, checks, stills
webpack-override.mjs  the lyrics → placeholder fallback for the bundler
```

Spec component → code: `Card`, `Squircle` → components/; `WordReveal` → components/Subtitles.tsx;
`ChatThread` → scenes/IntroThread.tsx; `LockScreen` → scenes/LockScene.tsx; `FocusTile` →
scenes/FocusScene.tsx; `Alert` → scenes/BlockOutro.tsx; `BadgeCounter` →
components/MessagesIcon.tsx (`Badge`) + components/Roulette.tsx; `Grain` → components/Backdrop.tsx.
The volume HUD from the first cut was replaced by the incoming call (scenes/CallScene.tsx),
which is what the drop's lyric is about.
