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
PORT        = 1234 # fixed application port
REPLICATION = 3

# Main function for client functionality
def main():
    # Get IP address and port number of server socket
    if len(sys.argv) != 2:
        print('Usage: python3 client.py IP_ADDRESS')
        sys.exit('client.py exiting')
    ip_address = str(sys.argv[1])

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
    Leader = 0 # Assuming the server with index 0 as the leader for initialization
    server_addrs = [ip_address]
    init = True
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
                    print('Server @ {}:{} disconnected!'.format(ip_address, PORT+Leader))
                    back_success =False
                    while not back_success:
                        Leader = Leader + 1
                        try:
                            # Creates client socket with IPv4 and TCP
                            client = socket(family=AF_INET, type=SOCK_STREAM)
                            # Connect to server socket
                            ip_address = server_addrs[Leader]
                            print("ip_address: ")
                            print(ip_address, PORT+Leader)
                        
                            client.connect((ip_address, PORT+Leader))
                            back_success = True
                        except:
                            continue

                    if back_success:
                        print('Successfully connected to server @ {}:{}'.format(ip_address, PORT+Leader))
                        sockets_list = [sys.stdin, client]
                    # client.close()
                    # sys.exit('Closing application.')
                else:
                    if init:
                        info_list = message.decode(encoding=ENCODING).split(',')
                        for info in info_list:
                            server_addrs.append(info)
                        init = False
              
                    print(message.decode(encoding=ENCODING))


if __name__ == '__main__':
    main()