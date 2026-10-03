import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {AccentText} from '../Accent';
import {C, FONT} from '../brand';
import {SceneWrap} from './SceneWrap';

export const Point: React.FC<{index: number; total: number; title: string; text: string}> = ({
	index,
	total,
	title,
	text,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const s = spring({frame, fps, config: {damping: 200}});
	const num = String(index + 1).padStart(2, '0');

	return (
		<SceneWrap>
			<div
				style={{
					padding: '56px 52px',
					borderRadius: 36,
					background: C.card,
					border: `2px solid rgba(154,110,234,${0.25 + s * 0.45})`,
					boxShadow: `0 0 ${80 * s}px rgba(154,110,234,0.25)`,
					transform: `translateX(${interpolate(s, [0, 1], [120, 0])}px)`,
					opacity: s,
				}}
			>
				<div style={{display: 'flex', alignItems: 'baseline', gap: 18, marginBottom: 28}}>
					<span style={{fontFamily: FONT, fontWeight: 900, fontSize: 120, color: C.purple, lineHeight: 1}}>
						{num}
					</span>
					<span style={{fontFamily: FONT, fontWeight: 700, fontSize: 36, color: C.gray500}}>
						/ {String(total).padStart(2, '0')}
					</span>
				</div>
				<AccentText
					text={title}
					delay={6}
					style={{fontFamily: FONT, fontWeight: 900, fontSize: 64, lineHeight: 1.1, color: C.white, textTransform: 'uppercase'}}
				/>
				<AccentText
					text={text}
					delay={18}
					stagger={1}
					style={{fontFamily: FONT, fontWeight: 500, fontSize: 38, lineHeight: 1.4, color: C.gray300, marginTop: 28}}
				/>
			</div>
		</SceneWrap>
	);
};
