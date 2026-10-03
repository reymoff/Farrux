import {Composition} from 'remotion';
import {KaraProReel, reelDuration, reelSchema, type ReelProps} from './KaraProReel';

const defaults: ReelProps = {
	handle: '@karapro.agency',
	kicker: 'Таргет в Нукусе',
	headline: 'Почему реклама *сливает бюджет*',
	sub: 'Три ошибки, которые я вижу в каждом втором кабинете',
	points: [
		{title: 'Нет *оффера*', text: 'Человек видит «скидки», но не понимает, зачем писать именно вам.'},
		{title: 'Широкая *аудитория*', text: 'Весь Узбекистан вместо Нукуса и района, где живут клиенты.'},
		{title: 'Креатив *без хука*', text: 'Первые 2 секунды решают всё. Нет зацепки, нет просмотра.'},
	],
	stat: {value: 3, prefix: 'x', suffix: '', label: 'больше заявок после *разбора* ошибок'},
	cta: {title: 'Хочешь разбор *своего кабинета*?', keyword: 'РАЗБОР', note: 'Напиши это слово в директ'},
	showSafeZones: false,
};

export const RemotionRoot: React.FC = () => (
	<Composition
		id="KaraProReel"
		component={KaraProReel}
		schema={reelSchema}
		defaultProps={defaults}
		width={1080}
		height={1920}
		fps={30}
		durationInFrames={reelDuration(defaults)}
		calculateMetadata={({props}: {props: ReelProps}) => ({durationInFrames: reelDuration(props)})}
	/>
);
