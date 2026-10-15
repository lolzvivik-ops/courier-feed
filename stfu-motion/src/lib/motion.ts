/**
 * Motion primitives. Everything is a pure function of continuous time so the
 * motion-blur sampler can evaluate sub-frame positions.
 */
import {Easing, useCurrentFrame, useVideoConfig} from 'remotion';

/** Current time in 60-fps frames (fractional inside the motion-blur sampler). */
export const useT = (): number => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	return frame * (60 / fps);
};

export const clamp = (x: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
/** 0→1 over [start, start + dur] (in t units), clamped. */
export const prog = (t: number, start: number, dur: number) => (dur <= 0 ? (t >= start ? 1 : 0) : clamp((t - start) / dur));
export const smooth = (x: number) => {
	const k = clamp(x);
	return k * k * (3 - 2 * k);
};

// Curves (spec §5). Different elements of one scene use different curves.
/** Entrances. */
export const EXPO_OUT = Easing.bezier(0.16, 1, 0.3, 1);
/** Moves from A to B. */
export const MOVE = Easing.bezier(0.65, 0, 0.35, 1);
/** Exits accelerate away (ease-in cubic). */
export const EXIT = Easing.bezier(0.32, 0, 0.67, 0);
/** Secondary entrances (softer than expo). */
export const QUART_OUT = Easing.bezier(0.25, 1, 0.5, 1);
/** Fast-in, long settle; for things that fall. */
export const CIRC_OUT = Easing.bezier(0, 0.55, 0.45, 1);
/** Gentle in-out for camera moves. */
export const SINE = Easing.bezier(0.37, 0, 0.63, 1);

/** Interpolate between keyframes [t, value] with one easing for every segment. */
export const keys = (t: number, frames: Array<[number, number]>, ease: (x: number) => number = MOVE): number => {
	if (t <= frames[0][0]) return frames[0][1];
	for (let i = 1; i < frames.length; i++) {
		const [t1, v1] = frames[i];
		if (t <= t1) {
			const [t0, v0] = frames[i - 1];
			return lerp(v0, v1, ease(prog(t, t0, t1 - t0)));
		}
	}
	return frames[frames.length - 1][1];
};

export type SpringCfg = {mass: number; stiffness: number; damping: number};
/** Pops: damping 14–18, stiffness 140–200, mass 0.8 → ≤ 6 % overshoot (spec §5). */
export const POP: SpringCfg = {mass: 0.8, stiffness: 180, damping: 16};
/** A slightly looser spring for squash & stretch. */
export const BOUNCY: SpringCfg = {mass: 0.8, stiffness: 200, damping: 14};
/** Heavy UI parts (cards settling, stacks). */
export const SETTLE: SpringCfg = {mass: 1, stiffness: 150, damping: 18};

/**
 * Damped spring from 0 to 1, released at t = 0 (t in 60-fps frames).
 * Closed form, so it is exact at fractional frames (Remotion's spring() steps per frame).
 */
export const spring = (t: number, cfg: SpringCfg = POP, v0 = 0): number => {
	if (t <= 0) return 0;
	const s = t / 60;
	const {mass: m, stiffness: k, damping: c} = cfg;
	const w0 = Math.sqrt(k / m);
	const zeta = c / (2 * Math.sqrt(k * m));
	if (zeta < 1) {
		const wd = w0 * Math.sqrt(1 - zeta * zeta);
		const e = Math.exp(-zeta * w0 * s);
		return 1 + e * (-Math.cos(wd * s) + ((v0 - zeta * w0) / wd) * Math.sin(wd * s));
	}
	// critically damped (good enough for zeta >= 1 here)
	const e = Math.exp(-w0 * s);
	return 1 - e * (1 + (w0 - v0) * s);
};

/** Velocity-like signal of a spring (derivative, normalised by w0); used for squash & stretch. */
export const springVel = (t: number, cfg: SpringCfg = POP): number => {
	const dt = 0.25;
	const w0 = Math.sqrt(cfg.stiffness / cfg.mass);
	return ((spring(t + dt, cfg) - spring(t - dt, cfg)) / (2 * dt)) * (60 / w0);
};

/** Deterministic hash noise in [0, 1). */
export const hash = (n: number) => {
	const x = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
	return x - Math.floor(x);
};

/** Smooth 1-D value noise in [-1, 1]. */
export const noise1 = (x: number, seed = 0) => {
	const i = Math.floor(x);
	const f = x - i;
	const a = hash(i + seed * 101.3) * 2 - 1;
	const b = hash(i + 1 + seed * 101.3) * 2 - 1;
	return lerp(a, b, f * f * (3 - 2 * f));
};

/** Idle "breathing" of a card: rotation in degrees, float in px. Each seed has its own phase. */
export const idle = (t: number, seed: number, amp = 1) => {
	const s = t / 60;
	const p = seed * 2.39996;
	const TAU = Math.PI * 2;
	return {
		rx: amp * (2.4 * Math.sin((TAU * s) / 4.1 + p) + 0.7 * Math.sin((TAU * s) / 1.9 + p * 1.7)),
		ry: amp * (3.2 * Math.sin((TAU * s) / 5.3 + p * 1.3) + 0.8 * Math.sin((TAU * s) / 2.3 + p * 0.6)),
		y: amp * (8 * Math.sin((TAU * s) / 3.7 + p * 0.8)),
		x: amp * (3 * Math.sin((TAU * s) / 6.1 + p * 2.1)),
	};
};
