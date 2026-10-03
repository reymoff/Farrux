import '@fontsource/montserrat/500.css';
import '@fontsource/montserrat/700.css';
import '@fontsource/montserrat/900.css';

// Токены из брендбука KaraPro 2024 (актуальный фиолетовый #9A6EEA, не #7B5CE4)
export const C = {
	black: '#000000',
	white: '#FFFFFF',
	purple: '#9A6EEA',
	purple300: '#D0A6F7',
	purple700: '#553A9E',
	gray300: '#C3C3C3',
	gray500: '#818181',
	card: '#0B0B0C',
};

export const FONT = 'Montserrat, sans-serif';

// Безопасная зона Reels 1080x1920: верх 200, иконки справа 130, ник/описание с 1190
export const SAFE = {left: 70, right: 1080 - 150, top: 230, bottom: 1170};
export const SAFE_W = SAFE.right - SAFE.left;

// Текст с акцентом: *слово* красится в purple300
export const splitAccent = (text: string) =>
	text.split(/(\*[^*]+\*)/g).filter(Boolean).map((part) =>
		part.startsWith('*') ? {t: part.slice(1, -1), hl: true} : {t: part, hl: false},
	);
