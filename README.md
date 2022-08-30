# JoinRequestChatBot

This is a small bot which forwards all chats from people trying to join your group to a second group, and all messages from that second group back to the proper private chat.

You can directly accept/decline new users in that group with inline buttons.

Add the bot with add member right in the main group. Set the `mainchat` variable on line 38 to your main chat id, and the `joinrequestchat` to the one you want to handle the join requests in. Oh, and don't forget to add your token in line 223
