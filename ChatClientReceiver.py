import socket
import hashlib
import time
import sys

class ChatClientReceiver:
    def __init__(self, server_address, server_port):
        # variables
        self.server_address = server_address
        self.server_port = server_port
        self.sender_name = "Batwoman"
        self.receiver_name = "Superman"
        self.sequence_number = 0
        # socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def identify(self):
        self.sock.sendto(f"NAME {self.sender_name}".encode(), (self.server_address, self.server_port))
        response, _ = self.sock.recvfrom(1024)
        print(response.decode())

    def relay(self):
        self.sock.sendto(f"CONN {self.receiver_name}".encode(), (self.server_address, self.server_port))
        response, _ = self.sock.recvfrom(1024)
        print(response.decode())

    def calculate_checksum(self, data):
        return hashlib.md5(data.encode()).hexdigest()

    def receive_data(self):
        response = b""
        header = None
        seq_num = None
        checksum = None
        receive_file = None
        while True:
            try:
                segment, _ = self.sock.recvfrom(2048)
                header_sep = segment.index(b"\n\n")
                # handle quit:
                if not header:
                    header = segment[:header_sep].decode()
                    seq_num = int(header.split("\n")[0].split(":")[1])
                    # print(seq_num)
                    if seq_num == -1:
                        print("Server has closed the connection")
                        return -1
                    checksum = header.split("\n")[1].split(":")[1]
                    receive_file = header.split("\n")[2].split(":")[1]
                response += segment[header_sep+2:]
                self.sock.settimeout(1)
            except socket.timeout:
                break
            except UnicodeDecodeError:
            # possibly corrupted, so we drop the file and request retransmission
                self.send_ack()
                return 0
        # TODO: handle parsing response
        try:
            data = response.decode()
            if len(data) == 0:
                return 0
        except UnicodeDecodeError:
            # possibly corrupted, so we drop the file and request retransmission
            self.send_ack()
            return 0

        if seq_num != self.sequence_number or checksum != self.calculate_checksum(data):
            if seq_num != self.sequence_number:
                print(f"Expected sequence number: {self.sequence_number}, received: {seq_num}")
            if checksum != self.calculate_checksum(data):
                print(f"Expected checksum: {self.calculate_checksum(data)}, received: {checksum}")
            self.send_ack()
            return 0 
        
        self.sequence_number = 1 - self.sequence_number
        if receive_file == sys.stdout:
            print(data)
            return 0
        with open(receive_file, 'a') as file:
            file.write(data)
        self.send_ack()
        return 0
    
    def receive_file(self):
        while True:
            try:
                a = self.receive_data()
                if a == -1:
                    break
                self.sock.settimeout(3)
            except socket.timeout:
                break
    def send_segment(self, segment):
        self.sock.sendto(segment.encode(), (self.server_address, self.server_port))

    def send_ack(self):
        segment = f"ACK:{self.sequence_number}"
        self.send_segment(segment)

    def close_connection(self):
        # self.sock.sendto("QUIT".encode(), (self.server_address, self.server_port))
        # response, _ = self.sock.recvfrom(1024)
        # print(response.decode())
        self.sock.close()

def main():
    if len(sys.argv) < 5:
        print("Usage: python ChatClientSender.py -s server_name -p port_number -t send_file receive_file")
        sys.exit(1)
    
    port_number = int(sys.argv[4])
    server_name = sys.argv[2]
    sender = ChatClientReceiver(server_name, port_number)
    sender.identify()
    sender.relay()
    
    # TODO: something is wrong here
    sender.receive_file()
    sender.close_connection()

if __name__ == "__main__":
    main()

    # command for copy and paste
    # python ChatClientReceiver.py -s date.cs.umass.edu -p 8888