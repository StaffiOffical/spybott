# Шпион-бот (Telegram Business)

Официальный способ через **Telegram Business / Chat automation**.

Бот:
- сохраняет входящие сообщения из подключённых личных чатов
- хранит их ~3 дня
- при удалении присылает тебе копию в личку с ботом
- ловит редактирования (было → стало)

## Установка

```bash
python -m venv venv
source venv/bin/activate          # Linux/mac
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env
# заполни BOT_TOKEN и OWNER_ID
python bot.py
```

## Настройка бота

1. Создай бота у @BotFather
2. `/mybots` → выбери бота → **Bot Settings** → **Business Mode** → Enable
3. Скопируй токен в `.env`
4. Узнай свой id (например через @userinfobot) → `OWNER_ID`

## Подключение к аккаунту

На телефоне / десктопе:

**Настройки → Telegram Business → Chat bots**  
(или **Автоматизация чатов**)

- Добавь своего бота
- Выбери чаты, которые нужно мониторить

После этого бот начнёт получать `business_message` / `deleted_business_messages`.

## Важно

- Работает **только в личных чатах**, которые ты сам подключил.
- Сообщения, которые были до подключения, бот не видит.
- Исчезающие (view once) фото — Telegram не всегда отдаёт файл боту. Обычные фото/видео сохраняются нормально.
- Хранение 3 дня. Можно поменять в `config.py` → `RETENTION_DAYS`.

## Запуск 24/7

На своём ПК + VPN/прокси (если в РФ), либо на любом хосте.
