import React from 'react';
import {EXPO_OUT, idle, lerp, noise1, prog, smooth, useT} from '../lib/motion';
import {useTheme} from '../theme';

export type FloaterSpec = {
	/** position relative to the stage origin (card centre), px */
	x: number;
	y: number;
	size: number;
	/** 0 = just behind the card, 1 = far back (more blur, slower, smaller) */
	depth: number;
	kind: 'bubble' | 'dot' | 'pill' | 'ring';
	color?: string;
	/** pops in at this t (from the card edge outwards); defaults to the group's enter */
	at?: number;
	/** where it pops from (the card edge), relative to its final position */
	from?: {x: number; y: number};
	opacity?: number;
};

/**
 * The third parallax layer: small soft shapes behind the card. Far ones are
 * blurred 4–10 px and move less; all drift slowly, never in sync.
 */
export const Floaters: React.FC<{
	specs: FloaterSpec[];
	enterAt: number;
	exitAt: number;
	seed: number;
}> = ({specs, enterAt, exitAt, seed}) => {
	const t = useT();
	const theme = useTheme();
	if (t < enterAt - 2 || t > exitAt + 14) return null;
	const out = smooth(prog(t, exitAt, 12));
	const cam = idle(t, seed, 1);
	return (
		<>
			{specs.map((f, i) => {
				const at = f.at ?? enterAt + i * 5; // 5-frame stagger
				const p = EXPO_OUT(prog(t, at, 26));
				if (p <= 0) return null;
				const d = f.depth;
				const drift = 1 - d * 0.6;
				const s = t / 60;
				const dx = 16 * noise1(s * 0.35 + i * 7.3, seed) * drift - cam.x * (0.6 - d * 0.5) - cam.ry * 3 * (1 - d);
				const dy = 18 * noise1(s * 0.3 + i * 3.1, seed + 5) * drift - cam.y * (0.5 - d * 0.4) - s * 6 * drift;
				const fx = f.from ? lerp(f.from.x, 0, p) : 0;
				const fy = f.from ? lerp(f.from.y, 0, p) : 0;
				const size = f.size * (1 - d * 0.35) * lerp(0.6, 1, p) * (1 + out * 0.15);
				const blur = 4 + d * 6 + out * 6;
				const alpha = (f.opacity ?? 0.9) * (1 - d * 0.35) * smooth(p * 1.4) * (1 - out);
				const color = f.color ?? theme.floater;
				const common: React.CSSProperties = {
					position: 'absolute',
					left: f.x + dx + fx - size / 2,
					top: f.y + dy + fy - size / 2,
					width: size,
					height: f.kind === 'pill' ? size * 0.42 : size,
					opacity: alpha,
					filter: `blur(${blur.toFixed(1)}px)`,
				};
				if (f.kind === 'ring') {
					return <div key={i} style={{...common, borderRadius: '50%', border: `${Math.max(3, size * 0.12)}px solid ${color}`}} />;
				}
				if (f.kind === 'bubble') {
					return (
						<div key={i} style={common}>
							<svg width={size} height={size} viewBox="0 0 100 100" style={{display: 'block', overflow: 'visible'}}>
								<path d="M50 14C25.7 14 6 29.2 6 48s19.7 34 44 34c4.3 0 8.4-.5 12.3-1.3 4.6 4.2 11.3 7.1 19 7.6.9 0 1.4-1 .8-1.7-3.6-3.8-5.6-8.2-6.1-12.6C88 68 94 58.5 94 48 94 29.2 74.3 14 50 14z" fill={color} />
							</svg>
						</div>
					);
				}
				return <div key={i} style={{...common, borderRadius: size, background: color}} />;
			})}
		</>
	);
};
