/**
 * Continuous-corner rounded rectangles (iOS "squircle"), as an SVG path.
 * Port of the corner-smoothing construction used by Figma (see the
 * "figma-squircle" write-up): a circular arc in the middle of each corner,
 * eased into the straight edges with two cubic Béziers.
 */

const rad = (deg: number) => (deg * Math.PI) / 180;

type Corner = {a: number; b: number; c: number; d: number; p: number; arc: number; r: number};

const cornerParams = (radius: number, smoothing: number, budget: number): Corner => {
	let r = Math.min(radius, budget);
	let s = smoothing;
	let p = (1 + s) * r;
	const maxS = budget / Math.max(r, 1e-6) - 1;
	s = Math.max(0, Math.min(s, maxS));
	p = Math.min(p, budget);
	const arcMeasure = 90 * (1 - s);
	const arc = Math.sin(rad(arcMeasure / 2)) * r * Math.SQRT2;
	const angleAlpha = (90 - arcMeasure) / 2;
	const p3ToP4 = r * Math.tan(rad(angleAlpha / 2));
	const angleBeta = 45 * s;
	const c = p3ToP4 * Math.cos(rad(angleBeta));
	const d = c * Math.tan(rad(angleBeta));
	const b = (p - arc - c - d) / 3;
	const a = 2 * b;
	if (r <= 0) r = 0;
	return {a, b, c, d, p, arc, r};
};

const n = (x: number) => (Math.abs(x) < 1e-4 ? '0' : x.toFixed(3));

/** Path of a w×h squircle at (x, y). smoothing 0.6 ≈ iOS. */
export const squirclePath = (w: number, h: number, radius: number, smoothing = 0.6, x = 0, y = 0): string => {
	const budget = Math.min(w, h) / 2;
	const k = cornerParams(Math.max(0, radius), smoothing, budget);
	const {a, b, c, d, p, arc, r} = k;
	if (r <= 0.01) {
		return `M${n(x)} ${n(y)}H${n(x + w)}V${n(y + h)}H${n(x)}Z`;
	}
	return [
		`M${n(x + w - p)} ${n(y)}`,
		`c${n(a)} 0 ${n(a + b)} 0 ${n(a + b + c)} ${n(d)}`,
		`a${n(r)} ${n(r)} 0 0 1 ${n(arc)} ${n(arc)}`,
		`c${n(d)} ${n(c)} ${n(d)} ${n(b + c)} ${n(d)} ${n(a + b + c)}`,
		`L${n(x + w)} ${n(y + h - p)}`,
		`c0 ${n(a)} 0 ${n(a + b)} ${n(-d)} ${n(a + b + c)}`,
		`a${n(r)} ${n(r)} 0 0 1 ${n(-arc)} ${n(arc)}`,
		`c${n(-c)} ${n(d)} ${n(-(b + c))} ${n(d)} ${n(-(a + b + c))} ${n(d)}`,
		`L${n(x + p)} ${n(y + h)}`,
		`c${n(-a)} 0 ${n(-(a + b))} 0 ${n(-(a + b + c))} ${n(-d)}`,
		`a${n(r)} ${n(r)} 0 0 1 ${n(-arc)} ${n(-arc)}`,
		`c${n(-d)} ${n(-c)} ${n(-d)} ${n(-(b + c))} ${n(-d)} ${n(-(a + b + c))}`,
		`L${n(x)} ${n(y + p)}`,
		`c0 ${n(-a)} 0 ${n(-(a + b))} ${n(d)} ${n(-(a + b + c))}`,
		`a${n(r)} ${n(r)} 0 0 1 ${n(arc)} ${n(-arc)}`,
		`c${n(c)} ${n(-d)} ${n(b + c)} ${n(-d)} ${n(a + b + c)} ${n(-d)}`,
		'Z',
	].join('');
};

/** iOS app-icon mask: corner radius ≈ 22.37 % of the side. */
export const ICON_RADIUS = 0.2237;
