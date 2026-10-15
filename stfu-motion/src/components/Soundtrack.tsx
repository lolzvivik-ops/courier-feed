import React from 'react';
import {Audio, Sequence, getStaticFiles, staticFile, useVideoConfig} from 'remotion';
import {AUDIO_START, SFX_REF_DBFS, TRACK_RMS_DBFS} from '../config';
import {DURATION_SEC, SFX, SFX_FILES} from '../timeline';

/** Mono SFX are spread to stereo at -3 dB per channel (equal-power), measured by check_mix.py. */
const MONO_PAN_DB = 3;
/** dB under the track → linear volume for a file normalised to SFX_REF_DBFS. */
const dbToGain = (db: number) => 10 ** ((db + TRACK_RMS_DBFS - SFX_REF_DBFS + MONO_PAN_DB) / 20);

/**
 * The track (main) + quiet UI sounds on the events (spec §7).
 * `npm run audio` writes public/generated/track.wav: the fragment cut from the
 * same decode the beat analysis used, with the pre-drop lowpass dip, peaks at
 * -1.5 dBFS. Without it we fall back to the raw MP3 (no dip, no headroom).
 */
export const Soundtrack: React.FC = () => {
	const {fps} = useVideoConfig();
	const files = getStaticFiles().map((f) => f.name);
	const prepared = files.includes('generated/track.wav');
	const hasMp3 = files.includes('stfu.mp3');
	if (!prepared && !hasMp3) {
		throw new Error('Missing track: put the song at public/stfu.mp3 and run `npm run audio`. No substitutes.');
	}
	return (
		<>
			{prepared ? (
				<Audio src={staticFile('generated/track.wav')} />
			) : (
				<Audio src={staticFile('stfu.mp3')} trimBefore={Math.round(AUDIO_START * fps)} trimAfter={Math.round((AUDIO_START + DURATION_SEC) * fps)} />
			)}
			{SFX.map((s) => {
				const from = Math.round(((s.t - (SFX_FILES[s.file as keyof typeof SFX_FILES].pre * 60) / 1000) * fps) / 60);
				return (
					<Sequence key={s.id} from={Math.max(0, from)} name={`sfx:${s.id}`} layout="none">
						<Audio src={staticFile(`sfx/${s.file}.wav`)} volume={dbToGain(s.gainDb)} />
					</Sequence>
				);
			})}
		</>
	);
};
