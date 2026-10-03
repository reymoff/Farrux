import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C} from './brand';

const HEX_W = 60;
const HEX_H = 104;

export const Background: React.FC = () => {
	const frame = useCurrentFrame();
	const drift = interpolate(frame, [0, 900], [0, -HEX_H], {extrapolateRight: 'extend'});
	const glowX = 30 + Math.sin(frame / 90) * 6;
	const glowY = 22 + Math.cos(frame / 110) * 4;

	return (
		<AbsoluteFill style={{backgroundColor: C.black}}>
			<AbsoluteFill
				style={{
					background: `radial-gradient(circle at ${glowX}% ${glowY}%, rgba(154,110,234,0.32) 0%, rgba(85,58,158,0.12) 30%, rgba(0,0,0,0) 60%)`,
				}}
			/>
			<svg width={1080} height={1920 + HEX_H} style={{position: 'absolute', top: drift % HEX_H}}>
				<defs>
					<pattern id="hex" width={HEX_W} height={HEX_H} patternUnits="userSpaceOnUse">
						<path
							d={`M${HEX_W / 2} 0 L${HEX_W} ${HEX_H / 6} L${HEX_W} ${HEX_H / 2} L${HEX_W / 2} ${(HEX_H * 2) / 3} L0 ${HEX_H / 2} L0 ${HEX_H / 6} Z M${HEX_W / 2} ${(HEX_H * 2) / 3} L${HEX_W / 2} ${HEX_H}`}
							fill="none"
							stroke={C.purple}
							strokeOpacity={0.12}
							strokeWidth={1.2}
						/>
					</pattern>
				</defs>
				<rect width="100%" height="100%" fill="url(#hex)" />
			</svg>
			<AbsoluteFill
				style={{background: 'linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,0.85) 100%)'}}
			/>
		</AbsoluteFill>
	);
};
