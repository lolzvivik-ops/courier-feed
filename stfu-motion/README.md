# STFU — iOS-UI storytelling (Remotion)

A 19.33 s vertical motion piece cut to **STFU — Yeat**: kinetic headline on top,
an iOS-style card in the middle that acts the line out, every hit on the grid.
Everything is code (React + TypeScript + Remotion), rendered deterministically.

| bars | headline | card | main event (on the beat) |
|---|---|---|---|
| 0 | 47 unread. | Messages icon | jumps on beat 1 (squash & stretch), badge pops and rolls 1→47, icon opens into the thread |
| 1–2 | You text. You call. | iMessage thread, "Do Not Answer" | one bubble per 808 hit, tail hops to the newest, "Read 3:47 AM" a beat later |
| 3 | At 3:47 AM. | lock screen, Wednesday, October 15 | a missed call lands on every beat, ×1→×3→×7→×12, the phone buzzes |
| 4–5 | And I just turn on the silence. | Focus → Do Not Disturb | finger down on the 808, toggle on the last beat before the drop, track dips into a lowpass |
| 6 | Silence. | volume HUD | **drop**: light→dark wipe from the card centre (8 frames), shake; volume falls to 0, speaker slashes |
| 7–8 | and you're blocked. | "Block Contact?" alert | press lands on the downbeat, alert collapses into a "Blocked" pill |
| 9–11 | Finally quiet. | Messages icon | badge rolls 47→4, then 3-2-1-0 on 8ths and pops; back to light; last frame = first frame |

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

Checks:

```bash
npm run sync-report    # event frames vs detected onsets (pass: mean < 1 frame @60, max ≤ 20 ms)
npm run mix-check      # renders the mix, checks clipping and where each UI sound sits
npm run check-text     # no Cyrillic anywhere; prints every on-screen string
npm run check-static   # no stretch without motion longer than 0.5 s (on the preview render)
node scripts/render_stills.mjs --guides 1 --sheet review 0 250 370 566 641 766   # stills + safe zones
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
  coming back at bar 49 (an exact repeat of the first hook, similarity 0.90).
  At 149 BPM 11 bars are 17.7 s, so the last scene got one more bar (12 bars, 19.33 s).
- `src/scenes.ts` is the script: words, cues and hits in beats (8ths only, validated).
  `src/timeline.ts` turns it into times from `beats.json`; nothing is placed in seconds by hand.
  Bubbles, presses, the countdown and the punchline land on detected 808 hits.
- Cards "punch" (+2.5 %, ~10-frame exponential decay, shadow tightens) on kicks from `beats.json`.
- `npm run sync-report` (60 fps): mean |Δ| 3.7 ms, max 8.5 ms over 84 events.

## Decisions worth knowing

- **Motion blur**: `src/components/MotionBlur.tsx` instead of `<CameraMotionBlur>`. Same
  method (sub-frame renders averaged, 180° shutter, 10 samples) but layers are averaged as a
  running mean (opacity 1/k) rather than `plus-lighter` at 1/N, so static pixels stay exact
  (no banding in the soft gradient and shadows), and the shutter is centred on the frame
  (CameraMotionBlur samples ahead of it, shifting every hit ~0.7 frame early).
- **Fonts**: Inter Tight / Inter woff2 from `@fontsource` in `public/fonts` (the same files Google
  Fonts serves) via `@remotion/fonts`, so renders never depend on network access.
- **Squircles**: continuous corners from `src/lib/squircle.ts` (Figma-style corner smoothing 0.6),
  used for every card, the icon and the morphs (icon → thread, alert → pill → icon).
- **Audio**: one decode (ffmpeg) for analysis and playback so the grid is sample-exact.
  The master decodes to +1.9 dBFS, so the cut gets a static −3.4 dB (peak −1.5 dBFS) instead
  of a limiter. 14 synthesized UI sounds (no Apple sounds, no samples) sit 20–25 dB under it.
- **Loop**: frame 0 and the last frame differ by < 1 level once the 24 fps grain is averaged out.
- **Safe zones** (TikTok 150 / 140 / 420): text axis and cards sit 10 px left of centre so card
  UI clears the right rail; `--guides 1` draws the zones.

## Layout

```
src/
  config.ts       AUDIO_START / AUDIO_END, sync offset, layouts (9:16, 1:1), levels
  scenes.ts       the script (all on-screen text lives here)
  timeline.ts     script × beats.json → times, kicks, SFX, the dip
  data/beats.json analysis output
  components/     Card, Squircle, Headline (word reveal), MotionBlur, Backdrop (bg, grain,
                  theme wipe), Roulette (odometer digits), MessagesIcon/Badge, Floaters, Icons
  scenes/         IntroThread, LockScene, FocusScene, SilenceScene, BlockOutro
scripts/          analysis, audio prep, SFX synthesis, checks, stills
```

Spec component → code: `Card`, `Squircle` → components/; `WordReveal` → components/Headline.tsx;
`ChatThread` → scenes/IntroThread.tsx; `LockScreen` → scenes/LockScene.tsx; `FocusTile` →
scenes/FocusScene.tsx; `VolumeHUD` → scenes/SilenceScene.tsx; `Alert` → scenes/BlockOutro.tsx;
`BadgeCounter` → components/MessagesIcon.tsx (`Badge`) + components/Roulette.tsx; `Grain` →
components/Backdrop.tsx.
