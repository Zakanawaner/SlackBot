################################################################
# Trello Gateway program. The one that communicates with Slack #
################################################################

import requests


class Gateway:
    def __init__(self, token):
        super(Gateway, self).__init__()
        # Getting token information
        self.token = token

    # Methods for Slack / Bot communication (A lot of potential here)
    # Get list of workspace users
    def method_get_users(self, new=False, id_user=''):
        if new:
            return requests.get('https://slack.com/api/users.info', {
                'token': self.token,
                'user': id_user
            }).json()
        else:
            return requests.get('https://slack.com/api/users.list', {
                'token': self.token,
            }).json()

    # Get Slack channels and projects
    def method_get_channels(self, types='', new=False, id_channel=''):
        if new:
            return requests.get('https://slack.com/api/conversations.info', {
                'token': self.token,
                'channel': id_channel,
            }).json()
        else:
            return requests.get('https://slack.com/api/conversations.list', {
                'token': self.token,
                'types': types,
            }).json()

    # Post a message in a channel
    def method_post_message(self, response, channel):
        requests.post('https://slack.com/api/chat.postMessage', {
            'token': self.token,
            'channel': channel,
            'text': response,
        }).json()

    # Get members of a channel or project
    def method_channel_members(self, channel):
        return requests.get('https://slack.com/api/conversations.members', {
            'token': self.token,
            'channel': channel,
        }).json()

    # Get all messages from a channel
    def method_channel_message_history(self, channel):
        return requests.get('https://slack.com/api/conversations.history', {
            'token': self.token,
            'channel': channel,
        }).json()

    def method_open_direct_channel(self, user_id):
        return requests.post('https://slack.com/api/conversations.open', {
            'token': self.token,
            'users': user_id,
        }).json()

    def method_share_file(self, channel_id, file):
        file = requests.get('https://slack.com/api/files.remote.add', {
            'token': self.token,
            'users': channel_id,

        }).json()
        return requests.post('https://slack.com/api/files.upload', {
            'token': self.token,
            'users': channel_id,
            'file': file
        }).json()
