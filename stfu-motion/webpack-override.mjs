// Shared by remotion.config.ts (CLI renders/studio) and scripts/render_stills.mjs (bundle()).
// Lyrics are local-only (copyrighted): use src/data/lyrics.json when present, else the
// committed placeholder with the same timings (tsconfig "paths" mirrors this for tsc/tsx).
import path from 'node:path';

export const webpackOverride = (config) => ({
	...config,
	resolve: {
		...config.resolve,
		alias: {
			...(config.resolve?.alias ?? {}),
			'lyrics-data': [path.resolve('src/data/lyrics.json'), path.resolve('src/data/lyrics.placeholder.json')],
		},
	},
});
