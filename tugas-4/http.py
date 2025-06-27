import sys
import os.path
import uuid
import json
import base64
from glob import glob
from datetime import datetime


class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.txt': 'text/plain',
            '.html': 'text/html',
        }
        self.file_dir = './files'
        os.makedirs(self.file_dir, exist_ok=True)

    # Function to upload file
    def upload_file(self, filename, content_b64):
        try:
            file_data = base64.b64decode(content_b64)
            with open(os.path.join(self.file_dir, filename), 'wb') as f:
                f.write(file_data)
            return True
        except:
            return False

    # Function to delete file
    def delete_file(self, filename):
        try:
            os.remove(os.path.join(self.file_dir, filename))
            return True
        except:
            return False

    def response(self, kode=404, message='Not Found', messagebody=bytes(), headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = []
        resp.append(f"HTTP/1.1 {kode} {message}\r\n")
        resp.append(f"Date: {tanggal}\r\n")
        resp.append("Connection: close\r\n")
        resp.append("Server: myserver/1.1\r\n")
        resp.append(f"Content-Length: {len(messagebody)}\r\n")

        for kk in headers:
            resp.append(f"{kk}:{headers[kk]}\r\n")

        resp.append("\r\n")

        response_headers = ''.join(resp)

        if not isinstance(messagebody, bytes):
            messagebody = messagebody.encode()

        return response_headers.encode() + messagebody

    def proses(self, data):
        print(data)
        header_body_split = data.split("\r\n\r\n", 1)
        header_part = header_body_split[0]
        body = header_body_split[1] if len(header_body_split) > 1 else ""

        requests = header_part.split("\r\n")
        baris = requests[0]
        all_headers = [n for n in requests[1:] if n != '']

        j = baris.split(" ")
        try:
            method = j[0].upper().strip()
            object_address = j[1].strip()

            if method == 'GET':
                return self.http_get(object_address, all_headers)
            elif method == 'POST':
                return self.http_post(object_address, all_headers, body)
            elif method == 'DELETE':
                return self.http_delete(object_address, all_headers)
            else:
                return self.response(400, 'Bad Request', '', {})
        except IndexError:
            return self.response(400, 'Bad Request', '', {})

    # method=='GET'
    def http_get(self, object_address, headers):
        files = glob('./files/*')
        thedir = './'

        if object_address == '/':
            return self.response(200, 'OK', 'Ini Adalah web Server percobaan', {})
        elif object_address == '/video':
            return self.response(302, 'Found', '', dict(location='https://youtu.be/katoxpnTf04'))
        elif object_address == '/santai':
            return self.response(200, 'OK', 'santai saja', {})
        elif object_address == '/list':
            files_list = []
            for f in os.listdir(self.file_dir):
                if os.path.isfile(os.path.join(self.file_dir, f)):
                    files_list.append({'name': f, 'size': os.path.getsize(os.path.join(self.file_dir, f))})

            response_data = json.dumps({'files': files_list})
            return self.response(200, 'OK', response_data, {'Content-type': 'application/json'})

        object_address = object_address[1:]
        if thedir + object_address not in files:
            return self.response(404, 'Not Found', '', {})

        with open(thedir + object_address, 'rb') as fp:
            isi = fp.read()

        fext = os.path.splitext(thedir + object_address)[1]
        content_type = self.types.get(fext, 'application/octet-stream')
        headers = {'Content-type': content_type}
        return self.response(200, 'OK', isi, headers)

    # method=='POST'
    def http_post(self, object_address, headers, body):
        if object_address == '/upload':
            try:
                data = json.loads(body)
                filename = data.get('filename')
                content = data.get('content')
                if self.upload_file(filename, content):
                    return self.response(
                        200,
                        'OK',
                        json.dumps({'status': 'success'}),
                        {'Content-Type': 'application/json'}
                    )
            except Exception as e:
                return self.response(
                    500,
                    'Internal Server Error',
                    json.dumps({'status': 'error', 'message': str(e)}),
                    {'Content-Type': 'application/json'}
                )
        return self.response(
            400,
            'Bad Request',
            json.dumps({'status': 'error', 'message': 'Invalid POST endpoint'}),
            {'Content-Type': 'application/json'}
        )

    # method=='DELETE'
    def http_delete(self, object_address, headers):
        if object_address.startswith('/delete/'):
            filename = object_address[8:]
            if self.delete_file(filename):
                return self.response(
                    200,
                    'OK',
                    json.dumps({'status': 'success'}),
                    {'Content-Type': 'application/json'}
                )
            else:
                return self.response(
                    404,
                    'Not Found',
                    json.dumps({'status': 'error'}),
                    {'Content-Type': 'application/json'}
                )
        return self.response(
            400,
            'Bad Request',
            'Invalid delete request',
            {}
        )


if __name__ == "__main__":
    httpserver = HttpServer()
    d = httpserver.proses('GET testing.txt HTTP/1.0')
    print(d)
    d = httpserver.proses('GET donalbebek.jpg HTTP/1.0')
    print(d)
import sys
import socket
import json
import logging
import ssl
import os
import base64

# alamat server Mesin1
server_address = ('172.16.16.101', 50000)

# buat header HTTP
ip_addr = socket.gethostbyname(socket.gethostname())
Header = f""" HTTP/1.1
Host: {server_address[0]}
User-Agent: {ip_addr}
Accept: */*
"""

def make_socket(destination_address='172.16.16.101', port=50000):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (destination_address, port)
        logging.warning(f"connecting to {server_address}")
        sock.connect(server_address)
        return sock
    except Exception as ee:
        logging.warning(f"error {str(ee)}")

def make_secure_socket(destination_address='localhost', port=50000):
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.load_verify_locations(os.getcwd() + '/domain.crt')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (destination_address, port)
        logging.warning(f"connecting to {server_address}")
        sock.connect(server_address)
        secure_socket = context.wrap_socket(sock, server_hostname=destination_address)
        logging.warning(secure_socket.getpeercert())
        return secure_socket
    except Exception as ee:
        logging.warning(f"error {str(ee)}")

def send_command(command_str, is_secure=False):
    alamat_server = server_address[0]
    port_server = server_address[1]
    if is_secure:
        sock = make_secure_socket(alamat_server, port_server)
    else:
        sock = make_socket(alamat_server, port_server)

    try:
        command_str += "\r\n"
        sock.sendall(command_str.encode())
        data_received = "" 
        while True:
            data = sock.recv(2048)
            if data:
                data_received += data.decode()
                if "\r\n\r\n" in data_received:
                    break
            else:
                break
        return data_received
    except Exception as ee:
        logging.warning(f"error during data receiving {str(ee)}")
        return False

def parse_http_response(response: str):
    try:
        headers, body = response.split("\r\n\r\n", 1)
        status_line = headers.split("\r\n")[0]
        status_code = int(status_line.split()[1])
        return status_code, body
    except Exception as e:
        print("Failed to parse HTTP response:", e)
        return None, None

def list_dir():
    response = send_command(f"GET /list{Header}")
    status_code, body = parse_http_response(response)
    if status_code != 200:
        return f"Failed to get server directory: HTTP {status_code}"
    try:
        body = response.split("\r\n\r\n", 1)[1].strip()
        dir = json.loads(body)
    except (IndexError, json.JSONDecodeError) as e:
        return f"Failed to parse JSON: {e}\nResponse:\n{repr(response)}"
    dirList = "Server Directory:\n"
    for file in dir['files']:
        dirList += f"- File: {file['name']}, Size: {file['size']} bytes\n"
    return dirList

def upload_file(filepath, host='localhost'):
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    data = json.dumps({'filename': filename, 'content': content})
    request = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(data)}\r\n"
        "\r\n"
        f"{data}"
    )
    response = send_command(request)
    status_code, body = parse_http_response(response)
    return f"Upload status: HTTP {status_code}\nResponse body: {body}"

def delete_file(filepath, host='localhost'):
    response = send_command(f"DELETE /delete/{filepath}{Header}")
    status_code, body = parse_http_response(response)
    return f"Delete status: HTTP {status_code}\nResponse body: {body}"

if __name__ == '__main__':
    print("\n=== List all files on the server ===")
    print(list_dir())

    print("\n=== Upload file 'testing.txt' ===")
    print(upload_file('testing.txt'))

    print("\n=== List all files again ===")
    print(list_dir())

    print("\n=== Delete file 'testing.txt' ===")
    print(delete_file('testing.txt'))

    print("\n=== List all files after delete ===")
    print(list_dir())
