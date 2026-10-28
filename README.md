# bot_redonats — мост DonationAlerts → Twitch-чат

Асинхронный Python-сервис: читает алерты о донатах и других событиях из RabbitMQ,
форматирует сообщение и публикует его в обменник, откуда его забирает Twitch-бот.

Сбор алертов с DonationAlerts происходит **вне этого репозитория** — здесь только воркер.

## Архитектура

```
Внешний продюсер (вне репозитория)
        │
        ▼
  RabbitMQ (RABBIT_ALERTS) ── очередь "donations_alerts"
        │
        ▼
  donats_worker.py
        │
  RabbitConsumer → DonatEventHandler (форматирование)
        │
  Sender ──► RabbitMQ Exchange ("twitch_out")
                    │
                    ▼
              Twitch-чат (отдельный сервис)
```

### Поток сообщения

1. Внешний продюсер публикует полезную нагрузку алерта в очередь `donations_alerts`
   на брокере `RABBIT_ALERTS`.
2. `RabbitConsumer.worker_wrapper()` принимает сообщение и вызывает
   `DonatEventHandler.on_message`.
3. `AlertEventSchema` (Marshmallow) валидирует payload и превращает его в dataclass
   `AlertEvent`.
4. `handle_event()` выбирает обработчик по типу события (`DONATION`, `FOLLOW`,
   `SUBSCRIBE`) и формирует текст для чата.
5. `Sender.send_message()` через `Publisher` публикует `FQueueMessage` в обменник
   `twitch_out`.
6. Twitch-бот (отдельный сервис) читает сообщения из `twitch_out`.

### Обработка ошибок

- `on_message` логирует сбой и пробрасывает исключение дальше.
- Обёртка в `RabbitConsumer` перехватывает ошибку, логирует её и делает `reject`
  сообщения — потребление продолжается.

## Совместимость payload'ов

`AlertEventSchema` понимает два формата:

- **legacy** — с полем `alert_type` (тип события передаётся числом);
- **сырой донат** — без `alert_type` (payload из Centrifugo); трактуется как
  `DONATION`, имя донора берётся из `username`, иначе из `name`.

Суммы выводятся как есть: конвертации валют и подавления дублей в этом сервисе нет.

## Стек

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) — менеджер зависимостей
- [FastStream](https://faststream.airt.ai/) (`faststream[rabbit]`) — RabbitMQ
- Marshmallow / marshmallow-enum — валидация payload'ов
- Pydantic — модели сообщений очереди
- Sentry (`sentry-sdk`) — трекинг ошибок
- Ruff — линт и форматирование, Pyright — проверка типов
- pytest + pytest-asyncio — тесты

## Структура

```
.
├── donats_worker.py       # точка входа: RabbitMQ → Twitch-чат
├── donats/
│   ├── consumer.py        # RabbitConsumer — подписка с ручным ack
│   ├── publisher.py       # Publisher — ленивое подключение к RabbitMQ
│   ├── sender.py          # Sender — публикация сообщений в чат
│   ├── handlers.py        # DonatEventHandler — обработчики событий
│   ├── models.py          # AlertEvent + перечисления
│   ├── queue_models.py    # FQueueMessage / FQueueEvent (Pydantic)
│   ├── schemas.py         # Marshmallow-схема payload → AlertEvent
│   ├── settings.py        # конфигурация из переменных окружения
│   └── utils.py           # logger_setup (консоль + Sentry)
├── services/              # systemd-юнит для продакшена
├── tests/units/           # юнит-тесты
├── .github/workflows/     # CI и деплой
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## Быстрый старт

### Установка зависимостей

```bash
make dev        # uv sync --dev
```

### Настройка окружения

Скопируйте `.env` (он в `.gitignore`) и укажите как минимум адрес брокера:

```dotenv
RABBIT_URL=amqp://user:password@localhost:5672/
RABBIT_VHOST=gunlinux_bot
RABBIT_ALERTS=amqp://user:password@alerts-host:5672/vhost
```

Если `RABBIT_ALERTS` не задан, используется значение `RABBIT_URL`.

### Запуск

```bash
uv run python donats_worker.py
```

Отдельного CLI нет: скрипт сразу вызывает `asyncio.run(main())`.

## Переменные окружения

Читаются в `donats/settings.py` через `python-dotenv`.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `RABBIT_URL` | `amqp://user:password@localhost:5672/` | Исходящий брокер (и значение по умолчанию для inbound) |
| `RABBIT_VHOST` | `gunlinux_bot` | Виртуальный хост исходящего брокера |
| `RABBIT_ALERTS` | = `RABBIT_URL` | Брокер входящих алертов |
| `LOG_LEVEL` | `DEBUG` | Уровень логирования (числом, напр. `20`) |
| `LOG_FORMAT` | `[%(asctime)s] %(name)-18s [%(levelname)s] %(message)s` | Формат строк лога |
| `SENTRY_DSN` | пусто (Sentry выключен) | DSN для отправки ошибок |
| `TESTING` | `0` | Если задано — Sentry не инициализируется |
| `BEER_URL` | `http://127.0.0.1:6016/donate` | Сейчас не используется |
| `RECLIENT_ID`, `RECLIENT_SECRET`, `REOWNER_ID`, `REBOT_ID` | `""` | Twitch-настройки, сейчас не используются |
| `TOKEN_FILE`, `CHANNEL_TOKEN_FILE` | `tokens.json`, `channels_tokens.json` | Сейчас не используются |
| `COMMAND_DIR` | `./commands/` | Сейчас не используется |

Имена очередей — константы в `settings.py`, а не переменные окружения:
`DONATIONS_ALERTS` (`donations_alerts`, читается), `TWITCH_OUT` (`twitch_out`,
исходящий), а также `LOCAL_EVENTS`, `BEER_STAT`, `TWITCH_EVENTS`.

## Разработка

```bash
make lint     # ruff check
make fix      # ruff check --fix + ruff format
make types    # pyright
make check    # lint + fix + types
make test     # pytest
make test-dev # pytest -vv -s
```

Соглашения:

- одинарные кавычки в строках (задаёт `ruff format`);
- длина строки не ограничена (E501 отключён);
- докстринги не обязательны (правила `D` отключены).

## Docker

```bash
docker build -t bot_redonats .
docker run --rm --network host --env-file .env bot_redonats
```

Образ собирается из `python:3.12-slim`, зависимости ставятся `uv sync --frozen
--no-dev`, запуск — `uv run --no-sync donats_worker.py`.

## Деплой

Деплой автоматический: workflow `.github/workflows/deploy.yaml` срабатывает после
успешного CI на `main`, собирает образ, пушит его в Docker Hub
(`gunlinuxloki/bot_redonats`) с тегом короткого SHA и `latest`, затем по SSH
запускает `.github/deploy.sh` на `gunlinux.ru`.

На сервере скрипт:

1. обновляет checkout до `origin/main`;
2. подтягивает образ нужного тега;
3. устанавливает systemd-юнит `services/bot@donats_worker.service`, подставляя
   тег образа;
4. включает и перезапускает `bot@donats_worker.service`.

Юнит запускает контейнер с `--network host` и `--env-file
/home/loki/projects/bot/bot_redonats/.env`; секреты остаются на хосте и в
репозиторий не попадают.

## Тесты

```bash
uv run pytest
```

Тесты лежат в `tests/units/`, асинхронные — через `pytest-asyncio`
(`asyncio_mode = "auto"`).
