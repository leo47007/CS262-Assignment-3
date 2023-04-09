'''
This file implements unit tests for fault-tolerance functions

Usage: python3 unit_tests.py
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


leader = 0
server_addrs = [SERVER_IP]

def main():
    global leader
    global server_addrs

    # Simulate server
    server = socket(AF_INET, SOCK_STREAM)
    server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server.bind((SERVER_IP, PORT))
    server.listen(MAX_CLIENTS)
    
    # Simulate backups
    backup_1 = connect_with_leader(1)
    backup_2 = connect_with_leader(2)

    # Connect server to backups
    server_to_backup_sockets = []
    for _ in range(2):
        sock, _ = server.accept()
        server_to_backup_sockets.append(sock)

    # Simulate update state
    users = {
        'sam': {'password': 'yushun', 'mailbox': ['hi', 'hello']}
    }
    update_state(server_to_backup_sockets ,users)
    
    message_1 = backup_1.recv(BUFFER_SIZE).decode(encoding=ENCODING)
    message_2 = backup_2.recv(BUFFER_SIZE).decode(encoding=ENCODING)

    print(message_1)
    print(message_2)

if __name__ == '__main__':
    main()