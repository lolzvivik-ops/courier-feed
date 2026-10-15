#!/usr/bin/env node
/**
 * Render review stills with one bundle + one browser.
 *
 *   node scripts/render_stills.mjs [--comp STFU-9x16] [--scale 0.5] [--samples 10]
 *        [--out out/stills] [--sheet name] frames...
 *
 * `frames` are numbers or a:b:step ranges. With --sheet, also writes a labelled
 * contact sheet (out/stills/<name>.png) using ffmpeg's tile filter.
 */
import {bundle} from '@remotion/bundler';
import {openBrowser, renderStill, selectComposition} from '@remotion/renderer';
import {execFileSync} from 'node:child_process';
import {mkdirSync} from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const opt = (name, def) => {
	const i = args.indexOf(`--${name}`);
	if (i === -1) return def;
	const v = args[i + 1];
	args.splice(i, 2);
	return v;
};
const comp = opt('comp', 'STFU-9x16');
const scale = Number(opt('scale', '0.5'));
const samples = Number(opt('samples', '10'));
const outDir = opt('out', 'out/stills');
const sheet = opt('sheet', '');
const cols = Number(opt('cols', '6'));
const guides = opt('guides', '0') === '1';
const frames = args.flatMap((a) => {
	if (a.includes(':')) {
		const [s, e, st] = a.split(':').map(Number);
		const r = [];
		for (let f = s; f <= e; f += st || 1) r.push(f);
		return r;
	}
	return [Number(a)];
});

mkdirSync(outDir, {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts'), onProgress: () => undefined});
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE ?? null;
const browser = await openBrowser('chrome', {browserExecutable});
const inputProps = {format: comp === 'STFU-1x1' ? '1x1' : '9x16', samples, muted: true, guides};
const composition = await selectComposition({serveUrl, id: comp, inputProps, puppeteerInstance: browser, browserExecutable});
const files = [];
for (const frame of frames) {
	const f = Math.min(frame, composition.durationInFrames - 1);
	const output = path.join(outDir, `${comp}_${String(f).padStart(4, '0')}.png`);
	const t0 = Date.now();
	await renderStill({composition, serveUrl, output, frame: f, inputProps, scale, puppeteerInstance: browser, browserExecutable, overwrite: true});
	files.push({output, f});
	console.log(`frame ${f} → ${output} (${Date.now() - t0} ms)`);
}
await browser.close({silent: true});

if (sheet && files.length) {
	const inputs = files.flatMap(({output}) => ['-i', output]);
	const labels = files
		.map(({f}, i) => `[${i}:v]drawtext=text='${f}  t=${(f / composition.fps).toFixed(2)}s':x=12:y=12:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=6[v${i}]`)
		.join(';');
	const rows = Math.ceil(files.length / cols);
	const pad = rows * cols - files.length;
	const padIn = pad ? `;color=c=gray:s=${Math.round(composition.width * scale)}x${Math.round(composition.height * scale)}:d=1[p];[p]split=${pad}${Array.from({length: pad}, (_, i) => `[pp${i}]`).join('')}` : '';
	const all = files.map((_, i) => `[v${i}]`).join('') + Array.from({length: pad}, (_, i) => `[pp${i}]`).join('');
	const graph = `${labels}${padIn};${all}xstack=inputs=${files.length + pad}:layout=${Array.from({length: files.length + pad}, (_, i) => `${(i % cols) ? Array.from({length: i % cols}, () => 'w0').join('+') : '0'}_${Math.floor(i / cols) ? Array.from({length: Math.floor(i / cols)}, () => 'h0').join('+') : '0'}`).join('|')}`;
	const out = path.join(outDir, `${sheet}.png`);
	execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...inputs, '-filter_complex', graph, '-frames:v', '1', out]);
	console.log(`sheet → ${out}`);
}
