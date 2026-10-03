# Farrux: видео-кит для Claude Code

Открой репо в Claude Code, и хук `SessionStart` сам поставит всё ниже (`scripts/setup-video-kit.sh`, повторный запуск ~5 сек).

| # | Что | Зачем | Тип |
|---|-----|-------|-----|
| 1 | [HyperFrames](https://github.com/heygen-com/hyperframes) | HTML в MP4: титры, сцены | плагин |
| 2 | [Remotion skills](https://github.com/remotion-dev/skills) | видео на React, субтитры, рендер | скиллы `remotion-*` |
| 3 | [taste-skill](https://github.com/Leonxlnx/taste-skill) | анти-шаблонный дизайн | скиллы `design-taste-*` и др. |
| 4 | [impeccable](https://github.com/pbakaus/impeccable) | `/impeccable audit`, `polish` и ещё 22 | плагин |
| 5 | [Emil Kowalski skills](https://github.com/emilkowalski/skills) | анимации: кривые, тайминги | скиллы `animate`, `emil-design-eng` |
| 6 | [video-use](https://github.com/browser-use/video-use) | режет сырое видео по расшифровке | скилл, нужен `ELEVENLABS_API_KEY` в `~/video-use/.env` |
| 7 | [frontend-design](https://github.com/anthropics/claude-plugins-official) | выразительные кадры и страницы | плагин |

## Шаблон рилса KaraPro

`reels-karapro/`: готовый ролик на Remotion в стиле KaraPro, тексты меняются без кода. Подробности в его README.

## Рамка зон Instagram

`assets/ramka-instagram-1080x1920.png`: прозрачный PNG 1080×1920. Кладёшь верхним слоем, смотришь, что закроет интерфейс Reels.
Верх 200 px, низ 320 px, иконки справа 130 px, ник и описание от 1190 px.

## Шрифты

- [fontshare.com](https://www.fontshare.com) бесплатные, лицензию смотри у каждого
- [fontesk.com](https://fontesk.com) подборки
- [fontjoy.com](https://fontjoy.com) пары шрифтов

Remotion бесплатен для частных лиц и компаний до 3 человек, дальше платно (их LICENSE.md).
