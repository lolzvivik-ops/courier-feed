import React from 'react';
import {LEAD} from '../config';
import {EXPO_OUT, MOVE, lerp, prog, useT} from '../lib/motion';
import {FONT, useTheme} from '../theme';
import {type SceneT, TL_SCENES} from '../timeline';
import {useLayout} from './Stage';

/** Words reveal in 9 frames (opacity, blur 14→0, y +16→0, scale .96→1). */
const REVEAL = 9;
/** The line blurs out over the 6 frames before its scene ends. */
const LINE_OUT = 6;

/** When a scene's line must be gone (the outro clears before the loop wipe). */
const lineEnd = (sc: SceneT) => (sc.id === 'outro' ? sc.cue('lightWipe') : sc.end);

const Line: React.FC<{sc: SceneT; t: number}> = ({sc, t}) => {
	const theme = useTheme();
	const L = useLayout();
	const end = lineEnd(sc);
	// clears fully by the downbeat, so it never sits under the next line's first word
	const out = MOVE(prog(t, end - LINE_OUT, LINE_OUT));
	return (
		<div
			style={{
				position: 'absolute',
				left: L.axisX - L.textMaxWidth / 2,
				top: L.textTop,
				width: L.textMaxWidth,
				textAlign: 'center',
				fontFamily: FONT.display,
				fontWeight: 700,
				fontSize: L.fontSize,
				letterSpacing: '-0.025em',
				lineHeight: 1.05,
				textWrap: 'balance',
				color: theme.text,
				opacity: 1 - out,
				filter: out > 0.001 ? `blur(${(out * 12).toFixed(2)}px)` : undefined,
				transform: out > 0 ? `scale(${lerp(1, 0.985, out)})` : undefined,
			}}
		>
			{sc.wordsT.map((w, i) => {
				const p = EXPO_OUT(prog(t, w.t - LEAD, REVEAL));
				const blur = (1 - p) * 14;
				return (
					<React.Fragment key={i}>
						<span
							style={{
								display: 'inline-block',
								opacity: p,
								filter: blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : undefined,
								transform: p < 1 ? `translateY(${((1 - p) * 16).toFixed(2)}px) scale(${lerp(0.96, 1, p).toFixed(4)})` : undefined,
							}}
						>
							{w.text}
						</span>
						{i < sc.wordsT.length - 1 ? ' ' : null}
					</React.Fragment>
				);
			})}
		</div>
	);
};

/** The headline layer. Not inside the camera: the text never drifts. */
export const Headline: React.FC = () => {
	const t = useT();
	return (
		<>
			{TL_SCENES.filter((sc) => t >= sc.wordsT[0].t - LEAD && t <= lineEnd(sc)).map((sc) => (
				<Line key={sc.id} sc={sc} t={t} />
			))}
		</>
	);
};
