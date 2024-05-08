import socket
import hashlib
import time
import sys
import sched
import time
import threading

class ChatClientSender:
    def __init__(self, server_address, server_port):
        # variables
        self.server_address = server_address
        self.server_port = server_port
        self.sender_name = "Superman"  
        self.receiver_name = "Batwoman"
        self.sequence_number = 0
        # increased rto to allow more space

        self.window_size = 16
        self.rto = 1.5
        self.est_rtt = 0
        self.rtt_var = 0

        # packet specific
        self.schedulers = [None for _ in range(16)]
        self.start_time = [time.time() for _ in range(16)]
        self.chunk_index = {}
        self.chunks = NotImplemented
        self.queue = NotImplemented

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
        return hashlib.md5(data).hexdigest()
    
    def chunk_data(self, data, receive_filename):
        chunk_length = 2000 - len(f"SEQ_NUM:{self.sequence_number}\nCHECKSUM:{self.calculate_checksum(data)}\nRECV_FILE:{receive_filename}\nBYTES_OFFSET:2000\n\n".encode())
        chunks = [(data[i:i+chunk_length], i) for i in range(0, len(data), chunk_length)]
        return chunks
    
    def calculate_rto(self, time):
        alpha = 0.125
        beta = 0.25
        if self.est_rtt == 0: 
            self.est_rtt = time
            self.rtt_var = time / 2
        else:
            self.rtt_var = (1 - beta) * self.rtt_var + beta * abs(time - self.est_rtt)
            self.est_rtt = (1 - alpha) * self.est_rtt + alpha * time
        self.rto = min(self.est_rtt + 4 * self.rtt_var, 6)
        return self.rto


    def send_segment(self, segment):
        self.sock.sendto(segment, (self.server_address, self.server_port))

    def send_data(self, data, receive_filename, offset=None, seq_num=None):
        checksum = self.calculate_checksum(data)
        segment = f"SEQ_NUM:{seq_num}\nCHECKSUM:{checksum}\nRECV_FILE:{receive_filename}\nBYTES_OFFSET:{offset}\n\n".encode() + data  
        self.send_segment(segment)

    def send_chunk(self, index, receive_filename):
        print("Sending segment:", index, " RTO:", self.rto)
        chunk, offset = self.chunks[index]
        self.send_data(chunk, receive_filename, offset=offset, seq_num=index)
        sched_index = self.get_scheduler()
        self.schedulers[sched_index] = threading.Timer(self.rto, self.handle_timeout, args=(index, receive_filename))
        self.schedulers[sched_index].start()
        self.chunk_index[index] = (sched_index, self.rto)
        self.start_time[sched_index] = time.time()
        print("Finished sending segment: ", index, " offset:", offset, " RTO:", self.rto)

    def get_scheduler(self):
        for index, timer in enumerate(self.schedulers):
            if timer is None:
                return index
    
    def handle_timeout(self, index, receive_filename):
        print("Timeout, retransmitting segment:", self.sequence_number, " RTO:", self.rto)
        self.schedulers[self.chunk_index[index][0]] = None
        rto = self.chunk_index[index][1]
        self.rto = min(2 *self.rto, 2*rto, 6)
        self.send_chunk(index, receive_filename)

    def send_file(self, data, receive_filename):
        self.chunks = self.chunk_data(data, receive_filename)
        self.queue = list(range(len(self.chunks)))
        for index in self.queue[:self.window_size]:
            self.send_chunk(index, receive_filename)
            # time.sleep(0.5)
        while self.queue:
            try:
                ack, _ = self.sock.recvfrom(1024)
                if len(ack) == 0:
                    continue
                ack = ack.decode()
                ack_sequence_number = int(ack.split('\n')[0].split(':')[1])
                ack_checksum = ack.split('\n')[1].split(':')[1]

                if ack_sequence_number in self.queue[:self.window_size] and ack_checksum == self.calculate_checksum(f"{ack_sequence_number}".encode()):
                    print("ACK received for segment:", ack_sequence_number)
                    duration = time.time() - self.start_time[self.chunk_index[ack_sequence_number][0]]
                    self.calculate_rto(duration) 
                    self.queue.remove(ack_sequence_number)
                    self.schedulers[self.chunk_index[ack_sequence_number][0]].cancel()
                    self.schedulers[self.chunk_index[ack_sequence_number][0]] = None
                    if len(self.queue) >= self.window_size:
                        next_chunk = self.queue[self.window_size - 1]
                        self.send_chunk(next_chunk, receive_filename)
                        #time.sleep(0.5)
                else:
                    print(f"Wrong ACK={ack_sequence_number} received. Ignoring the ACK. RTO={self.rto}")

            except (UnicodeDecodeError, ValueError, IndexError) as e:
                print("An error occurred:", e)
                print("ACK segment likely corrupted, ignoring.", " RTO:", self.rto)

        # print("Time: ", duration, " Estimated RTO:", self.rto, "s")

        print("File transmission complete.")

    def close_connection(self):
        segment = f"SEQ_NUM:{-1}\n\n".encode()
        for _ in range(3): self.send_segment(segment)
        self.sock.close()

def main():
    if len(sys.argv) < 5:
        print("Usage: python ChatClientSender.py -s server_name -p port_number -t send_file receive_file")
        sys.exit(1)

    start_time = time.time()
    
    port_number = int(sys.argv[4])
    server_name = sys.argv[2]
    sender = ChatClientSender(server_name, port_number)
    sender.identify()
    sender.relay()
    time.sleep(1)
    if len(sys.argv) == 5:
        send_file = sys.stdin.buffer.read()
        receive_file = "sys.stdout"
        sender.send_file(send_file, receive_file)
        sender.close_connection()
    else:
        send_file = sys.argv[6]
        receive_file = sys.argv[7]
        with open(send_file, 'rb') as file:
            data = file.read()
        sender.send_file(data, receive_file)
        sender.close_connection()
    end_time = time.time()
    run_time = end_time - start_time
    print("Transmitted the file in: ", run_time, "s")

if __name__ == "__main__":
    main()

# quick copy and paste
# python ChatClientSender.py -s date.cs.umass.edu -p 8888 -t file2.txt recv_file2.txt
# python ChatClientSender.py -s date.cs.umass.edu -p 8888 -t file3.txt recv_file3.txt
# python ChatClientSender.py -s date.cs.umass.edu -p 8888 -t test.png recv_test.png