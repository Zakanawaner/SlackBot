############################################################
# Application server program. The one that initialises the #
# bot and starts the server                                #
############################################################

import os
from slackeventsapi import SlackEventAdapter
from slack import WebClient
from flask import Flask, request, make_response
from OneThousandBot import Bot

# Send it to environmental variables
TOKEN = os.environ.get('TOKEN')
SIGNING = os.environ.get('SIGNING')
API_KEY_TRELLO = os.environ.get('API_KEY_TRELLO')
TOKEN_TRELLO = os.environ.get('TOKEN_TRELLO')

# Server initialization
app = Flask(__name__)

# URL Validation Handshake
slack_events_adapter = SlackEventAdapter(SIGNING, '/listening', app)
slack_client = WebClient(TOKEN)

# Command /help
@app.route('/help', methods=["GET", "POST"])
def help_bot():
    return make_response(bot.help(request), 200)

# Command /add
@app.route('/add', methods=["GET", "POST"])
def add():
    return make_response(bot.add(request), 200)

# Command /addtrello
@app.route('/trellobot', methods=["GET", "POST"])
def trellobot():
    return make_response(bot.trello(request), 200)

# Command /deleteboard
@app.route('/deleteboard', methods=["GET", "POST"])  # todo test all the way and delete it from classes
def delete_board():
    return make_response(bot.delete_board(request), 200)

# Command /updateboard
@app.route('/updateboard', methods=["GET", "POST"])
def update_board():
    return make_response(bot.update_board(request), 200)

# Command /createboard
@app.route('/createboard', methods=["GET", "POST"])
def create_board():
    return make_response(bot.create_board(request), 200)

# Command /work
@app.route('/work', methods=["GET", "POST"])
def work():
    return make_response(bot.work(request), 200)

# User clicked into your App Home
@slack_events_adapter.on('app_home_opened')
def app_home_opened(event_data):
    bot.event_app_home_opened(event_data)

# Subscribe to only the message events that mention your app or bot
@slack_events_adapter.on('app_mention')
def app_mention(event_data):
    bot.event_app_mention(event_data)

# A channel was archived
@slack_events_adapter.on('channel_archive')
def channel_archived(event_data):
    bot.event_channel_archived(event_data)

# A channel was created
@slack_events_adapter.on('channel_created')
def channel_created(event_data):
    bot.event_channel_created(event_data)

# A channel was deleted
@slack_events_adapter.on('channel_deleted')
def channel_deleted(event_data):
    bot.event_channel_deleted(event_data)

# Bot left a channel
@slack_events_adapter.on('channel_left')
def channel_left(event_data):
    bot.event_channel_left(event_data)

# A channel was renamed
@slack_events_adapter.on('channel_rename')
def channel_rename(event_data):
    bot.event_channel_rename(event_data)

# A private channel was archived
@slack_events_adapter.on('group_archive')
def channel_archived(event_data):
    bot.event_group_archived(event_data)

# Bot left a private channel
@slack_events_adapter.on('group_left')
def group_left(event_data):
    bot.event_channel_left(event_data)

# Bot joined a private group
@slack_events_adapter.on('group_joined')
def group_joined(event_data):
    bot.event_member_joined_channel(event_data)

# A private channel was deleted
@slack_events_adapter.on('group_deleted')
def group_deleted(event_data):
    bot.event_channel_deleted(event_data)

# A member joined a channel
@slack_events_adapter.on('member_joined_channel')
def member_joined_channel(event_data):
    bot.event_member_joined_channel(event_data)

# A member left a channel
@slack_events_adapter.on('member_left_channel')
def member_left_channel(event_data):
    bot.event_member_left_channel(event_data)

# A message was posted on a channel
@slack_events_adapter.on('message')
def message(event_data):
    bot.event_message(event_data)

# A new member has joined
@slack_events_adapter.on('team_join')
def team_join(event_data):
    bot.event_team_join(event_data)


if __name__ == "__main__":
    # Initialising the bot core
    bot = Bot(TOKEN, TOKEN_TRELLO, API_KEY_TRELLO)
    # Calling the server
    app.run(port=5000)
