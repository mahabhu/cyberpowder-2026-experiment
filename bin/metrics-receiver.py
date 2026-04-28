#!/usr/bin/env python3
import datetime
import json
import socket
import sys


UDP_IP = "127.0.0.1"   # IP address to bind to (localhost in this case)
UDP_PORT = 55555       # Port to bind to

args = sys.argv
if len(args) > 1:
    UDP_IP = args[1]
elif len(args) > 2:
    UDP_PORT = int(args[2])
else:
    print("Usage: python3 metrics-receiver.py [IP] [PORT]")
    print("Using default IP and port:", UDP_IP, UDP_PORT)

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the IP address and port
sock.bind((UDP_IP, UDP_PORT))

print("UDP Receiver started...")

while True:
    # Receive message from the sender
    data, addr = sock.recvfrom(1024)

    # Decode the received message as JSON
    try:
        json_data = json.loads(data.decode('utf-8'))
        json_data['timestamp_gmt'] = datetime.datetime.utcfromtimestamp(
            json_data['timestamp']
        ).strftime('%Y-%m-%dT%H:%M:%SZ')
        print(json.dumps(json_data))
    except json.JSONDecodeError:
        pass
