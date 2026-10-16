/**
 * Text acceptance (spec §10):
 *  1. no Cyrillic character anywhere in the project's sources/data;
 *  2. every on-screen string is printed once, for proofreading;
 *  3. on-screen strings are plain ASCII (+ "×", "·", "’") and US-style.
 *   npx tsx scripts/check_text.ts
 */
import {readdirSync, readFileSync, statSync} from 'node:fs';
import path from 'node:path';
import {LYRICS} from '../src/lyrics';
import {COPY} from '../src/scenes';

// Cyrillic, Cyrillic Supplement, Extended-A/B/C — built from code points so this file stays ASCII
const range = (a: number, b: number) => `${String.fromCodePoint(a)}-${String.fromCodePoint(b)}`;
const CYRILLIC = new RegExp(`[${range(0x0400, 0x052f)}${range(0x1c80, 0x1c8f)}${range(0x2de0, 0x2dff)}${range(0xa640, 0xa69f)}]`, 'u');
const ROOTS = ['src', 'scripts', 'public', 'README.md', 'package.json', 'remotion.config.ts'];
const TEXT = /\.(tsx?|mjs|js|json|py|md|txt|css|svg)$/;

const files: string[] = [];
const walk = (p: string) => {
	if (!statSync(p, {throwIfNoEntry: false})) return;
	if (statSync(p).isDirectory()) {
		for (const f of readdirSync(p)) walk(path.join(p, f));
	} else if (TEXT.test(p)) {
		files.push(p);
	}
};
ROOTS.forEach(walk);

let bad = 0;
for (const f of files) {
	readFileSync(f, 'utf8')
		.split('\n')
		.forEach((line, i) => {
			if (CYRILLIC.test(line)) {
				bad++;
				console.log(`CYRILLIC  ${f}:${i + 1}: ${line.trim().slice(0, 100)}`);
			}
		});
}
console.log(`Cyrillic scan: ${files.length} files, ${bad} hits`);

const strings = new Set<string>();
const collect = (v: unknown) => {
	if (typeof v === 'string') strings.add(v);
	else if (typeof v === 'number') strings.add(String(v));
	else if (Array.isArray(v)) v.forEach(collect);
	else if (v && typeof v === 'object') Object.values(v).forEach(collect);
};
LYRICS.forEach((l) => strings.add(l.words.map((w) => w.display).join(' ')));
collect(COPY);
const ALLOWED = /^[\x20-\x7E×·’•]*$/;
console.log('\nOn-screen strings:');
let odd = 0;
for (const s of strings) {
	const ok = ALLOWED.test(s);
	if (!ok) odd++;
	console.log(`  ${ok ? ' ' : '!'} ${JSON.stringify(s)}`);
}
if (bad || odd) {
	console.error(`\nFAIL: ${bad} Cyrillic hits, ${odd} strings with unexpected characters`);
	process.exit(1);
}
console.log('\nPASS');
