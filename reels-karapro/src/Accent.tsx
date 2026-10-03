import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, splitAccent} from './brand';

type Seg = {t: string; hl: boolean};

// Режем на слова, сохраняя акцент; знаки препинания без пробела липнут к предыдущему слову
const toWords = (text: string): Seg[][] => {
	const words: Seg[][] = [];
	let prevEndsWithSpace = true;
	for (const part of splitAccent(text)) {
		part.t.split(/(\s+)/).forEach((chunk, i) => {
			if (!chunk || /^\s+$/.test(chunk)) return;
			const glued = i === 0 && !prevEndsWithSpace && words.length > 0;
			if (glued) words[words.length - 1].push({t: chunk, hl: part.hl});
			else words.push([{t: chunk, hl: part.hl}]);
		});
		prevEndsWithSpace = /\s$/.test(part.t);
	}
	return words;
};

// Слова выезжают по одному, акцентные красятся в purple300
export const AccentText: React.FC<{
	text: string;
	style: React.CSSProperties;
	delay?: number;
	stagger?: number;
}> = ({text, style, delay = 0, stagger = 3}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	return (
		<div style={{...style, display: 'flex', flexWrap: 'wrap', columnGap: '0.28em'}}>
			{toWords(text).map((segs, i) => {
				const s = spring({frame: frame - delay - i * stagger, fps, config: {damping: 200}});
				return (
					<span
						key={i}
						style={{display: 'inline-block', opacity: s, transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)`}}
					>
						{segs.map((seg, j) => (
							<span key={j} style={seg.hl ? {color: C.purple300} : undefined}>
								{seg.t}
							</span>
						))}
					</span>
				);
			})}
		</div>
	);
};
