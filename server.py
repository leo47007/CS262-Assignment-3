'''
This file implements server functionality of chat application.

Usage: python3 server.py LEADER_IP MACHINE_NUM
'''
# Import relevant python packages
from collections import defaultdict
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread
import sys

# Constants/configurations
ENCODING    = 'utf-8' # message encoding
BUFFER_SIZE = 2048 # fixed 2KB buffer size
PORT        = 1234 # base application port for leader server

SERVER_IP      = '100.90.130.16' # REPLACE ME with output of ipconfig getifaddr en0
MAX_CLIENTS    = 100
LOGIN_ATTEMPTS = 3

# Fault-tolerance (parameters and global variables)
STATE_SIZE   = 3 # state length (username, password, and mailbox length)
TIMEOUT_TIME = 0.1 # time for waiting for potential backup to connect (in seconds)
replicas     = 2 # 2-fault tolerant system
leader       = 0 # server ID for leader
server_addrs = [] # list of server IP addresses

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
    message = '\nPlease enter 1 or 2 :\n1. Create account.\n2. Login'
    sock.send(message.encode(encoding=ENCODING))

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

    update_state(backup_sockets, users)
    return username

# Thread for server socket to interact with each client user in chat application
def client_thread(sock, addr, users, active_sockets, backup_sockets):
     # Handle 1) user creation and 2) login
    print('*** started client thread!')

    # For initialization, send to client all backup IPs
    message = ''
    for server_address in server_addrs[1:]:
        message += server_address
        message += ','
    message += '@'
    sock.send(message.encode(encoding=ENCODING))
    
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
            update_state(backup_sockets, users)
        # If we're unable to send a message, close connection.  
        except:
            remove_connection(sock, addr, active_sockets)
            print('{} logged off.'.format(src_username))
            return

# Updates backup server states based
def update_state(backup_sockets, users):
    print("LEADER: Updating states in backup replica servers")
    for username in users:
        for sock in backup_sockets:
            message = '{}.{}.{}.'.format(username, users[username]['password'], len(users[username]['mailbox']))
            if len(users[username]['mailbox']) != 0:
                for mail in users[username]['mailbox']:
                    message += '{}.'.format(mail)
            sock.send(message.encode(encoding=ENCODING))

# Creates a client socket for backup server to connect to leader server
def connect_with_leader(my_machine_num):
    leader_port = PORT + leader
    client = socket(family=AF_INET, type=SOCK_STREAM) # creates client socket with IPv4 and TCP
    client.connect((server_addrs[leader], leader_port)) # connect to server socket
    print('BACKUP: ({}-{}) LEADER-BACKUP socket established @ {}:{}.'.format(leader, my_machine_num, server_addrs[leader], leader_port))
    return client

def main():
    # Global variables that have to be updated throughout
    global leader
    global replicas
    global server_addrs

    if len(sys.argv) != 3:
        print('Usage: python3 server.py LEADER_IP MACHINE_NUM')
        sys.exit('server.py exiting')
    
    leader_ip   = str(sys.argv[1])
    machine_num = int(sys.argv[2])
    assert machine_num <= replicas, 'Model machine number greater than expected total number of model machines'
    
    server_addrs = [leader_ip] # initialize list of server IPs with leader IP address

    # Creates server socket with IPv4 and TCP
    server = socket(AF_INET, SOCK_STREAM)
    server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1) # allow for multiple clients

    # Remember to run 'ipconfig getifaddr en0' and update SERVER_IP
    server.bind((SERVER_IP, PORT+machine_num))
    server.listen(MAX_CLIENTS) # accept up to MAX_CLIENTS active connections

    # If you are a replica, connect to the leader server
    if machine_num != leader:
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
        if machine_num == leader:
            # If you are an initializing leader, create a clean slate of backup server sockets and IP addresses
            backup_sockets = []
            server_addrs   = [SERVER_IP] # first IP is your own (leader's local IP)
            
            # If you are a new leader, set timeout for waiting for each potential backup server.
            if leader != 0:
                server.settimeout(TIMEOUT_TIME)

            # Attempt to connect to replicas number of backup servers
            for backup_num in range(replicas):
                try:
                    sock, backup_addr = server.accept()
                    backup_sockets.append(sock)
                    server_addrs.append(backup_addr[0])
                    print('LEADER: {}/{} LEADER-backup socket established @ {}'.format(backup_num+1, replicas, backup_addr[0]))
                except:
                    replicas -= 1 # could not connect to this backup due to timeout
                    pass
            print('LEADER: server_addrs: {}'.format(server_addrs))

            # Send to each backup complete list of backup IP_addresses
            if replicas > 0:
                message = ''
                for addr in server_addrs[1:]:
                    message += addr
                    message += ','
                for backup_socket in backup_sockets:
                    backup_socket.send(message.encode(encoding=ENCODING))
                    print('LEADER: Finished sending backup IP addresses to backup @ {}'.format(backup_socket))
            
            # Main leader server loop
            while True:
                server.settimeout(None)
                sock, client_addr = server.accept()
                active_sockets.append(sock) # update active sockets list
                print ('LEADER: {}:{} connected'.format(client_addr[0], client_addr[1]))
                # Start new thread for each client user
                Thread(target=client_thread, args=(sock, client_addr, users, active_sockets, backup_sockets)).start()
        
        # Backup Execution
        else:
            message = backup_client_socket.recv(BUFFER_SIZE)

            # Leader server socket has disconnected
            if not message:
                print('BACKUP: Leader server @ {}:{} disconnected!'.format(server_addrs[leader], PORT+leader))

                # Attempt to connect to new leader (if you are new leader, you will exit this block)
                backup_success = False
                while not backup_success:
                    leader += 1
                    replicas -= 1
                    try:
                        # If I am a replica, try to connect to new leader
                        if machine_num != leader:
                            backup_client_socket = connect_with_leader(machine_num)
                            backup_init = True # ensure backup initialization phase
                            backup_success = True
                        # If I am new leader, exit this loop and start leader initialization
                        else:
                            backup_success = True
                    except:
                        continue

            # Recieved message from leader server socket
            else:
                # Backup initialization phase: recieve all backup IPs
                if backup_init:
                    server_addrs = [server_addrs[leader]]
                    addr_list = message.decode(encoding=ENCODING).split(',')[:-1]
                    for addr in addr_list:
                        server_addrs.append(addr)
                    print('BACKUP: All server IP addresses: {}'.format(server_addrs))
                    backup_init = False
                # Normal backup loop: recieve updates from leader server
                else:
                    leader_msg = message.decode(encoding=ENCODING).split('.')

                    username                    = leader_msg[0]
                    users[username]['password'] = leader_msg[1]
                    mailbox_len                 = int(leader_msg[2])

                    users[username]['mailbox'] = []
                    if mailbox_len != 0:
                        for mail_idx in range(mailbox_len):
                            users[username]['mailbox'].append(leader_msg[STATE_SIZE + mail_idx])
                    print('<msg from LEADER>: {}'.format(users))

if __name__ == '__main__':
    main()