import React from 'react';
import {Composition} from 'remotion';
import './fonts';
import {LAYOUTS, MOTION_BLUR} from './config';
import {Main} from './Main';
import {DURATION_SEC} from './timeline';

const frames = (fps: number) => Math.round(DURATION_SEC * fps);

export const RemotionRoot: React.FC = () => (
	<>
		{/* master: 1080×1920, 60 fps (preview = this at --scale=0.5) */}
		<Composition
			id="STFU-9x16"
			component={Main}
			fps={60}
			durationInFrames={frames(60)}
			width={LAYOUTS['9x16'].width}
			height={LAYOUTS['9x16'].height}
			defaultProps={{format: '9x16', samples: MOTION_BLUR.samples}}
		/>
		{/* upload version: same piece sampled at 30 fps (the 180° shutter gets twice as long) */}
		<Composition
			id="STFU-9x16-30fps"
			component={Main}
			fps={30}
			durationInFrames={frames(30)}
			width={LAYOUTS['9x16'].width}
			height={LAYOUTS['9x16'].height}
			defaultProps={{format: '9x16', samples: MOTION_BLUR.samples}}
		/>
		{/* 1:1 from the same composition, only the layout changes */}
		<Composition
			id="STFU-1x1"
			component={Main}
			fps={60}
			durationInFrames={frames(60)}
			width={LAYOUTS['1x1'].width}
			height={LAYOUTS['1x1'].height}
			defaultProps={{format: '1x1', samples: MOTION_BLUR.samples}}
		/>
	</>
);
