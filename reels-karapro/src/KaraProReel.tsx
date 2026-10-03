import {AbsoluteFill, Img, Series, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {z} from 'zod';
import {Background} from './Background';
import {C, FONT, SAFE, SAFE_W} from './brand';
import {Logo} from './Logo';
import {Cta} from './scenes/Cta';
import {Hook} from './scenes/Hook';
import {Point} from './scenes/Point';
import {Stat} from './scenes/Stat';

export const reelSchema = z.object({
	handle: z.string(),
	kicker: z.string(),
	headline: z.string(),
	sub: z.string(),
	points: z.array(z.object({title: z.string(), text: z.string()})).min(1).max(5),
	stat: z.object({value: z.number(), prefix: z.string(), suffix: z.string(), label: z.string()}),
	cta: z.object({title: z.string(), keyword: z.string(), note: z.string()}),
	showSafeZones: z.boolean(),
});

export type ReelProps = z.infer<typeof reelSchema>;

// Длительности сцен в кадрах при 30 fps
export const T = {hook: 105, point: 84, stat: 84, cta: 120};
export const reelDuration = (p: ReelProps) => T.hook + p.points.length * T.point + T.stat + T.cta;

const Chrome: React.FC<{handle: string; total: number}> = ({handle, total}) => {
	const frame = useCurrentFrame();
	const progress = interpolate(frame, [0, total], [0, 1], {extrapolateRight: 'clamp'});
	return (
		<>
			<div style={{position: 'absolute', left: SAFE.left, top: SAFE.top}}>
				<Logo height={46} />
			</div>
			<div
				style={{
					position: 'absolute',
					left: SAFE.left,
					top: SAFE.bottom - 50,
					width: SAFE_W,
					display: 'flex',
					alignItems: 'center',
					gap: 24,
				}}
			>
				<span style={{fontFamily: FONT, fontWeight: 500, fontSize: 30, color: C.gray500}}>{handle}</span>
				<div style={{flex: 1, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.12)'}}>
					<div style={{width: `${progress * 100}%`, height: '100%', borderRadius: 2, background: C.purple}} />
				</div>
			</div>
		</>
	);
};

export const KaraProReel: React.FC<ReelProps> = (p) => {
	const total = reelDuration(p);
	return (
		<AbsoluteFill style={{backgroundColor: C.black}}>
			<Background />
			<Series>
				<Series.Sequence durationInFrames={T.hook}>
					<Hook kicker={p.kicker} headline={p.headline} sub={p.sub} />
				</Series.Sequence>
				{p.points.map((pt, i) => (
					<Series.Sequence key={i} durationInFrames={T.point}>
						<Point index={i} total={p.points.length} title={pt.title} text={pt.text} />
					</Series.Sequence>
				))}
				<Series.Sequence durationInFrames={T.stat}>
					<Stat {...p.stat} />
				</Series.Sequence>
				<Series.Sequence durationInFrames={T.cta}>
					<Cta {...p.cta} />
				</Series.Sequence>
			</Series>
			<Chrome handle={p.handle} total={total} />
			{p.showSafeZones ? <Img src={staticFile('ramka-instagram-1080x1920.png')} style={{position: 'absolute'}} /> : null}
		</AbsoluteFill>
	);
};
