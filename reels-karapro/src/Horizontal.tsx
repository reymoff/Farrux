import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {z} from 'zod';
import {AccentText} from './Accent';
import {Background} from './Background';
import {C, FONT} from './brand';
import {Logo} from './Logo';

// Плашка-заголовок поверх горизонтального видео (рендер с альфой)
export const hookOverlaySchema = z.object({kicker: z.string(), title: z.string()});

export const HookOverlay: React.FC<z.infer<typeof hookOverlaySchema>> = ({kicker, title}) => {
	const frame = useCurrentFrame();
	const {fps, durationInFrames} = useVideoConfig();
	const s = spring({frame, fps, config: {damping: 200}});
	const out = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					right: 36,
					top: 36,
					maxWidth: 330,
					padding: '18px 24px 22px',
					borderRadius: 24,
					background: 'rgba(0,0,0,0.72)',
					border: `2px solid ${C.purple}`,
					boxShadow: '0 0 50px rgba(154,110,234,0.45)',
					opacity: s * out,
					transform: `translateX(${interpolate(s, [0, 1], [60, 0])}px)`,
				}}
			>
				<div
					style={{
						fontFamily: FONT,
						fontWeight: 700,
						fontSize: 18,
						letterSpacing: 2,
						color: C.purple300,
						textTransform: 'uppercase',
						marginBottom: 8,
					}}
				>
					{kicker}
				</div>
				<AccentText
					text={title}
					delay={6}
					style={{fontFamily: FONT, fontWeight: 900, fontSize: 34, lineHeight: 1.08, color: C.white, textTransform: 'uppercase'}}
				/>
			</div>
		</AbsoluteFill>
	);
};

// Финальная заставка с кодовым словом
export const endCardSchema = z.object({title: z.string(), keyword: z.string(), note: z.string(), handle: z.string()});

export const EndCard: React.FC<z.infer<typeof endCardSchema>> = ({title, keyword, note, handle}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const fadeIn = interpolate(frame, [0, 6], [0, 1], {extrapolateRight: 'clamp'});
	const pop = spring({frame: frame - 10, fps, config: {damping: 10}});
	const pulse = 1 + Math.sin(Math.max(0, frame - 25) / 6) * 0.03;

	return (
		<AbsoluteFill style={{opacity: fadeIn}}>
			<Background />
			<AbsoluteFill style={{padding: '60px 80px', justifyContent: 'center'}}>
				<div style={{position: 'absolute', left: 80, top: 50}}>
					<Logo height={40} />
				</div>
				<AccentText
					text={title}
					style={{fontFamily: FONT, fontWeight: 900, fontSize: 64, lineHeight: 1.05, color: C.white, textTransform: 'uppercase'}}
				/>
				<div style={{display: 'flex', alignItems: 'center', gap: 30, marginTop: 36}}>
					<div
						style={{
							padding: '18px 56px',
							borderRadius: 999,
							background: C.purple,
							color: C.white,
							fontFamily: FONT,
							fontWeight: 900,
							fontSize: 76,
							letterSpacing: 4,
							boxShadow: '0 0 80px rgba(154,110,234,0.7)',
							transform: `scale(${pop * pulse})`,
						}}
					>
						{keyword}
					</div>
					<div
						style={{
							fontFamily: FONT,
							fontWeight: 700,
							fontSize: 38,
							color: C.gray300,
							opacity: interpolate(frame, [22, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
						}}
					>
						{note}
					</div>
				</div>
				<div style={{position: 'absolute', left: 80, bottom: 50, fontFamily: FONT, fontWeight: 500, fontSize: 26, color: C.gray500}}>
					{handle}
				</div>
			</AbsoluteFill>
		</AbsoluteFill>
	);
};
