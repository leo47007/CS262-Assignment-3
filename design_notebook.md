# Design Notebook (Replication -- Chat Application)

We document the design decisions and thought processes behind the server and client implementations in this design notebook.
This notebook is organized around key questions that we answer and implement as Python-based functions.

## How many server replicas are there for this 2-fault tolerant system?

- A total of 3 (2+1) servers are implemented for this 2-fault tolerant system.
- The initial leader uses port `PORT`, the first replica uses port `PORT+1`, and the second replica uses port `PORT+2` regardless of IP address.

## How are the server leader and server replicas connected?

- The server leader is connected with each server replica through pairs of sockets. 
In this case, the leader uses server sockets while the replicas use client sockets. 
There is no explicit connection between the replicas themselves.

## How are the client and servers (leader and replicas) connected?

- The client is only connected to the leader via sockets.
There is no connection between the client and any of the server replica backups.

## How do the server leader and replicas detect and recover from fault crash failures?

- In our setup, the server leader does not have to detect crash failures from the server replicas.
Even if both replicas crash, the leader and client can still run the chat application perfectly and fulfill 2-fault tolerance.
- The server replicas can detect a server leader crash since there is a socket-based connection between them.
For a replica, if the message recieved from leader is empty, then that means the leader has died.
Server replicas do not have to detect whether or not other server replicas have crashed.

- When a server leader crashes, every replica has two options: 1) become the next leader or 2) connect to the next leader.
- Since the initial leader is indexed as server `0`, we know the next leader is indexed as server `1`.
- The next leader has to *attempt* to connect to `replicas` (i.e., the number of expected replicas) number of backups.
- If a replica is still a replica after the prior leader crashes, this replica will *attempt* to connect to the target next server. 
If the connection times out, that means this target next server has silently crashed and we will look for the next possible server by further increasing the `leader` index.

## How does the client detect and recover fault crash failures?

- The client can detect a server leader crash since there is a socket-based connection between them.
For the client, if the message recieved from the server leader is empty, then that means the leader has died.

- When a client first connects with the server leader, it recieves from the server leader a list of IP addresses for the backup servers.
In the case of a leader crash, the client can cycle through this list of potential backups and attempt to connect to them.
Note that we do not need information about ports since the initial leader uses port `PORT`, the first replica uses port `PORT+1`, and the second replica uses port `PORT+2` regardless of IP address.

## How is message store persistency achieved?

- Every time the central data structure `users` -- which contains information on all user usernames, passwords, and mailboxes -- is updated, the leader server sends an updated copy of this data structure to all backup servers.
Thus, if the leader server crashes, the backup servers can just step in with all the necessary information.

## What was our testing strategy?

- We tested all of the following permutations of crash sequences (as indicated by index of server):

  - (0-1) - this tested 2 consecutive changes of leader servers.
  - (0-2) - this tested 1 change of leader server (server 2 crashing is silent)
  - (1-0) - this tested 1 change of leader server (server 1 crashing is silent). This case forced server 2 to realize that server 1 crashed before confirming that server 2 was going to be the next leader.
  - (1-2) - this tested no change of leader server (both server 1 and 2 crashing are silent)
  - (2-0)- this tested 1 change of leader server (server 2 crashing is silent). This case forced server 1 to attempt to wait for server 2 to connect as a new backup before realizing that server 2 has already crashed via timeout.
  - (2-1) - this tested no change of leader server (both server 1 and 2 crashing are silent)

## What do the unit tests contain?

- The unit tests are centered around the two functions:
  - `connect_with_leader()` - used by new server replicas to connect to new server leader
  - `update_state()` - used by server leader to send updated `users` data structure to all active replica servers.
