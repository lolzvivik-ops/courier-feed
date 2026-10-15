import React from 'react';
import {LEAD} from '../config';
import {Card} from '../components/Card';
import {Floaters, type FloaterSpec} from '../components/Floaters';
import {Bed, Briefcase, Moon, PersonFill} from '../components/Icons';
import {EXPO_OUT, MOVE, POP, QUART_OUT, SETTLE, SINE, clamp, lerp, prog, smooth, spring, useT} from '../lib/motion';
import {COPY} from '../scenes';
import {FONT, IOS, useTheme} from '../theme';
import {scene} from '../timeline';

const W = 800;
const H = 640;
const TRACK_W = 160;
const TRACK_H = 96;
const KNOB = 84;

const rgb = (a: number[], b: number[], k: number) => `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], clamp(k)))).join(',')})`;

/** iOS switch: knob slides with a spring, stretches while pressed, track fills green. */
const Toggle: React.FC<{on: number; press: number; fill: number}> = ({on, press, fill}) => {
	const stretch = 14 * press;
	const travel = TRACK_W - KNOB - 12;
	const knobW = KNOB + stretch;
	const x = 6 + on * travel - (on > 0.5 ? stretch : 0) * clamp(on);
	return (
		<div style={{position: 'relative', width: TRACK_W, height: TRACK_H, borderRadius: TRACK_H / 2, background: rgb([233, 233, 235], [48, 209, 88], fill)}}>
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

export const FocusScene: React.FC = () => {
	const t = useT();
	const theme = useTheme();
	const focus = scene('focus');
	const enterAt = focus.start - 2;
	const exitAt = scene('silence').start - 8;
	if (t < enterAt - 2 || t > exitAt + 14) return null;

	const tTouch = focus.cue('touch') - LEAD;
	const tTog = focus.cue('toggle') - LEAD;
	// finger down on the 808 hit, release + switch on the beat
	const press = smooth(prog(t, tTouch, 5)) * (1 - smooth(prog(t, tTog + 1, 8)));
	const on = clamp(spring(t - tTog, POP), 0, 1.06);
	const fill = QUART_OUT(prog(t, tTog, 7));
	// leans toward the finger while pressed, springs back after the switch
	const lean = press + (t > tTog ? (1 - clamp(spring(t - tTog - 1, SETTLE))) * 0.5 * (1 - press) : 0);
	const dim = MOVE(prog(t, tTog + 2, 12));
	const ripple = prog(t, tTog, 20);
	const roll = MOVE(prog(t, tTog + 1, 8));
	const cam = 1 + 0.04 * SINE(prog(t, focus.start, focus.end - focus.start));

	const others = [
		{label: COPY.focus.others[0], color: '#40C8E0', icon: <Bed size={42} color="#FFFFFF" />},
		{label: COPY.focus.others[1], color: '#BF5AF2', icon: <PersonFill size={40} color="#FFFFFF" />},
		{label: COPY.focus.others[2], color: '#34C3A5', icon: <Briefcase size={38} color="#FFFFFF" />},
	];

	const floaters: FloaterSpec[] = [
		{x: -470, y: -230, size: 64, depth: 0.5, kind: 'ring', color: '#CFCEF7'},
		{x: 478, y: -300, size: 44, depth: 0.75, kind: 'dot', color: '#DDDCF5'},
		{x: 462, y: 230, size: 110, depth: 0.4, kind: 'pill', color: '#FFFFFF'},
		{x: -450, y: 300, size: 36, depth: 0.85, kind: 'dot', color: '#D9D9E2'},
		{x: -330, y: -420, size: 28, depth: 0.9, kind: 'dot', color: '#CFCEF7'},
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
				{/* ripple when it switches on */}
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
							opacity: (1 - ripple) * 0.55,
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
						background: rgb([229, 229, 234], [94, 92, 230], fill),
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
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
						<div style={{height: 40, lineHeight: '40px', color: IOS.indigo, fontWeight: 500}}>
							{COPY.focus.on}
						</div>
					</div>
				</div>
				<div style={{position: 'absolute', left: W - 40 - TRACK_W, top: 144}}>
					<Toggle on={on} press={press} fill={fill} />
				</div>

				<div style={{position: 'absolute', left: 166, right: 40, top: 296, height: 1.5, background: theme.separator}} />
				{others.map((o, i) => (
					<div key={o.label} style={{position: 'absolute', left: 0, right: 0, top: 312 + i * 104, height: 104, opacity: lerp(1, 0.38, dim)}}>
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
