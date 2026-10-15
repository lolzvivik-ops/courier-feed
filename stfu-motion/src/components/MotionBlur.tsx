import React from 'react';
import {AbsoluteFill, Freeze, useCurrentFrame} from 'remotion';

/**
 * Camera motion blur: the scene is rendered `samples` times at sub-frame
 * instants across the shutter and averaged.
 *
 * Same idea as <CameraMotionBlur> from @remotion/motion-blur, with two changes
 * that matter here (both measured on this piece, see README):
 *  - Averaging: layer k is laid over layers 1…k-1 with opacity 1/k (a running
 *    mean). CameraMotionBlur sums layers with `plus-lighter` at opacity 1/N,
 *    which rounds every layer to 8 bits first, so static pixels drift by up to
 *    ±5 levels and the soft background gradient / shadows band. With the
 *    running mean a pixel that doesn't move is reproduced bit-exactly.
 *  - Timing: the shutter is centred on the frame. CameraMotionBlur samples
 *    frame+0.05 … frame+0.5 (+1 offset), i.e. every hit lands ~0.7 frame early.
 * Layers must be opaque, so the background is rendered inside every sample.
 */
export const MotionBlur: React.FC<{
	samples: number;
	shutterAngle: number;
	children: React.ReactNode;
}> = ({samples, shutterAngle, children}) => {
	const frame = useCurrentFrame();
	if (samples <= 1 || shutterAngle <= 0) {
		return <>{children}</>;
	}
	const shutter = shutterAngle / 360;
	return (
		<AbsoluteFill style={{isolation: 'isolate'}}>
			{Array.from({length: samples}, (_, i) => {
				const offset = ((i + 0.5) / samples - 0.5) * shutter;
				return (
					<AbsoluteFill key={i} style={i === 0 ? undefined : {opacity: 1 / (i + 1)}}>
						<Freeze frame={frame + offset}>{children}</Freeze>
					</AbsoluteFill>
				);
			})}
		</AbsoluteFill>
	);
};
