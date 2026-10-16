/**
 * The timeline: SCRIPT (scenes.ts) × beat grid (beats.json) × sung words
 * (lyrics.ts) → times.
 *
 * Unit: `t` = time in 60-fps frames from the start of the fragment (float).
 * Components read the current time with useT() in the same unit, so a 30-fps
 * render runs the exact same animation, just sampled half as often.
 */
import beatsJson from './data/beats.json';
import {AUDIO_END, AUDIO_START, KICK_MAX_DEV_MS, KICK_MIN_STRENGTH, SYNC_OFFSET_MS} from './config';
import {LYRICS, lyricWord} from './lyrics';
import {type Cue, SCENES, type SceneId, type SceneSpec} from './scenes';

const B = beatsJson;
export const BEAT_SEC = B.tempo.beatPeriod;
export const BPM = B.tempo.bpm;
/** One beat in 60-fps frames (24.16 at 149 BPM). */
export const BEAT = BEAT_SEC * 60;
export const BAR = BEAT * 4;
const OFFSET = (SYNC_OFFSET_MS / 1000) * 60;

/** Fragment-relative beat → t (60-fps frames). */
export const tAt = (beat: number) => beat * BEAT + OFFSET;

const fail = (msg: string): never => {
	throw new Error(`[timeline] ${msg}`);
};

// --- validation: fragment on the grid, beat cues on 8ths, length in range ---------
const nearestDownbeat = B.downbeats.reduce((a, b) => (Math.abs(b - AUDIO_START) < Math.abs(a - AUDIO_START) ? b : a));
if (Math.abs(nearestDownbeat - AUDIO_START) > 0.005) {
	fail(`AUDIO_START ${AUDIO_START}s is not on a downbeat (nearest: ${nearestDownbeat}s)`);
}
const totalBars = SCENES.reduce((s, sc) => s + sc.bars, 0);
export const DURATION_SEC = totalBars * 4 * BEAT_SEC;
if (Math.abs(AUDIO_START + DURATION_SEC - AUDIO_END) > 0.01) {
	fail(`script is ${totalBars} bars (${DURATION_SEC.toFixed(3)}s) but AUDIO_END - AUDIO_START = ${(AUDIO_END - AUDIO_START).toFixed(3)}s`);
}
if (DURATION_SEC < 18 || DURATION_SEC > 22) fail(`duration ${DURATION_SEC.toFixed(2)}s outside 18–22 s`);
const on8th = (x: number) => Math.abs(x * 2 - Math.round(x * 2)) < 1e-6;

// --- scenes ---------------------------------------------------------------------
export type SceneT = SceneSpec & {
	index: number;
	startBeat: number;
	endBeat: number;
	/** t of the first and of the next downbeat */
	start: number;
	end: number;
	hitT: number;
	/** t of a scene cue (a beat, or the onset of a sung word) */
	cue: (name: string) => number;
};

let acc = 0;
export const TL_SCENES: SceneT[] = SCENES.map((sc, index) => {
	const startBeat = acc;
	acc += sc.bars * 4;
	const at = (c: Cue, name: string): number => {
		if (typeof c === 'number') {
			if (!on8th(c)) fail(`scene ${sc.id}: ${name} at beat ${c} is not on an 8th`);
			if (c < 0 || c > sc.bars * 4) fail(`scene ${sc.id}: ${name} at beat ${c} is outside the scene`);
			return tAt(startBeat + c);
		}
		return lyricWord(c).t;
	};
	const resolved: Record<string, number> = {};
	for (const [name, c] of Object.entries(sc.cues)) resolved[name] = at(c, name);
	return {
		...sc,
		index,
		startBeat,
		endBeat: acc,
		start: tAt(startBeat),
		end: tAt(acc),
		hitT: at(sc.hit.at, 'hit'),
		cue: (name: string) => resolved[name] ?? fail(`scene ${sc.id} has no cue "${name}"`),
	};
});

export const scene = (id: SceneId): SceneT => TL_SCENES.find((s) => s.id === id) ?? fail(`no scene ${id}`);
export const DROP_T = scene('call').start;
export const END_T = tAt(totalBars * 4);

/** Word cues must fall inside (or just before) their own card's time on screen. */
for (const sc of TL_SCENES) {
	for (const [name, c] of Object.entries(sc.cues)) {
		if (typeof c === 'number') continue;
		const t = sc.cue(name);
		if (t < sc.start - BEAT || t > sc.end + BEAT / 2) fail(`scene ${sc.id}: cue ${name} (word "${lyricWord(c).text}") is outside the scene`);
	}
}

// --- kicks → card punches ---------------------------------------------------------
/** Kick positions on the 16th grid (t), from the detected 808/kick onsets. */
export const KICKS: number[] = (() => {
	const out: number[] = [];
	for (const k of B.kicks) {
		if (k.t < AUDIO_START - 0.02 || k.t >= AUDIO_END) continue;
		if (k.s < KICK_MIN_STRENGTH || Math.abs(k.dev) > KICK_MAX_DEV_MS) continue;
		const beat16 = Math.round(((k.t - AUDIO_START) / BEAT_SEC) * 4) / 4;
		const t = tAt(beat16);
		if (out.length && t - out[out.length - 1] < 10) continue; // one punch per decay window
		out.push(t);
	}
	return out;
})();

// --- sound design -------------------------------------------------------------------
export type Sfx = {id: string; file: string; t: number; gainDb: number};
/** Each file has its transient `pre` ms after its start; events are placed so the transient hits `t`. */
export const SFX_FILES = {
	pop: {pre: 0},
	roll: {pre: 0},
	swoosh: {pre: 140},
	bubble: {pre: 0},
	buzz: {pre: 0},
	ring: {pre: 0},
	toggle: {pre: 0},
	impact: {pre: 0},
	press: {pre: 0},
	collapse: {pre: 60},
	burst: {pre: 0},
} as const;

const intro = scene('intro');
const thread = scene('thread');
const lock = scene('lock');
const call = scene('call');
const focus = scene('focus');
const block = scene('block');
const outro = scene('outro');

const sfx = (id: string, file: keyof typeof SFX_FILES, t: number, gainDb: number): Sfx => ({id, file, t, gainDb});
/** 14 quiet UI sounds on the events; gains are dB under the track (spec §7: -20…-26). */
export const SFX: Sfx[] = [
	sfx('icon-jump', 'pop', intro.hitT, -23),
	sfx('badge-count', 'roll', intro.cue('badge'), -25),
	sfx('icon-morph', 'swoosh', intro.cue('morph'), -24),
	sfx('text-soon', 'bubble', thread.cue('bubble0'), -23),
	sfx('text-as', 'bubble', thread.cue('bubble1'), -23),
	sfx('text-die', 'bubble', thread.cue('bubble3'), -23),
	sfx('missed-we', 'buzz', lock.cue('notif1'), -24),
	sfx('missed-night', 'buzz', lock.cue('notif4'), -23),
	sfx('island-ring', 'ring', lock.cue('island'), -24),
	sfx('drop', 'impact', call.hitT, -23),
	sfx('decline', 'press', call.cue('decline'), -22),
	sfx('dnd-toggle', 'toggle', focus.cue('toggle'), -22),
	sfx('block-press', 'press', block.cue('press'), -23),
	sfx('badge-pop', 'burst', outro.hitT, -21),
];

/**
 * Lowpass "dip" of the track before the drop (spec §7): a 16th after the call
 * alert pops out of the Dynamic Island, up to the drop (≈ 300 ms, no vocal there).
 */
export const DIP = {start: (lock.cue('island') - OFFSET) / 60 + BEAT_SEC / 4, end: (call.start - OFFSET) / 60, cutoffHz: 380};

/** Where the subtitles change (first word of each line), for the scene/line overlap checks. */
export const LYRIC_LINE_STARTS = LYRICS.map((l) => l.words[0].t);

export const TIMELINE_SUMMARY = {
	bpm: BPM,
	beatSec: BEAT_SEC,
	bars: totalBars,
	durationSec: DURATION_SEC,
	audioStart: AUDIO_START,
	audioEnd: AUDIO_END,
	dropSec: DROP_T / 60,
};
