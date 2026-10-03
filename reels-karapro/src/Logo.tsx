import {C, FONT} from './brand';

// Логомарк KaraPro: 4 полигона из фирменного SVG, viewBox 990x960
export const Logo: React.FC<{height?: number; color?: string; withText?: boolean}> = ({
	height = 44,
	color = C.purple,
	withText = true,
}) => (
	<div style={{display: 'flex', alignItems: 'center', gap: height * 0.35}}>
		<svg height={height} viewBox="0 0 990 960">
			<polygon points="360,360 360,0 660,0 480,360" fill={color} />
			<polygon points="360,840 360,480 480,480 660,840" fill={color} />
			<polygon points="780,0 570,420 780,840 990,420" fill={color} />
			<rect x={0} y={0} width={240} height={960} fill={color} />
		</svg>
		{withText ? (
			<span style={{fontFamily: FONT, fontWeight: 700, fontSize: height * 0.8, color: C.white}}>
				KaraPro
			</span>
		) : null}
	</div>
);
