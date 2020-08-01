###########################################################
# Application database. The one that stores the workspace #
# data in json files                                      #
###########################################################

from datetime import datetime
from OneThousandPasarell import Gateway
import json
import psycopg2
import os


class Project:
    def __init__(self, obj, token):
        super(Project, self).__init__()
        self.connection = None
        self.cursor = None
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
        self.start_connection()
        self.cursor.execute("SELECT * "
                            "FROM channels "
                            "WHERE id = %s;", (self.id,))
        channel = self.cursor.fetchone()
        if channel is None:
            self.cursor.execute('INSERT INTO channels (id, metadata, trello, messages) VALUES (%s,%s,%s,%s)',
                                (self.id,
                                 json.dumps({
                                    'name': self.name,
                                    'creator': self.creator,
                                    'is_member': self.is_member,
                                    'is_private': self.is_private,
                                    'num_members': len(self.participants['members']) if 'members' in self.participants else 0,
                                    'num_calendar': len(self.calendar),
                                    'topic': self.topic,
                                    'purpose': self.purpose,
                                    'participants': self.participants['members'] if 'members' in self.participants else [],
                                    'calendar': self.calendar}),
                                 json.dumps(self.board),
                                 json.dumps(self.messages['messages'])))
            self.connection.commit()
        else:
            channel = list(channel)
            channel[1]['num_members'] = len(self.participants['members'])
            channel[1]['participants'] = self.participants['members']
            channel[1]['num_calendar'] = len(self.calendar)
            channel[1]['calendar'] = self.calendar
            channel[2] = self.board
            if channel[3] != []:
                if channel[3][0]['ts'] != self.messages['messages'][0]['ts']:
                    index = 0
                    for i, message in enumerate(self.messages['messages']):
                        if message["ts"] == channel[3][0]['ts']:
                            index = i
                            break
                    for i in range(index, 0, -1):
                        channel[3].insert(0, self.messages['messages'][i - 1])
            self.cursor.execute('UPDATE channels SET metadata = %s, trello = %s, messages = %s WHERE id = %s;',
                                (json.dumps(channel[1]),
                                 json.dumps(channel[2]),
                                 json.dumps(channel[3]),
                                 self.id))
            self.connection.commit()
            self.stop_connection()

    # When a channel is deleted, the Bot creates a reading file
    def create_reading_file(self):
        self.start_connection()
        self.cursor.execute("SELECT * "
                            "FROM channels "
                            "WHERE id = %s;", (self.id,))
        channel = self.cursor.fetchone()
        channel = list(channel)
        with open('{}_readable.txt'.format(self.name), 'w+') as f:
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
        self.start_connection()
        self.cursor.execute("SELECT messages "
                            "FROM channels "
                            "WHERE id = %s;", (self.id,))
        channel = self.cursor.fetchone()
        channel = list(channel)
        channel[0].insert(0, event['event'])
        self.cursor.execute('UPDATE channels SET messages = %s WHERE id = %s;',
                            (json.dumps(channel[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # A new user added to a channel
    def new_user_added(self, user_id):
        self.start_connection()
        self.cursor.execute("SELECT metadata "
                            "FROM channels "
                            "WHERE id = %s;", (self.id,))
        channel = self.cursor.fetchone()
        channel = list(channel)
        if user_id not in channel[0]['participants']:
            self.participants['members'].append(user_id)
            channel[0]['num_members'] += 1
            channel[0]['participants'].append(user_id)
        self.cursor.execute('UPDATE channels SET metadata = %s WHERE id = %s;',
                            (json.dumps(channel[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # Adding a new task to the project
    def add_task(self, name_list, task):
        done = False
        for i, _list in enumerate(self.board['lists']):
            if _list['name'].lower().replace(' ', '') == name_list.lower().replace(' ', ''):
                self.board['lists'][i]['tasks'].append(task)
                self.board['num_tasks'] += 1
                index_list = i
                done = True
                break
        if done:
            self.start_connection()
            self.cursor.execute("SELECT trello "
                                "FROM channels "
                                "WHERE id = %s;", (self.id,))
            board = list(self.cursor.fetchone())
            board[0]['lists'][index_list]['tasks'].append(task)
            board = tuple(board)
            self.cursor.execute("UPDATE channels SET trello = %s WHERE id = %s;",
                                (json.dumps(board[0]),
                                 self.id))
            self.connection.commit()
            self.stop_connection()

    # Update command executed
    def update_board(self):
        self.start_connection()
        self.cursor.execute("SELECT trello "
                            "FROM channels "
                            "WHERE id = %s;", (self.id,))
        board = list(self.cursor.fetchone())
        board[0] = self.board
        board = tuple(board)
        self.cursor.execute("UPDATE channels SET trello = %s WHERE id = %s;",
                            (json.dumps(board[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # A trello board was added in this channel
    def trello_board_added(self, board):
        self.board = board
        self.update_board()

    # Start database connection
    def start_connection(self):
        self.connection = psycopg2.connect(user=os.environ.get('SQL_USER'),
                                           password=os.environ.get('SQL_PASSWORD'),
                                           host=os.environ.get('SQL_HOST'),
                                           port=os.environ.get('SQL_PORT'),
                                           database=os.environ.get('SQL_NAME'))
        self.cursor = self.connection.cursor()

    # Stop database connection
    def stop_connection(self):
        self.cursor.close()
        self.connection.close()


class User:
    def __init__(self, obj, token, all_channels):
        super(User, self).__init__()
        self.connection = None
        self.cursor = None
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
        self.start_connection()
        self.cursor.execute("SELECT * "
                            "FROM users "
                            "WHERE id = %s;", (self.id,))
        user = self.cursor.fetchone()
        if user is None:
            self.cursor.execute('INSERT INTO users (id, metadata, trello) VALUES (%s,%s,%s)',
                                (self.id,
                                 json.dumps({
                                        'name': self.name,
                                        'channel_id': self.direct_channel_id,
                                        'real_name': self.real_name,
                                        'team_id': self.team_id,
                                        'tz_offset': self.tz_offset,
                                        'is_admin': self.is_admin,
                                        'is_owner': self.is_owner,
                                        'num_groups': len(self.groups),
                                        'num_calendar': len(self.calendar),
                                        'groups': self.groups,
                                        'calendar': self.calendar}),
                                 json.dumps(self.member)))
            self.connection.commit()
        else:
            user = list(user)
            user[1]['num_groups'] = len(self.groups)
            user[1]['groups'] = self.groups
            user[1]['num_calendar'] = len(self.calendar)
            user[1]['calendar'] = self.calendar
            user[2] = self.member
            self.cursor.execute('UPDATE users SET metadata = %s, trello = %s WHERE id = %s;',
                                (json.dumps(user[1]),
                                 json.dumps(user[2]),
                                 self.id))
            self.connection.commit()
            self.stop_connection()

    # When a user is deleted, the Bot creates a reading file
    def creating_reading_file(self):
        with open('{}_readable.txt'.format(self.real_name), 'w+') as f:
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
        done = False
        already_exists = False
        for i, board in enumerate(self.member['boards']):
            if board['id'] == board_id:
                for j, _list in enumerate(board['lists']):
                    if _list['name'].lower().replace(' ', '') == name_list.lower().replace(' ', ''):
                        if 'tasks' in _list.keys():
                            for task_ in _list['tasks']:
                                if task_['name'].lower().replace(' ', '') == task['name'].lower().replace(' ', ''):
                                    already_exists = True
                                    break
                            if not already_exists:
                                self.member['boards'][i]['lists'][j]['tasks'].append(task)
                                self.member['num_tasks'] += 1
                                done = True
                                index_list = j
                                break
                        else:
                            self.member['boards'][i]['lists'][j]['tasks'].append(task)
                            self.member['num_tasks'] += 1
                            done = True
                            index_list = j
                            break
            if done:
                index_board = i
                break
        if done:
            self.start_connection()
            self.cursor.execute("SELECT trello "
                                "FROM users "
                                "WHERE id = %s;", (self.id,))
            boards = list(self.cursor.fetchone())
            boards[0]['boards'][index_board]['lists'][index_list]['tasks'].append(task)
            boards = tuple(boards)
            self.cursor.execute("UPDATE users SET trello = %s WHERE id = %s;",
                                (json.dumps(boards[0]),
                                 self.id))
            self.connection.commit()
            self.stop_connection()
        return done, already_exists

    # User added to a task
    def added_to_task(self, index_board, index_list, task):  # todo test
        self.start_connection()
        self.cursor.execute("SELECT trello "
                            "FROM users "
                            "WHERE id = %s;", (self.id,))
        boards = list(self.cursor.fetchone())
        boards[0]['boards'][index_board]['lists'][index_list]['tasks'].append(task)
        boards = tuple(boards)
        self.cursor.execute("UPDATE users SET trello = %s WHERE id = %s;",
                            (json.dumps(boards[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # User added to a channel with a board
    def board_added_to_user(self):
        self.start_connection()
        self.cursor.execute("SELECT trello "
                            "FROM users "
                            "WHERE id = %s;", (self.id,))
        boards = list(self.cursor.fetchone())
        boards[0]['boards'] = self.member['boards']
        boards = tuple(boards)
        self.cursor.execute("UPDATE users SET trello = %s WHERE id = %s;",
                            (json.dumps(boards[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # A user joined a channel
    def new_group_added(self, channel_id):
        self.start_connection()
        self.cursor.execute("SELECT metadata "
                            "FROM users "
                            "WHERE id = %s;", (self.id,))
        user = self.cursor.fetchone()
        user = list(user)
        if channel_id not in user[0]['groups']:
            self.groups.append(channel_id)
            user[0]['num_groups'] += 1
            user[0]['groups'].append(channel_id)
        self.cursor.execute('UPDATE users SET metadata = %s WHERE id = %s;',
                            (json.dumps(user[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # A board was deleted
    def board_deleted(self, channel_id):
        self.groups.pop(self.groups.index(channel_id))
        self.start_connection()
        self.cursor.execute("SELECT metadata "
                            "FROM users "
                            "WHERE id = %s;", (self.id,))
        user = self.cursor.fetchone()
        user = list(user)
        user[0]['groups'] = self.groups
        user[0]['num_groups'] -= 1
        self.cursor.execute('UPDATE users SET metadata = %s WHERE id = %s;',
                            (json.dumps(user[0]),
                             self.id))
        self.connection.commit()
        self.stop_connection()

    # Start database connection
    def start_connection(self):
        self.connection = psycopg2.connect(user=os.environ.get('SQL_USER'),
                                           password=os.environ.get('SQL_PASSWORD'),
                                           host=os.environ.get('SQL_HOST'),
                                           port=os.environ.get('SQL_PORT'),
                                           database=os.environ.get('SQL_NAME'))
        self.cursor = self.connection.cursor()

    # Stop database connection
    def stop_connection(self):
        self.cursor.close()
        self.connection.close()
