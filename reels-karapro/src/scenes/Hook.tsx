import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {AccentText} from '../Accent';
import {C, FONT} from '../brand';
import {SceneWrap} from './SceneWrap';

export const Kicker: React.FC<{text: string}> = ({text}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const s = spring({frame, fps, config: {damping: 14}});
	return (
		<div
			style={{
				alignSelf: 'flex-start',
				transform: `scale(${s})`,
				transformOrigin: 'left center',
				padding: '14px 30px',
				borderRadius: 999,
				border: `2px solid ${C.purple}`,
				background: 'rgba(154,110,234,0.18)',
				color: C.purple300,
				fontFamily: FONT,
				fontWeight: 700,
				fontSize: 34,
				letterSpacing: 2,
				textTransform: 'uppercase',
				marginBottom: 44,
			}}
		>
			{text}
		</div>
	);
};

export const Hook: React.FC<{kicker: string; headline: string; sub: string}> = ({kicker, headline, sub}) => (
	<SceneWrap>
		<Kicker text={kicker} />
		<AccentText
			text={headline}
			delay={6}
			style={{
				fontFamily: FONT,
				fontWeight: 900,
				fontSize: 92,
				lineHeight: 1.05,
				textTransform: 'uppercase',
				color: C.white,
			}}
		/>
		<AccentText
			text={sub}
			delay={30}
			stagger={1}
			style={{fontFamily: FONT, fontWeight: 500, fontSize: 40, lineHeight: 1.35, color: C.gray300, marginTop: 40}}
		/>
	</SceneWrap>
);
