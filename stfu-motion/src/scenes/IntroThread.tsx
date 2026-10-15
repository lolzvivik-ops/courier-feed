import React from 'react';
import {Easing} from 'remotion';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {ChevronLeft, ChevronRight, PersonFill, Plus, Waveform} from '../components/Icons';
import {Badge, MessagesFace} from '../components/MessagesIcon';
import {MOVE, POP, QUART_OUT, SETTLE, SINE, clamp, lerp, prog, smooth, spring, useT} from '../lib/motion';
import {ICON_RADIUS} from '../lib/squircle';
import {COPY} from '../scenes';
import {FONT, IOS, useTheme} from '../theme';
import {scene} from '../timeline';

export const ICON = 300;
const W = 800;
const H = 840;
const R = 64;
const HEADER_H = 200;
const INPUT_H = 124;
const MSG_BOTTOM = H - INPUT_H - 14;
const BUBBLE_H = 92;
const GAP = 8;
const READ_H = 42;
const STAMP_GAP = 26;
/** Container-transform curve: leaves on the kick, settles long. */
const MORPH = Easing.bezier(0.3, 0, 0.08, 1);

const mix = (a: [number, number, number], b: [number, number, number], k: number) =>
	`rgb(${a.map((v, i) => Math.round(lerp(v, b[i], k))).join(',')})`;

/** Incoming bubble tail (bottom-left hook), in the bubble's colour. */
const Tail: React.FC<{color: string; opacity: number}> = ({color, opacity}) => (
	<svg width={40} height={40} viewBox="0 0 40 40" style={{position: 'absolute', left: -9, bottom: 0, opacity, overflow: 'visible'}}>
		<path d="M10 2 L30 2 L30 40 L22 40 C17 37.6 13 38.5 6.5 40 C4.6 40.4 0.4 40.2 0.6 39.6 C6.6 34.6 10 28.5 10 18 Z" fill={color} />
	</svg>
);

const VideoGlyph: React.FC<{color: string}> = ({color}) => (
	<svg width={54} height={36} viewBox="0 0 54 36" style={{display: 'block'}}>
		<rect x="1" y="3" width="36" height="30" rx="8" fill="none" stroke={color} strokeWidth="3.4" />
		<path d="M40 14.5 L52 7 V29 L40 21.5 Z" fill="none" stroke={color} strokeWidth="3.4" strokeLinejoin="round" />
	</svg>
);

export const IntroThread: React.FC = () => {
	const t = useT();
	const theme = useTheme();
	const intro = scene('intro');
	const thread = scene('thread');
	const exitAt = scene('lock').start - 8;
	if (t > exitAt + 14) return null;

	// --- the jump: hit on beat 0. It leaves a quarter frame after 0 so every motion-blur
	// sample of frame 0 is still the rest pose (frame 0 = last frame = loop point).
	const T = 22;
	const jumpH = 96;
	const t0 = Math.max(0, t - 0.25);
	const u = clamp(t0 / T);
	const inAir = t0 > 0 && t0 < T;
	const jy = inAir ? -jumpH * 4 * u * (1 - u) : 0;
	const vy = inAir ? (-jumpH * 4 * (1 - 2 * u)) / T : 0;
	// stretch with speed, easing off over the last 2 frames before touchdown; the squash
	// then builds over 2 frames, so no sample of the motion blur sees a jump in shape
	const stretch = 1 + Math.min(0.11, Math.abs(vy) * 0.0062) * smooth(t0 / 2) * (1 - smooth((t0 - (T - 2)) / 2));
	const land = t0 >= T ? 0.12 * smooth((t0 - T) / 2) * Math.exp(-Math.max(0, t0 - T - 2) / 5.5) * Math.cos(Math.max(0, t0 - T - 2) * 0.42) : 0;
	const sy = stretch * (1 - land);
	const sx = (1 / Math.sqrt(stretch)) * (1 + land * 0.75);
	const rz = inAir ? -4 * Math.sin(Math.PI * u) : 0;

	// --- icon → card (container transform), launched on the kick of beat 3
	const tm = intro.cue('morph') - LEAD;
	const k = MORPH(prog(t, tm, 24));
	const w = lerp(ICON, W, k);
	const h = lerp(ICON, H, k);
	const r = lerp(ICON * ICON_RADIUS, R, k);
	const faceOpacity = 1 - smooth((k - 0.06) / 0.4);
	const glyphOpacity = 1 - smooth(k / 0.26);
	const ui = smooth((k - 0.3) / 0.55);

	// --- badge: pops on beat 1, rolls 1 → 47 by beat 2, then becomes the back-button count
	const tb = intro.cue('badge');
	const pop = spring(t - (tb - LEAD), POP);
	const count = 1 + (COPY.unread - 1) * QUART_OUT(prog(t, tb, intro.cue('counted') - tb));
	const kb = MOVE(prog(t, tm + 1, 22));
	const bh = lerp(96, 46, kb);
	const bx = lerp(w - 26, 124, kb);
	// arcs over the header instead of crossing the avatar
	const by = lerp(26, 74, kb) - Math.sin(Math.PI * kb) * 70;
	const badgeColor = mix([255, 69, 58], [10, 132, 255], kb);

	const idleAmp = 0.75 * smooth(prog(t, 16, 40));
	const cam = 1 + 0.04 * SINE(prog(t, 0, thread.end));

	// --- bubbles: one per 808 hit; the stack shifts up, the tail hops to the newest
	const arrivals = [0, 1, 2, 3].map((i) => thread.cue(`bubble${i}`) - LEAD);
	const shift = arrivals.map((a) => clamp(spring(t - a, SETTLE), 0, 1.04));
	const readAt = thread.cue('read');
	const readK = spring(t - readAt, SETTLE);
	const offsetOf = (i: number) => {
		let o = readK * READ_H;
		for (let j = i + 1; j < 4; j++) o += shift[j] * (BUBBLE_H + GAP);
		return o;
	};

	const floaters: FloaterSpec[] = [
		{x: -478, y: -250, size: 74, depth: 0.45, kind: 'bubble', color: '#DCDCE2'},
		{x: 488, y: -360, size: 58, depth: 0.75, kind: 'bubble', color: '#CFE3FF'},
		{x: 470, y: 300, size: 84, depth: 0.3, kind: 'bubble', color: '#DCDCE2'},
		{x: -440, y: 420, size: 34, depth: 0.85, kind: 'dot', color: '#D6D6DC'},
		...arrivals.map(
			(a, i): FloaterSpec => ({
				x: i % 2 ? 470 : -470,
				y: 120 - i * 120,
				size: 30 + (i % 3) * 8,
				depth: 0.55 + (i % 2) * 0.2,
				kind: 'bubble',
				color: i % 2 ? '#D9E8FF' : '#E2E2E8',
				at: a + 2,
				from: {x: i % 2 ? -90 : 90, y: 30},
			}),
		),
	];

	return (
		<div style={{position: 'absolute', transform: `scale(${cam.toFixed(5)})`}}>
			<Floaters specs={floaters} enterAt={tm + 8} exitAt={exitAt} seed={11} />
			<Card
				w={w}
				h={h}
				r={r}
				y={jy}
				sx={sx}
				sy={sy}
				rz={rz}
				seed={3}
				idleAmp={idleAmp}
				exitAt={exitAt}
				overlay={
					pop > 0.001 ? (
						<Badge
							value={count}
							height={bh}
							color={badgeColor}
							style={{left: bx, top: by, transform: `scale(${pop.toFixed(4)})`}}
						/>
					) : null
				}
			>
				{/* thread content, laid out at final size and centred while the clip grows */}
				<div style={{position: 'absolute', left: (w - W) / 2, top: (h - H) / 2, width: W, height: H, opacity: ui, transform: `translateY(${((1 - ui) * 24).toFixed(2)}px)`}}>
					{/* header */}
					<div style={{position: 'absolute', left: 30, top: 52, color: IOS.blue}}>
						<ChevronLeft size={44} color={IOS.blue} strokeWidth={2.8} />
					</div>
					<div style={{position: 'absolute', right: 40, top: 56}}>
						<VideoGlyph color={IOS.blue} />
					</div>
					<div style={{position: 'absolute', left: W / 2 - 54, top: 24, width: 108, height: 108, borderRadius: 54, background: IOS.orange, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'}}>
						<div style={{marginTop: 22}}>
							<PersonFill size={84} color="rgba(255,255,255,0.92)" />
						</div>
					</div>
					<div style={{position: 'absolute', left: 0, width: W, top: 142, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 4, fontFamily: FONT.ui, fontWeight: 500, fontSize: 26, color: theme.label}}>
						{COPY.contact}
						<ChevronRight size={20} color={theme.tertiary} strokeWidth={3} />
					</div>
					<div style={{position: 'absolute', left: 0, right: 0, top: HEADER_H, height: 1.5, background: theme.separator}} />

					{/* timestamp, attached above the first bubble */}
					<div
						style={{
							position: 'absolute',
							left: 0,
							width: W,
							top: MSG_BOTTOM - offsetOf(0) - BUBBLE_H - STAMP_GAP - 30,
							textAlign: 'center',
							fontFamily: FONT.ui,
							fontSize: 24,
							color: theme.secondary,
						}}
					>
						<span style={{fontWeight: 600}}>{COPY.threadStamp.day}</span> {COPY.threadStamp.time}
					</div>

					{COPY.bubbles.map((text, i) => {
						const e = spring(t - arrivals[i], POP);
						if (e <= 0) return null;
						const tailOn = smooth(prog(t, arrivals[i], 3)) * (1 - smooth(prog(t, arrivals[i + 1] ?? 1e9, 3)));
						return (
							<div
								key={i}
								style={{
									position: 'absolute',
									left: 28,
									top: MSG_BOTTOM - offsetOf(i) - BUBBLE_H,
									height: BUBBLE_H,
									display: 'flex',
									alignItems: 'center',
									padding: '0 32px',
									borderRadius: BUBBLE_H / 2,
									background: theme.bubbleIn,
									color: theme.bubbleInText,
									fontFamily: FONT.ui,
									fontSize: 41,
									letterSpacing: '-0.012em',
									whiteSpace: 'nowrap',
									transformOrigin: '0% 100%',
									transform: `translateY(${((1 - e) * 26).toFixed(2)}px) scale(${lerp(0.42, 1, e).toFixed(4)})`,
									opacity: clamp(e * 2.5),
								}}
							>
								<Tail color={theme.bubbleIn} opacity={tailOn} />
								<span style={{position: 'relative'}}>{text}</span>
							</div>
						);
					})}

					{/* read receipt, slides in a beat after the last bubble */}
					<div
						style={{
							position: 'absolute',
							left: 42,
							top: MSG_BOTTOM - READ_H + 12,
							fontFamily: FONT.ui,
							fontSize: 24,
							color: theme.secondary,
							opacity: clamp(readK * 1.6),
							transform: `translateY(${((1 - clamp(readK)) * 10).toFixed(2)}px)`,
						}}
					>
						<span style={{fontWeight: 600}}>{COPY.read.label}</span> {COPY.read.time}
					</div>

					{/* input bar */}
					<div style={{position: 'absolute', left: 30, top: H - INPUT_H / 2 - 33, width: 66, height: 66, borderRadius: 33, background: theme.cardInset, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
						<Plus size={34} color={theme.secondary} />
					</div>
					<div
						style={{
							position: 'absolute',
							left: 116,
							right: 30,
							top: H - INPUT_H / 2 - 34,
							height: 68,
							borderRadius: 34,
							border: `2px solid ${theme.separator}`,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							padding: '0 22px 0 28px',
							fontFamily: FONT.ui,
							fontSize: 32,
							color: theme.tertiary,
						}}
					>
						{COPY.inputPlaceholder}
						<Waveform size={34} color={theme.tertiary} />
					</div>
				</div>

				{/* the icon face, fading out as the container opens */}
				{faceOpacity > 0.001 ? (
					<div style={{position: 'absolute', inset: 0, opacity: faceOpacity}}>
						<MessagesFace size={ICON} glyphOpacity={glyphOpacity} glyphScale={1 + k * 0.8} />
					</div>
				) : null}
			</Card>
		</div>
	);
};
