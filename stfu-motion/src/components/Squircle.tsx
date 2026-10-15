import React from 'react';
import {squirclePath} from '../lib/squircle';

/**
 * A box clipped to a continuous-corner shape. Content is laid out in the
 * box's own w×h coordinate space.
 */
export const Squircle: React.FC<{
	w: number;
	h: number;
	r: number;
	smoothing?: number;
	fill?: string;
	style?: React.CSSProperties;
	children?: React.ReactNode;
}> = ({w, h, r, smoothing = 0.6, fill, style, children}) => (
	<div
		style={{
			position: 'absolute',
			left: 0,
			top: 0,
			width: w,
			height: h,
			clipPath: `path('${squirclePath(w, h, r, smoothing)}')`,
			background: fill,
			overflow: 'hidden',
			...style,
		}}
	>
		{children}
	</div>
);
