import asyncio
import html
import json
import logging
import traceback

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
    Poll,
    Audio,
    VideoNote,
    Venue,
    Sticker,
    Location,
    Dice,
    Contact,
)
from telegram.error import RetryAfter
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    ChatJoinRequestHandler,
    Defaults,
    filters,
    MessageHandler,
    CallbackQueryHandler,
    PicklePersistence,
    CommandHandler,
    Application,
)
from typing import List

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="log.log",
)

logger = logging.getLogger(__name__)

JOINREQUESTCHAT = -100
MAINCHAT = -100
DEVCHAT = 208589966
background_tasks = set()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(chat_id=DEVCHAT, text=message)


def create_buttons(user_id: int):
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅", callback_data=f"y_{user_id}"),
                InlineKeyboardButton("❌", callback_data=f"n_{user_id}"),
            ]
        ]
    )
    return buttons


async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="Hey, welcome to the Translation Platform Talk group. In order to combat spam, the moderators had to "
        "enable join requests. Please answer any questions they have, or tell them a fun fact about yourself"
        " proactively.",
    )
    # this needs to be a get_chat, because has_private_forwards is only set here
    user = await context.bot.get_chat(chat_id=update.effective_user.id)
    if user.has_private_forwards and not user.username:
        message = f"The user {user.full_name} has sent a join request, but can not be mentioned :(."
        context.bot_data["user_mentions"][user.id] = user.full_name
    else:
        if user.username:
            mention = f"@{user.username}"
        else:
            mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
        message = f"The user {mention} has sent a join request \\o/"
        context.bot_data["user_mentions"][user.id] = mention
    send_message = await context.bot.send_message(
        chat_id=JOINREQUESTCHAT, text=message, reply_markup=create_buttons(user.id)
    )
    if user.id in context.bot_data["messages_to_edit"]:
        context.bot_data["messages_to_edit"][user.id].append(send_message.message_id)
    else:
        context.bot_data["messages_to_edit"][user.id] = [send_message.message_id]
        context.bot_data["last_message_to_user"][user.id] = send_message.message_id


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data.split("_")
    user_id = int(data[1])
    if data[0] == "y":
        await context.bot.approve_chat_join_request(chat_id=MAINCHAT, user_id=user_id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{update.effective_user.mention_html()} accepted the join request.",
            reply_to_message_id=update.callback_query.message.message_id,
        )
    else:
        await context.bot.decline_chat_join_request(chat_id=MAINCHAT, user_id=user_id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{update.effective_user.mention_html()} rejected the join request.",
            reply_to_message_id=update.callback_query.message.message_id,
        )
    del context.bot_data["user_mentions"][user_id]
    task = asyncio.create_task(
        edit_buttons(context.bot, context.bot_data["messages_to_edit"][user_id])
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    del context.bot_data["messages_to_edit"][user_id]
    del context.bot_data["last_message_to_user"][user_id]


async def edit_buttons(bot: Bot, messages_to_edit: List[int]):
    # every second we edit out a button. We wait this long, so we don't rate limit the bot
    # instead of reversed here, I should have done prepend instead of append I guess
    for message_id in reversed(messages_to_edit):
        try:
            await bot.edit_message_reply_markup(
                chat_id=JOINREQUESTCHAT, message_id=message_id, reply_markup=None
            )
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.edit_message_reply_markup(
                chat_id=JOINREQUESTCHAT, message_id=message_id, reply_markup=None
            )
        await asyncio.sleep(1)


async def message_from_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message.reply_markup:
        if update.message.reply_to_message.from_user.id == context.bot.id:
            await update.message.reply_text(
                "Sorry, you either replied to the wrong message, "
                "or this user has been dealt with already."
            )
            return
    # we get the user id from the old reply markup
    user_id = int(
        update.message.reply_to_message.reply_markup.inline_keyboard[0][
            0
        ].callback_data.split("_")[1]
    )
    if user_id not in context.bot_data["user_mentions"]:
        await update.message.reply_text("Sorry, this user has been dealt with already.")
        return
    await context.bot.copy_message(
        chat_id=user_id,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
    )
    send_message = await update.message.reply_text(
        f"Message sent to {context.bot_data['user_mentions'][user_id]}",
        reply_markup=create_buttons(user_id),
    )
    context.bot_data["messages_to_edit"][user_id].append(send_message.message_id)
    context.bot_data["last_message_to_user"][
        user_id
    ] = update.effective_message.message_id


async def message_from_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in context.bot_data["user_mentions"]:
        await update.message.reply_text("Hi. Use /start to check me out.")
        return
    user_id = update.effective_user.id
    user_mention = (
        f"@{update.effective_user.username}"
        if update.effective_user.username
        else update.effective_user.mention_html()
    )
    if update.effective_message.effective_attachment:
        # Polls need to be forwarded
        if isinstance(update.effective_message.effective_attachment, Poll):
            await update.effective_message.forward(JOINREQUESTCHAT)
            message = await context.bot.send_message(
                chat_id=JOINREQUESTCHAT,
                text=f"The above Poll was sent by {user_mention}",
                reply_to_message_id=context.bot_data["last_message_to_user"][user_id],
                reply_markup=create_buttons(user_id),
            )
            context.bot_data["messages_to_edit"][user_id].append(message.message_id)
            return
        previous_caption = (
            update.effective_message.caption + "\n\n"
            if update.effective_message.caption
            else ""
        )
        message = await update.effective_message.copy(
            chat_id=JOINREQUESTCHAT,
            caption=f"{previous_caption}This message was sent by {user_mention}",
            reply_to_message_id=context.bot_data["last_message_to_user"][user_id],
            reply_markup=create_buttons(user_id),
        )
        context.bot_data["messages_to_edit"][user_id].append(message.message_id)
        # all of these cant get a caption, so we have to send a message instead
        if isinstance(
            update.effective_message.effective_attachment,
            (Audio, VideoNote, Venue, Sticker, Location, Dice, Contact),
        ):
            message = await context.bot.send_message(
                chat_id=JOINREQUESTCHAT,
                text=f"The above message was sent by {user_mention}",
                reply_to_message_id=message.message_id,
                reply_markup=create_buttons(user_id),
            )
            context.bot_data["messages_to_edit"][user_id].append(message.message_id)
    else:
        message = await context.bot.send_message(
            chat_id=JOINREQUESTCHAT,
            text=f"{update.effective_message.text_html_urled}\n\nThis message was sent by {user_mention}",
            reply_to_message_id=context.bot_data["last_message_to_user"][user_id],
            reply_markup=create_buttons(user_id),
        )
        context.bot_data["messages_to_edit"][user_id].append(message.message_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I'm a bot for the Translation Platform Talk group. You can find my source code on GitHub, "
        "check out https://github.com/poolitzer/JoinRequestChatBot",
    )


async def first_run_check(ready_application: Application):
    if "messages_to_edit" not in ready_application.bot_data:
        application.bot_data["messages_to_edit"] = {}
    if "user_mentions" not in ready_application.bot_data:
        application.bot_data["user_mentions"] = {}
    if "last_message_to_user" not in ready_application.bot_data:
        application.bot_data["last_message_to_user"] = {}


if __name__ == "__main__":
    defaults = Defaults(parse_mode="html")
    persistence = PicklePersistence(filepath="bot_data.pickle")
    application = (
        ApplicationBuilder()
        .token("TOKEN")
        .defaults(defaults)
        .persistence(persistence)
        .post_init(first_run_check)
        .build()
    )

    application.add_handler(ChatJoinRequestHandler(join_request))
    application.add_handler(
        MessageHandler(filters.Chat(JOINREQUESTCHAT), message_from_group)
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE, message_from_private)
    )
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    application.run_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.CHAT_JOIN_REQUEST,
            Update.CALLBACK_QUERY,
        ]
    )
