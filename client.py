'''
This file implements client functionality of chat application.

Usage: python3 client.py IP_ADDRESS
'''
# Import relevant python packages
from select import select
from socket import socket, AF_INET, SOCK_STREAM
import sys

# Constants/configurations
ENCODING    = 'utf-8' # message encoding
BUFFER_SIZE = 2048 # fixed 2KB buffer size
# PORT        = 1234 # fixed application port

# Fault-tolerance
REPLICATION = 2 # 2-fault tolerant system

# Main function for client functionality
def main():
    # Get IP address and port number of server socket
    if len(sys.argv) != 3:
        print('Usage: python3 client.py IP_ADDRESS PORT')
        sys.exit('client.py exiting')
    ip_address = str(sys.argv[1])
    PORT = int(sys.argv[2])
    
    # Creates client socket with IPv4 and TCP
    client = socket(family=AF_INET, type=SOCK_STREAM)
    # Connect to server socket
    client.connect((ip_address, PORT))
    print('Successfully connected to server @ {}:{}'.format(ip_address, PORT))

    '''
    Inputs can come from either:
        1. server socket via 'client'
        2. client user input via 'sys.stdin'
    '''
    sockets_list = [sys.stdin, client]

    # Enabling fault-tolerance
    leader = 0 # initialize the server with index 0 as leader
    server_addrs = [ip_address] # list of all possible server IP addresses
    init = True # initialization phase where first leader sends backup IPs

    while True:
        read_objects, _, _ = select(sockets_list, [], []) # do not use wlist, xlist

        for read_object in read_objects:

            # Recieved message from client user input
            if read_object == sys.stdin:
                message = sys.stdin.readline()
                client.send(message.encode(encoding=ENCODING))
            # Recieved message from server socket
            else:
                message = read_object.recv(BUFFER_SIZE)
                # Server socket has disconnected
                if not message:
                    print('Server @ {}:{} disconnected!'.format(ip_address, PORT+leader))
                    import time
                    time.sleep(0.5)
                    backup_success = False
                    while not backup_success and leader <= REPLICATION:
                        leader = leader + 1
                        try:
                            # Creates client socket with IPv4 and TCP
                            client = socket(family=AF_INET, type=SOCK_STREAM)
                            # Connect to server socket
                            ip_address = server_addrs[leader]
                            print("Attempting to connect to backup @ {}:{}".format(ip_address, PORT+leader))
                            client.connect((ip_address, PORT+leader))
                            sockets_list = [sys.stdin, client]
                            init = True
                            backup_success = True
                        except:
                            continue

                    if backup_success:
                        print('Successfully connected to backup server @ {}:{}'.format(ip_address, PORT+leader))
                        
                    else:
                        client.close()
                        sys.exit('Not able to find backup server. Closing application.')
                else:
                    if init:
                        print(message.decode(encoding=ENCODING))
                        msg = message.decode(encoding=ENCODING).split('@')
                        print(msg)
                        addr_list = msg[0].split(',')[:-1]
                        welcome_msg = msg[1]
                        for addr in addr_list:
                            server_addrs.append(addr)
                        init = False
                        print('All backup server IP addresses: {}'.format(addr_list))
                        print(welcome_msg)
                    else:
                        print(message.decode(encoding=ENCODING))


if __name__ == '__main__':
    main()