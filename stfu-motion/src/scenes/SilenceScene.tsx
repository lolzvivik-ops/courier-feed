import React from 'react';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {Slash, SpeakerBody, SpeakerWaves} from '../components/Icons';
import {Roulette} from '../components/Roulette';
import {MOVE, SINE, clamp, prog, useT} from '../lib/motion';
import {COPY} from '../scenes';
import {FONT, useTheme} from '../theme';
import {scene} from '../timeline';

const W = 800;
const H = 430;
const PILL_X = 40;
const PILL_Y = 168;
const PILL_W = W - 80;
const PILL_H = 136;
const ICON = 84;

/**
 * Volume level over time: holds, then on the 808 hit it falls like a weight
 * (accelerating), lands at 0 and rebounds a hair before settling (inertia).
 */
const levelAt = (t: number, tFall: number, from: number) => {
	if (t <= tFall) return from;
	const fallDur = 13;
	const p = prog(t, tFall, fallDur);
	if (p < 1) return from * (1 - p * p * (1.6 - 0.6 * p));
	const q = t - (tFall + fallDur);
	// one small rebound (~1/3 s), then exactly 0 — no sub-pixel sliver left behind
	return q < 10 ? 0.022 * Math.sin((q / 10) * Math.PI) : 0;
};

/** Speaker icon in one colour; drawn twice (dark over the fill, light outside it). */
const Speaker: React.FC<{color: string; level: number; slash: number; gap: string}> = ({color, level, slash, gap}) => (
	<div style={{position: 'relative', width: ICON, height: ICON}}>
		<div style={{position: 'absolute', inset: 0}}>
			<SpeakerBody size={ICON} color={color} />
		</div>
		<div style={{position: 'absolute', inset: 0}}>
			<SpeakerWaves size={ICON} color={color} level={level} />
		</div>
		<div style={{position: 'absolute', inset: 0}}>
			<Slash size={ICON} color={color} draw={slash} gap={gap} />
		</div>
	</div>
);

export const SilenceScene: React.FC = () => {
	const t = useT();
	const theme = useTheme();
	const silence = scene('silence');
	// enters with the dark wipe (which starts a frame early), never ahead of it in the light theme
	const enterAt = silence.start;
	const exitAt = scene('block').start - 8;
	if (t < enterAt - 2 || t > exitAt + 14) return null;

	const from = COPY.volume.level / 100;
	const tFall = silence.cue('fall') - LEAD;
	const level = levelAt(t, tFall, from);
	const waves = clamp(level / from);
	const slash = MOVE(prog(t, tFall + 10, 8));
	const fillW = PILL_W * level;
	const cam = 1 + 0.04 * SINE(prog(t, silence.start, silence.end - silence.start));
	const iconLeft = PILL_X + 34;
	const iconTop = PILL_Y + (PILL_H - ICON) / 2;
	const trackColor = theme.name === 'dark' ? '#3A3A3C' : '#E5E5EA';

	const floaters: FloaterSpec[] = [
		{x: -470, y: -250, size: 70, depth: 0.5, kind: 'ring', color: '#2C2C30'},
		{x: 482, y: -190, size: 40, depth: 0.8, kind: 'dot', color: '#26262A'},
		{x: 455, y: 250, size: 120, depth: 0.35, kind: 'pill', color: '#232327'},
		{x: -440, y: 290, size: 46, depth: 0.7, kind: 'ring', color: '#2A2A2E'},
	];

	return (
		<div style={{position: 'absolute', transform: `scale(${cam.toFixed(5)})`}}>
			<Floaters specs={floaters} enterAt={enterAt + 6} exitAt={exitAt} seed={41} />
			<Card w={W} h={H} r={64} seed={19} enterAt={enterAt} exitAt={exitAt}>
				<div style={{position: 'absolute', left: 48, top: 52, fontFamily: FONT.ui, fontWeight: 600, fontSize: 34, color: theme.secondary}}>{COPY.volume.label}</div>
				<div
					style={{
						position: 'absolute',
						right: 48,
						top: 40,
						height: 64,
						display: 'flex',
						alignItems: 'center',
						fontFamily: FONT.display,
						fontWeight: 600,
						fontSize: 52,
						color: theme.label,
					}}
				>
					<Roulette value={level * 100} digitHeight={64} digitWidth={31} />
					<span style={{marginLeft: 2}}>%</span>
				</div>

				{/* the slider: track, white fill, and a two-tone speaker that follows the fill edge */}
				<div style={{position: 'absolute', left: PILL_X, top: PILL_Y, width: PILL_W, height: PILL_H, borderRadius: PILL_H / 2, background: trackColor, overflow: 'hidden'}}>
					<div style={{position: 'absolute', left: 0, top: 0, width: fillW, height: PILL_H, background: '#FFFFFF'}} />
				</div>
				<div style={{position: 'absolute', left: iconLeft, top: iconTop, clipPath: `inset(0 0 0 ${Math.max(0, fillW + PILL_X - iconLeft).toFixed(2)}px)`}}>
					<Speaker color="#FFFFFF" level={waves} slash={slash} gap={trackColor} />
				</div>
				<div style={{position: 'absolute', left: iconLeft, top: iconTop, clipPath: `inset(0 ${Math.max(0, ICON - (fillW + PILL_X - iconLeft)).toFixed(2)}px 0 0)`}}>
					<Speaker color="#1C1C1E" level={waves} slash={slash} gap="#FFFFFF" />
				</div>
			</Card>
		</div>
	);
};
