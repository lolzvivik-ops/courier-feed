import React from 'react';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {PersonFill, PhoneFill} from '../components/Icons';
import {LYRICS} from '../lyrics';
import {EXPO_OUT, MOVE, SINE, clamp, lerp, prog, smooth, useT} from '../lib/motion';
import {COPY} from '../scenes';
import {FONT, IOS} from '../theme';
import {scene} from '../timeline';

const W = 800;
const H = 1000;
const AVATAR = 260;
const AVATAR_Y = 300;
const BTN = 150;
const BTN_Y = 740;

const AlarmGlyph: React.FC<{size: number}> = ({size}) => (
	<svg width={size} height={size} viewBox="0 0 24 24" style={{display: 'block'}}>
		<circle cx="12" cy="13" r="7.2" fill="none" stroke="#FFFFFF" strokeWidth="2" />
		<path d="M12 9.2V13l2.6 1.8M4.6 5.6l2.6-2M19.4 5.6l-2.6-2" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
	</svg>
);
const BubbleGlyph: React.FC<{size: number}> = ({size}) => (
	<svg width={size} height={size} viewBox="0 0 24 24" style={{display: 'block'}}>
		<path d="M12 4C7 4 3 7.2 3 11.2c0 2.2 1.2 4.1 3.1 5.4-.2 1.3-.9 2.5-1.9 3.4 2.1-.1 3.9-.9 5.1-2 .9.2 1.8.3 2.7.3 5 0 9-3.2 9-7.1S17 4 12 4z" fill="#FFFFFF" />
	</svg>
);

/**
 * The drop. Full-screen incoming call from "Do Not Answer": the avatar sends a
 * ring out on every sung word of the two lines over the drop, the phone buzzes,
 * and on the hook's first "Shut" the finger hits Decline.
 */
export const CallScene: React.FC = () => {
	const t = useT();
	const call = scene('call');
	const enterAt = call.start; // enters with the dark wipe, never ahead of it in the light theme
	const tDecline = call.cue('decline') - LEAD;
	const exitAt = tDecline + 10;
	if (t < enterAt - 2 || t > exitAt + 14) return null;

	const ringWords = [...LYRICS[3].words, ...LYRICS[4].words].map((w) => w.t);
	let buzz = 0;
	for (const wt of ringWords) {
		const d = t - wt;
		if (d >= -1 && d < 18) buzz += Math.sin(d * 2.9) * Math.exp(-Math.max(0, d) / 5) * smooth((d + 1) / 2);
	}
	// finger down on Decline (6 frames), release, call ends
	const press = smooth(prog(t, tDecline - 4, 4)) * (1 - smooth(prog(t, tDecline + 2, 6)));
	const ended = MOVE(prog(t, tDecline + 2, 8));
	const cam = 1 + 0.04 * SINE(prog(t, call.start, call.end - call.start));
	const drift = t / 60;

	const floaters: FloaterSpec[] = [
		{x: -470, y: -260, size: 64, depth: 0.5, kind: 'ring', color: '#2C2C31'},
		{x: 482, y: -330, size: 44, depth: 0.8, kind: 'dot', color: '#2A1F14'},
		{x: 460, y: 280, size: 120, depth: 0.35, kind: 'pill', color: '#222226'},
		{x: -446, y: 330, size: 42, depth: 0.7, kind: 'ring', color: '#2A2A2F'},
	];

	return (
		<div style={{position: 'absolute', transform: `scale(${cam.toFixed(5)})`}}>
			<Floaters specs={floaters} enterAt={enterAt + 6} exitAt={exitAt} seed={61} />
			<Card w={W} h={H} r={70} seed={37} enterAt={enterAt} exitAt={exitAt} x={buzz * 3.4} fill="#120F1C">
				{/* blurred contact-poster backdrop, warm from the avatar */}
				<div
					style={{
						position: 'absolute',
						inset: 0,
						background: [
							`radial-gradient(circle at ${50 + 3 * Math.sin(drift * 0.9)}% ${32 + 2 * Math.cos(drift * 0.7)}%, rgba(255, 140, 60, 0.42), rgba(255,140,60,0) 46%)`,
							'radial-gradient(circle at 20% 90%, rgba(94, 92, 230, 0.32), rgba(94,92,230,0) 50%)',
							'linear-gradient(180deg, #1D1A33 0%, #241A33 46%, #0E0C16 100%)',
						].join(', '),
						opacity: lerp(1, 0.75, ended),
					}}
				/>
				<div style={{position: 'absolute', left: 0, width: W, top: 78, textAlign: 'center', fontFamily: FONT.ui, fontWeight: 600, fontSize: 64, letterSpacing: '-0.02em', color: '#FFFFFF'}}>
					{COPY.contact}
				</div>
				{/* "mobile" → "Call Ended" */}
				<div style={{position: 'absolute', left: 0, width: W, top: 162, height: 44, overflow: 'hidden', textAlign: 'center', fontFamily: FONT.ui, fontSize: 34, color: 'rgba(235,235,245,0.62)'}}>
					<div style={{transform: `translateY(${(-ended * 44).toFixed(2)}px)`}}>
						<div style={{height: 44, lineHeight: '44px'}}>{COPY.call.kind}</div>
						<div style={{height: 44, lineHeight: '44px', color: IOS.red, fontWeight: 500}}>{COPY.call.ended}</div>
					</div>
				</div>

				{/* avatar + a ring out on every sung word */}
				{ringWords.map((wt, i) => {
					const p = prog(t, wt - LEAD, 40);
					if (p <= 0 || p >= 1 || t > tDecline + 2) return null;
					return (
						<div
							key={i}
							style={{
								position: 'absolute',
								left: W / 2 - AVATAR / 2,
								top: AVATAR_Y,
								width: AVATAR,
								height: AVATAR,
								borderRadius: AVATAR / 2,
								border: '4px solid rgba(255, 196, 140, 0.55)',
								transform: `scale(${lerp(1, 1.85, EXPO_OUT(p)).toFixed(4)})`,
								opacity: (1 - p) * (1 - ended),
							}}
						/>
					);
				})}
				<div
					style={{
						position: 'absolute',
						left: W / 2 - AVATAR / 2,
						top: AVATAR_Y,
						width: AVATAR,
						height: AVATAR,
						borderRadius: AVATAR / 2,
						background: IOS.orange,
						overflow: 'hidden',
						display: 'flex',
						alignItems: 'flex-end',
						justifyContent: 'center',
						boxShadow: '0 20px 50px rgba(0,0,0,0.35)',
						filter: ended > 0 ? `saturate(${lerp(1, 0.35, ended)})` : undefined,
					}}
				>
					<PersonFill size={210} color="rgba(255,255,255,0.92)" />
				</div>

				{/* Remind Me / Message */}
				{[
					{x: W / 2 - 190, label: COPY.call.remind, glyph: <AlarmGlyph size={40} />},
					{x: W / 2 + 190, label: COPY.call.message, glyph: <BubbleGlyph size={38} />},
				].map((b) => (
					<div key={b.label} style={{position: 'absolute', left: b.x - 90, top: 610, width: 180, textAlign: 'center', opacity: lerp(1, 0.3, ended)}}>
						<div style={{width: 76, height: 76, borderRadius: 38, margin: '0 auto', background: 'rgba(255,255,255,0.16)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>{b.glyph}</div>
						<div style={{marginTop: 10, fontFamily: FONT.ui, fontSize: 25, color: 'rgba(255,255,255,0.7)'}}>{b.label}</div>
					</div>
				))}

				{/* Decline / Accept */}
				{[
					{x: W / 2 - 190, bg: IOS.red, rot: 135, label: COPY.call.decline, pressed: press},
					{x: W / 2 + 190, bg: IOS.green, rot: 0, label: COPY.call.accept, pressed: 0},
				].map((b) => {
					const isAccept = b.rot === 0;
					// Accept breathes with the ring; Decline sinks and lights up under the finger
					const breathe = isAccept ? 1 + 0.05 * clamp(buzz) * (1 - ended) : 1;
					const s = (1 - 0.1 * b.pressed) * breathe * (isAccept ? lerp(1, 0.9, ended) : 1);
					return (
						<div key={b.label} style={{position: 'absolute', left: b.x - 110, top: BTN_Y, width: 220, textAlign: 'center', opacity: isAccept ? lerp(1, 0.25, ended) : 1}}>
							<div
								style={{
									width: BTN,
									height: BTN,
									borderRadius: BTN / 2,
									margin: '0 auto',
									background: b.bg,
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'center',
									transform: `scale(${s.toFixed(4)})`,
									filter: b.pressed > 0.01 ? `brightness(${(1 + 0.3 * b.pressed).toFixed(3)})` : undefined,
									boxShadow: b.pressed > 0.01 ? `0 0 ${(40 * b.pressed).toFixed(1)}px rgba(255,69,58,${(0.6 * b.pressed).toFixed(2)})` : undefined,
								}}
							>
								<div style={{transform: `rotate(${b.rot}deg)`}}>
									<PhoneFill size={74} color="#FFFFFF" />
								</div>
							</div>
							<div style={{marginTop: 18, fontFamily: FONT.ui, fontSize: 30, color: 'rgba(255,255,255,0.86)'}}>{b.label}</div>
						</div>
					);
				})}
				{/* decline confirmation: the red button's halo expands as the call drops */}
				{t > tDecline ? (
					<div
						style={{
							position: 'absolute',
							left: W / 2 - 190 - BTN / 2,
							top: BTN_Y,
							width: BTN,
							height: BTN,
							borderRadius: BTN / 2,
							border: `5px solid ${IOS.red}`,
							transform: `scale(${lerp(1, 1.7, EXPO_OUT(prog(t, tDecline, 16))).toFixed(4)})`,
							opacity: 1 - prog(t, tDecline, 16),
						}}
					/>
				) : null}
			</Card>
		</div>
	);
};
