import {Config} from '@remotion/cli/config';

// Lossless frames into the encoder. Codec settings (H.264 CRF 15, yuv420p,
// bt709, AAC 320k — spec §9) live in the npm scripts so audio-only checks
// (wav) can use the same config.
Config.setVideoImageFormat('png');
Config.setOverwriteOutput(true);
Config.setDelayRenderTimeoutInMilliseconds(120_000);

// Use a preinstalled Chromium when the machine has one (e.g. CI / sandboxes).
if (process.env.REMOTION_BROWSER_EXECUTABLE) {
	Config.setBrowserExecutable(process.env.REMOTION_BROWSER_EXECUTABLE);
}
if (process.env.REMOTION_CONCURRENCY) {
	Config.setConcurrency(Number(process.env.REMOTION_CONCURRENCY));
}
