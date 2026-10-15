import React from 'react';
import {IOS, FONT} from '../theme';
import {MessagesGlyph} from './Icons';
import {Roulette, visibleColumns} from './Roulette';

/** Messages-style app icon face (no shape: the parent clips it). */
export const MessagesFace: React.FC<{size: number; glyphOpacity?: number; glyphScale?: number}> = ({size, glyphOpacity = 1, glyphScale = 1}) => (
	<div style={{position: 'absolute', inset: 0, background: IOS.messages}}>
		{/* soft top light, like the real icon's gloss-free gradient */}
		<div style={{position: 'absolute', inset: 0, background: 'radial-gradient(120% 80% at 30% 0%, rgba(255,255,255,0.22), rgba(255,255,255,0) 60%)'}} />
		<div
			style={{
				position: 'absolute',
				left: '50%',
				top: '50%',
				width: size * 0.74,
				height: size * 0.74,
				transform: `translate(-50%, -48%) scale(${glyphScale})`,
				opacity: glyphOpacity,
			}}
		>
			<MessagesGlyph size={size * 0.74} />
		</div>
	</div>
);

/**
 * Red notification badge with a rolling count. `value` is continuous; the pill
 * widens smoothly while a second digit rolls in.
 */
export const Badge: React.FC<{
	value: number;
	height: number;
	color?: string;
	style?: React.CSSProperties;
}> = ({value, height, color = IOS.red, style}) => {
	const digitW = height * 0.38;
	const cols = visibleColumns(value);
	const width = height + (cols - 1) * digitW * 1.05;
	return (
		<div
			style={{
				position: 'absolute',
				width,
				height,
				marginLeft: -width / 2,
				marginTop: -height / 2,
				borderRadius: height / 2,
				background: color,
				boxShadow: `0 ${height * 0.06}px ${height * 0.16}px rgba(255, 59, 48, 0.28), inset 0 1px 0 rgba(255,255,255,0.25)`,
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				color: '#FFFFFF',
				fontFamily: FONT.ui,
				fontWeight: 500,
				fontSize: height * 0.6,
				letterSpacing: '-0.01em',
				overflow: 'hidden',
				...style,
			}}
		>
			<div style={{width: digitW * 2, flexShrink: 0, transform: `translateX(${(-(2 - cols) * digitW * 0.5).toFixed(2)}px)`}}>
				<Roulette value={value} digitHeight={height} digitWidth={digitW} />
			</div>
		</div>
	);
};
