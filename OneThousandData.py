###########################################################
# Application database. The one that stores the workspace #
# data in json files                                      #
###########################################################

from pathlib import Path
from datetime import datetime
from OneThousandPasarell import Gateway
import json


class Project:
    def __init__(self, obj, token):
        super(Project, self).__init__()
        # Setting project info
        self.name = obj['name']
        self.token = token
        self.gateway = Gateway(self.token)
        self.id = obj['id']
        self.creator = obj['creator']
        self.is_member = obj['is_member']
        self.is_private = obj['is_private']
        self.participants = self.gateway.method_channel_members(self.id)
        self.messages = self.gateway.method_channel_message_history(self.id)
        if 'messages' not in self.messages.keys():
            self.messages['messages'] = []
        self.calendar = []
        self.topic = obj['topic']['value']
        self.purpose = obj['purpose']['value']
        self.board = {}
        self.has_trello = False

    # Save project data in the database (on init)
    def save_data(self):
        # If the project already exists on the database, we compare the info from Slack and the info from the DB
        # we give priority to Slack information
        if Path('./BD/Channels/{}.txt'.format(self.name)).exists():
            with open('./BD/Channels/{}.txt'.format(self.name), 'r') as f:
                data = json.loads(f.read())
            if data['num_members'] != len(self.participants['members']):
                data['num_members'] = len(self.participants['members'])
                data['PARTICIPANTS'] = self.participants['members']
            if data['num_calendar'] != len(self.calendar):
                data['num_calendar'] = len(self.calendar)
                data['CALENDAR'] = self.calendar
            if data['MESSAGES'][0]['ts'] != self.messages['messages'][0]['ts']:
                for i, message in self.messages['messages']:
                    if message["ts"] == data['MESSAGES'][0]['ts']:
                        index = i
                        break
                mess = next(message for message in self.messages['messages'] if message["ts"] == data['MESSAGES'][0]['ts'])
                index = self.messages['messages'].index(mess)
                for i in range(index + 1):
                    data['MESSAGES'].insert(0, self.messages['messages'][index - i])
            with open('./BD/Channels/{}.txt'.format(self.name), 'w') as f:
                f.write(json.dumps(data))
        # If the project doesn't exist in the DB, we dump all the info
        else:
            with open('./BD/Channels/{}.txt'.format(self.name), 'w+') as f:
                if 'members' in self.participants:
                    num_members = len(self.participants['members'])
                    members = self.participants['members']
                else:
                    num_members = 0
                    members = []
                f.write(json.dumps({
                    'name': self.name,
                    'id': self.id,
                    'creator': self.creator,
                    'is_member': self.is_member,
                    'is_private': self.is_private,
                    'num_members': num_members,
                    'num_calendar': len(self.calendar),
                    'topic': self.topic,
                    'purpose': self.purpose,
                    'PARTICIPANTS': members,
                    'trello_board': self.board,
                    'CALENDAR': self.calendar,
                    'MESSAGES': self.messages['messages'],
                    }))

    def create_reading_file(self):
        with open('./BD/Channels/{}_readable.txt'.format(self.name), 'w+') as f:
            trello_board = ''
            if self.board != {}:
                trello_board = json.dumps(self.board)
            f.write('id: \n' + self.id + '\n' +
                    'name: \n' + self.name + '\n' +
                    'creator: \n' + self.creator + '\n' +
                    'trello_board: \n' + trello_board + '\n' +
                    'is_member: \n' + str(self.is_member) + '\n' +
                    'is_private: \n' + str(self.is_private) + '\n' +
                    'num_members: \n' + str(len(self.participants['members'])) + '\n' +
                    'num_calendar: \n' + str(len(self.calendar)) + '\n' +
                    'topic: \n' + self.topic + '\n' +
                    'purpose: \n' + self.purpose + '\n')
            f.write('\nPARTICIPANTS:\n')
            for member in self.participants['members']:
                f.write(member + '\n')
            f.write('\nCALENDAR:\n')
            for cal in self.calendar:
                f.write(cal + '\n')
            f.write('\nMESSAGES:\n')
            if 'messages' in self.messages.keys():
                for message in self.messages['messages']:
                    if 'bot_id' in message.keys():
                        us = message['bot_id']
                    else:
                        us = message['user']
                    f.write(str(datetime.fromtimestamp(float(message['ts']))) + '\n' + us + ' -> ')
                    f.write(message['text'] + '\n')

    # If a new message was posted, we dump it on the database
    def save_new_message(self, event):
        self.messages['messages'].insert(0, event['event'])
        with open('./BD/Channels/{}.txt'.format(self.name), 'r') as f:
            data = json.loads(f.read())
        data['MESSAGES'].insert(0, event['event'])
        with open('./BD/Channels/{}.txt'.format(self.name), 'w') as f:
            f.write(json.dumps(data))

    def new_user_added(self, user_id):
        if user_id not in self.participants['members']:
            self.participants['members'].append(user_id)
            with open('./BD/Channels/{}.txt'.format(self.name), 'r') as f:
                data = json.loads(f.read())
            data['num_members'] += 1
            data['PARTICIPANTS'].append(user_id)
            with open('./BD/Channels/{}.txt'.format(self.name), 'w+') as f:
                f.write(json.dumps(data))

    # Adding a new task to the project
    def add_task(self, name_list, task):
        for i, _list in enumerate(self.board['lists']):
            if _list['name'].lower().replace(' ', '') == name_list.lower().replace(' ', ''):
                self.board['lists'][i]['tasks'].append(task)
                self.board['num_tasks'] += 1
        with open('./BD/Channels/{}.txt'.format(self.name), 'r') as f:
            data = json.loads(f.read())
        data['trello_board'] = self.board
        with open('./BD/Channels/{}.txt'.format(self.name), 'w') as f:
            f.write(json.dumps(data))


class User:
    def __init__(self, obj, token, all_channels):
        super(User, self).__init__()
        # Setting project info
        self.name = obj['name']
        self.token = token
        self.id = obj['id']
        self.team_id = obj['team_id']
        self.real_name = obj['real_name']
        self.tz_offset = obj['tz_offset']
        self.is_admin = obj['is_admin']
        self.is_owner = obj['is_owner']
        self.direct_channel_id = ''
        self.groups = []
        self.working = False
        self.start = None
        self.end = None
        self.greeted = False
        for channel in all_channels:
            if self.id in channel.participants['members']:
                self.groups.append(channel.id)
        self.calendar = []
        self.member = {}
        self.has_trello = False

    # Save user data in the database (on init)
    def save_data(self):
        # If the user already exists on the database, we compare the info from Slack and the info from the DB
        # we give priority to Slack information
        if Path('./BD/Users/{}.txt'.format(self.real_name)).exists():
            with open('./BD/Users/{}.txt'.format(self.real_name), 'r') as f:
                data = json.loads(f.read())
            if data['num_groups'] != len(self.groups):
                data['num_groups'] = len(self.groups)
                data['GROUPS'] = self.groups
            if data['num_calendar'] != len(self.calendar):
                data['num_calendar'] = len(self.calendar)
                data['CALENDAR'] = self.calendar
            with open('./BD/Users/{}.txt'.format(self.real_name), 'w') as f:
                f.write(json.dumps(data))
        # If the user doesn't exist in the DB, we dump all the info
        else:
            with open('./BD/Users/{}.txt'.format(self.real_name), 'w+') as f:
                f.write(json.dumps({
                    'name': self.name,
                    'id': self.id,
                    'channel_id': self.direct_channel_id,
                    'real_name': self.real_name,
                    'team_id': self.team_id,
                    'tz_offset': self.tz_offset,
                    'is_admin': self.is_admin,
                    'is_owner': self.is_owner,
                    'num_groups': len(self.groups),
                    'num_calendar': len(self.calendar),
                    'trello_user': self.member,
                    'GROUPS': self.groups,
                    'CALENDAR': self.calendar,
                }))

    def creating_reading_file(self):
        with open('./BD/Users/{}_readable.txt'.format(self.real_name), 'w+') as f:
            trello_member = {'None'}
            if self.member != {}:
                trello_member = self.member
            f.write('id: \n' + self.id + '\n' +
                    'name: \n' + self.name + '\n' +
                    'real_name: \n' + self.real_name + '\n' +
                    'team_id: \n' + self.team_id + '\n' +
                    'trello_member: \n' + json.dumps(trello_member) + '\n' +
                    'tz_offset: \n' + str(self.tz_offset) + '\n' +
                    'is_admin: \n' + str(self.is_admin) + '\n' +
                    'is_owner: \n' + str(self.is_owner) + '\n' +
                    'num_groups: \n' + str(len(self.groups)) + '\n' +
                    'num_calendar: \n' + str(len(self.calendar)) + '\n')
            f.write('\nGROUPS:\n')
            for group in self.groups:
                f.write(group + '\n')
            f.write('\nCALENDAR:\n')
            for cal in self.calendar:
                f.write(cal + '\n')

    # Adding a new task to the user
    def add_task(self, board_id, name_list, task):
        for i, board in enumerate(self.member['boards']):
            if board['id'] == board_id:
                for j, _list in enumerate(board['lists']):
                    if _list['name'].lower().replace(' ', '') == name_list.lower().replace(' ', ''):
                        self.member['boards'][i]['lists'][j]['tasks'].append(task)
                        self.member['num_tasks'] += 1
        with open('./BD/Users/{}.txt'.format(self.real_name), 'r') as f:
            data = json.loads(f.read())
        data['trello_user'] = self.member
        with open('./BD/Users/{}.txt'.format(self.real_name), 'w') as f:
            f.write(json.dumps(data))

    def new_group_added(self, channel_id):
        if channel_id not in self.groups:
            self.groups.append(channel_id)
            with open('./BD/Users/{}.txt'.format(self.real_name), 'r') as f:
                data = json.loads(f.read())
            data['num_groups'] += 1
            data['GROUPS'].append(channel_id)
            with open('./BD/Users/{}.txt'.format(self.real_name), 'w+') as f:
                f.write(json.dumps(data))

    def board_deleted(self, channel_id):
        self.groups.pop(self.groups.index(channel_id))
        with open('./BD/Users/{}.txt'.format(self.real_name), 'r') as f:
            data = json.loads(f.read())
        data['num_groups'] -= 1
        data['GROUPS'].pop(data['GROUPS'].index(channel_id))
        with open('./BD/Users/{}.txt'.format(self.real_name), 'w+') as f:
            f.write(json.dumps(data))
