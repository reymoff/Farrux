// Проверка синтаксиса скрипта страницы: node tests/check.js (из папки mafia)
const s = require("fs").readFileSync(__dirname + "/../app/index.html", "utf8");
const m = s.match(/<script>([\s\S]*?)<\/script>/g);
new Function(m[m.length - 1].replace(/<\/?script>/g, ""));
console.log("syntax ok");
