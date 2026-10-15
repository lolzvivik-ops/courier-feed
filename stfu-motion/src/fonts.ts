import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

/**
 * Inter Tight (headlines) and Inter (UI), the same files Google Fonts serves,
 * bundled from @fontsource into public/fonts so renders never depend on the
 * network. loadFont() holds the render until each face is ready.
 */
const FACES: Array<[family: string, file: string, weight: string]> = [
	['Inter Tight', 'inter-tight-latin-700-normal.woff2', '700'],
	['Inter Tight', 'inter-tight-latin-600-normal.woff2', '600'],
	['Inter', 'inter-latin-400-normal.woff2', '400'],
	['Inter', 'inter-latin-500-normal.woff2', '500'],
	['Inter', 'inter-latin-600-normal.woff2', '600'],
	['Inter', 'inter-latin-700-normal.woff2', '700'],
];

export const fontsReady = Promise.all(
	FACES.map(([family, file, weight]) => loadFont({family, url: staticFile(`fonts/${file}`), weight, format: 'woff2'})),
);
