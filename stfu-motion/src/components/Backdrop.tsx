import React from 'react';
import {AbsoluteFill, Img, staticFile, useVideoConfig} from 'remotion';
import {EXPO_OUT, MOVE, hash, prog, useT} from '../lib/motion';
import {DARK, LIGHT, type Theme, ThemeContext, useTheme} from '../theme';
import {DROP_T, scene} from '../timeline';
import {LEAD} from '../config';
import {useLayout} from './Stage';

/** Radial background (spec §3): lighter in the middle, a touch darker at the edges. */
export const Background: React.FC = () => {
	const theme = useTheme();
	return (
		<AbsoluteFill
			style={{
				background: `radial-gradient(ellipse 80% 62% at 50% 50%, ${theme.bg.inner} 0%, ${theme.bg.mid} 52%, ${theme.bg.outer} 100%)`,
			}}
		/>
	);
};

/** Film grain, 2–3 %, re-rolled 24 times a second (stepped, not smooth). */
export const Grain: React.FC<{opacity: number}> = ({opacity}) => {
	const t = useT();
	const {width, height} = useVideoConfig();
	const step = Math.floor((t / 60) * 24);
	const ox = Math.floor(hash(step * 3.1) * 512);
	const oy = Math.floor(hash(step * 7.7 + 1) * 512);
	return (
		<AbsoluteFill style={{overflow: 'hidden', opacity, mixBlendMode: 'overlay', pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					left: -ox,
					top: -oy,
					width: width + 1024,
					height: height + 1024,
					backgroundImage: `url(${staticFile('grain.png')})`,
					backgroundSize: '512px 512px',
					imageRendering: 'pixelated',
				}}
			/>
		</AbsoluteFill>
	);
};

/** Preload so the first frame never renders without grain. */
export const GrainPreload: React.FC = () => <Img src={staticFile('grain.png')} style={{display: 'none'}} />;

/**
 * Theme state over time: light until the drop, a circular wipe to dark from
 * the card centre in 8 frames, then back to light in the last ~0.4 s (loop).
 */
export const themeWipe = (t: number) => {
	const toDark = EXPO_OUT(prog(t, DROP_T - LEAD, 8));
	const back = MOVE(prog(t, scene('outro').cue('lightWipe'), 16));
	return {toDark, back};
};

/** Renders `children(theme)` once, or twice with a circular clip while a wipe runs. */
export const ThemeSplit: React.FC<{children: (theme: Theme) => React.ReactNode}> = ({children}) => {
	const t = useT();
	const L = useLayout();
	const {width, height} = useVideoConfig();
	const cx = L.axisX;
	const cy = L.cardCenterY;
	const rMax = Math.hypot(Math.max(cx, width - cx), Math.max(cy, height - cy)) + 8;
	const {toDark, back} = themeWipe(t);

	// Feathered edge: a hard clip, sampled 10× by the motion blur, would show as
	// concentric steps; a soft 90 px edge blends them into one smooth wavefront.
	const FEATHER = 90;
	const layer = (theme: Theme, k?: number) => {
		let style: React.CSSProperties | undefined;
		if (k !== undefined) {
			const r = k * (rMax + FEATHER);
			const mask = `radial-gradient(circle at ${cx}px ${cy}px, #000 ${Math.max(0, r - FEATHER).toFixed(1)}px, transparent ${r.toFixed(1)}px)`;
			style = {maskImage: mask, WebkitMaskImage: mask};
		}
		return (
			<ThemeContext.Provider value={theme}>
				<AbsoluteFill style={style}>{children(theme)}</AbsoluteFill>
			</ThemeContext.Provider>
		);
	};

	if (back > 0) {
		if (back >= 1) return layer(LIGHT);
		return (
			<>
				{layer(DARK)}
				{layer(LIGHT, back)}
			</>
		);
	}
	if (toDark <= 0) return layer(LIGHT);
	if (toDark >= 1) return layer(DARK);
	return (
		<>
			{layer(LIGHT)}
			{layer(DARK, toDark)}
		</>
	);
};
