# Шаблон рилса KaraPro (Remotion)

1080×1920, 30 fps, ~19 сек. Чёрный фон, гекс-сетка, фиолетовое свечение #9A6EEA, Montserrat 900 капсом, логомарк KaraPro.
Весь текст лежит в безопасной зоне Reels: ниже 230 px, выше 1170 px, левее 930 px.

## Запуск

```bash
npm i
npm run studio    # редактор в браузере, тексты правятся справа в панели Props
npm run render    # out/reel.mp4
```

## Структура ролика

| Сцена | Длина | Поля |
|---|---|---|
| Хук | 3.5 с | `kicker`, `headline`, `sub` |
| Пункты (1–5 шт.) | 2.8 с каждый | `points[].title`, `points[].text` |
| Цифра | 2.8 с | `stat.value` (считается от 0), `prefix`, `suffix`, `label` |
| Призыв | 4 с | `cta.title`, `cta.keyword`, `cta.note` |

Длина ролика пересчитывается сама от числа пунктов. Тайминги в `T` в `src/KaraProReel.tsx`.

- `*слово*` в любом тексте красится в светло-фиолетовый.
- `showSafeZones: true` накладывает рамку зон Instagram поверх кадра для проверки.

Рендер из CLI со своими текстами:

```bash
npx remotion render src/index.ts KaraProReel out/my.mp4 --props=./my-props.json
```

Лицензия Remotion: бесплатно для частных лиц и компаний до 3 человек, дальше нужна платная лицензия.
