import React from 'react';

/**
 * Odometer digits for a continuous value: every digit is a strip that rolls,
 * and a column only moves while the column to its right passes 9→0
 * (mechanical carry). Fast rolls smear vertically under the motion blur.
 * Leading zeros are blank, so 9→10 grows a column and 10→9 retires it.
 */
export const Roulette: React.FC<{
	value: number;
	digitHeight: number;
	digitWidth: number;
	columns?: number;
	style?: React.CSSProperties;
}> = ({value, digitHeight, digitWidth, columns = 2, style}) => {
	const v = Math.max(0, value);
	const cols = [];
	for (let c = 0; c < columns; c++) {
		const place = 10 ** c;
		let pos: number;
		if (c === 0) {
			pos = v % 10;
		} else {
			const lower = (v / (place / 10)) % 10; // position of the column to the right
			pos = Math.floor(v / place) + Math.max(0, lower - 9);
		}
		const blankLeading = c > 0;
		cols.unshift(
			<div key={c} style={{position: 'relative', width: digitWidth, height: digitHeight, overflow: 'hidden'}}>
				<div style={{position: 'absolute', left: 0, top: 0, width: digitWidth, transform: `translateY(${(-(pos % 10) * digitHeight).toFixed(3)}px)`}}>
					{Array.from({length: 11}, (_, i) => (
						<div key={i} style={{height: digitHeight, lineHeight: `${digitHeight}px`, textAlign: 'center'}}>
							{blankLeading && i % 10 === 0 && pos < 10 ? '' : String(i % 10)}
						</div>
					))}
				</div>
			</div>,
		);
	}
	return <div style={{display: 'flex', fontVariantNumeric: 'tabular-nums', ...style}}>{cols}</div>;
};

/** How many columns are visible (continuous, for widening a badge while 9↔10 rolls). */
export const visibleColumns = (value: number) => {
	const v = Math.max(0, value);
	if (v >= 10) return 2;
	return 1 + Math.max(0, (v % 10) - 9);
};
