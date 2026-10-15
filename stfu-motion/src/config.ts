/**
 * Project-wide knobs. Everything time-related is derived from src/data/beats.json
 * (written by scripts/analyze_beats.py); nothing here is a hand-placed second.
 */

/**
 * Fragment of the decoded track, in seconds. Both ends are downbeats:
 * bar 43 → bar 55 of the song (149 BPM, 12 bars = 19.33 s). The drop is the
 * hook coming back at bar 49 (= bar 6 of the fragment). Recommended by
 * scripts/analyze_beats.py → beats.json "fragment"; edit to try another cut
 * (the timeline refuses a start that is not on a downbeat).
 */
export const AUDIO_START = 69.3228;
export const AUDIO_END = 88.65166;

/** Global audio/visual offset in ms (positive = visuals later). Tuned by `npm run sync-report`. */
export const SYNC_OFFSET_MS = 0;

/**
 * Visual hits lead the audio by this many 60-fps frames: eyes are slower than
 * ears, so an entrance that starts 1 frame early reads as "on" the beat.
 */
export const LEAD = 1;

/** Kicks that drive the card "punch" (strength is relative to the loudest kick). */
export const KICK_MIN_STRENGTH = 0.5;
export const KICK_MAX_DEV_MS = 20;

/**
 * UI-sound levels: gains in src/timeline.ts are "dB under the track". The track's
 * RMS after `npm run audio` is TRACK_RMS_DBFS; every SFX file is normalised to
 * an active RMS of SFX_REF_DBFS (scripts/make_sfx.py). `npm run mix-check` verifies.
 */
export const TRACK_RMS_DBFS = -8.2;
export const SFX_REF_DBFS = -20;

/** 180° shutter; samples are overridable per render (input prop `samples`). */
export const MOTION_BLUR = {shutterAngle: 180, samples: 10};

export type Format = '9x16' | '1x1';

export type Layout = {
	width: number;
	height: number;
	/** Platform UI overlays to keep text and key UI out of (TikTok for 9:16). */
	safe: {top: number; right: number; bottom: number; left: number};
	/** Horizontal axis for text and cards (nudged left of centre to clear the right rail). */
	axisX: number;
	textTop: number;
	textMaxWidth: number;
	fontSize: number;
	cardCenterY: number;
	/** Uniform scale applied to every card (cards are designed at 9:16 size). */
	stageScale: number;
};

export const LAYOUTS: Record<Format, Layout> = {
	'9x16': {
		width: 1080,
		height: 1920,
		safe: {top: 150, right: 140, bottom: 420, left: 0},
		axisX: 530,
		textTop: 196,
		textMaxWidth: 780,
		fontSize: 74,
		cardCenterY: 1000,
		stageScale: 1,
	},
	'1x1': {
		width: 1080,
		height: 1080,
		safe: {top: 60, right: 60, bottom: 60, left: 60},
		axisX: 540,
		textTop: 78,
		textMaxWidth: 900,
		fontSize: 64,
		cardCenterY: 630,
		stageScale: 0.7,
	},
};
