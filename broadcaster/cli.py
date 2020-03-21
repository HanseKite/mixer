import time
import queue
import argparse
import logging
import time
import common
import client
import threading

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)


TIMEOUT = 10  # in seconds


class ServerError(RuntimeError):
    def __init__(self, message):
        super().__init__(message)


class CliClient(client.Client):
    def __init__(self, args):
        super().__init__(args.host, args.port)
        self.formatter = common.CommandFormatter()
        self.terminate = False
        consumer_thread = threading.Thread(None, self.consume)
        consumer_thread.start()

    def listRooms(self):
        command = common.Command(common.MessageType.LIST_ROOMS)
        self.post_command(command)

    def deleteRoom(self, name):
        command = common.Command(common.MessageType.DELETE_ROOM, name.encode())
        self.post_command(command)

    def clearRoom(self, name):
        command = common.Command(common.MessageType.CLEAR_ROOM, name.encode())
        self.post_command(command)

    def listRoomClients(self, name):
        command = common.Command(common.MessageType.LIST_ROOM_CLIENTS, name.encode())
        self.post_command(command)

    def listClients(self):
        command = common.Command(common.MessageType.LIST_CLIENTS)
        self.post_command(command)

    def listAllClients(self):
        command = common.Command(common.MessageType.LIST_ALL_CLIENTS)
        self.post_command(command)

    def post_command(self, command: common.Command):
        self.addCommand(command)

    def consume(self):
        # consume pending replies
        while not self.terminate:
            received, _ = super().consume_one()
            if received is None:
                time.sleep(0.1)
            else:
                if received.type == common.MessageType.CONNECTION_LOST:
                    self.disconnect()

                print(self.formatter.format(received))
                # a fake prompt
                print('> ')


def process_room_command(args):
    client = None

    try:
        if args.command == 'list':
            client = CliClient(args)
            client.connect()
            client.listRooms()

        elif args.command == 'delete':
            count = len(args.name)
            if count:
                client = CliClient(args)
                client.connect()
                for name in args.name:
                    client.deleteRoom(name)
            else:
                print('Expected one or more room names')

        elif args.command == 'clear':
            count = len(args.name)
            if count:
                client = CliClient(args)
                client.connect()
                for name in args.name:
                    client.clearRoom(name)
            else:
                print('Expected one or more room names')

        elif args.command == 'clients':
            count = len(args.name)
            if count:
                client = CliClient(args)
                client.connect()
                for name in args.name:
                    client.listRoomClients(name)
            else:
                print('Expected one or more room names')
    except ServerError as e:
        logging.error(e)
    finally:
        if client:
            client.disconnect()


def process_client_command(args):
    client = None

    try:
        if args.command == 'list':
            client = CliClient(args)
            client.connect()
            client.listClients()
    except ServerError as e:
        logging.error(e)
    finally:
        if client is not None:
            client.disconnect()


commands = [
    "connect",
    "disconnect",

    "listrooms",
    "join <roomname>",
    "leave <roomname>",

    "listjoinedclients",
    "listallclients",
    "setclientname <clientname>",

    "listroomclients <roomname>",

    "help"
    "exit"  # this loop
]


def help():
    print("Allowed commands : ")
    for c in commands:
        print(" ", c)
    print()


def interactive_loop():
    client = CliClient(args)
    client.connect()
    done = False
    while not done:
        try:
            prompt = "> "
            print(prompt, end="", flush=False)
            user_input = input()
            items = user_input.split()
            if not items:
                continue
            input_command = items[0]
            candidates = [c for c in commands if c.startswith(input_command)]
            if len(candidates) == 0:
                print(f"Command not recognised : {input_command}.")
                help()
                continue
            if len(candidates) >= 2:
                print(f"ambigous command {input_command} : found {candidates}.")
                continue

            command = candidates[0].split()[0]
            command_args = items[1:]
            if input_command != command:
                print(command, command_args)
            if command == "connect":
                if client is None or not client.isConnected():
                    client = CliClient(args)
                else:
                    print(f"Error : already connected. Use disconnect first")
            elif command == "exit":
                client.terminate = True
                done = True
            elif command == "help":
                help()
            else:
                if client is None or not client.isConnected():
                    raise RuntimeError('Not connected, use "connect" first')
                if command == "listrooms":
                    client.listRooms()
                elif command == "listroomclients":
                    client.listRoomClients(command_args[0])
                elif command == "listjoinedclients":
                    client.listClients()
                elif command == "listallclients":
                    client.listAllClients()
                elif command == "join":
                    client.joinRoom(command_args[0])
                elif command == "leave":
                    client.leaveRoom(command_args[0])
                elif command == "setclientname":
                    client.setClientName(command_args[0])
                elif command == "disconnect":
                    client.disconnect()
                    client = None
                else:
                    pass
        except Exception as e:
            print(f'Exception: {e}')


parser = argparse.ArgumentParser(prog='cli', description='Command Line Interface for VRtist server')
sub_parsers = parser.add_subparsers()

parser.add_argument('--host', help='Host name', default=common.DEFAULT_HOST)
parser.add_argument('--port', help='Port', default=common.DEFAULT_PORT)
parser.add_argument('--timeout', help='Timeout for server response', default=TIMEOUT)

# Room commands are relative to... a room!
room_parser = sub_parsers.add_parser('room', help='Rooms related commands')
room_parser.add_argument('command', help='Commands. Use "list" to list all the rooms of the server. Use "delete" to delete one or more rooms. Use "clear" to clear the commands stack of rooms. Use "clients" to list the clients connected to rooms.', choices=(
    'list', 'delete', 'clear', 'clients'))
room_parser.add_argument('name', help='Room name. You can specify multiple room names separated by spaces.', nargs='*')
room_parser.set_defaults(func=process_room_command)

# Client commands are relative to a client independently of any room
client_parser = sub_parsers.add_parser('client', help='Clients related commands')
client_parser.add_argument('command', help='', choices=('list', 'disconnect'))
client_parser.set_defaults(func=process_client_command)

args = parser.parse_args()
if hasattr(args, 'func'):
    args.func(args)
else:
    interactive_loop()