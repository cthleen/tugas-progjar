from socket import *
import socket
from datetime import datetime
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProcessTheClient(threading.Thread):
    def __init__(self, connection, address):
        self.connection = connection
        self.address = address
        threading.Thread.__init__(self)

    def run(self):
        while True:
            try:
                data = self.connection.recv(32)
                if data:
                    data = data.decode('utf-8')
                    if data.startswith("TIME") and data.endswith("\r\n"):
                        resp = "JAM " + datetime.strftime(datetime.now(), "%H:%M:%S") + "\r\n"
                        logging.info(f"[SENDING] Response to client {self.address}")
                        self.connection.sendall(resp.encode('utf-8'))
                    elif data.startswith("QUIT"):
                        logging.info(f"[CLIENT EXIT] Client from {self.address} has exited. Bye bye.")
                        resp = "invalid req\r\n"
                        self.connection.sendall(resp.encode('utf-8'))
                    else:
                        logging.warning(f"[INVALID REQUEST] From {self.address}")
                        self.connection.close()
                        break
            except OSError as e:
                logging.error(f"[ERROR] OSError occurred: {e}")
                break
        self.connection.close()

class Server(threading.Thread):
    def __init__(self):
        self.the_clients = []
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        threading.Thread.__init__(self)

    def run(self):
        self.my_socket.bind(('0.0.0.0', 45000))
        self.my_socket.listen(1)
        logging.info("[SERVER STARTED] Listening on port 45000")
        while True:
            self.connection, self.client_address = self.my_socket.accept()
            logging.info(f"[CONNECTION] From {self.client_address}")
            clt = ProcessTheClient(self.connection, self.client_address)
            clt.start()
            self.the_clients.append(clt)

def main():
    svr = Server()
    svr.start()

if __name__ == "__main__":
    main()