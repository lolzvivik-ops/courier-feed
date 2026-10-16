/**
 * SCRIPT — what the cards do, and on which word or beat.
 *
 * The text on screen is the song itself (src/lyrics.ts). Cards change on
 * downbeats; inside a card, each event fires either on a beat (a number:
 * beats from the scene's downbeat, 8ths only) or on a sung word: W(line, word)
 * indexes the lines of lyrics.txt (0-based), e.g. W(5, 0) = first word of the
 * sixth line (the hook's first "Shut"). Lines: 0–2 pre-hook, 3–4 over the
 * drop, 5–8 the hook.
 */
import type {WordRef} from './lyrics';

export const W = (line: number, word: number): WordRef => ({line, word});
export type Cue = number | WordRef;

export type SceneId = 'intro' | 'thread' | 'lock' | 'call' | 'focus' | 'block' | 'outro';

export type SceneSpec = {
	id: SceneId;
	bars: number;
	/** the one main event of the scene */
	hit: {at: Cue; what: string};
	cues: Record<string, Cue>;
};

export const SCENES: SceneSpec[] = [
	{
		id: 'intro',
		bars: 2,
		hit: {at: 0, what: 'Messages icon jumps on the first downbeat'},
		// badge pops on the first sung word, lands on 47 on the second; the icon opens on the next line
		cues: {badge: W(0, 0), counted: W(0, 1), morph: W(1, 0)},
	},
	{
		id: 'thread',
		bars: 2,
		hit: {at: W(1, 1), what: 'a text lands on each of the line\'s last four words'},
		cues: {bubble0: W(1, 1), bubble1: W(1, 2), bubble2: W(1, 3), bubble3: W(1, 4), read: 5},
	},
	{
		id: 'lock',
		bars: 2,
		hit: {at: W(2, 0), what: 'a missed call on every word of the line'},
		// the Dynamic Island turns into an incoming call the beat before the drop
		cues: {notif0: W(2, 0), notif1: W(2, 1), notif2: W(2, 2), notif3: W(2, 3), notif4: W(2, 4), island: 7},
	},
	{
		id: 'call',
		bars: 2,
		hit: {at: W(3, 0), what: 'DROP on the hook\'s first word: dark, full-screen incoming call'},
		cues: {decline: W(5, 0)},
	},
	{
		id: 'focus',
		bars: 2,
		hit: {at: W(5, 3), what: 'Do Not Disturb switches on, on the second "shut"'},
		cues: {toggle: W(5, 3), silenced0: W(6, 1), silenced1: W(6, 2), silenced2: W(6, 3)},
	},
	{
		id: 'block',
		bars: 1,
		hit: {at: W(7, 2), what: '"Block Contact" pressed on the line\'s third word'},
		cues: {touch: W(7, 0), press: W(7, 2), pill: W(7, 3)},
	},
	{
		id: 'outro',
		bars: 1,
		hit: {at: W(8, 3), what: 'badge rolls to 0 and pops on the last word'},
		cues: {badge: W(8, 0), roll: W(8, 1), roll2: W(8, 2), zero: W(8, 3), lightWipe: 3},
	},
];

export type Accent = 'red' | 'green' | 'indigo';
/** Trigger words drawn in the colour of what they set off (every other cue word just "stamps"). */
export const ACCENTS: Array<{at: WordRef; color: Accent}> = [
	{at: W(3, 0), color: 'green'}, // drop word → incoming call
	{at: W(5, 0), color: 'red'}, // first "Shut" → Decline
	{at: W(5, 3), color: 'indigo'}, // second "shut" → Do Not Disturb
	{at: W(7, 2), color: 'red'}, // → Block Contact
	{at: W(8, 3), color: 'red'}, // last word → the badge pops
];

/** UI copy, kept next to the script so every visible string is in one place. */
export const COPY = {
	contact: 'Do Not Answer',
	unread: 47,
	bubbles: ['hey', 'why are you ignoring me', 'hello??', 'answer me'],
	threadStamp: {day: 'Today', time: '3:41 AM'},
	read: {label: 'Read', time: '3:47 AM'},
	inputPlaceholder: 'iMessage',
	lock: {date: 'Wednesday, October 15', time: '3:47', when: 'now', title: 'Missed Call'},
	missedCounts: [1, 3, 5, 8, 12],
	island: {label: 'iPhone'},
	call: {kind: 'mobile', decline: 'Decline', accept: 'Accept', remind: 'Remind Me', message: 'Message', ended: 'Call Ended'},
	focus: {header: 'Focus', title: 'Do Not Disturb', off: 'Off', on: 'On', silenced: 'notifications silenced', others: ['Sleep', 'Personal', 'Work']},
	silencedCounts: [12, 29, 47],
	alert: {
		title: 'Block Contact?',
		body: 'You will not receive phone calls, messages, or FaceTime from this contact.',
		cancel: 'Cancel',
		confirm: 'Block Contact',
	},
	blocked: 'Blocked',
} as const;
