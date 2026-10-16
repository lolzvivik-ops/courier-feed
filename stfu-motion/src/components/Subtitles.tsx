import React from 'react';
import {LEAD} from '../config';
import {type LyricLine, LYRICS} from '../lyrics';
import {EXPO_OUT, MOVE, POP, lerp, prog, spring, useT} from '../lib/motion';
import {ACCENTS, type Accent, SCENES} from '../scenes';
import {FONT, IOS, useTheme} from '../theme';
import {END_T} from '../timeline';
import {useLayout} from './Stage';

/** Words reveal in 9 frames (opacity, blur 14→0, y +16→0, scale .96→1). */
const REVEAL = 9;
/** A line blurs out over 6 frames, finishing as the next line's first word starts. */
const LINE_OUT = 6;

const ACCENT_COLOR: Record<Accent, string> = {red: IOS.red, green: IOS.green, indigo: IOS.indigo};
const key = (line: number, word: number) => `${line}:${word}`;
const accentOf = new Map(ACCENTS.map((a) => [key(a.at.line, a.at.word), a.color]));
/** Words that fire a card event "stamp" in (land big, settle). */
const triggers = new Set(
	SCENES.flatMap((s) => [s.hit.at, ...Object.values(s.cues)]).flatMap((c) => (typeof c === 'number' ? [] : [key(c.line, c.word)])),
);

/** When line i must be gone: as the next line starts, or just before the loop point. */
const lineEnd = (i: number) => (i + 1 < LYRICS.length ? LYRICS[i + 1].words[0].t - LEAD : END_T - 3);

const Line: React.FC<{line: LyricLine; index: number; t: number}> = ({line, index, t}) => {
	const theme = useTheme();
	const L = useLayout();
	const out = MOVE(prog(t, lineEnd(index) - LINE_OUT, LINE_OUT));
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
			{line.words.map((w, i) => {
				const start = w.t - LEAD;
				const p = EXPO_OUT(prog(t, start, REVEAL));
				const blur = (1 - p) * 14;
				const k = key(w.line, w.index);
				const accent = accentOf.get(k);
				// trigger words land a little big and settle on a spring (≤ 6 % overshoot)
				const stamp = triggers.has(k) ? lerp(accent ? 1.22 : 1.1, 1, spring(t - start, POP)) : 1;
				const scale = lerp(0.96, 1, p) * stamp;
				return (
					<React.Fragment key={i}>
						<span
							style={{
								display: 'inline-block',
								opacity: p,
								color: accent ? ACCENT_COLOR[accent] : undefined,
								filter: blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : undefined,
								transform: p < 1 || Math.abs(scale - 1) > 1e-4 ? `translateY(${((1 - p) * 16).toFixed(2)}px) scale(${scale.toFixed(4)})` : undefined,
							}}
						>
							{w.display}
						</span>
						{i < line.words.length - 1 ? ' ' : null}
					</React.Fragment>
				);
			})}
		</div>
	);
};

/**
 * Subtitles: the sung line, word by word on the vocal (lyrics.json). Not in the
 * camera: the text never drifts. Lines change with the singer, not with the cards.
 */
export const Subtitles: React.FC = () => {
	const t = useT();
	return (
		<>
			{LYRICS.map((line, i) =>
				t >= line.words[0].t - LEAD && t <= lineEnd(i) ? <Line key={i} line={line} index={i} t={t} /> : null,
			)}
		</>
	);
};
