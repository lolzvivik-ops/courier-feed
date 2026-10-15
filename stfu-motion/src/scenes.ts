/**
 * SCRIPT — the story, as data. Swap any text; the structure is what matters.
 *
 * Every position is in beats from the scene's first downbeat and must sit on an
 * 8th (multiples of 0.5). One bar = 4 beats. Scenes change on downbeats.
 * Cue positions were picked against the kick map of the fragment (beats.json):
 * bubbles, presses and the punchline word land on 808 hits.
 *
 * All on-screen text lives in this file (English only, US iOS conventions).
 */

export type SceneId = 'intro' | 'thread' | 'lock' | 'focus' | 'silence' | 'block' | 'outro';

export type SceneSpec = {
	id: SceneId;
	bars: number;
	/** Headline, revealed word by word. */
	text: string;
	/** Beat of each word (same count as words in `text`). */
	words: number[];
	/** The one main event of the scene. */
	hit: {beat: number; what: string};
	/** Secondary cues used by the card. */
	cues: Record<string, number>;
};

export const SCENES: SceneSpec[] = [
	{
		id: 'intro',
		bars: 1,
		text: '47 unread.',
		// Starts on the "and": frame 0 is the clean cover (also the loop frame).
		words: [0.5, 1],
		hit: {beat: 0, what: 'Messages icon jumps (squash & stretch)'},
		cues: {badge: 1, counted: 2, morph: 3},
	},
	{
		id: 'thread',
		bars: 2,
		text: 'You text. You call.',
		words: [0, 0.5, 1, 1.5],
		hit: {beat: 5.5, what: 'last bubble lands, "Read" follows'},
		// one bubble per 808 hit
		cues: {bubble0: 1, bubble1: 2.5, bubble2: 4, bubble3: 5.5, read: 6.5},
	},
	{
		id: 'lock',
		bars: 1,
		text: 'At 3:47 AM.',
		words: [0, 0.5, 1],
		hit: {beat: 0, what: 'missed-call stack starts growing'},
		cues: {notif0: 0, notif1: 1, notif2: 2, notif3: 3},
	},
	{
		id: 'focus',
		bars: 2,
		text: 'And I just turn on the silence.',
		words: [0, 0.5, 1, 1.5, 2, 2.5, 3],
		hit: {beat: 7, what: 'Do Not Disturb toggle switches on (last beat before the drop)'},
		cues: {touch: 6.5, toggle: 7},
	},
	{
		id: 'silence',
		bars: 1,
		text: 'Silence.',
		words: [0],
		hit: {beat: 0, what: 'DROP: light → dark wipe, camera shake'},
		cues: {wipe: 0, fall: 1.5},
	},
	{
		id: 'block',
		bars: 2,
		text: "and you're blocked.",
		words: [0, 0.5, 1],
		hit: {beat: 4, what: '"Block Contact" pressed on the downbeat'},
		cues: {touch: 3.5, press: 4, pill: 5},
	},
	{
		id: 'outro',
		// 2 scripted bars + 1 so the piece lands inside 18–22 s at 149 BPM.
		bars: 3,
		text: 'Finally quiet.',
		// "quiet." is the punchline: it lands on an 808 hit.
		words: [0, 1],
		hit: {beat: 9, what: 'badge reaches 0 and pops'},
		cues: {badge: 0.5, roll: 2.5, three: 7.5, two: 8, one: 8.5, zero: 9, lightWipe: 11},
	},
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
	missedCounts: [1, 3, 7, 12],
	focus: {header: 'Focus', title: 'Do Not Disturb', off: 'Off', on: 'On', others: ['Sleep', 'Personal', 'Work']},
	volume: {label: 'Volume', level: 70},
	alert: {
		title: 'Block Contact?',
		body: 'You will not receive phone calls, messages, or FaceTime from this contact.',
		cancel: 'Cancel',
		confirm: 'Block Contact',
	},
	blocked: 'Blocked',
} as const;
