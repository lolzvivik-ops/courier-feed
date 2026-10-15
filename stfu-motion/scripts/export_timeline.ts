/**
 * Dump the resolved timeline for the Python tools (audio prep, sync report):
 *   npx tsx scripts/export_timeline.ts  →  .cache/timeline.json
 * Times are seconds from the fragment start (t / 60).
 */
import {mkdirSync, writeFileSync} from 'node:fs';
import {AUDIO_END, AUDIO_START, LEAD, SYNC_OFFSET_MS} from '../src/config';
import {DIP, KICKS, SFX, SFX_FILES, TIMELINE_SUMMARY, TL_SCENES} from '../src/timeline';

type Ev = {kind: string; id: string; sec: number; grid: string};
const sec = (t: number) => t / 60;
const events: Ev[] = [];
for (const sc of TL_SCENES) {
	events.push({kind: 'scene-change', id: sc.id, sec: sec(sc.start), grid: 'downbeat'});
	sc.wordsT.forEach((w, i) => events.push({kind: 'word', id: `${sc.id}#${i} "${w.text}"`, sec: sec(w.t), grid: '8th'}));
	events.push({kind: 'main-event', id: `${sc.id}: ${sc.hit.what}`, sec: sec(sc.hitT), grid: 'beat'});
	for (const name of Object.keys(sc.cues)) {
		events.push({kind: 'cue', id: `${sc.id}.${name}`, sec: sec(sc.cue(name)), grid: '8th'});
	}
}
KICKS.forEach((k, i) => events.push({kind: 'punch', id: `kick ${i}`, sec: sec(k), grid: 'kick'}));

const out = {
	summary: TIMELINE_SUMMARY,
	audioStart: AUDIO_START,
	audioEnd: AUDIO_END,
	syncOffsetMs: SYNC_OFFSET_MS,
	leadFrames60: LEAD,
	dip: DIP,
	sfx: SFX.map((s) => ({...s, sec: sec(s.t), startSec: sec(s.t) - SFX_FILES[s.file as keyof typeof SFX_FILES].pre / 1000})),
	events: events.sort((a, b) => a.sec - b.sec),
};
mkdirSync('.cache', {recursive: true});
writeFileSync('.cache/timeline.json', JSON.stringify(out, null, 1));
console.log(`.cache/timeline.json: ${events.length} events, ${SFX.length} sfx, ${TIMELINE_SUMMARY.durationSec.toFixed(3)} s`);
