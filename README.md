# CS262-Assignment-3

First, update the `SERVER_IP` variable within `server.py` to your local IP address with the result of `ipconfig getifaddr en0`.

Then, in four separate terminals, run the following in sequence, where `LEADER_IP` and `LEADER_PORT` are the IP address and port of the leader server socket, respectively:
- `python3 server.py LEADER_IP 0`
- `python3 server.py LEADER_IP 1`
- `python3 server.py LEADER_IP 2`
- `python3 client.py LEADER_IP LEADER_PORT`

---

To run the unit tests, which test functionality of `connect_with_leader()` and `update_state()`, run `python3 unit_tests.py` after updating the `SERVER_IP` variable within `server.py` to your local IP address with the result of `ipconfig getifaddr en0`.
