/**
 * The timeline: SCRIPT (scenes.ts) × beat grid (beats.json) → times.
 *
 * Unit: `t` = time in 60-fps frames from the start of the fragment (float).
 * Components read the current time with useT() in the same unit, so a 30-fps
 * render runs the exact same animation, just sampled half as often.
 */
import beatsJson from './data/beats.json';
import {AUDIO_END, AUDIO_START, KICK_MAX_DEV_MS, KICK_MIN_STRENGTH, SYNC_OFFSET_MS} from './config';
import {SCENES, type SceneId, type SceneSpec} from './scenes';

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

// --- validation: fragment on the grid, script on 8ths, length in range ---------
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
for (const sc of SCENES) {
	const n = sc.text.split(/\s+/).length;
	if (n !== sc.words.length) fail(`scene ${sc.id}: ${n} words but ${sc.words.length} word beats`);
	for (const [name, b] of [...sc.words.map((w, i) => [`word${i}`, w] as const), ['hit', sc.hit.beat] as const, ...Object.entries(sc.cues)]) {
		if (!on8th(b)) fail(`scene ${sc.id}: ${name} at beat ${b} is not on an 8th`);
		if (b < 0 || b > sc.bars * 4) fail(`scene ${sc.id}: ${name} at beat ${b} is outside the scene`);
	}
}

// --- scenes ---------------------------------------------------------------------
export type WordT = {text: string; beat: number; t: number};
export type SceneT = SceneSpec & {
	index: number;
	startBeat: number;
	endBeat: number;
	/** t of the first and of the next downbeat */
	start: number;
	end: number;
	wordsT: WordT[];
	hitT: number;
	/** t of a scene cue */
	cue: (name: string) => number;
};

let acc = 0;
export const TL_SCENES: SceneT[] = SCENES.map((sc, index) => {
	const startBeat = acc;
	acc += sc.bars * 4;
	const words = sc.text.split(/\s+/);
	return {
		...sc,
		index,
		startBeat,
		endBeat: acc,
		start: tAt(startBeat),
		end: tAt(acc),
		wordsT: words.map((text, i) => ({text, beat: startBeat + sc.words[i], t: tAt(startBeat + sc.words[i])})),
		hitT: tAt(startBeat + sc.hit.beat),
		cue: (name: string) => {
			const b = sc.cues[name];
			if (b === undefined) fail(`scene ${sc.id} has no cue "${name}"`);
			return tAt(startBeat + b);
		},
	};
});

export const scene = (id: SceneId): SceneT => TL_SCENES.find((s) => s.id === id) ?? fail(`no scene ${id}`);
export const DROP_T = scene('silence').start;
export const END_T = tAt(totalBars * 4);

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
	toggle: {pre: 0},
	impact: {pre: 0},
	press: {pre: 0},
	collapse: {pre: 60},
	burst: {pre: 0},
} as const;

const intro = scene('intro');
const thread = scene('thread');
const lock = scene('lock');
const focus = scene('focus');
const silence = scene('silence');
const block = scene('block');
const outro = scene('outro');

const sfx = (id: string, file: keyof typeof SFX_FILES, t: number, gainDb: number): Sfx => ({id, file, t, gainDb});
/** 14 quiet UI sounds on the events; gains are dB under the track (spec §7: -20…-26). */
export const SFX: Sfx[] = [
	sfx('icon-jump', 'pop', intro.hitT, -23),
	sfx('badge-count', 'roll', intro.cue('badge'), -25),
	sfx('icon-morph', 'swoosh', intro.cue('morph'), -24),
	sfx('bubble-0', 'bubble', thread.cue('bubble0'), -23),
	sfx('bubble-1', 'bubble', thread.cue('bubble1'), -23),
	sfx('bubble-2', 'bubble', thread.cue('bubble2'), -23),
	sfx('bubble-3', 'bubble', thread.cue('bubble3'), -22),
	sfx('missed-call-1', 'buzz', lock.cue('notif1'), -24),
	sfx('missed-call-3', 'buzz', lock.cue('notif3'), -23),
	sfx('dnd-toggle', 'toggle', focus.cue('toggle'), -22),
	sfx('drop', 'impact', silence.hitT, -22),
	sfx('block-press', 'press', block.cue('press'), -23),
	sfx('alert-collapse', 'collapse', block.cue('press') + 6, -24),
	sfx('badge-pop', 'burst', outro.hitT, -21),
];

/**
 * Lowpass "dip" of the track before the drop (spec §7): from a 16th after the
 * DND toggle to the drop (≈ 300 ms), in seconds from the fragment start.
 */
export const DIP = {start: (focus.cue('toggle') - OFFSET) / 60 + BEAT_SEC / 4, end: (silence.start - OFFSET) / 60, cutoffHz: 380};

export const TIMELINE_SUMMARY = {
	bpm: BPM,
	beatSec: BEAT_SEC,
	bars: totalBars,
	durationSec: DURATION_SEC,
	audioStart: AUDIO_START,
	audioEnd: AUDIO_END,
	dropSec: DROP_T / 60,
};
