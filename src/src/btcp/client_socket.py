from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
import numpy as np
import time
import threading


# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        # Keeps track of the state, connected or not, might need third option for termination
        self.connected = False
        # Received segments
        self.acknowledgements = []
        # The sequence number, 2 bytes
        self.sequence_nr = np.random.bytes(2)
        self.sequence_nr_server = None
        self.ack_nr = None
        self.window_server = None

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # look for corresponding event in array, awaken event
        segment = segment[0]
        # TODO debug checksum
        if self.check_cksum(segment):
            self.sequence_nr_server = segment[:2]
            self.window_server = segment[5]
            self.ack_nr = segment[3:4]

            if self.connected:
                # Add segment to acknowledgements
                ack_arrived.set()
                self.acknowledgements.append(segment)
            else:
                # TODO check if SYN and ACK are set, and check x+1

                handshake.set()
                # Set the new ack_nr + window (should this be global? critical section?)
                # Signal to receiving_data thread

    # Perform a three-way handshake to establish a connection
    def connect(self):
        global handshake
        handshake = threading.Event()
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 1, 0, self._window, []))
        handshake.wait()
        # todo make loop/ use clock, read segment
        self.sequence_nr = self.increment_bytes(self.sequence_nr)
        self._lossy_layer.send_segment(self.create_segment(
            self.sequence_nr, self.increment_bytes(self.sequence_nr_server), 1, 0, 0, self._window, []))
        self.connected = True
        print("connected!!")

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        # TODO implement nr of tries
        global pending_segments, lock  # List of segments waiting for ack, corresponding lock
        lock = threading.Lock()
        # Chop data into segments of size PAYLOAD_SIZE and save into segments list
        segments = list(self.slice_data(data))
        # Add headers to all segments in the list
        for i in range(len(segments)):
            seg = BTCPSocket.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 0, 0, self._window, segments[i])
            segments[i] = seg
            self.sequence_nr = self.increment_bytes(self.sequence_nr)
        # Send segments
        threading.start_new_thread(self.sending_data(segments))
        threading.start_new_thread(self.receiving_data(self))
        # TODO Finish

    # Slice data into segments of size PAYLOAD_SIZE
    def slice_data(self, data):
        for i in range(0, len(data), PAYLOAD_SIZE):
            yield data[i:i+PAYLOAD_SIZE]

    # Sending thread: Start the clock and send all the data
    def sending_data(self, segments):
        # Send first segments
        window = self.window_server
        for i in range(window):
            self.send_segment(segments[i])
            del segments[i]
        # Start the clock
        threading.start_new_thread(self.clock(pending_segments))
        global send_more
        send_more = threading.Event()
        # Send all remaining segments
        while segments: # while there is still stuff to send
            send_more.wait()
            send_more.clear()
            # Acquire the new window and send as many segments as possible
            window = self.window_server
            for i in range(window):
                self.send_segment(segments[i])
                del segments[i]

    # Decrement each segments timeout value every millisecond, resend if timeout reached
    def clock(self, segments):
        time.wait(1) # wait for 1 millisecond (can be changed: depending if we want time accuracy or smaller overhead)
        lock.acquire()
        for pair in segments:
            if pair[1] >= self._timeout: # pair[1] corresponds
                self.send_segment(pair[0])
            else:
                pair[1] = time.time() - pair[1]
        lock.release()

    # Receiving thread: Receive ACKs, signal to the sending thread and delete ACKed segments from pending_segments
    def receiving_data(self, segments):
        global ack_arrived
        ack_arrived = threading.Event()
        while True:
            ack_arrived.wait()
            ack_arrived.clear()
            # Notify sending thread to send more segments and delete the ACKed segment from pending_segments
            send_more.set()
            for seg in pending_segments:
                if seg[0] == self.ack_nr[0] and seg[1] == self.ack_nr[1]:
                    lock.acquire()
                    del seg
                    lock.release()

    # Send segment and save it into pending_segments
    def send_segment(self, segment):
        seg_time_pair = []
        time_sent = time.time()
        seg_time_pair.append((segment, time_sent))
        lock.acquire()
        pending_segments.append(seg_time_pair)
        lock.release()
        self._lossy_layer.send_segment(segment)

    # Perform a handshake to terminate a connection
    def disconnect(self):
        # Lets implement this after testing the connection establisment, so we dont waste time
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, [0x00, 0x00], 0, 0, 1, super()._window, []))
        # wait for response with ack and fin, try some amount of times before giving up
        self.connected = False
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
