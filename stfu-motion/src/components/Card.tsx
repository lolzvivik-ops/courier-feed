import React from 'react';
import {EXIT, EXPO_OUT, QUART_OUT, idle, lerp, prog, useT} from '../lib/motion';
import {punchAt} from '../lib/punch';
import {useTheme} from '../theme';
import {Squircle} from './Squircle';

export type CardProps = {
	w: number;
	h: number;
	r?: number;
	smoothing?: number;
	/** offset of the card centre from the stage origin */
	x?: number;
	y?: number;
	/** phase of the idle motion; every card gets its own */
	seed: number;
	/** t at which the defocus entrance starts (omit = already in) */
	enterAt?: number;
	enterDur?: number;
	/** t at which the defocus exit starts (omit = stays) */
	exitAt?: number;
	exitDur?: number;
	fill?: string;
	idleAmp?: number;
	punchAmt?: number;
	/** extra uniform scale (camera push-in, morphs) */
	scale?: number;
	/** squash & stretch, anchored at the bottom edge */
	sx?: number;
	sy?: number;
	/** in-plane rotation, degrees */
	rz?: number;
	/** extra 3D tilt on top of the idle motion, degrees (e.g. a press leaning in) */
	rx?: number;
	ry?: number;
	/** shadow strength multiplier */
	shadow?: number;
	children?: React.ReactNode;
	/** drawn with the card's transform but outside its clip (badges, pills) */
	overlay?: React.ReactNode;
};

/**
 * The shared card: squircle body, two-layer shadow lit from the top-left,
 * 1 px top rim, idle 3D breathing, kick punch, and the defocus entrance/exit
 * (in: blur 20→0, scale .86→1, fade; out: scale →1.08, blur →16, fade).
 */
export const Card: React.FC<CardProps> = ({
	w,
	h,
	r = 64,
	smoothing = 0.6,
	x = 0,
	y = 0,
	seed,
	enterAt,
	enterDur = 24,
	exitAt,
	exitDur = 12,
	fill,
	idleAmp = 1,
	punchAmt = 1,
	scale = 1,
	sx = 1,
	sy = 1,
	rz = 0,
	rx = 0,
	ry = 0,
	shadow = 1,
	children,
	overlay,
}) => {
	const t = useT();
	const theme = useTheme();
	if (enterAt !== undefined && t < enterAt) return null;
	if (exitAt !== undefined && t > exitAt + exitDur) return null;

	const e = enterAt === undefined ? 1 : EXPO_OUT(prog(t, enterAt, enterDur));
	const fade = enterAt === undefined ? 1 : QUART_OUT(prog(t, enterAt, enterDur * 0.45));
	const out = exitAt === undefined ? 0 : EXIT(prog(t, exitAt, exitDur));
	const pu = punchAt(t) * punchAmt;
	const s = lerp(0.86, 1, e) * lerp(1, 1.08, out) * (1 + 0.025 * pu) * scale;
	const blur = (1 - e) * 20 + out * 16;
	const opacity = fade * (1 - out);
	const m0 = idle(t, seed, idleAmp);
	const m = {...m0, rx: m0.rx + rx, ry: m0.ry + ry};

	return (
		<div
			style={{
				position: 'absolute',
				left: x,
				top: y,
				width: 0,
				height: 0,
				perspective: 1800,
				opacity,
				filter: blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : undefined,
			}}
		>
			<div
				style={{
					position: 'absolute',
					left: -w / 2,
					top: -h / 2,
					width: w,
					height: h,
					transform: `translate3d(${m.x.toFixed(2)}px, ${(m.y + ((1 - sy) * h * s) / 2).toFixed(2)}px, 0) rotateX(${m.rx.toFixed(3)}deg) rotateY(${m.ry.toFixed(3)}deg) rotateZ(${rz.toFixed(3)}deg) scale(${(s * sx).toFixed(5)}, ${(s * sy).toFixed(5)})`,
				}}
			>
				<CardShadow w={w} h={h} r={r} punch={pu} tiltX={m.rx} tiltY={m.ry} alpha={shadow} />
				<Squircle w={w} h={h} r={r} smoothing={smoothing} fill={`${theme.sheen}, ${fill ?? theme.card}`}>
					{children}
					<Rim />
				</Squircle>
				{overlay}
			</div>
		</div>
	);
};

/** Two-layer soft shadow (spec §3), lit from the top-left; tightens ("lands") on punches. */
export const CardShadow: React.FC<{w: number; h: number; r: number; punch?: number; tiltX?: number; tiltY?: number; alpha?: number}> = ({
	w,
	h,
	r,
	punch = 0,
	tiltX = 0,
	tiltY = 0,
	alpha = 1,
}) => {
	const theme = useTheme();
	const land = 1 - 0.3 * punch;
	const a = theme.shadowAlpha * alpha * (1 + 0.25 * punch);
	const sx = 4 + tiltY * 1.5;
	const sy = 30 * land - tiltX * 1.5;
	const inset = Math.min(4, Math.min(w, h) * 0.04);
	return (
		<div
			style={{
				position: 'absolute',
				left: inset,
				top: inset,
				width: w - inset * 2,
				height: h - inset * 2,
				borderRadius: Math.max(0, r - inset),
				boxShadow: `${sx.toFixed(1)}px ${sy.toFixed(1)}px ${(60 * land).toFixed(1)}px rgba(0,0,0,${Math.min(0.6, 0.08 * a).toFixed(3)}), ${(sx * 0.25).toFixed(1)}px ${(8 * land).toFixed(1)}px ${(16 * land).toFixed(1)}px rgba(0,0,0,${Math.min(0.5, 0.05 * a).toFixed(3)})`,
			}}
		/>
	);
};

/** 1 px highlight on the top edge (only visible on dark / coloured surfaces). */
export const Rim: React.FC<{color?: string}> = ({color}) => {
	const theme = useTheme();
	return (
		<div
			style={{
				position: 'absolute',
				left: 0,
				right: 0,
				top: 0,
				height: 3,
				background: `linear-gradient(to bottom, ${color ?? theme.rim} 0px, ${color ?? theme.rim} 1px, rgba(255,255,255,0) 2.5px)`,
				pointerEvents: 'none',
			}}
		/>
	);
};
