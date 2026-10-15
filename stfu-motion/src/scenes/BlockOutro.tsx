import React from 'react';
import {Easing} from 'remotion';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {HandRaised} from '../components/Icons';
import {Badge, MessagesFace} from '../components/MessagesIcon';
import {EXPO_OUT, MOVE, POP, QUART_OUT, SINE, clamp, hash, lerp, prog, smooth, spring, useT} from '../lib/motion';
import {ICON_RADIUS} from '../lib/squircle';
import {COPY} from '../scenes';
import {FONT, IOS, useTheme} from '../theme';
import {END_T, scene} from '../timeline';
import {ICON} from './IntroThread';

const AW = 720;
const AH = 430;
const AR = 52;
const PW = 420;
const PH = 128;
const BTN_Y = AH - 116;
const MORPH = Easing.bezier(0.3, 0, 0.08, 1);

/** Countdown value: a long decelerating roll 47 → 4, then 3-2-1-0 on 8ths. */
const countAt = (t: number) => {
	const o = scene('outro');
	const start = o.cue('roll') - LEAD;
	const steps = ['three', 'two', 'one', 'zero'].map((c) => o.cue(c) - LEAD);
	const settle = steps[0] - 12;
	let v = COPY.unread - (COPY.unread - 4) * EXPO_OUT(prog(t, start, settle - start));
	for (const s of steps) v -= MOVE(prog(t, s, 7));
	return Math.max(0, v);
};

export const BlockOutro: React.FC = () => {
	const t = useT();
	const theme = useTheme();
	const block = scene('block');
	const outro = scene('outro');
	const enterAt = block.start - 2;
	if (t < enterAt - 2) return null;

	// --- alert: finger down, then the press lands on the downbeat and the alert collapses
	const tTouch = block.cue('touch') - LEAD;
	const tPress = block.cue('press') - LEAD;
	const hold = smooth(prog(t, tTouch, 5));
	const flash = Math.exp(-Math.max(0, t - tPress) / 4) * smooth(prog(t, tPress - 1, 2));
	const highlight = hold * (1 - smooth(prog(t, tPress + 4, 8))) * 0.1 + flash * 0.1;
	const sink = hold * (1 - smooth(prog(t, tPress, 6)));
	const k1 = MOVE(prog(t, tPress + 1, 18));
	const alertContent = 1 - smooth(prog(t, tPress + 1, 5));
	const pillContent = smooth(prog(t, tPress + 5, 9));

	// --- pill → Messages icon on the outro downbeat
	const tm = outro.start - LEAD;
	const k2 = MORPH(prog(t, tm, 20));
	const face = smooth(k2 * 1.6);
	const pillOut = 1 - smooth(k2 / 0.3);

	const w = lerp(lerp(AW, PW, k1), ICON, k2);
	const h = lerp(lerp(AH, PH, k1), ICON, k2);
	const r = lerp(lerp(AR, PH / 2, k1), ICON * ICON_RADIUS, k2);

	// --- badge countdown and pop
	const tBadge = outro.cue('badge') - LEAD;
	const badgePop = spring(t - tBadge, POP);
	const value = countAt(t);
	const tZero = outro.cue('zero') - LEAD;
	const burst = prog(t, tZero, 14);
	const badgeGone = t >= tZero + 10;
	const relief = t >= tZero ? 0.07 * Math.exp(-(t - tZero) / 7) * Math.cos((t - tZero) * 0.36) * smooth((t - tZero) / 2) : 0;

	// --- idle fades out before the loop point so the last frame is the rest pose
	const tWipe = outro.cue('lightWipe');
	const idleAmp = lerp(1, 0.75, k2) * (1 - smooth(prog(t, tWipe - 30, END_T - 12 - (tWipe - 30))));
	const camPeak = 1.04;
	const cam =
		t <= tWipe
			? 1 + (camPeak - 1) * SINE(prog(t, block.start, tWipe - block.start))
			: lerp(camPeak, 1, MOVE(prog(t, tWipe, END_T - 10 - tWipe)));

	const floaters: FloaterSpec[] = [
		{x: -460, y: -240, size: 60, depth: 0.5, kind: 'ring', color: '#2E2E33'},
		{x: 470, y: -300, size: 34, depth: 0.8, kind: 'dot', color: '#3A1F1E'},
		{x: 465, y: 230, size: 100, depth: 0.35, kind: 'pill', color: '#232327'},
		{x: -450, y: 280, size: 40, depth: 0.75, kind: 'dot', color: '#28282C'},
	];

	const cancelColor = IOS.blue;
	return (
		<div style={{position: 'absolute', transform: `scale(${cam.toFixed(5)})`}}>
			<Floaters specs={floaters} enterAt={enterAt + 6} exitAt={outro.cue('roll')} seed={53} />
			<Card
				w={w}
				h={h}
				r={r}
				seed={29}
				enterAt={enterAt}
				fill={theme.cardInset}
				idleAmp={idleAmp}
				scale={(1 - 0.015 * sink) * (1 + relief)}
				rx={-1.2 * sink}
				ry={1.4 * sink}
				overlay={
					badgePop > 0.001 && !badgeGone ? (
						<>
							<Badge
								value={value}
								height={96}
								style={{
									left: w - 26,
									top: 26,
									transform: `scale(${(badgePop * lerp(1, 1.45, EXPO_OUT(burst))).toFixed(4)})`,
									opacity: 1 - smooth(burst * 1.6),
									filter: burst > 0 ? `blur(${(burst * 8).toFixed(2)}px)` : undefined,
								}}
							/>
							{burst > 0
								? Array.from({length: 9}, (_, i) => {
										const a = (i / 9) * Math.PI * 2 + hash(i) * 0.5;
										const d = 40 + 95 * EXPO_OUT(burst) * (0.8 + hash(i + 9) * 0.4);
										const s = (10 + hash(i + 3) * 8) * (1 - burst * 0.6);
										return (
											<div
												key={i}
												style={{
													position: 'absolute',
													left: w - 26 + Math.cos(a) * d - s / 2,
													top: 26 + Math.sin(a) * d - s / 2,
													width: s,
													height: s,
													borderRadius: s,
													background: IOS.red,
													opacity: 1 - smooth(burst),
												}}
											/>
										);
									})
								: null}
						</>
					) : null
				}
			>
				{/* alert, laid out at full size around the card centre */}
				{alertContent > 0.001 ? (
					<div style={{position: 'absolute', left: (w - AW) / 2, top: (h - AH) / 2, width: AW, height: AH, opacity: alertContent}}>
						<div style={{position: 'absolute', left: 0, width: AW, top: 44, textAlign: 'center', fontFamily: FONT.ui, fontWeight: 600, fontSize: 42, letterSpacing: '-0.01em', color: theme.label}}>
							{COPY.alert.title}
						</div>
						<div style={{position: 'absolute', left: 64, width: AW - 128, top: 108, textAlign: 'center', fontFamily: FONT.ui, fontSize: 31, lineHeight: 1.32, color: theme.label, opacity: 0.86}}>
							{COPY.alert.body}
						</div>
						<div style={{position: 'absolute', left: AW / 2, top: BTN_Y, width: AW / 2, height: AH - BTN_Y, background: `rgba(255,255,255,${highlight.toFixed(3)})`}} />
						<div style={{position: 'absolute', left: 0, right: 0, top: BTN_Y, height: 1.5, background: theme.separator}} />
						<div style={{position: 'absolute', left: AW / 2 - 0.75, top: BTN_Y, width: 1.5, height: AH - BTN_Y, background: theme.separator}} />
						{[
							{label: COPY.alert.cancel, color: cancelColor, weight: 400, x: 0},
							{label: COPY.alert.confirm, color: IOS.red, weight: 600, x: AW / 2},
						].map((b) => (
							<div
								key={b.label}
								style={{
									position: 'absolute',
									left: b.x,
									top: BTN_Y,
									width: AW / 2,
									height: AH - BTN_Y,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
									fontFamily: FONT.ui,
									fontWeight: b.weight,
									fontSize: 38,
									color: b.color,
									transform: b.x > 0 ? `scale(${(1 - 0.03 * sink).toFixed(4)})` : undefined,
								}}
							>
								{b.label}
							</div>
						))}
					</div>
				) : null}

				{/* "Blocked" pill content */}
				{pillContent * pillOut > 0.001 ? (
					<div
						style={{
							position: 'absolute',
							left: 0,
							top: 0,
							width: w,
							height: h,
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							gap: 20,
							opacity: pillContent * pillOut,
							transform: `scale(${lerp(0.9, 1, QUART_OUT(pillContent)).toFixed(4)})`,
						}}
					>
						<div style={{width: 80, height: 80, borderRadius: 40, background: IOS.red, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
							<HandRaised size={46} color="#FFFFFF" />
						</div>
						<div style={{fontFamily: FONT.ui, fontWeight: 600, fontSize: 42, letterSpacing: '-0.01em', color: theme.label, whiteSpace: 'nowrap'}}>{COPY.blocked}</div>
					</div>
				) : null}

				{/* Messages face fading in as the pill becomes the icon */}
				{face > 0.001 ? (
					<div style={{position: 'absolute', inset: 0, opacity: face}}>
						<MessagesFace size={ICON} glyphOpacity={smooth((k2 - 0.35) / 0.5)} glyphScale={lerp(0.7, 1, clamp(k2))} />
					</div>
				) : null}
			</Card>
		</div>
	);
};
