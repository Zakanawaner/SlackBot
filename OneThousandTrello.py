############################################################
# Trello client program. The one that gets all Trello Info #
############################################################
# Añadir cuando se cree un nuevo tablero y tarjetas de trello.... ¿cómo?

import requests
import json
import os


class Trello:
    def __init__(self, token, api_key):
        super(Trello, self).__init__()
        # Getting Trello credentials
        self.query = {
               'key': api_key,
               'token': token
            }
        # Hard-coding OneThousandProjects' team's ID
        self.organization_id = os.environ.get('ORGANIZATION_ID')
        # URL template initializations (a lot of potential here)
        self.post_new_team = 'https://api.trello.com/1/organizations?'
        self.get_organization = 'https://api.trello.com/1/organizations/{}?'
        self.get_members_url = 'https://api.trello.com/1/organizations/{}/members?'
        self.get_member_url = 'https://api.trello.com/1/members/{}?'
        self.get_boards_url = 'https://api.trello.com/1/organizations/{}/boards?'
        self.delete_board_url = 'https://api.trello.com/1/boards/{}?'
        self.create_board_url = 'https://api.trello.com/1/boards/?'
        self.get_board_url = 'https://api.trello.com/1/boards/{}?'
        self.get_list_url = 'https://api.trello.com/1/boards/{}/lists?'
        self.get_cards_url = 'https://api.trello.com/1/lists/{}/cards?'
        self.get_checklist_url = 'https://api.trello.com/1/cards/{}/checklists?'
        self.get_board_members_url = 'https://api.trello.com/1/boards/{}/members?'
        self.get_member_boards_url = 'https://api.trello.com/1/members/{}/boards'
        self.post_new_card_url = 'https://api.trello.com/1/cards?'
        self.post_new_comment_card_url = 'https://api.trello.com/1/cards/{}/actions/comments?'
        self.add_member_to_task_url = 'https://api.trello.com/1/cards/{}/idMembers?'
        self.add_member_to_board_url = 'https://api.trello.com/1/boards/{}/members/{}?'
        # Processing Trello boards' data
        self.boards = self.get_boards_structure()
        # Processing Trello members'data
        self.members = self.get_members_structure()

    def get_boards_structure(self):
        # Getting all raw boards
        raw_boards = json.loads(
                requests.get(self.get_boards_url.format(self.organization_id), params=self.query).text
            )
        # Getting what we want from the raw info
        boards = [{'id': board['id'], 'name': board['name'], 'members': [membership['idMember'] for membership in board['memberships']], 'num_tasks': 0} for board in raw_boards]
        # Building the board structure with its cards and checklists
        for i, board in enumerate(boards):
            raw_lists = json.loads(
                requests.get(self.get_list_url.format(board['id']), params=self.query).text
            )
            lists = [{'id': list_['id'], 'name': list_['name']} for list_ in raw_lists]
            if len(lists) != 0:
                boards[i]['lists'] = lists
                for j, _list in enumerate(lists):
                    raw_tasks = json.loads(
                        requests.get(self.get_cards_url.format(_list['id']), params=self.query).text
                    )
                    tasks = [{'id': task['id'], 'name': task['name'], 'members': task['idMembers'], 'time': 0} for task in raw_tasks]
                    if len(tasks) != 0:
                        boards[i]['lists'][j]['tasks'] = tasks
                        boards[i]['num_tasks'] += len(tasks)
                        for k, task in enumerate(tasks):
                            get_checklist = json.loads(
                                requests.get(self.get_checklist_url.format(task['id']), params=self.query).text
                            )
                            checklists = [(checklist['id'], checklist['name']) for checklist in get_checklist]
                            boards[i]['lists'][j]['tasks'][k]['checklists'] = checklists
        return boards

    def assign_boards(self, slack_channel):
        done = False
        for board in self.boards:
            if board['name'].lower().replace('_', '').replace(' ', '').replace('-', '') == slack_channel.name.replace('_', '').replace(' ', '').replace('-', ''):
                slack_channel.board = board
                done = True
                break
        return slack_channel, done

    def get_members_structure(self):
        # Getting all raw boards
        raw_members = json.loads(
            requests.get(self.get_members_url.format(self.organization_id), params=self.query).text
        )
        # Getting what we want from the raw info
        members = [{'id': member['id'], 'name': member['fullName'], 'boards': [], 'num_tasks': 0} for member in raw_members]
        for i, member in enumerate(members):
            num_boards = 0
            for board in self.boards:
                num_lists = 0
                if member['id'] in board['members']:
                    members[i]['boards'].append({'id': board['id'], 'name': board['name'], 'lists': []})
                    if 'lists' in board.keys():
                        for _list in board['lists']:
                            num_tasks = 0
                            members[i]['boards'][num_boards]['lists'].append({'id': _list['id'], 'name': _list['name'], 'tasks': []})
                            if 'tasks' in _list.keys():
                                for task in _list['tasks']:
                                    if member['id'] in task['members']:
                                        members[i]['boards'][num_boards]['lists'][num_lists]['tasks'].append(task)
                                        num_tasks += 1
                            num_lists += 1
                    num_boards += 1
        return members

    def assign_members(self, slack_member):
        done = False
        for member in self.members:
            if member['name'].lower().replace('_', '').replace(' ', '').replace('-', '') == slack_member.real_name.lower().replace('_', '').replace(' ', '').replace('-', ''):
                slack_member.member = member
                done = True
                break
        return slack_member, done

    def add_task(self, name_task, list_id, member_id):
        requests.post(self.post_new_card_url, params={'key': self.query['key'], 'token': self.query['token'], 'idMembers': [member_id], 'name': name_task, 'idList': list_id})
        raw_tasks = json.loads(
            requests.get(self.get_cards_url.format(list_id), params=self.query).text
        )
        for task in raw_tasks:
            if task['name'] == name_task:
                return {'id': task['id'], 'name': task['name'], 'members': task['idMembers'], 'time': None}
        return {}

    def new_comment_card(self, card_id, comment):
        requests.post(self.post_new_comment_card_url.format(card_id), params={'key': self.query['key'], 'token': self.query['token'], 'text': comment})

    def delete_board(self, board_id):
        requests.post(self.delete_board_url.format(board_id), params={'key': self.query['key'], 'token': self.query['token']})

    def update_board(self, board_id):
        exists = False
        for i, board in enumerate(self.boards):
            if board['id'] == board_id:
                index_board = i
                exists = True
                break
        if exists:
            raw_lists = json.loads(
                requests.get(self.get_list_url.format(board_id), params=self.query).text
            )
            lists = [{'id': list_['id'], 'name': list_['name']} for list_ in raw_lists]
            self.boards[index_board]['lists'] = lists
            if len(lists) != 0:
                for j, _list in enumerate(lists):
                    raw_tasks = json.loads(
                        requests.get(self.get_cards_url.format(_list['id']), params=self.query).text
                    )
                    tasks = [{'id': task['id'], 'name': task['name'], 'members': task['idMembers'], 'time': 0} for task in
                             raw_tasks]
                    if len(tasks) != 0:
                        self.boards[index_board]['lists'][j]['tasks'] = tasks
                        self.boards[index_board]['num_tasks'] += len(tasks)
            return True, self.boards[index_board]
        else:
            return False, {}

    def create_board(self, board_name):
        requests.post(self.create_board_url, params={'key': self.query['key'], 'token': self.query['token'], 'idOrganization': self.organization_id, 'name': board_name})
        raw_boards = json.loads(
            requests.get(self.get_boards_url.format(self.organization_id), params=self.query).text
        )
        for i, board in enumerate(raw_boards):
            if board['name'] == board_name:
                self.boards.append({'id': board['id'], 'name': board['name'], 'members': [membership['idMember'] for membership in board['memberships']], 'num_tasks': 0})
                return {'id': board['id'], 'name': board['name'], 'members': [membership['idMember'] for membership in board['memberships']], 'num_tasks': 0}

    def add_member_to_task(self, task_id, member_id):
        requests.post(self.add_member_to_task_url.format(task_id), params={'key': self.query['key'], 'token': self.query['token'], 'value': member_id})

    def add_member_to_board(self, board_id, member_id):
        requests.post(self.add_member_to_board_url.format(board_id, member_id), params={'key': self.query['key'], 'token': self.query['token'], 'type': 'normal'})
