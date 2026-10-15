import {KICKS} from '../timeline';
import {smooth} from './motion';

/**
 * Kick "punch" envelope in [0, 1]: rises over 1.5 frames into the kick, then
 * decays exponentially (≈ 4 % left after 10 frames) — spec §4.
 */
export const punchAt = (t: number): number => {
	let v = 0;
	for (const k of KICKS) {
		const d = t - k;
		if (d < -1.5) break;
		if (d > 14) continue;
		v = Math.max(v, d < 0 ? smooth((d + 1.5) / 1.5) : Math.exp(-d / 3.2));
	}
	return v;
};
