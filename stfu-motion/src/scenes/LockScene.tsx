import React from 'react';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {Camera, Flashlight, PhoneArrow} from '../components/Icons';
import {Roulette} from '../components/Roulette';
import {Squircle} from '../components/Squircle';
import {MOVE, POP, SETTLE, SINE, clamp, lerp, noise1, prog, smooth, spring, useT} from '../lib/motion';
import {COPY} from '../scenes';
import {FONT, IOS} from '../theme';
import {scene} from '../timeline';

const W = 800;
const H = 960;
const NOTE_W = 736;
const NOTE_H = 160;
const NOTE_Y = 540;

const Padlock: React.FC<{size: number}> = ({size}) => (
	<svg width={size} height={size} viewBox="0 0 24 24" style={{display: 'block'}}>
		<path d="M7.5 10.5V7.8a4.5 4.5 0 0 1 9 0v2.7" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="2.2" />
		<rect x="5" y="10.2" width="14" height="11" rx="3" fill="rgba(255,255,255,0.9)" />
	</svg>
);

/** One missed-call notification, light material over the wallpaper. */
const Note: React.FC<{count: number; scale?: number; y?: number; opacity?: number; ghost?: boolean}> = ({count, scale = 1, y = 0, opacity = 1, ghost}) => (
	<div
		style={{
			position: 'absolute',
			left: (W - NOTE_W) / 2,
			top: NOTE_Y,
			width: NOTE_W,
			height: NOTE_H,
			transform: `translateY(${y.toFixed(2)}px) scale(${scale.toFixed(4)})`,
			transformOrigin: '50% 0%',
			opacity,
		}}
	>
		<Squircle w={NOTE_W} h={NOTE_H} r={46} fill={ghost ? 'rgba(236, 232, 248, 0.55)' : 'rgba(246, 244, 252, 0.86)'}>
			{ghost ? null : (
				<>
					<div style={{position: 'absolute', left: 24, top: 38, width: 84, height: 84}}>
						<Squircle w={84} h={84} r={20} fill={IOS.phone}>
							<div style={{position: 'absolute', left: 16, top: 16}}>
								<PhoneArrow size={52} color="#FFFFFF" />
							</div>
						</Squircle>
					</div>
					<div style={{position: 'absolute', left: 130, top: 30, fontFamily: FONT.ui, fontWeight: 600, fontSize: 36, color: '#000', letterSpacing: '-0.01em'}}>
						{COPY.lock.title}
					</div>
					<div style={{position: 'absolute', left: 130, top: 80, fontFamily: FONT.ui, fontWeight: 400, fontSize: 34, color: 'rgba(0,0,0,0.78)'}}>
						{COPY.contact}
					</div>
					<div style={{position: 'absolute', right: 30, top: 34, fontFamily: FONT.ui, fontSize: 27, color: 'rgba(60,60,67,0.6)'}}>{COPY.lock.when}</div>
					{/* the ×N counter, rolling */}
					<div
						style={{
							position: 'absolute',
							right: 24,
							top: 80,
							height: 52,
							padding: '0 15px 0 13px',
							borderRadius: 26,
							background: 'rgba(255, 69, 58, 0.14)',
							color: IOS.red,
							display: 'flex',
							alignItems: 'center',
							fontFamily: FONT.ui,
							fontWeight: 600,
							fontSize: 34,
						}}
					>
						<span style={{marginRight: 2}}>×</span>
						<Roulette value={count} digitHeight={52} digitWidth={21} />
					</div>
				</>
			)}
		</Squircle>
	</div>
);

export const LockScene: React.FC = () => {
	const t = useT();
	const lock = scene('lock');
	const enterAt = lock.start - 2;
	const exitAt = scene('focus').start - 8;
	if (t < enterAt - 2 || t > exitAt + 14) return null;

	const cues = [0, 1, 2, 3].map((i) => lock.cue(`notif${i}`));
	const counts = COPY.missedCounts;
	// count rolls to the next value on each beat
	let count: number = counts[0];
	for (let i = 1; i < cues.length; i++) {
		count = lerp(count, counts[i], MOVE(prog(t, cues[i] - LEAD, 10)));
	}
	// newest notification drops onto the stack; the stack gets deeper behind it
	let drop = 1;
	let buzz = 0;
	for (let i = 1; i < cues.length; i++) {
		if (t >= cues[i] - LEAD) drop = spring(t - (cues[i] - LEAD), POP);
		const d = t - cues[i];
		if (d >= -1 && d < 16) buzz += Math.sin(d * 2.7) * Math.exp(-Math.max(0, d) / 4) * smooth((d + 1) / 2);
	}
	const depth1 = clamp(spring(t - (cues[1] - LEAD), SETTLE), 0, 1.05);
	const depth2 = clamp(spring(t - (cues[2] - LEAD), SETTLE), 0, 1.05);
	const cam = 1 + 0.04 * SINE(prog(t, lock.start, lock.end - lock.start));
	const drift = t / 60;

	const floaters: FloaterSpec[] = [
		{x: -470, y: -330, size: 120, depth: 0.55, kind: 'pill', color: '#FFFFFF'},
		{x: 480, y: -120, size: 96, depth: 0.7, kind: 'pill', color: '#FFFFFF'},
		{x: -455, y: 260, size: 40, depth: 0.85, kind: 'dot', color: '#D8D4EA'},
		{x: 470, y: 420, size: 140, depth: 0.4, kind: 'pill', color: '#FFFFFF'},
	];

	return (
		<div style={{position: 'absolute', transform: `scale(${cam.toFixed(5)})`}}>
			<Floaters specs={floaters} enterAt={enterAt + 4} exitAt={exitAt} seed={23} />
			<Card w={W} h={H} r={70} seed={7} enterAt={enterAt} exitAt={exitAt} x={buzz * 3.2} fill="#14123A">
				{/* wallpaper: night gradient with slowly drifting glows */}
				<div
					style={{
						position: 'absolute',
						inset: 0,
						background: [
							`radial-gradient(circle at ${22 + 4 * noise1(drift * 0.4, 1)}% ${30 + 3 * noise1(drift * 0.3, 2)}%, rgba(86, 140, 255, 0.55), rgba(86,140,255,0) 46%)`,
							`radial-gradient(circle at ${84 + 3 * noise1(drift * 0.35, 3)}% ${72 + 4 * noise1(drift * 0.3, 4)}%, rgba(255, 110, 170, 0.5), rgba(255,110,170,0) 50%)`,
							`radial-gradient(circle at 46% 108%, rgba(255, 168, 92, 0.42), rgba(255,168,92,0) 46%)`,
							'linear-gradient(172deg, #0C1748 0%, #22206A 42%, #4E2A80 74%, #7E3A86 100%)',
						].join(', '),
					}}
				/>
				{/* Dynamic Island */}
				<div style={{position: 'absolute', left: W / 2 - 128, top: 24, width: 256, height: 74, borderRadius: 37, background: '#000'}} />
				<div style={{position: 'absolute', left: W / 2 - 17, top: 120}}>
					<Padlock size={34} />
				</div>
				<div style={{position: 'absolute', left: 0, width: W, top: 166, textAlign: 'center', fontFamily: FONT.ui, fontWeight: 600, fontSize: 40, color: 'rgba(255,255,255,0.88)'}}>
					{COPY.lock.date}
				</div>
				<div
					style={{
						position: 'absolute',
						left: 0,
						width: W,
						top: 206,
						textAlign: 'center',
						fontFamily: FONT.display,
						fontWeight: 600,
						fontSize: 238,
						lineHeight: 1,
						letterSpacing: '-0.035em',
						color: 'rgba(255,255,255,0.94)',
					}}
				>
					{COPY.lock.time}
				</div>

				{/* the stack: two ghost layers, then the live notification on top */}
				<Note count={0} ghost y={34 * depth2} scale={lerp(1, 0.9, depth2)} opacity={0.75 * clamp(depth2 * 1.5)} />
				<Note count={0} ghost y={18 * depth1} scale={lerp(1, 0.95, depth1)} opacity={0.9 * clamp(depth1 * 1.5)} />
				<Note count={count} y={(1 - drop) * -64} scale={lerp(1.05, 1, clamp(drop))} opacity={clamp(drop * 2)} />

				{/* bottom controls */}
				{[
					{x: 62, icon: <Flashlight size={46} color="#FFFFFF" />},
					{x: W - 62 - 104, icon: <Camera size={46} color="#FFFFFF" />},
				].map(({x, icon}) => (
					<div
						key={x}
						style={{position: 'absolute', left: x, top: H - 172, width: 104, height: 104, borderRadius: 52, background: 'rgba(20, 16, 40, 0.38)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}
					>
						{icon}
					</div>
				))}
				<div style={{position: 'absolute', left: W / 2 - 135, top: H - 32, width: 270, height: 10, borderRadius: 5, background: 'rgba(255,255,255,0.92)'}} />
			</Card>
		</div>
	);
};
