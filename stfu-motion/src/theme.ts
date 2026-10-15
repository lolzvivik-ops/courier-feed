import {createContext, useContext} from 'react';

/** Design tokens (spec §3). */
export type Theme = {
	name: 'light' | 'dark';
	bg: {inner: string; mid: string; outer: string};
	text: string;
	card: string;
	/** grouped/inset rows inside a card */
	cardInset: string;
	label: string;
	secondary: string;
	tertiary: string;
	separator: string;
	/** top-edge highlight of cards */
	rim: string;
	/** light from the top-left, laid over card surfaces */
	sheen: string;
	shadowAlpha: number;
	bubbleIn: string;
	bubbleInText: string;
	floater: string;
	grainOpacity: number;
};

export const IOS = {
	blue: '#0A84FF',
	red: '#FF453A',
	green: '#30D158',
	indigo: '#5E5CE6',
	orange: 'linear-gradient(180deg, #FFB547 0%, #FF7A1A 100%)',
	messages: 'linear-gradient(180deg, #67F07F 0%, #1DC63F 100%)',
	phone: 'linear-gradient(180deg, #67F07F 0%, #1DC63F 100%)',
};

export const LIGHT: Theme = {
	name: 'light',
	bg: {inner: '#F8F8FA', mid: '#F2F2F5', outer: '#ECECF0'},
	text: '#0B0B0E',
	card: '#FFFFFF',
	cardInset: '#F2F2F7',
	label: '#000000',
	secondary: 'rgba(60, 60, 67, 0.6)',
	tertiary: 'rgba(60, 60, 67, 0.3)',
	separator: 'rgba(60, 60, 67, 0.18)',
	rim: 'rgba(255, 255, 255, 1)',
	sheen: 'linear-gradient(150deg, rgba(255,255,255,0) 30%, rgba(236,236,242,0.55) 100%)',
	shadowAlpha: 1,
	bubbleIn: '#E9E9EB',
	bubbleInText: '#000000',
	floater: '#FFFFFF',
	grainOpacity: 0.028,
};

export const DARK: Theme = {
	name: 'dark',
	bg: {inner: '#121216', mid: '#0B0B0E', outer: '#060608'},
	text: '#F5F5F7',
	card: '#1C1C1E',
	cardInset: '#2C2C2E',
	label: '#FFFFFF',
	secondary: 'rgba(235, 235, 245, 0.6)',
	tertiary: 'rgba(235, 235, 245, 0.3)',
	separator: 'rgba(84, 84, 88, 0.6)',
	rim: 'rgba(255, 255, 255, 0.14)',
	sheen: 'linear-gradient(150deg, rgba(255,255,255,0.055) 0%, rgba(255,255,255,0) 45%)',
	shadowAlpha: 5,
	bubbleIn: '#262629',
	bubbleInText: '#FFFFFF',
	floater: '#2A2A2E',
	grainOpacity: 0.035,
};

export const ThemeContext = createContext<Theme>(LIGHT);
export const useTheme = () => useContext(ThemeContext);

export const FONT = {
	display: '"Inter Tight", "Inter", system-ui, sans-serif',
	ui: '"Inter", system-ui, sans-serif',
};
