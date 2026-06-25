# netmon-web

Веб-приложение для диагностики сети: ping, traceroute, MTR, HTTP-проверки, DNS, массовый мониторинг сайтов.

## Быстрый запуск (одной командой)

Скачивает последний релиз, распаковывает в домашнюю папку, ставит зависимости и запускает.

### Linux / macOS

```bash
curl -L https://github.com/mnekrasovv/netmon-web/releases/latest/download/netmon-web.zip -o /tmp/netmon-web.zip && unzip -oq /tmp/netmon-web.zip -d ~ && bash ~/netmon-web/run.sh
```

### Windows (PowerShell)

```powershell
iwr https://github.com/mnekrasovv/netmon-web/releases/latest/download/netmon-web.zip -OutFile $env:TEMP\netmon-web.zip; Expand-Archive -Force $env:TEMP\netmon-web.zip $env:USERPROFILE; & "$env:USERPROFILE\netmon-web\run.bat"
```

### Windows (cmd)

```cmd
powershell -Command "iwr https://github.com/mnekrasovv/netmon-web/releases/latest/download/netmon-web.zip -OutFile $env:TEMP\netmon-web.zip; Expand-Archive -Force $env:TEMP\netmon-web.zip $env:USERPROFILE" && "%USERPROFILE%\netmon-web\run.bat"
```

После запуска откроется `http://127.0.0.1:8765` в браузере. Скрипт сам создаст `.venv`, поставит `fastapi`, `uvicorn`, `requests`. Нужен только Python 3.8+.

## Ручная установка

```bash
git clone https://github.com/mnekrasovv/netmon-web.git
cd netmon-web
bash run.sh        # Linux
# или
run.bat            # Windows
```

## Возможности

- **Dashboard** — обзор системы, внешний IP, шлюз, количество хостов и отчётов
- **Diagnose** — интерактивные тесты (Ping / Traceroute / MTR / HTTP / DNS / Внешний IP / Sysinfo / Интерфейсы / Соединения / ARP) с live-выводом через Server-Sent Events
- **Monitor** — массовый мониторинг сайтов из `sites.json` параллельно, с графиками статусов и категорий, фильтром и сортировкой
- **Hosts** — управление списком хостов (CRUD)
- **Reports** — сохранённые отчёты (txt / html / json) с просмотром, скачиванием, удалением

Кастомные хосты можно добавить прямо в табе Diagnose без редактирования конфига.

## Структура

```
netmon-web/
├── server.py          # FastAPI app
├── core/              # ping, trace, dns, http, sysinfo, hosts, batch, reports
├── static/            # SPA: HTML + CSS + Vanilla JS + Chart.js (CDN)
├── configs/           # hosts.conf, sites.json
├── reports/           # сохранённые отчёты
├── run.bat / run.sh   # лаунчеры с автоустановкой
└── requirements.txt
```

## Порт

`127.0.0.1:8765` — только локально, никаких внешних соединений принимать не будет.

Сменить порт: `python server.py --port 9000` (или `run.sh --port 9000`).

## Лицензия

[MIT](LICENSE)
