'''
This file implements server functionality of chat application.

Usage: python3 server.py
'''
# Import relevant python packages
from select import select
from collections import defaultdict
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
import sys
# Constants/configurations
ENCODING    = 'utf-8' # message encoding
BUFFER_SIZE = 2048 # fixed 2KB buffer size
PORT        = 1234 # fixed application port

SERVER_IP      = '10.250.249.9' # REPLACE ME with output of ipconfig getifaddr en0
MAX_CLIENTS    = 100
LOGIN_ATTEMPTS = 3

# Fault Tolerance
REPLICATION  = 2 # Number of servers (leader + replicas)
LEADER       = 0 # server ID for leader
INFO_COUNT   = 3 # state length (username, password, and mailbox length)
SERVER_ADDRS = [] # list of server IP addresses

# Remove sock from active sockets
def remove_connection(sock, addr, active_sockets):
    assert sock in active_sockets, 'ERROR: remove_connection encountered corrupted active_sockets'
    active_sockets.remove(sock)
    sock.close()
    print('Removed {}:{} from active sockets'.format(addr[0], addr[1]))

# Handles user creation for new users
def create_user(sock, addr, users, active_sockets):
    # Solicit username
    sock.send('\nPlease enter a username: '.encode(encoding=ENCODING))
    username = sock.recv(BUFFER_SIZE)
    if not username:
        remove_connection(sock, addr, active_sockets)
        return
    username = username.decode(encoding=ENCODING).strip() # get the username in string without \n
    
    # New username
    if username not in users:
        # Solicit password
        sock.send('Please enter a password.'.encode(encoding=ENCODING))
        password = sock.recv(BUFFER_SIZE)
        if not password:
            remove_connection(sock, addr, active_sockets)
            return
        password = password.decode(encoding=ENCODING).strip()

        # Update user information
        users[username]['socket']   = sock
        users[username]['password'] = password
        users[username]['mailbox']  = []

        # Confirm success of account creation
        print('{}:{} successfully created account with username: {}'.format(addr[0], addr[1], username))
        sock.send('\nSuccessfully created account with username: {}\n'.format(username).encode(encoding=ENCODING))
        
        return username
    # Username has already been taken (re-enter)
    else:
        sock.send('{} is already taken. Please enter a unique username.\n'.format(username).encode(encoding=ENCODING))
        return create_user(sock, addr, users, active_sockets)
    
# Handles login for existing user
def login(sock, addr, users, active_sockets, backup_sockets, attempt_num):
    # Solicit username
    sock.send('\nPlease enter your username.'.encode(encoding=ENCODING))
    username = sock.recv(BUFFER_SIZE)
    if not username:
        remove_connection(sock, addr, active_sockets)
        return
    username = username.decode(encoding=ENCODING).strip() # get the username in string without \n

    # Username exists
    if username in users:
        # Solicit password
        sock.send('Please enter your password.'.encode(encoding=ENCODING))
        password = sock.recv(BUFFER_SIZE)
        if not password:
            remove_connection(sock, addr, active_sockets)
            return
        password = password.decode(encoding=ENCODING).strip()

        # Entered correct password
        if password == users[username]['password']:
            # update user's active socket
            users[username]['socket'] = sock

            print('{} successfully logged via {}:{}'.format(username, addr[0], addr[1]))
            sock.send('\nSuccessfully logged in\n'.encode(encoding=ENCODING))

            # No mail to send
            if len(users[username]['mailbox']) == 0:
                sock.send('\nYou do not have any queued messages.'.encode(encoding=ENCODING))
            # Send mail and clear mailbox
            else:
                sock.send('\nWelcome back, {}. Unread messages:\n'.format(username).encode(encoding=ENCODING))
                for message in users[username]['mailbox']:
                    users[username]['socket'].send(message.encode(encoding=ENCODING))
                users[username]['mailbox'] = []
        
            return username
        # Entered incorrect password
        else:
            sock.send('\nIncorrect password.\n'.encode(encoding=ENCODING))
            if attempt_num < LOGIN_ATTEMPTS:
                sock.send('Failed to login. You have {} remaining attempts.\n'.format(LOGIN_ATTEMPTS-attempt_num).encode(encoding=ENCODING))
                return login(sock, addr, users, active_sockets, backup_sockets, attempt_num+1)
            else:
                sock.send('Failed to login. Returning to the welcome page.\n'.encode(encoding=ENCODING))
                return welcome(sock, addr, users, active_sockets, backup_sockets)
    
    # Username does not exist
    else:
        sock.send('\n{} is not a valid username.\n'.format(username.strip()).encode(encoding=ENCODING))
        if attempt_num < LOGIN_ATTEMPTS:
            sock.send('Failed to login. You have {} remaining attempt(s).\n'.format(LOGIN_ATTEMPTS-attempt_num).encode(encoding=ENCODING))
            return login(sock, addr, users, active_sockets, backup_sockets, attempt_num+1)
        else:
            sock.send('Failed to login. Returning to the welcome page.\n'.encode(encoding=ENCODING))
            return welcome(sock, addr, users, active_sockets, backup_sockets)

# Handles 1) user creation and 2) login for users
def welcome(sock, addr, users, active_sockets, backup_sockets):
    sock.send('\nPlease enter 1 or 2 :\n1. Create account.\n2. Login'.encode(encoding=ENCODING))
    choice = sock.recv(BUFFER_SIZE)
    if not choice:
        remove_connection(sock, addr, active_sockets)
        return
    choice = int(choice.decode(encoding=ENCODING))

    if choice == 1:
        username = create_user(sock, addr, users, active_sockets)
    elif choice == 2:
        username = login(sock, addr, users, active_sockets, backup_sockets, attempt_num=1)
    else:
        sock.send('{} is not a valid option. Please enter either 1 or 2!'.format(choice).encode(encoding=ENCODING))
        welcome(sock, addr, users, active_sockets, backup_sockets)
    update(users, backup_sockets)
    return username

# Thread for server socket to interact with each client user in chat application
def client_thread(sock, addr, users, active_sockets, machine_num, backup_sockets):
    # Send to client all backup IPs
    message = ''
    for addr in SERVER_ADDRS[1:]:
        message += addr
        message += ','
    message += '@'
    sock.send(message.encode(encoding=ENCODING))

     # Handle 1) user creation and 2) login
    print('*** in client thread')
    src_username = welcome(sock, addr, users, active_sockets, backup_sockets)

    # Let user know all other users available for messaging
    sock.send('\nWelcome to chatroom!\nAll users:\n'.encode(encoding=ENCODING))
    for index, username in enumerate(users):
        sock.send('{}. {}\n'.format(index, username).encode(encoding=ENCODING))

    while True:
        try:
            sock.send('\nPlease enter 1, 2, or 3:\n1. Send message.\n2. List all users.\n3. Delete your account.'.encode(encoding=ENCODING))
            choice = sock.recv(BUFFER_SIZE)
            if not choice:
                remove_connection(sock, addr, active_sockets)
                print('{} logged off.'.format(src_username))
                return
            choice = int(choice.decode(encoding=ENCODING))

            # Send message to another user
            if choice == 1:
                # Solicit target user
                sock.send('\nEnter username of message recipient:'.encode(encoding=ENCODING))
                dst_username = sock.recv(BUFFER_SIZE)
                if not dst_username:
                    remove_connection(sock, addr, active_sockets)
                    print('{} logged off.'.format(src_username))
                    return
                dst_username = dst_username.decode(encoding=ENCODING).strip()
                
                # Client specified target user that does not exist - return to general chat application loop
                if dst_username not in users:
                    sock.send('Target user {} does not exist!\n'.format(dst_username).encode(encoding=ENCODING))
                    continue
                
                # Solicit message
                sock.send('Enter your message: '.encode(encoding=ENCODING))
                message = sock.recv(BUFFER_SIZE)
                if not message:
                    remove_connection(sock, addr, active_sockets)
                    print('{} logged off.'.format(src_username))
                    return
                message = '<{}> {}'.format(src_username, message.decode(encoding=ENCODING))

                # Target user is online so deliver message immediately
                if users[dst_username]['socket'] in active_sockets:
                    users[dst_username]['socket'].send(message.encode(encoding=ENCODING))
                    sock.send('\nMessage delivered to active user.\n'.encode(encoding=ENCODING))
                    print('(DELIVERED TO USER) <to {}> {}'.format(dst_username, message))

                # Target user is currently offline so deliver message to mailbox
                else:
                    users[dst_username]['mailbox'].append(message)
                    sock.send('\nMessage delivered to mailbox.\n'.encode(encoding=ENCODING))
                    print('(DELIVERED TO MAILBOX) <to {}> {}'.format(dst_username, message))

            elif choice == 2:
                sock.send('\nAll users:\n'.encode(encoding=ENCODING))
                for index, username in enumerate(users):
                    sock.send('{}. {}\n'.format(index, username).encode(encoding=ENCODING))

            elif choice == 3:
                sock.send('\nType confirm to delete your current account'.encode(encoding=ENCODING))
                confirm = sock.recv(BUFFER_SIZE)
                if not confirm:
                    remove_connection(sock, addr, active_sockets)
                    print('{} logged off.'.format(src_username))
                    return
                confirm = confirm.decode(encoding=ENCODING).strip()
                if confirm == 'confirm':
                    del users[src_username]
                    remove_connection(sock, addr, active_sockets)
                    print('{} deleted account.'.format(src_username))
                    return

            else:
                sock.send('\n{} is not a valid option. Please enter either 1, 2, or 3.'.format(choice).encode(encoding=ENCODING))
            update(users, backup_sockets)
        # If we're unable to send a message, close connection.  
        except:
            remove_connection(sock, addr, active_sockets)
            print('{} logged off.'.format(src_username))
            return
        
def update(users, backup_sockets):
    print("Updating states in Backup replicas")
    for index, username in enumerate(users):
        for sock in backup_sockets:
            message = '{}.{}.{}.'.format(username, users[username]['password'], len(users[username]['mailbox']))
        
            if len(users[username]['mailbox']) != 0:
                for mail in users[username]['mailbox']:
                    message += '{}.'.format(mail)
            sock.send(message.encode(encoding=ENCODING))

# Creates and connects client sockets for model machines that have lower machine number than you.
def connect_with_leader(my_machine_number):
    leader_port   = PORT + LEADER
    client = socket(family=AF_INET, type=SOCK_STREAM) # creates client socket with IPv4 and TCP
    client.connect((SERVER_ADDRS[LEADER], leader_port)) # connect to server socket
    print('BACKUP: ({}-{}) LEADER-backup socket established @ {}:{}.'.format(LEADER, my_machine_number, SERVER_ADDRS[LEADER], leader_port))
    return client

def main():
    # Global variables that have to be updated throughout
    global LEADER
    global REPLICATION
    global SERVER_ADDRS

    if len(sys.argv) != 3:
        print('Usage: python3 server.py leader_ip machine_number')
        sys.exit('server.py exiting')
    
    leader_ip   = str(sys.argv[1])
    machine_num = int(sys.argv[2])
    assert machine_num <= REPLICATION, 'Model machine number greater than expected total number of model machines'
    SERVER_ADDRS = [leader_ip]

    # Creates server socket with IPv4 and TCP
    server = socket(AF_INET, SOCK_STREAM)
    server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1) # allow for multiple clients

    # Remember to run 'ipconfig getifaddr en0' and update SERVER_IP
    server.bind((SERVER_IP, PORT+machine_num))
    server.listen(MAX_CLIENTS) # accept up to MAX_CLIENTS active connections

    # If you are a replica, connect to the leader server
    if machine_num != LEADER:
        backup_client_socket = connect_with_leader(machine_num)
    
    active_sockets = [] # running list of active client sockets
    '''
    'users' is a hashmap to store all client data
        - key: username
        - values: 'password', 'socket', 'mailbox'
    '''
    users = defaultdict(dict)
    backup_init = True

    info_count = 0

    while True:
        # Leader Execution
        if machine_num == LEADER:
            backup_sockets = []
            SERVER_ADDRS = [SERVER_IP]
            # Make sure leader is connected with all required number of backups
            for backup_num in range(REPLICATION):
                sock, backup_addr = server.accept()
                backup_sockets.append(sock)
                SERVER_ADDRS.append(backup_addr[0])
                print('LEADER: {}/{} LEADER-backup socket established @ backup IP'.format(backup_num+1, REPLICATION, backup_addr[0]))
            print('LEADER: SERVER_ADDRS: {}'.format(SERVER_ADDRS))
            # Send to each backup complete list of backup IP_addresses
            message = ''
            for addr in SERVER_ADDRS[1:]:
                message += addr
                message += ','
            for backup_socket in backup_sockets:
                backup_socket.send(message.encode(encoding=ENCODING))
                print('LEADER: Finished sending backup IP addresses to {}'.format(backup_socket))
            # Main leader server loop
            while True:
                sock, client_addr = server.accept()
                active_sockets.append(sock) # update active sockets list
                print ('LEADER: {}:{} connected'.format(client_addr[0], client_addr[1]))
                # Start new thread for each client user
                Thread(target=client_thread, args=(sock, client_addr, users, active_sockets, machine_num, backup_sockets)).start()
        
        # Backup Execution
        else:
            message = backup_client_socket.recv(BUFFER_SIZE)

            # Leader server socket has disconnected
            if not message:
                print('BACKUP: Leader server @ {}:{} disconnected!'.format(SERVER_ADDRS[LEADER], PORT+LEADER))
                LEADER      = LEADER + 1
                REPLICATION = REPLICATION - 1
                # if I am a replica, connect to new leader
                if machine_num != LEADER:
                    backup_client_socket = connect_with_leader(machine_num)
                    backup_init = True

            # Recieved message from leader server socket
            else:
                if backup_init:
                    SERVER_ADDRS = [SERVER_ADDRS[LEADER]]
                    addr_list = message.decode(encoding=ENCODING).split(',')[:-1]
                    for addr in addr_list:
                        SERVER_ADDRS.append(addr)
                    print('BACKUP: All server IP addresses: {}'.format(SERVER_ADDRS))
                    backup_init = False
                else:
                    print('<MSG from LEADER>: {}'.format(users))
                    info_list = message.decode(encoding=ENCODING).split('.')

                    username  = info_list[0]
                    users[username]['password'] = info_list[1]
                    info_count = int(info_list[2])
                    users[username]['mailbox'] = []
                    if info_count != 0:
                        for info_index in range(info_count):
                            users[username]['mailbox'].append(info_list[INFO_COUNT + info_index])

if __name__ == '__main__':
    main()