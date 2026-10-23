import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, BusinessMessagesDeleted
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, OWNER_ID, RETENTION_DAYS
from db import init_db, save_message, get_messages, cleanup_old

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def get_from_name(msg: Message) -> str:
    user = msg.from_user
    if not user:
        return "Неизвестный"
    name = user.full_name or ""
    if user.username:
        name += f" (@{user.username})"
    return name.strip() or str(user.id)


async def extract_and_save(msg: Message):
    """Сохраняем входящее business-сообщение"""
    if not msg.business_connection_id:
        return

    content_type = "text"
    text = msg.text or msg.caption
    file_id = None
    caption = msg.caption

    if msg.photo:
        content_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        content_type = "video"
        file_id = msg.video.file_id
    elif msg.video_note:
        content_type = "video_note"
        file_id = msg.video_note.file_id
    elif msg.voice:
        content_type = "voice"
        file_id = msg.voice.file_id
    elif msg.audio:
        content_type = "audio"
        file_id = msg.audio.file_id
    elif msg.document:
        content_type = "document"
        file_id = msg.document.file_id
    elif msg.sticker:
        content_type = "sticker"
        file_id = msg.sticker.file_id
    elif msg.animation:
        content_type = "animation"
        file_id = msg.animation.file_id

    await save_message(
        business_connection_id=msg.business_connection_id,
        chat_id=msg.chat.id,
        message_id=msg.message_id,
        from_user_id=msg.from_user.id if msg.from_user else None,
        from_name=get_from_name(msg),
        content_type=content_type,
        text=text,
        file_id=file_id,
        caption=caption,
    )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user and message.from_user.id != OWNER_ID:
        await message.answer("Это приватный бот.")
        return

    await message.answer(
        f"<b>Шпион-бот готов</b>\n\n"
        f"Хранит сообщения ~{RETENTION_DAYS} дня.\n"
        f"При удалении присылает копию сюда.\n\n"
        f"<b>Как подключить:</b>\n"
        f"1. Настройки → Telegram Business → Chat bots\n"
        f"   (или Автоматизация чатов)\n"
        f"2. Добавь этого бота\n"
        f"3. Выбери чаты, которые нужно мониторить\n\n"
        f"После подключения все новые сообщения из этих чатов будут сохраняться."
    )


@dp.business_connection()
async def on_business_connection(bc: BusinessConnection):
    """Когда тебя подключают / отключают"""
    status = "подключён" if bc.is_enabled else "отключён"
    user = bc.user
    name = user.full_name if user else "?"
    await bot.send_message(
        OWNER_ID,
        f"Business connection {status}\n"
        f"Пользователь: {name} (id={bc.user.id if bc.user else '?'})\n"
        f"connection_id: <code>{bc.id}</code>"
    )


@dp.business_message()
async def on_business_message(message: Message):
    """Любое новое сообщение в подключённом чате"""
    await extract_and_save(message)


@dp.edited_business_message()
async def on_edited_business_message(message: Message):
    """Сообщение отредактировали — сохраняем новую версию + уведомляем"""
    await extract_and_save(message)

    old_rows = await get_messages(message.chat.id, [message.message_id])
    old_text = old_rows[0]["text"] if old_rows else "—"

    new_text = message.text or message.caption or "[медиа]"
    name = get_from_name(message)

    await bot.send_message(
        OWNER_ID,
        f"✏️ <b>Сообщение отредактировано</b>\n"
        f"От: {name}\n"
        f"Чат id: <code>{message.chat.id}</code>\n\n"
        f"<b>Было:</b>\n{old_text}\n\n"
        f"<b>Стало:</b>\n{new_text}"
    )


@dp.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    """Сообщения удалили — достаём из базы и шлём владельцу"""
    rows = await get_messages(event.chat.id, event.message_ids)

    if not rows:
        await bot.send_message(
            OWNER_ID,
            f"🗑 Удалены сообщения (id: {event.message_ids})\n"
            f"Чат: <code>{event.chat.id}</code>\n"
            f"В базе их уже нет (слишком старые или не успели сохраниться)."
        )
        return

    for row in rows:
        name = row["from_name"] or "Неизвестный"
        header = (
            f"🗑 <b>Удалено сообщение</b>\n"
            f"От: {name}\n"
            f"Чат id: <code>{row['chat_id']}</code>\n"
            f"Тип: {row['content_type']}\n"
        )

        try:
            if row["content_type"] == "text" or not row["file_id"]:
                text = row["text"] or "[пусто]"
                await bot.send_message(OWNER_ID, header + f"\n{text}")

            elif row["content_type"] == "photo":
                await bot.send_photo(
                    OWNER_ID,
                    row["file_id"],
                    caption=header + (f"\n{row['caption']}" if row["caption"] else ""),
                )
            elif row["content_type"] == "video":
                await bot.send_video(
                    OWNER_ID,
                    row["file_id"],
                    caption=header + (f"\n{row['caption']}" if row["caption"] else ""),
                )
            elif row["content_type"] == "voice":
                await bot.send_voice(OWNER_ID, row["file_id"], caption=header)
            elif row["content_type"] == "video_note":
                await bot.send_message(OWNER_ID, header + "\n(кружок)")
                await bot.send_video_note(OWNER_ID, row["file_id"])
            elif row["content_type"] == "document":
                await bot.send_document(
                    OWNER_ID,
                    row["file_id"],
                    caption=header + (f"\n{row['caption']}" if row["caption"] else ""),
                )
            elif row["content_type"] == "sticker":
                await bot.send_message(OWNER_ID, header + "\n(стикер)")
                await bot.send_sticker(OWNER_ID, row["file_id"])
            elif row["content_type"] == "animation":
                await bot.send_animation(
                    OWNER_ID,
                    row["file_id"],
                    caption=header + (f"\n{row['caption']}" if row["caption"] else ""),
                )
            else:
                await bot.send_message(
                    OWNER_ID,
                    header + f"\n{row['text'] or '[медиа]'}"
                )
        except Exception as e:
            logger.exception("Не удалось переслать удалённое")
            await bot.send_message(
                OWNER_ID,
                header + f"\nНе смог отправить медиа: {e}\nТекст: {row['text'] or '—'}"
            )


async def periodic_cleanup():
    while True:
        try:
            deleted = await cleanup_old()
            if deleted:
                logger.info(f"Очищено старых сообщений: {deleted}")
        except Exception:
            logger.exception("Ошибка очистки")
        await asyncio.sleep(6 * 3600)  # раз в 6 часов


async def main():
    await init_db()
    asyncio.create_task(periodic_cleanup())
    logger.info("Шпион-бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
