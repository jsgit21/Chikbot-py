# General documentation

# Discord webhook documentation

During each refresh of the wom group, there will be an update to a local database Discord.wom_group which tracks what users we have locally
I decided to keep a database image instead of hitting the API everytime just to reduce the need to call the API for every single message being sent to the webhook

Simply put, this table ends up being used as a check for all the messages flowing through the webhook.
Dink messages will send an embed with the user's RSN as the embeds author.name (message.embeds[0].author.name)

- If this RSN is not found in our local WOM group then the message will be deleted and sent to the Webhook Graveyard which can be seen by moderators.
- If the message doesn't have an embed, something is probably wrong, so it is also deleted and sent to the graveyard.

If a new users is trying to set up Dink the first day they join the clan, chances are their name is not going to be in the local WOM group (Discord.wom_group).
If necessary, Chikbot can be rebooted to force a refresh to that table, but honestly this is pretty unlikely, and worst case scenario it will refresh every day at 9am EST.
