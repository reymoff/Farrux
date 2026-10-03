import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {AccentText} from '../Accent';
import {C, FONT} from '../brand';
import {SceneWrap} from './SceneWrap';

export const Cta: React.FC<{title: string; keyword: string; note: string}> = ({title, keyword, note}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const pop = spring({frame: frame - 14, fps, config: {damping: 10}});
	const pulse = 1 + Math.sin(Math.max(0, frame - 30) / 6) * 0.03;

	return (
		<SceneWrap>
			<AccentText
				text={title}
				style={{fontFamily: FONT, fontWeight: 900, fontSize: 80, lineHeight: 1.08, color: C.white, textTransform: 'uppercase'}}
			/>
			<div
				style={{
					alignSelf: 'flex-start',
					marginTop: 50,
					padding: '30px 64px',
					borderRadius: 999,
					background: C.purple,
					color: C.white,
					fontFamily: FONT,
					fontWeight: 900,
					fontSize: 84,
					letterSpacing: 4,
					boxShadow: '0 0 90px rgba(154,110,234,0.7)',
					transform: `scale(${pop * pulse})`,
					transformOrigin: 'left center',
				}}
			>
				{keyword}
			</div>
			<div
				style={{
					marginTop: 40,
					fontFamily: FONT,
					fontWeight: 500,
					fontSize: 38,
					color: C.gray300,
					opacity: interpolate(frame, [30, 45], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
				}}
			>
				{note}
			</div>
		</SceneWrap>
	);
};
