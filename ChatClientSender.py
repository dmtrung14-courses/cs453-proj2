import socket
import hashlib
import time
import sys

class ChatClientSender:
    def __init__(self, server_address, server_port):
        self.server_address = server_address
        self.server_port = server_port
        # Hardcoded sender name
        self.sender_name = "Superman"  
        self.sequence_number = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.sendto(f"NAME {self.sender_name}".encode(), (self.server_address, self.server_port))
        response, _ = self.sock.recvfrom(1024)
        print(response.decode())

    def calculate_checksum(self, data):
        return hashlib.md5(data.encode()).hexdigest()

    def send_segment(self, segment):
        self.sock.sendto(segment.encode(), (self.server_address, self.server_port))

    def send_data(self, data, receive_filename):
        checksum = self.calculate_checksum(data)
        segment = f"{self.sequence_number}:{checksum}:{data}:{receive_filename}"  
        self.send_segment(segment)
        while True:
            try:
                # Set timeout for ACKs
                self.sock.settimeout(5)  
                ack, _ = self.sock.recvfrom(1024)
                ack = ack.decode('latin1')
                ack_sequence_number = int(ack.split(':')[0])
                if ack_sequence_number == self.sequence_number:
                    print("ACK received for segment:", self.sequence_number)
                    self.sequence_number = 1 - self.sequence_number 
                    break
            except socket.timeout:
                print("Timeout, retransmitting segment:", self.sequence_number)
                self.send_segment(segment)

    def send_file(self, filename, receive_filename):
        with open(filename, 'r') as file:
            with open(receive_filename, 'w') as receive_file:  
                for line in file:
                    receive_file.write(line.strip() + '\n')  
                    self.send_data(line.strip(), receive_filename)  
                    print(len(line.strip()))
                    # Delay between sending segments
                    time.sleep(0.5)  
        print("File transmission complete.")

    def close_connection(self):
        self.sock.sendto("QUIT".encode(), (self.server_address, self.server_port))
        response, _ = self.sock.recvfrom(1024)
        self.sock.close()
        print(response.decode())

def main():
    if len(sys.argv) < 5:
        print("Usage: python ChatClientSender.py -s server_name -p port_number -t send_file receive_file")
        sys.exit(1)
    
    port_number = int(sys.argv[4])
    server_name = sys.argv[2]
    sender = ChatClientSender(server_name, port_number)
    if len(sys.argv) == 5:
        send_file = sys.stdin
        receive_file = sys.stdout
        for line in send_file:
            if line.strip() == "QUIT":
                sender.close_connection()
                break
            else:
                receive_file.write(line.strip() + '\n')
                sender.send_data(line.strip(), receive_file)
                time.sleep(0.5)
    else:
        send_file = sys.argv[6]
        receive_file = sys.argv[7]
        sender.send_file(send_file, receive_file)
        sender.close_connection()

if __name__ == "__main__":
    main()