import React from 'react';
import {AbsoluteFill} from 'remotion';
import {type Format, LEAD, MOTION_BLUR} from './config';
import {Background, Grain, GrainPreload, ThemeSplit} from './components/Backdrop';
import {Subtitles} from './components/Subtitles';
import {MotionBlur} from './components/MotionBlur';
import {Soundtrack} from './components/Soundtrack';
import {LayoutProvider, Stage, useLayout} from './components/Stage';
import {smooth, useT} from './lib/motion';
import {IntroThread} from './scenes/IntroThread';
import {LockScene} from './scenes/LockScene';
import {FocusScene} from './scenes/FocusScene';
import {CallScene} from './scenes/CallScene';
import {BlockOutro} from './scenes/BlockOutro';
import {LIGHT, useTheme} from './theme';
import {DROP_T} from './timeline';

export type MainProps = {
	format: Format;
	/** motion-blur samples (1 = off) */
	samples: number;
	/** render without sound (stills) */
	muted?: boolean;
	/** draw the platform safe zones (review only) */
	guides?: boolean;
};

/** TikTok UI overlays (spec §3): top 150, bottom 420, right 140 at 1080×1920. */
const SafeGuides: React.FC = () => {
	const L = useLayout();
	const zone = (style: React.CSSProperties) => (
		<div style={{position: 'absolute', background: 'rgba(255, 0, 80, 0.18)', outline: '2px dashed rgba(255,0,80,0.7)', ...style}} />
	);
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			{zone({left: 0, right: 0, top: 0, height: L.safe.top})}
			{zone({left: 0, right: 0, bottom: 0, height: L.safe.bottom})}
			{zone({right: 0, top: L.safe.top, bottom: L.safe.bottom, width: L.safe.right})}
			{L.safe.left ? zone({left: 0, top: L.safe.top, bottom: L.safe.bottom, width: L.safe.left}) : null}
		</AbsoluteFill>
	);
};

/** Micro camera shake on the drop: ~0.6 s, decaying. */
const dropShake = (t: number) => {
	const d = t - (DROP_T - LEAD);
	if (d < 0 || d > 42) return {x: 0, y: 0, r: 0};
	const env = Math.exp(-d / 7) * smooth(d / 1.5);
	return {x: 9 * env * Math.sin(d * 1.9), y: 7 * env * Math.cos(d * 2.6 + 0.5), r: 0.35 * env * Math.sin(d * 1.3 + 1)};
};

const World: React.FC = () => {
	const t = useT();
	const s = dropShake(t);
	return (
		<AbsoluteFill>
			<Background />
			<Stage transform={`translate(${s.x.toFixed(2)}px, ${s.y.toFixed(2)}px) rotate(${s.r.toFixed(3)}deg)`}>
				<IntroThread />
				<LockScene />
				<FocusScene />
				<CallScene />
				<BlockOutro />
			</Stage>
		</AbsoluteFill>
	);
};

const GrainLayer: React.FC = () => {
	const theme = useTheme();
	return <Grain opacity={theme.grainOpacity} />;
};

export const Main: React.FC<MainProps> = ({format, samples, muted, guides}) => (
	<LayoutProvider format={format}>
		<AbsoluteFill style={{background: LIGHT.bg.mid}}>
			<MotionBlur samples={samples} shutterAngle={MOTION_BLUR.shutterAngle}>
				<ThemeSplit>{() => <World />}</ThemeSplit>
			</MotionBlur>
			{/* text is not in the camera and not blurred by it: it never drifts */}
			<ThemeSplit>{() => <Subtitles />}</ThemeSplit>
			<ThemeSplit>{() => <GrainLayer />}</ThemeSplit>
			<GrainPreload />
			{guides ? <SafeGuides /> : null}
			{muted ? null : <Soundtrack />}
		</AbsoluteFill>
	</LayoutProvider>
);
