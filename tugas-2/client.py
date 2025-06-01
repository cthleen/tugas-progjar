from socket import *
import socket
import sys

clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_addr = ('172.18.0.3', 45000)
clientsocket.connect(server_addr)

try:
    while True:
        req = input("Enter your message (type 'QUIT' to exit): ")
        if req == "QUIT":
            clientsocket.sendall(req.encode())
            print("Closing connection...")
            clientsocket.close()
            print("Connection closed successfully.")
            exit()
        elif req.startswith("TIME"):
            req += "\r\n"
            clientsocket.sendall(req.encode())
            data = clientsocket.recv(14)
            if len(data) == 14:
                print(f"Server response: {data.decode('utf-8')}")
            else:
                print("Received an invalid response from the server.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    clientsocket.close()
    print("Socket closed.")
