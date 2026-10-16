/**
 * Subtitles = the sung words of the fragment, each timed to its vocal onset
 * (scripts/align_lyrics.py → src/data/lyrics.json, local only; the committed
 * placeholder has the same timings with bullets instead of words).
 */
import data from 'lyrics-data';
import {AUDIO_START, CENSOR, SYNC_OFFSET_MS} from './config';

export type LyricWord = {
	text: string;
	/** what is drawn (profanity masked when CENSOR) */
	display: string;
	/** onset, t (60-fps frames from the fragment start) */
	t: number;
	end: number;
	line: number;
	index: number;
};
export type LyricLine = {text: string; unsure: boolean; words: LyricWord[]};

const OFFSET = (SYNC_OFFSET_MS / 1000) * 60;
const toT = (songSec: number) => (songSec - AUDIO_START) * 60 + OFFSET;

/** f*ck, sh*t, b*tch: keep the first letter and the shape, hide one vowel. */
const mask = (w: string) => (CENSOR ? w.replace(/\b(f)u(ck)/gi, '$1*$2').replace(/\b(sh)i(t)/gi, '$1*$2').replace(/\b(b)i(tch)/gi, '$1*$2') : w);

export const LYRICS_PLACEHOLDER = Boolean((data as {placeholder?: boolean}).placeholder);

export const LYRICS: LyricLine[] = data.lines.map((ln, line) => ({
	text: ln.text,
	unsure: ln.unsure,
	words: ln.words.map((w, index) => ({text: w.text, display: mask(w.text), t: toT(w.start), end: toT(w.end), line, index})),
}));

export type WordRef = {line: number; word: number};
export const lyricWord = (ref: WordRef): LyricWord => {
	const w = LYRICS[ref.line]?.words[ref.word];
	if (!w) throw new Error(`[lyrics] no word ${ref.word} in line ${ref.line} — did the lyric sheet change? Update the cues in src/scenes.ts`);
	return w;
};
