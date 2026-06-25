# netmon-web

Веб-приложение для диагностики сети: ping, traceroute, MTR, HTTP-проверки, DNS, массовый мониторинг сайтов.

## Запуск

**Windows:** двойной клик на `run.bat`
**Linux:**   `bash run.sh`

Откроется `http://127.0.0.1:8765` в браузере.

Скрипт создаёт `.venv`, ставит зависимости автоматически. Нужен Python 3.8+.

## Возможности

- Интерактивная диагностика (Ping / Traceroute / MTR / HTTP / DNS / Внешний IP / Системная информация / Интерфейсы / Соединения)
- Массовый мониторинг сайтов из `sites.json` (параллельно, с графиками и статусами)
- Управление хостами (CRUD)
- Конструктор отчётов (txt / html / json)
- Live-стрим вывода команд (Server-Sent Events)
- Кастомные хосты на лету

## Структура

```
netmon-web/
├── server.py          # FastAPI app
├── core/              # ping, trace, dns, http, sysinfo, hosts, batch, reports
├── static/            # SPA: HTML + CSS + Vanilla JS
├── configs/           # hosts.conf, sites.json, settings.json
├── reports/           # сохранённые отчёты
├── run.bat / run.sh   # лаунчеры с автоустановкой
└── requirements.txt
```

## Порт

`127.0.0.1:8765` (только локально, никаких внешних соединений)
