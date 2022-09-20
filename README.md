# JoinRequestChatBot

This is a small bot which forwards all chats from people trying to join your group to a second group (probably consistent of your admins), and all messages from that second group back to the proper private chat.

There will be three buttons below all the messages belonging to an applying user: ✅, ❌ and 🛑. ✅ approves the join request, ❌ declines, and 🛑 bans the users (forever), so they can't reapply to join the group.

Every message is supported, a wanting-to-join user message will reply to the last one in chat, so you can mute the second chat and won't miss a follow-up to your conversation.

You can send a reply with a !, the bot ignores these messages.

Also features a 24 hour timer after the last send message, after which the wanting-to-join users join request is rejected.

Add the bot with add member + ban users right in the main group. Set the `mainchat` variable on line 38 to your main chat id, the `joinrequestchat` to the one you want to handle the join requests in, the `devchat` to the chat you want to receive errors in. Oh, and don't forget to add your token in line 223.
