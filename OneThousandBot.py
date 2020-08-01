################################################
# Bot program. The one that constructs the Bot #
################################################

from datetime import datetime
from OneThousandPasarell import Gateway
from OneThousandData import Project, User
from OneThousandTrello import Trello
import os

BOT_ID = os.environ.get('BOT_ID')


class Bot:
    def __init__(self, token, token_trello, api_key_trello):
        super(Bot, self).__init__()
        # Saving tokens and api key's
        self.token = token
        self.token_trello = token_trello
        self.api_key_trello = api_key_trello
        # Initializing the gateway
        self.gateway = Gateway(self.token)
        # Getting raw Slack projects
        self.projects = self.gateway.method_get_channels(types='private_channel')
        # Getting raw Slack channels
        self.channels = self.gateway.method_get_channels(types='public_channel')
        # Getting raw Slack users
        self.users = self.gateway.method_get_users()
        # Initializing Trello client
        self.trello_client = Trello(self.token_trello, self.api_key_trello)
        # Getting the info from the raw Slack channels, projects and users
        self.channels_db = self.get_channel_info(self.channels, [])
        self.channels_db = self.get_channel_info(self.projects, self.channels_db)
        self.users_db = self.get_users_info(self.users, self.channels_db, [])
        self.last_event = ''

    #####################################
    # USERS / CHANNELS HANDLING METHODS #
    #####################################

    # Find User index in the Bot class database
    def find_user(self, identity):
        for i, user in enumerate(self.users_db):
            if user.id == identity:
                return i
        return -1

    # Function that gets Users information for the first time
    def get_users_info(self, lists, all_channels, li, new=False):
        if new:
            for user in lists['members']:
                if (not user['is_bot'] or user['id'] == BOT_ID) and not user['deleted']:
                    unit = User(user, self.token, all_channels)
                    unit, unit.has_trello = self.trello_client.assign_members(unit)
                    channel = self.gateway.method_open_direct_channel(user['id'])
                    if 'channel' in channel.keys():
                        unit.direct_channel_id = channel['channel']['id']
                    unit.save_data()
                    li.append(unit)
        else:
            for user in lists['members']:
                if (not user['is_bot'] or user['id'] == BOT_ID) and not user['deleted']:
                    unit = User(user, self.token, all_channels)
                    unit, unit.has_trello = self.trello_client.assign_members(unit)
                    channel = self.gateway.method_open_direct_channel(user['id'])
                    if 'channel' in channel.keys():
                        unit.direct_channel_id = channel['channel']['id']
                    unit.save_data()
                    li.append(unit)
        return li

    # If a new user has joined
    def new_user(self, id_user):  # todo test
        user = self.gateway.method_get_users(new=True, id_user=id_user)
        self.users_db = self.get_users_info([user], self.channels_db, self.users_db, new=True)

    # Find Channel index in the Bot class database
    def find_channel(self, identity):
        for i, channel in enumerate(self.channels_db):
            if channel.id == identity:
                return i
        return -1

    # Function that gets Channels information for the first time
    def get_channel_info(self, lists, li, new=False):
        if new:
            unit = Project(lists['channel'], self.token)
            unit, unit.has_trello = self.trello_client.assign_boards(unit)
            unit.save_data()
            li.append(unit)
        else:
            for channel in lists['channels']:
                unit = Project(channel, self.token)
                unit, unit.has_trello = self.trello_client.assign_boards(unit)
                unit.save_data()
                li.append(unit)
        return li

    # A new channel has been created
    def new_channel(self, id_channel):
        if self.find_channel(id_channel) == -1:
            channel = self.gateway.method_get_channels(new=True, id_channel=id_channel)
            self.channels_db = self.get_channel_info(channel, self.channels_db, new=True)

    # A channel has been deleted
    def channel_deleted(self, id_channel):
        for i, user in enumerate(self.users_db):
            if id_channel in user.groups:
                self.users_db[i].board_deleted(id_channel)

    # An user was added to a channel with a board
    def add_board_to_member(self, index_channel, index_user):
        if self.users_db[index_user].member != {}:
            self.users_db[index_user].member['boards'].append({'id': self.channels_db[index_channel].board['id'], 'name': self.channels_db[index_channel].board['name'], 'lists': []})
            if 'lists' in self.channels_db[index_channel].board.keys():
                num_lists = 0
                for _list in self.channels_db[index_channel].board['lists']:
                    num_tasks = 0
                    self.users_db[index_user].member['boards'][len(self.users_db[index_user].member['boards']) - 1]['lists'].append(
                        {'id': _list['id'], 'name': _list['name'], 'tasks': []})
                    if 'tasks' in _list.keys():
                        for task in _list['tasks']:
                            if self.users_db[index_user].member['id'] in task['members']:
                                self.users_db[index_user].member['boards'][len(self.users_db[index_user].member['boards']) - 1]['lists'][num_lists]['tasks'].append(task)
                                num_tasks += 1
                    num_lists += 1
            self.users_db[index_user].new_group_added(self.channels_db[index_channel].id)

    def add_member_to_board(self, index_channel, index_user):
        if self.users_db[index_user].member != {}:
            if self.users_db[index_user].member['id'] not in self.channels_db[index_channel].board['members']:
                self.channels_db[index_channel].board['members'].append(self.users_db[index_user].member['id'])
                self.trello_client.add_member_to_board(self.channels_db[index_channel].board['id'], self.users_db[index_user].member['id'])

    ###################################
    # SLASH COMMANDS HANDLING METHODS #
    ###################################

    # /Work command handling
    def work(self, request):
        # Get request information
        index_user = self.find_user(request.form['user_id'])
        index_channel = self.find_channel(request.form['channel_id'])
        type_command = request.form['text'][:request.form['text'].find(' ')]
        task_name = request.form['text'][(request.form['text'].find(' ') + 1):]
        done_board = False
        done_member = False
        done_board_in_member = False
        # Loop for getting the board position on the user Class
        for i, board in enumerate(self.users_db[index_user].member['boards']):
            if self.channels_db[index_channel].board['id'] == board['id']:
                index_board = i
                done_board_in_member = True
                break
        if done_board_in_member:
            # Loop for checking if the User has the task assigned
            for i, list_ in enumerate(self.channels_db[index_channel].board['lists']):
                if 'tasks' in list_.keys():
                    for j, task in enumerate(list_['tasks']):
                        if task['name'].lower().replace(' ', '') == task_name.lower().replace(' ', ''):
                            done_board = True
                            list_index = i
                            task_index_board = j
                            break
                    if done_board:
                        for i, list_ in enumerate(self.users_db[index_user].member['boards'][index_board]['lists']):
                            for j, task in enumerate(list_['tasks']):
                                if task['name'].lower().replace(' ', '') == task_name.lower().replace(' ', ''):
                                    done_member = True
                                    task_index_member = j
                                    break
                            if done_member: break
                        if done_member:
                            response = ''
                            break
                        else:
                            self.trello_client.add_member_to_task(self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board]['id'], self.users_db[index_user].member['id'])
                            self.users_db[index_user].member['boards'][index_board]['lists'][list_index]['tasks'].append(self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board])
                            self.users_db[index_user].added_to_task(index_board, list_index, self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board])
                            task_index_member = len(self.users_db[index_user].member['boards'][index_board]['lists'][list_index]['tasks']) - 1
                            response = ' No estabas añadid@ en la tarea de Trello, pero como tienes muchas ganas de trabajar en ella, te añado.'
                            done_member = True
                        break
        else:
            response = 'El usuario que quieres añadir a la tarea no está en el proyecto. Para poder asignarle tareas deberías añadirlo al canal'
            return response
        # Check the type of commando [start/stop]
        if done_board and done_member:
            if type_command == 'start':
                if not self.users_db[index_user].working:
                    self.users_db[index_user].working = True
                    self.users_db[index_user].start = datetime.now()
                    response = 'Ok, <@' + request.form['user_id'] + '>. Comienzo a registrar tu trabajo en la tarea.' + response
                else:
                    response = '<@' + request.form['user_id'] + \
                               '>, se supone que ya estabas trabajando desde las {}h, {}m, {}s.'.format(
                                   self.users_db[index_user].start.hour,
                                   self.users_db[index_user].start.minute,
                                   self.users_db[index_user].start.second)
            elif type_command == 'stop' or task_name == 'stop':
                if self.users_db[index_user].working:
                    self.users_db[index_user].working = False
                    self.users_db[index_user].end = datetime.now()
                    work_time = self.users_db[index_user].end - self.users_db[index_user].start
                    if self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board]['time'] == 0:
                        self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board]['time'] = work_time
                        self.users_db[index_user].member['boards'][index_board]['lists'][list_index]['tasks'][task_index_member]['time'] = work_time
                    else:
                        self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board]['time'] += work_time
                        self.users_db[index_user].member['boards'][index_board]['lists'][list_index]['tasks'][task_index_member]['time'] += work_time
                    self.trello_client.new_comment_card(
                        self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board]['id'],
                        self.users_db[index_user].member['name'] + ' trabajó {} en esta tarea'.format(work_time))
                    response = 'Ok, <@' + request.form['user_id'] + \
                               '>. Has trabajado {} horas en la tarea {}.'.format(
                                   work_time,
                                   self.channels_db[index_channel].board['lists'][list_index]['tasks'][task_index_board]['name'])
                else:
                    response = '<@' + request.form['user_id'] + \
                               '>, no sabía que estabas trabajando'
            else:
                response = '<@' + request.form['user_id'] + \
                           '>, Me solo interpretar <start> o <stop>'
        else:
            response = '<@' + request.form['user_id'] + \
                       '>, La tarea que has introducido no es correcta. Verifica en qué tarea quieres trabajar, o si has hecho cambios en el tablero desde Trello, ejecuta el comando /updateboard para actualizar esos cambios y vuelve a intentarlo'
        return response

    # /Help command handling
    def help(self, request):
        response = '''Hola, estás en la sección de ayuda de OneThousandBot. Estoy en modo test, pero soy funcional. Los comandos son bastante sencillos de ejecutar. Simplemente escribe '/' y el comando correspondiente (que describo más abajo), seguido de los argumentos separados por espacio. Los comandos que puedes ejecutar son:
        /work start <nombre de la tarea de Trello>
        Con este comando me indicarás que comienzas a trabajar en esta tarea. Es importante que ejecutes este comando en el chat del proyecto que contiene la tarea, y que dicha tarea exista en el board de trello.
        /work stop <nombre de la tarea de Trello>
        Con este comando me indicarás que has terminado de trabajar en la tarea. Es importante que ejecutes este comando en el chat del proyecto que contiene la tarea, y que dicha tarea exista en el board de trello. Cuando hayas terminado tu sesión de trabajo, añadiré en la tarjeta de Trello el tiempo que has dedicado a la misma.
        /add <@usuario> <nombre de lista de Trello>|<nombre de la tarea a crear>
        Con este comando crearás una tarea nueva en Trello y se la asignarás al usuario que nombres. Esta tarea se creará dentro de la lista que tú especifiques (recuerda que debe existir dicha lista, dentro del board correspondiente al canal desde donde me envías el comando'''
        return response

    # /Add command handling
    def add(self, request):
        # Get request information
        index_user_in_request = request.form['text'].find('|')
        index_list_in_request = request.form['text'].find(' ') + 1
        index_task_in_request = request.form['text'][index_list_in_request:].find('|') + index_list_in_request + 1
        index_user = self.find_user(request.form['text'][2:index_user_in_request])
        index_channel = self.find_channel(request.form['channel_id'])
        list_name = request.form['text'][index_list_in_request:index_task_in_request - 1]
        task_name = request.form['text'][index_task_in_request:]
        done = False
        already_exists = False
        # Loop for checking if the task to add already exists
        if 'lists' in self.channels_db[index_channel].board:
            for list_ in self.channels_db[index_channel].board['lists']:
                if list_['name'].lower().replace(' ', '') == list_name.lower().replace(' ', ''):
                    if 'tasks' in list_.keys():
                        for task_ in list_['tasks']:
                            if task_['name'].lower().replace(' ', '') == task_name.lower().replace(' ', ''):
                                task = task_
                                already_exists = True
                                break
                    done = True
                    id_list = list_['id']
        # List especified doesn´t exists
        if not done:
            return 'La lista que has especificado no existe en el tablero. Estas son las listas en el tablero:\n' + \
                   str([list_['name'] + ' ' for list_ in self.channels_db[index_channel].board['lists']]) + \
                   '\nSi no existe la lista que buscas, créala en Trello antes de añadir la tarea o ejecuta aquí el comando' \
                   '/addlist <nombre de la lista>'
        else:
            # New task for the board
            if not already_exists:
                task = self.trello_client.add_task(task_name, id_list, self.users_db[index_user].member['id'])
                self.channels_db[index_channel].add_task(list_name, task)
            added, existed = self.users_db[index_user].add_task(self.channels_db[index_channel].board['id'], list_name, task)
            if added:
                self.trello_client.add_member_to_task(task['id'], self.users_db[index_user].member['id'])
                return 'Tarea ' + task_name + ' añadida a ' + self.users_db[index_user].real_name + \
                       ' en el proyecto ' + self.channels_db[index_channel].name + \
                       '.'
            if existed:
                return 'La tarea ' + task_name + ' ya existe y está asignada a ' + self.users_db[index_user].real_name + \
                       ' en el proyecto ' + self.channels_db[index_channel].name + \
                       '.'

    # /trellobot command handling
    def trello(self, request):
        index_channel = self.find_channel(request.form['channel_id'])
        board = self.channels_db[index_channel].board
        response = ''
        if board == {}:
            return 'Este canal no tiene un tablero de Trello asociado. Si quieres crearlo utiliza el comando /createboard'
        else:
            if 'lists' in board.keys():
                for list_ in board['lists']:
                    response += '\n\nLista:\n'
                    response += list_['name'] + '\n'
                    if 'tasks' in list_.keys():
                        response += 'Tareas: \n'
                        for task in list_['tasks']:
                            response += task['name'] + '\n'
                    else:
                        response += 'No hay tareas en esta lista\n'
            else:
                response += 'No hay listas en el tablero\n'
            return 'El tablero del proyecto ' + self.channels_db[self.find_channel(request.form['channel_id'])].name + ' se compone de:\n' + response

    # /deleteboard command handling
    def delete_board(self, request):
        self.trello_client.delete_board(request.form['text'])
        return 'Tablero eliminado :smiley:'

    # /updateboard command handling
    def update_board(self, request):
        channel = self.channels_db[self.find_channel(request.form['channel_id'])]
        if channel.board != {}:
            done, board = self.trello_client.update_board(channel.board['id'])
            if not done:
                return 'Hubo un problema'
            else:
                self.channels_db[self.find_channel(request.form['channel_id'])].board = board
                self.channels_db[self.find_channel(request.form['channel_id'])].update_board()
                return 'Tablero actualizado :smiley:'
        else:
            return 'Este canal no tiene tablero de trello asociado'

    # /createboard comand handling
    def create_board(self, request):
        index_channel = self.find_channel(request.form['channel_id'])
        board = self.channels_db[index_channel].board
        if board == {}:
            board_created = self.trello_client.create_board(self.channels_db[index_channel].name)
            for user in self.channels_db[index_channel].participants['members']:
                index_user = self.find_user(user)
                if 'id' in self.users_db[index_user].member:
                    if self.users_db[index_user].member['id'] not in board_created['members']:
                        board_created['members'].append(self.users_db[index_user].member['id'])
                        self.users_db[index_user].member['boards'].append({'id': board_created['id'], 'name': board_created['name'], 'lists': []})
                        self.users_db[index_user].board_added_to_user()
            self.channels_db[index_channel].trello_board_added(board_created)
            return 'Tablero creado :smiley:'
        else:
            return 'Este canal ya tiene un tablero de Trello asociado.'

    ##########################
    # EVENT HANDLING METHODS #
    ##########################

    def event_app_mention(self, event_data):
        self.gateway.method_post_message(
            'Hola, <@' + event_data['event']['user'] +
            '>. Puedo hacer muchas cosas, pero conversar contigo no es una de ellas... aún.',
            event_data['event']['channel'])

    def event_app_home_opened(self, event_data):
        if not self.users_db[self.find_user(event_data['event']['user'])].greeted:
            self.users_db[self.find_user(event_data['event']['user'])].greeted = True
            self.gateway.method_post_message(
                'Hola, <@' + event_data['event']['user'] + '>. Bienvenid@ a mi canal. ¿En qué puedo ayudarte? Escribe /helpbot si necesitas información sobre lo que puedo hacer',
                event_data['event']['channel'])

    def event_channel_archived(self, event_data):
        index = self.find_user(event_data['event']['user'])
        self.gateway.method_post_message(
            '<@' + event_data['event']['user'] + '>. Siempre puedes recuperar el canal que acabcas de archivar',
            self.users_db[index].direct_channel_id)

    def event_channel_created(self, event_data):
        if self.find_channel(event_data['event']['channel']['id']) == -1:
            self.new_channel(event_data['event']['channel']['id'])
            index = self.find_user(event_data['event']['channel']['creator'])
            self.gateway.method_post_message(
                'Hola, <@' + event_data['event']['channel']['creator'] + '>. Considera añadirme al canal ' +
                event_data['event']['channel']['name'] + ' Para que pueda gestionar el maquineo',
                self.users_db[index].direct_channel_id)

    def event_channel_deleted(self, event_data):
        index_channel = self.find_channel(event_data['event']['channel'])
        index = self.find_user(event_data['event']['actor_id'])
        name_channel = self.channels_db[index_channel].name
        had_trello = self.channels_db[index_channel].has_trello
        self.channels_db[index_channel].create_reading_file()
        self.channels_db.pop(index_channel)
        self.gateway.method_share_file(self.users_db[index].direct_channel_id, '{}_readable.txt'.format(name_channel))  # TODO send not working
        self.gateway.method_post_message(
            '<@' + self.users_db[index].id + '>. Te envío un fichero con el histório del canal ' + name_channel +
            ' que acabas de eliminar.', self.users_db[index].direct_channel_id)
        if had_trello:
            trello_id = self.channels_db[index_channel].board['id']
            self.gateway.method_post_message(
                'EL canal que acabas de eliminar tenía un tablero de Trello asociado. Si quieres que lo elimine por ti,'
                'pídemelo con /deleteboard ' + trello_id +
                '. Ese nombre raro es el indentificador de ' + name_channel, self.users_db[index].direct_channel_id)

        self.channel_deleted(event_data['event']['channel'])

    def event_channel_left(self, event_data):
        index_channel = self.find_channel(event_data['event']['channel'])
        index = self.find_user(self.channels_db[index_channel].creator)
        self.gateway.method_post_message(
            '<@' + self.users_db[index].id + '>. Ten en cuenta que ya no podré gestionar más el maquineo en ' +
            self.channels_db[index_channel].name + '. Siempre puedes volver a añadirme mencionándome en el canal',
            self.users_db[index].direct_channel_id)

    def event_channel_rename(self, event_data):
        self.gateway.method_post_message('No sé los demás, pero a mi me gustaba más el otro nombre...',
                                         event_data['event']['channel']['id'])

    def event_group_archived(self, event_data):
        index_channel = self.find_channel(event_data['event']['channel'])
        index = self.find_user(self.channels_db[index_channel].creator)
        self.gateway.method_post_message(
            '<@' + self.users_db[index].id + '>. Siempre puedes recuperar el canal ' + self.channels_db[
                index_channel].name + ' que acabcas de archivar', self.users_db[index].direct_channel_id)

    def event_member_joined_channel(self, event_data):
        if self.find_user(event_data['event']['user']) != -1:
            self.users_db[self.find_user(event_data['event']['user'])].new_group_added(event_data['event']['channel'])
            self.add_board_to_member(self.find_channel(event_data['event']['channel']), self.find_user(event_data['event']['user']))
            self.add_member_to_board(self.find_channel(event_data['event']['channel']), self.find_user(event_data['event']['user']))
            if event_data['event']['user'] != BOT_ID:
                self.gateway.method_post_message(
                    ':smiley::smiley::smiley: Hola, <@' + event_data['event']['user'] + '>! :smiley::smiley::smiley:',
                    event_data['event']['channel'])
            else:
                if self.find_channel(event_data['event']['channel']) == -1:
                    self.new_channel(event_data['event']['channel'])
                    for member in self.channels_db[self.find_channel(event_data['event']['channel'])].participants['members']:
                        self.users_db[self.find_user(member)].new_group_added(event_data['event']['channel'])
                index_channel = self.find_channel(event_data['event']['channel'])
                index = self.find_user(self.channels_db[index_channel].creator)
                self.gateway.method_post_message(
                    'Hola, <@' + self.channels_db[index_channel].creator + '>. Gracias por añadirme a tu canal.',
                    self.users_db[index].direct_channel_id)
                if not self.channels_db[index_channel].has_trello:
                    self.gateway.method_post_message(
                        'Te recomiendo crear un tablero en Trello para que puedas gestionar las tareas del proyecto.',
                        self.users_db[index].direct_channel_id)
        else:
            self.new_user(event_data['event']['user'])
            index = self.find_user(event_data['event']['user'])
            self.gateway.method_post_message(
                'Hola, <@' + event_data['event']['user'] + '>! Bienvenid@ a OneThousandProjects. Soy <@' + BOT_ID +
                '>, y he sido creado para hacer más fácil el trabajo dentro de este espacio. De momento estoy en '
                'desarrollo pero puedes entrar en los detalles de mi página para ver cómo puedes usar mis funcionalidades '
                ' Ya lo irás viendo, pero llegaré a hacer graaandes cosillas con el tiempo. '
                'Para cualquier pregunta que puedas tener conrespecto al entorno de trabajo, existe el canal problemas_con_el_uso_de_slack. También puedes'
                'ponerte en contacto con José, quien podrá guiarte por el entorno de trabajo.',
                self.users_db[index].direct_channel_id)
            if not self.users_db[index].has_trello:
                self.gateway.method_post_message(
                    'Te recomiendo que te hagas una cuenta de Trello. Si ya la tienes, por favor, asegúrate de que en'
                    'ambas cuentas (Slack y Trello) tienes el mismo nombre. Así podré reconocerte en ambos entornos.',
                    self.users_db[index].direct_channel_id)
        index_channel = self.find_channel(event_data['event']['channel'])
        self.channels_db[index_channel].new_user_added(event_data['event']['user'])

    def event_member_left_channel(self, event_data):
        index_channel = self.find_channel(event_data['event']['channel'])
        index_user = self.find_user(event_data['event']['user'])
        self.gateway.method_post_message(':disappointed_relieved::disappointed_relieved: Te echaremos de menos, <@' +
                                         event_data['event']['user'] + '>!! \n\n\n Aunque nunca me cayó bien del todo...',
                                         event_data['event']['channel'])
        user = self.gateway.method_get_users(new=True, id_user=event_data['event']['user'])
        if user['user']['deleted']:
            for i, project in enumerate(self.channels_db):
                if event_data['event']['user'] in project.participants['members']:
                    self.channels_db[i].participants['members'].pop(self.channels_db[i].participants['members'].index(event_data['event']['user']))
            self.users_db.pop(index_user)
        else:
            self.channels_db[index_channel].participants['members'].remove(event_data['event']['user'])
            self.users_db[self.find_user(event_data['event']['user'])].groups.remove(self.channels_db[index_channel].id)

    def event_message(self, event_data):
        if self.find_channel(event_data['event']['channel']) != -1:
            self.channels_db[self.find_channel(event_data['event']['channel'])].save_new_message(event_data)
        else:
            for user in self.users_db:
                if user.direct_channel_id == event_data['event']['channel'] and event_data['event']['user'] != BOT_ID:
                    self.event_message_app_home(event_data)

    def event_message_app_home(self, event_data):
        self.gateway.method_post_message('Yepa', event_data['event']['channel'])

    def event_team_join(self, event_data):
        self.new_user(event_data['event']['user'])
