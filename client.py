'''
This file implements client functionality of chat application.

Usage: python3 client.py IP_ADDRESS PORT
'''
# Import relevant python packages
from select import select
from socket import socket, AF_INET, SOCK_STREAM
import sys
from time import sleep

# Constants/configurations
ENCODING    = 'utf-8' # message encoding
BUFFER_SIZE = 2048 # fixed 2KB buffer size

# Fault-tolerance
REPLICAS = 2 # 2-fault tolerant system
SLEEP_TIME  = 0.5 # wait for 0.5 seconds to connect to backup servers

# Main function for client functionality
def main():
    # Get IP address and port number of server socket
    if len(sys.argv) != 3:
        print('Usage: python3 client.py IP_ADDRESS PORT')
        sys.exit('client.py exiting')
    ip_address = str(sys.argv[1])
    port = int(sys.argv[2])
    
    # Creates client socket with IPv4 and TCP
    client = socket(family=AF_INET, type=SOCK_STREAM)
    # Connect to server socket
    client.connect((ip_address, port))
    print('Successfully connected to server @ {}:{}'.format(ip_address, port))

    '''
    Inputs can come from either:
        1. server socket via 'client'
        2. client user input via 'sys.stdin'
    '''
    sockets_list = [sys.stdin, client]

    # Enable fault-tolerance
    leader = 0 # initialize the server with index 0 as leader
    server_addrs = [ip_address] # list of all possible server IP addresses
    init = True # initialization phase where leader sends backup IPs

    attempt_to_delete = False # variable to make sure that account deletion does not automatic re-connect

    while True:
        read_objects, _, _ = select(sockets_list, [], []) # do not use wlist, xlist

        for read_object in read_objects:

            # Recieved message from client user input
            if read_object == sys.stdin:
                message = sys.stdin.readline()
                client.send(message.encode(encoding=ENCODING))
                if attempt_to_delete:
                    if message == "confirm\n":
                        client.close()
                        sys.exit('Deleted account. closing application.')
                    else:
                        attempt_to_delete = False
                if message == '3\n':
                    attempt_to_delete = True
            # Recieved message from server socket
            else:
                message = read_object.recv(BUFFER_SIZE)
                # Server socket has disconnected
                if not message:
                    print('Server @ {}:{} disconnected!'.format(ip_address, port+leader))
                    sleep(SLEEP_TIME)
                    backup_success = False
                    # Attempt to connect to a backup server if there still exists any (i.e., leader <= REPLICAS)
                    while not backup_success and leader <= REPLICAS:
                        leader = leader + 1
                        # try connecting to next possible leader
                        try:
                            client = socket(family=AF_INET, type=SOCK_STREAM) # creates client socket with IPv4 and TCP
                            ip_address = server_addrs[leader] # connect to server socket
                            print("Attempting to connect to backup @ {}:{}".format(ip_address, port+leader))
                            client.connect((ip_address, port+leader))
                            sockets_list = [sys.stdin, client]
                            init = True # make sure that we are in initialization phase so we can recieve backup IPs when we enter chatroom.
                            backup_success = True
                        except:
                            continue

                    if backup_success:
                        print('Successfully connected to backup server @ {}:{}'.format(ip_address, port+leader))
                        
                    else:
                        client.close()
                        sys.exit('Unable to find a backup server. Closing application.')
                else:
                    if init:
                        msg = message.decode(encoding=ENCODING).split('@') # split backup IPs with welcome message
                        addr_list   = msg[0].split(',')[:-1]
                        welcome_msg = msg[1]
                        for addr in addr_list:
                            server_addrs.append(addr)
                        init = False # finished initialization phase
                        print('All backup server IP addresses: {}'.format(addr_list))
                        print(welcome_msg)
                    else:
                        print(message.decode(encoding=ENCODING))


if __name__ == '__main__':
    main()