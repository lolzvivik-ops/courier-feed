/**
 * Hand-drawn UI glyphs (SF-Symbols-like proportions, not Apple artwork).
 * All are 24×24 viewBox paths, sized by `size`.
 */
import React from 'react';

type P = {size?: number; color?: string; style?: React.CSSProperties; strokeWidth?: number};

const Svg: React.FC<P & {children: React.ReactNode; viewBox?: string}> = ({size = 24, style, children, viewBox = '0 0 24 24'}) => (
	<svg width={size} height={size} viewBox={viewBox} style={{display: 'block', overflow: 'visible', ...style}}>
		{children}
	</svg>
);

export const ChevronLeft: React.FC<P> = ({color = 'currentColor', strokeWidth = 2.6, ...p}) => (
	<Svg {...p}>
		<path d="M15.5 4 L7.5 12 L15.5 20" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
	</Svg>
);

export const ChevronRight: React.FC<P> = ({color = 'currentColor', strokeWidth = 2.4, ...p}) => (
	<Svg {...p}>
		<path d="M9 5 L16 12 L9 19" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
	</Svg>
);

export const PersonFill: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<circle cx="12" cy="8.2" r="4.4" fill={color} />
		<path d="M3.6 21.2c0-4.6 3.8-7.6 8.4-7.6s8.4 3 8.4 7.6c0 .5-.4.8-.9.8H4.5c-.5 0-.9-.3-.9-.8z" fill={color} />
	</Svg>
);

/** Crescent moon (Do Not Disturb). */
export const Moon: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M14.6 2.6A9.6 9.6 0 1 0 21.4 15 7.8 7.8 0 0 1 14.6 2.6z" fill={color} />
	</Svg>
);

export const Bed: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M2.5 6.5v12M2.5 15.5h19v3M21.5 15.5v-3a3 3 0 0 0-3-3h-7.5v6" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
		<circle cx="6.6" cy="11.4" r="2.1" fill={color} />
	</Svg>
);

export const Briefcase: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<rect x="2.5" y="7" width="19" height="13" rx="3" fill={color} />
		<path d="M8.5 7V5.4C8.5 4.6 9.1 4 9.9 4h4.2c.8 0 1.4.6 1.4 1.4V7" fill="none" stroke={color} strokeWidth={2} />
	</Svg>
);

/** Speaker body only; waves and slash are separate so they can animate. */
export const SpeakerBody: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M3.2 9.2c0-.7.5-1.2 1.2-1.2h3.1l4.6-3.9c.6-.5 1.5-.1 1.5.7v14.4c0 .8-.9 1.2-1.5.7L7.5 16H4.4c-.7 0-1.2-.5-1.2-1.2V9.2z" fill={color} />
	</Svg>
);

/** Two sound waves; `level` 0..1 hides them from the outside in. */
export const SpeakerWaves: React.FC<P & {level: number}> = ({color = 'currentColor', level, ...p}) => (
	<Svg {...p}>
		<path d="M16.3 8.6a4.6 4.6 0 0 1 0 6.8" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" opacity={Math.min(1, level * 2)} />
		<path d="M18.9 6a8.4 8.4 0 0 1 0 12" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" opacity={Math.max(0, level * 2 - 1)} />
	</Svg>
);

/** Diagonal slash drawn from the top-left; `draw` 0..1. */
export const Slash: React.FC<P & {draw: number; gap?: string}> = ({color = 'currentColor', draw, gap, ...p}) => {
	const len = 26;
	return (
		<Svg {...p}>
			{gap ? <path d="M2.5 3.2 L21.5 20.8" stroke={gap} strokeWidth={4.6} strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - draw)} fill="none" /> : null}
			<path d="M2.5 3.2 L21.5 20.8" stroke={color} strokeWidth={2.1} strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - draw)} fill="none" />
		</Svg>
	);
};

export const PhoneFill: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M6.6 2.9c.6-.4 1.4-.2 1.8.4l1.9 3c.4.6.3 1.3-.2 1.8l-1.4 1.3c.9 1.9 2.6 3.7 4.6 4.7l1.3-1.4c.5-.5 1.2-.6 1.8-.2l3 1.9c.6.4.8 1.2.4 1.8l-1.3 2c-.7 1.1-2 1.6-3.2 1.2C9.7 17.8 6.2 14.3 4.7 8.6c-.3-1.2.1-2.5 1.2-3.2l.7-2.5z" fill={color} />
	</Svg>
);

/** Phone handset with a small "missed" arrow. */
export const PhoneArrow: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M5.4 6.4c.5-.3 1.1-.2 1.4.3l1.5 2.4c.3.5.2 1-.2 1.4l-1.1 1c.7 1.5 2.1 2.9 3.6 3.7l1-1.1c.4-.4 1-.5 1.4-.2l2.4 1.5c.5.3.6 1 .3 1.4l-1 1.6c-.6.9-1.6 1.3-2.6 1C7.9 18.4 5.2 15.6 4 11.1c-.3-1 .1-2 .9-2.6l.5-2.1z" fill={color} />
		<path d="M14 4.5l3 3 4-4M17.5 3.5h3.5v3.5" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
	</Svg>
);

export const HandRaised: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path
			d="M8 11.5V5.2a1.5 1.5 0 0 1 3 0v5.3V3.9a1.5 1.5 0 0 1 3 0v6.6V5.1a1.5 1.5 0 0 1 3 0v8.4l1.3-2.1a1.5 1.5 0 0 1 2.6 1.5l-3.1 5.9A6 6 0 0 1 12.5 22h-.8A5.7 5.7 0 0 1 6 16.3V8.1a1.5 1.5 0 0 1 2 0z"
			fill={color}
		/>
	</Svg>
);

export const Flashlight: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M7.5 2.5h9v4l-2.5 4v10a1.5 1.5 0 0 1-1.5 1.5h-1A1.5 1.5 0 0 1 10 20.5v-10l-2.5-4v-4z" fill={color} />
		<circle cx="12" cy="13.5" r="1.2" fill="rgba(0,0,0,0.35)" />
	</Svg>
);

export const Camera: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M3 8.5C3 7.4 3.9 6.5 5 6.5h2.2l1.4-2h6.8l1.4 2H19c1.1 0 2 .9 2 2V18c0 1.1-.9 2-2 2H5c-1.1 0-2-.9-2-2V8.5z" fill={color} />
		<circle cx="12" cy="13" r="3.6" fill="rgba(0,0,0,0.3)" />
	</Svg>
);

export const Plus: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		<path d="M12 5v14M5 12h14" stroke={color} strokeWidth={2.2} strokeLinecap="round" />
	</Svg>
);

export const Waveform: React.FC<P> = ({color = 'currentColor', ...p}) => (
	<Svg {...p}>
		{[5, 8.5, 12, 15.5, 19].map((x, i) => (
			<path key={x} d={`M${x} ${12 - [2.5, 5, 7, 4.5, 2][i]}v${[5, 10, 14, 9, 4][i]}`} stroke={color} strokeWidth={2} strokeLinecap="round" />
		))}
	</Svg>
);

/** Speech bubble of the Messages icon (white, slightly oval, tail bottom-left). */
export const MessagesGlyph: React.FC<{size: number; color?: string}> = ({size, color = '#FFFFFF'}) => (
	<svg width={size} height={size} viewBox="0 0 100 100" style={{display: 'block'}}>
		<path
			d="M50 17c-24.3 0-44 14.6-44 32.6 0 10.3 6.4 19.4 16.4 25.4-.6 4.6-2.8 9.3-6.8 13.2-.7.7-.2 1.9.8 1.8 7.4-.6 13.9-3.4 18.3-7.3 4.7 1.3 9.9 2 15.3 2 24.3 0 44-14.6 44-32.6S74.3 17 50 17z"
			fill={color}
		/>
	</svg>
);
