import React from 'react';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {Bed, Briefcase, Moon, PersonFill} from '../components/Icons';
import {Roulette} from '../components/Roulette';
import {EXPO_OUT, MOVE, POP, QUART_OUT, SETTLE, SINE, clamp, lerp, prog, smooth, spring, useT} from '../lib/motion';
import {COPY} from '../scenes';
import {FONT, IOS, useTheme} from '../theme';
import {scene} from '../timeline';

const W = 800;
const H = 742;
const TRACK_W = 160;
const TRACK_H = 96;
const KNOB = 84;
const ROWS_Y = 400;

const rgb = (a: number[], b: number[], k: number) => `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], clamp(k)))).join(',')})`;

/** iOS switch: knob slides with a spring, stretches while pressed, track fills green. */
const Toggle: React.FC<{on: number; press: number; fill: number; off: number[]}> = ({on, press, fill, off}) => {
	const stretch = 14 * press;
	const travel = TRACK_W - KNOB - 12;
	const knobW = KNOB + stretch;
	const x = 6 + on * travel - (on > 0.5 ? stretch : 0) * clamp(on);
	return (
		<div style={{position: 'relative', width: TRACK_W, height: TRACK_H, borderRadius: TRACK_H / 2, background: rgb(off, [48, 209, 88], fill)}}>
			<div
				style={{
					position: 'absolute',
					left: x,
					top: 6,
					width: knobW,
					height: KNOB,
					borderRadius: KNOB / 2,
					background: '#FFFFFF',
					boxShadow: '0 6px 16px rgba(0,0,0,0.16), 0 2px 3px rgba(0,0,0,0.08)',
				}}
			/>
		</div>
	);
};

/**
 * Do Not Disturb switches on with the hook's second "shut"; on the next line the
 * silenced counter rolls one step per sung word.
 */
export const FocusScene: React.FC = () => {
	const t = useT();
	const theme = useTheme();
	const focus = scene('focus');
	const enterAt = focus.start - 2;
	const exitAt = scene('block').start - 8;
	if (t < enterAt - 2 || t > exitAt + 14) return null;

	const tTog = focus.cue('toggle') - LEAD;
	const tTouch = tTog - 8;
	// finger lands two 16ths before the word, switch flips on the word
	const press = smooth(prog(t, tTouch, 5)) * (1 - smooth(prog(t, tTog + 1, 8)));
	const on = clamp(spring(t - tTog, POP), 0, 1.06);
	const fill = QUART_OUT(prog(t, tTog, 7));
	// leans toward the finger while pressed, springs back after the switch
	const lean = press + (t > tTog ? (1 - clamp(spring(t - tTog - 1, SETTLE))) * 0.5 * (1 - press) : 0);
	const dim = MOVE(prog(t, tTog + 2, 12));
	const ripple = prog(t, tTog, 20);
	const roll = MOVE(prog(t, tTog + 1, 8));
	const silencedIn = spring(t - (tTog + 6), SETTLE);
	const steps = [0, 1, 2].map((i) => focus.cue(`silenced${i}`) - LEAD);
	let silenced = 0;
	let prev = 0;
	steps.forEach((s, i) => {
		const k = EXPO_OUT(prog(t, s, 14));
		silenced += (COPY.silencedCounts[i] - prev) * k;
		prev = COPY.silencedCounts[i];
	});
	// each word bumps the moon a little: the phone swallowing another notification
	const gulp = steps.reduce((m, s) => Math.max(m, t >= s ? Math.exp(-(t - s) / 5) * smooth((t - s) / 1.5) : 0), 0);
	const cam = 1 + 0.04 * SINE(prog(t, focus.start, focus.end - focus.start));
	const offTrack = theme.name === 'dark' ? [57, 57, 61] : [233, 233, 235];
	const offIcon = theme.name === 'dark' ? [58, 58, 60] : [229, 229, 234];

	const others = [
		{label: COPY.focus.others[0], color: '#40C8E0', icon: <Bed size={42} color="#FFFFFF" />},
		{label: COPY.focus.others[1], color: '#BF5AF2', icon: <PersonFill size={40} color="#FFFFFF" />},
		{label: COPY.focus.others[2], color: '#34C3A5', icon: <Briefcase size={38} color="#FFFFFF" />},
	];

	const floaters: FloaterSpec[] = [
		{x: -470, y: -230, size: 64, depth: 0.5, kind: 'ring', color: '#26254A'},
		{x: 478, y: -300, size: 44, depth: 0.75, kind: 'dot', color: '#232238'},
		{x: 462, y: 230, size: 110, depth: 0.4, kind: 'pill', color: '#222226'},
		{x: -450, y: 300, size: 36, depth: 0.85, kind: 'dot', color: '#26262B'},
	];

	return (
		<div style={{position: 'absolute', transform: `scale(${cam.toFixed(5)})`}}>
			<Floaters specs={floaters} enterAt={enterAt + 4} exitAt={exitAt} seed={31} />
			<Card w={W} h={H} r={64} seed={13} enterAt={enterAt} exitAt={exitAt} scale={1 - 0.012 * press} rx={-1.4 * lean} ry={1.1 * lean}>
				<div style={{position: 'absolute', left: 44, top: 38, fontFamily: FONT.ui, fontWeight: 700, fontSize: 42, letterSpacing: '-0.015em', color: theme.label}}>
					{COPY.focus.header}
				</div>

				{/* Do Not Disturb row with the press highlight */}
				<div style={{position: 'absolute', left: 16, right: 16, top: 108, height: 168, borderRadius: 40, background: theme.cardInset, opacity: press * 0.9}} />
				{ripple > 0 && ripple < 1 ? (
					<div
						style={{
							position: 'absolute',
							left: 40,
							top: 142,
							width: 100,
							height: 100,
							borderRadius: 50,
							border: `4px solid ${IOS.indigo}`,
							transform: `scale(${lerp(1, 2.1, EXPO_OUT(ripple)).toFixed(3)})`,
							opacity: (1 - ripple) * 0.65,
						}}
					/>
				) : null}
				<div
					style={{
						position: 'absolute',
						left: 40,
						top: 142,
						width: 100,
						height: 100,
						borderRadius: 50,
						background: rgb(offIcon, [94, 92, 230], fill),
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						transform: `scale(${(1 + 0.12 * gulp).toFixed(4)})`,
					}}
				>
					<Moon size={52} color={rgb([142, 142, 147], [255, 255, 255], fill)} />
				</div>
				<div style={{position: 'absolute', left: 166, top: 140, fontFamily: FONT.ui, fontWeight: 600, fontSize: 41, letterSpacing: '-0.012em', color: theme.label}}>
					{COPY.focus.title}
				</div>
				{/* Off → On, rolling up */}
				<div style={{position: 'absolute', left: 166, top: 196, height: 40, width: 300, overflow: 'hidden', fontFamily: FONT.ui, fontSize: 31, color: theme.secondary}}>
					<div style={{transform: `translateY(${(-roll * 40).toFixed(2)}px)`}}>
						<div style={{height: 40, lineHeight: '40px'}}>{COPY.focus.off}</div>
						<div style={{height: 40, lineHeight: '40px', color: IOS.indigo, fontWeight: 500}}>{COPY.focus.on}</div>
					</div>
				</div>
				<div style={{position: 'absolute', left: W - 40 - TRACK_W, top: 144}}>
					<Toggle on={on} press={press} fill={fill} off={offTrack} />
				</div>

				{/* silenced counter: slides in after the switch, rolls on each word */}
				<div
					style={{
						position: 'absolute',
						left: 24,
						right: 24,
						top: 292,
						height: 88,
						borderRadius: 30,
						background: 'rgba(94, 92, 230, 0.16)',
						display: 'flex',
						alignItems: 'center',
						padding: '0 26px',
						fontFamily: FONT.ui,
						fontSize: 33,
						color: theme.label,
						opacity: clamp(silencedIn * 1.4),
						transform: `translateY(${((1 - clamp(silencedIn)) * 18).toFixed(2)}px)`,
					}}
				>
					<div style={{fontWeight: 700, color: IOS.indigo, marginRight: 12}}>
						<Roulette value={silenced} digitHeight={44} digitWidth={21} />
					</div>
					{COPY.focus.silenced}
				</div>

				<div style={{position: 'absolute', left: 166, right: 40, top: ROWS_Y - 12, height: 1.5, background: theme.separator}} />
				{others.map((o, i) => (
					<div key={o.label} style={{position: 'absolute', left: 0, right: 0, top: ROWS_Y + i * 104, height: 104, opacity: lerp(1, 0.38, dim)}}>
						<div style={{position: 'absolute', left: 52, top: 12, width: 76, height: 76, borderRadius: 38, background: o.color, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
							{o.icon}
						</div>
						<div style={{position: 'absolute', left: 166, top: 26, fontFamily: FONT.ui, fontSize: 37, color: theme.label}}>{o.label}</div>
						{i < others.length - 1 ? <div style={{position: 'absolute', left: 166, right: 40, top: 102, height: 1.5, background: theme.separator}} /> : null}
					</div>
				))}
			</Card>
		</div>
	);
};
