import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {SAFE, SAFE_W} from '../brand';

// Плавный вход и уход сцены, контент только внутри безопасной зоны
export const SceneWrap: React.FC<{children: React.ReactNode; justify?: 'center' | 'flex-start'}> = ({
	children,
	justify = 'center',
}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const out = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	return (
		<AbsoluteFill
			style={{
				left: SAFE.left,
				top: SAFE.top + 90,
				width: SAFE_W,
				height: SAFE.bottom - SAFE.top - 160,
				justifyContent: justify,
				opacity: out,
				transform: `translateY(${interpolate(out, [0, 1], [-30, 0])}px)`,
			}}
		>
			{children}
		</AbsoluteFill>
	);
};
