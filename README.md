# netmon-web

Веб-приложение для диагностики сети: ping, traceroute, MTR, HTTP-проверки, DNS, TCP-порты, whois, массовый мониторинг сайтов. UI в браузере, тёмная/светлая темы, парсинг вывода в карточки и таблицы.

## Быстрый запуск

### Вариант 1 — скачать установщик (самое простое)

В [последнем релизе](https://github.com/mnekrasovv/netmon-web/releases/latest) есть готовые `install.bat` и `install.sh`. Скачать один файл → запустить → дальше всё само.

### Вариант 2 — одной командой из терминала

**Linux / macOS**

```bash
curl -L https://github.com/mnekrasovv/netmon-web/releases/latest/download/netmon-web.zip -o /tmp/netmon-web.zip && unzip -oq /tmp/netmon-web.zip -d ~ && bash ~/netmon-web/run.sh
```

**Windows (PowerShell)**

```powershell
iwr https://github.com/mnekrasovv/netmon-web/releases/latest/download/netmon-web.zip -OutFile $env:TEMP\netmon-web.zip; Expand-Archive -Force $env:TEMP\netmon-web.zip $env:USERPROFILE; & "$env:USERPROFILE\netmon-web\run.bat"
```

**Windows (cmd)**

```cmd
powershell -Command "iwr https://github.com/mnekrasovv/netmon-web/releases/latest/download/netmon-web.zip -OutFile $env:TEMP\netmon-web.zip; Expand-Archive -Force $env:TEMP\netmon-web.zip $env:USERPROFILE" && "%USERPROFILE%\netmon-web\run.bat"
```

После запуска откроется `http://127.0.0.1:8765` в браузере. Скрипт сам создаёт `.venv`, ставит `fastapi`, `uvicorn`, `requests`. Нужен только Python 3.8+.

### Вариант 3 — git clone

```bash
git clone https://github.com/mnekrasovv/netmon-web.git
cd netmon-web
bash run.sh        # Linux / macOS
# или
run.bat            # Windows
```

## Возможности

Семь разделов в боковой навигации:

- **Dashboard** — обзор системы (ОС, hostname, uptime, внешний IP, шлюз) + **Live availability** с плитками флагман-сервисов (Google / YouTube / GitHub / Telegram / Cloudflare DNS и др.), авто-обновление с конфигурируемым интервалом, sparkline истории latency
- **Diagnose** — интерактивные тесты с выбором хостов и тестов:
  - Ping / Traceroute / MTR (pure-Python fallback если нет нативного mtr) / HTTP
  - DNS-матрица (системный + Google/Cloudflare/Yandex/Quad9 × 5 доменов)
  - Внешний IP с гео-инфой / Система / Интерфейсы / Соединения / ARP
  - **Parsed view** — структурные карточки/таблицы с мини-графиками RTT, **Raw view** — консольный вывод (переключатель)
  - **Smart-подсказки** после прогона: правила анализа (ISP-проблема, плохой DNS, узкое место в MTR, кэш-перехват и т.д.)
  - Сохранение отчёта в txt (raw) + json (parsed)
- **Monitor** — массовая параллельная проверка `sites.json` с прогресс-баром, диаграммами по статусам и категориям, фильтром и сортировкой таблицы, экспортом HTML + JSON
- **Tools** — отдельные сетевые утилиты:
  - **TCP-порт чекер** с пресетами (`http`, `https`, `ssh`, `mysql`, `postgres`, `rdp`, `minecraft` и др.)
  - **nslookup** для A / AAAA / MX / NS / TXT / CNAME + автоматический reverse DNS для IP
  - **Whois** с парсингом registrar / organization / created / expires / name servers
- **Hosts** — управление списком хостов из `hosts.conf` (CRUD)
- **Sites editor** — полноценный редактор `sites.json`: категории + сайты, bulk-import, переименование, сброс к default
- **Reports** — сохранённые отчёты (txt / html / json) с просмотром в модалке, скачиванием, удалением

Дополнительно:
- **Переключатель тёмной/светлой темы** (тоггл в нижнем углу sidebar, запоминается в localStorage)
- **Индикатор версии и обновлений** в sidebar: показывает текущую версию, при наличии нового релиза подсвечивает и предлагает открыть страницу обновления
- **Live availability — настраиваемый список:** кнопка «Настроить» открывает редактор сервисов плитки на dashboard (host port name построчно)
- **Кнопка «Открыть папку»** в Reports — открывает папку отчётов в системном файловом менеджере
- Кастомные хосты добавляются прямо в Diagnose без редактирования конфига
- Long-running команды стримятся через **Server-Sent Events** (live-вывод по мере прихода)
- **install.bat / install.sh** запоминают установку: повторный запуск из той же копии не качает заново. Zip сохраняется в `~/Downloads/`, а не в TEMP. На Windows при отсутствии Python подтягивается **embeddable Python 3.11** в папку приложения (без админ-прав)

## Структура

```
netmon-web/
├── server.py                 # FastAPI app, ~30 эндпоинтов
├── core/
│   ├── runner.py             # subprocess + hard timeout/kill
│   ├── ping.py               # ping_stream + ping_stats
│   ├── trace.py              # traceroute + pure-Python MTR
│   ├── dns_check.py          # DNS-матрица и резолверы
│   ├── http_check.py         # HTTP проверки + external IP
│   ├── tcp_check.py          # TCP-порт чекер
│   ├── lookup.py             # whois (raw socket) + nslookup
│   ├── sysinfo.py            # система / интерфейсы / соединения / ARP
│   ├── parsers.py            # парсинг raw вывода в структуры
│   ├── hosts.py              # CRUD hosts.conf
│   ├── sites.py              # CRUD sites.json
│   ├── batch.py              # параллельная массовая проверка
│   ├── live_dashboard.py     # live availability tiles
│   ├── suggestions.py        # rule-based анализ результатов
│   └── reports.py            # сохранение/листинг отчётов
├── static/
│   ├── index.html            # SPA — sidebar layout, 7 табов
│   ├── css/style.css         # темы dark/light через CSS-переменные
│   └── js/                   # api, theme, icons, render, hosts, sites,
│                             # diagnose, monitor, tools, dashboard, reports, app
├── configs/
│   ├── hosts.conf            # формат: host|name|cat
│   └── sites.json            # категории сайтов для Monitor
├── reports/                  # сохранённые отчёты
├── run.bat / run.sh          # лаунчеры с автоустановкой в venv
└── requirements.txt          # fastapi, uvicorn, requests
```

## Порт

`127.0.0.1:8765` — только локально, никаких внешних соединений принимать не будет.

Сменить порт: `python server.py --port 9000` (или `bash run.sh --port 9000`).

## Лицензия

[MIT](LICENSE)
