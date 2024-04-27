import socket
import hashlib
import time
import sys

class ChatClientSender:
    def __init__(self, server_address, server_port):
        # variables
        self.server_address = server_address
        self.server_port = server_port
        self.sender_name = "Superman"  
        self.receiver_name = "Batwoman"
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

    def send_segment(self, segment):
        self.sock.sendto(segment.encode(), (self.server_address, self.server_port))

    def send_data(self, data, receive_filename):
        checksum = self.calculate_checksum(data)
        print(type(checksum))
        segment = f"SEQ_NUM:{self.sequence_number}\nCHECKSUM:{checksum}\nRECV_FILE:{receive_filename}\nBYTES:2000\n\n{data}"  
        self.send_segment(segment)

    def send_file(self, filename, receive_filename):
        with open(filename, 'r') as file:
            data = file.read()
        binary_data = data.encode()
        chunk_size = 2000 - len(f"SEQ_NUM:{self.sequence_number}\nCHECKSUM:{self.calculate_checksum('')}\nRECV_FILE:{receive_filename}\nBYTES:2000\n\n".encode())
        chunks = [binary_data[i:i+chunk_size] for i in range(0, len(binary_data), chunk_size)]
        for chunk in chunks:
            self.send_data(chunk.decode(), receive_filename)
            while True:
                try:
                    self.sock.settimeout(3)
                    ack, _ = self.sock.recvfrom(1024)
                    if len(ack) == 0:
                        break
                    ack = ack.decode()
                    ack_sequence_number = int(ack.split(':')[1])
                    if ack_sequence_number == 1 - self.sequence_number:
                        print("ACK received for segment:", self.sequence_number)
                        self.sequence_number = 1 - self.sequence_number 
                        break
                    else:
                        print("Wrong ACK received. Retransmitting segment:", self.sequence_number)
                        self.send_data(chunk.decode(), receive_filename)
                except socket.timeout:
                    print("Timeout, retransmitting segment:", self.sequence_number)
                    self.send_data(chunk.decode(), receive_filename)

        print("File transmission complete.")

    def close_connection(self):
        segment = f"SEG_NUM:{-1}\n\n"
        self.sock.sendto(segment.encode(), (self.server_address, self.server_port))
        response, _ = self.sock.recvfrom(1024)
        self.sock.close()
        # print(response.decode())

def main():
    if len(sys.argv) < 5:
        print("Usage: python ChatClientSender.py -s server_name -p port_number -t send_file receive_file")
        sys.exit(1)
    
    port_number = int(sys.argv[4])
    server_name = sys.argv[2]
    sender = ChatClientSender(server_name, port_number)
    sender.identify()
    sender.relay()
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

    # command for copy and paste:
    # python ChatClientSender.py -s date.cs.umass.edu -p 8888 -t file1.txt recv_file1.txt
    # python ChatClientSender.py -s date.cs.umass.edu -p 8888 -t file2.txt recv_file2.txt