import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {AccentText} from '../Accent';
import {C, FONT} from '../brand';
import {SceneWrap} from './SceneWrap';

export const Stat: React.FC<{value: number; prefix: string; suffix: string; label: string}> = ({
	value,
	prefix,
	suffix,
	label,
}) => {
	const frame = useCurrentFrame();
	const n = interpolate(frame, [0, 40], [0, value], {
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});

	return (
		<SceneWrap>
			<div
				style={{
					fontFamily: FONT,
					fontWeight: 900,
					fontSize: 230,
					lineHeight: 1,
					color: C.purple,
					textShadow: '0 0 80px rgba(154,110,234,0.55)',
					fontVariantNumeric: 'tabular-nums',
				}}
			>
				{prefix}
				{Math.round(n).toLocaleString('ru-RU')}
				{suffix}
			</div>
			<AccentText
				text={label}
				delay={20}
				style={{fontFamily: FONT, fontWeight: 700, fontSize: 52, lineHeight: 1.2, color: C.white, marginTop: 30}}
			/>
		</SceneWrap>
	);
};
