import React, {createContext, useContext} from 'react';
import {AbsoluteFill} from 'remotion';
import {type Format, type Layout, LAYOUTS} from '../config';

const LayoutContext = createContext<Layout>(LAYOUTS['9x16']);
export const LayoutProvider: React.FC<{format: Format; children: React.ReactNode}> = ({format, children}) => (
	<LayoutContext.Provider value={LAYOUTS[format]}>{children}</LayoutContext.Provider>
);
export const useLayout = () => useContext(LayoutContext);

/**
 * Card space: origin at the card centre of the layout, scaled for the format.
 * `transform` is the camera (shake), applied before the format scale.
 */
export const Stage: React.FC<{children: React.ReactNode; transform?: string}> = ({children, transform}) => {
	const L = useLayout();
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					left: L.axisX,
					top: L.cardCenterY,
					width: 0,
					height: 0,
					transform: `${transform ?? ''} scale(${L.stageScale})`,
				}}
			>
				{children}
			</div>
		</AbsoluteFill>
	);
};
