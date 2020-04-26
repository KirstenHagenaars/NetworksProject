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
        # Array of (sequenceNr, event) tuples corresponding to sent but unacknowledged segments, sequenceNr is 2 bytes
        self.pending_events = []
        # Keeps track of the state, connected or not, might need third option for termination
        self.connected = False
        # The sequence number, 2 bytes
        self.sequence_nr = np.random.bytes(2)
        self.sequence_nr_server = None

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # look for corresponding event in array, awaken event
        if self.connected:
            sequenceNr = segment[0] + segment[1]
            for tuple in self.pending_events:
                if sequenceNr == tuple[0]:
                    tuple[1].set()
                    # This should be able to communicate with the send_segment
                    break
        else:
            # TODO check if SYN and ACK are set, and check x+1
            self.sequence_nr_server = segment[0] + segment[1]
            handshake.set()
        # Set the new ack_nr + window (should this be global? critical section?)
        # Signal to receiving_data thread

    # Perform a three-way handshake to establish a connection
    def connect(self):
        global handshake
        handshake = threading.Event()
        self.pending_events = self.pending_events.append((self.sequence_nr, handshake))
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, [0x00, 0x00], 0, 1, 0, super()._window, []))
        handshake.wait()
        self.sequence_nr = self.increment_bytes(self.sequence_nr)
        self._lossy_layer.send_segment(self.create_segment(
            self.sequence_nr, self.increment_bytes(self.sequence_nr_server), True, False, False, super()._window,[]))
        # TODO discuss wait for handshake vs wait for normal ack
        self.connected = True

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        global pending_segments  # List of segments currently being sent
        # Chop data into segments of size PAYLOAD_SIZE and save into segments list
        segments = list(self.slice_data(self.data))
        # Add headers to all segments in the list
        for i in range(len(segments)):
            seg = BTCPSocket.create_segment(self, self.sequence_nr, [0x00, 0x00], 0, 0, 0, super()._window, segments[i])
            segments[i] = seg
            self.sequence_nr = BTCPSocket.increment_bytes(self.sequence_nr)
        # Send segments
        threading.start_new_thread(self.sending_data(self, segments))
        threading.start_new_thread(self.receiving_data(self))

    # Slice data into segments of size PAYLOAD_SIZE
    def slice_data(self, data):
        for i in range(0, len(data), PAYLOAD_SIZE):
            yield data[i:i+PAYLOAD_SIZE]

    # Sending thread: Start the clock and send all the data
    def sending_data(self, segments):
        # Send as many segments as the window size allows
        window = 10 # TODO retrieve window from ACK segment
        for i in range(window):
            self.send_segment(self, segments[i])
            del segments[i]
        threading.start_new_thread(self.clock(self), None)
        global ack_arrived
        ack_arrived = threading.Condition()
        # Wait until ack arrives
        # Pop it from the segments to be acked
        # Send new segment

    # Decrement each segments timeout value every millisecond, resend if timeout reached
    def clock(self):
        time.wait(1) # wait for 1 millisecond (can be changed: depending if we want time accuracy or smaller overhead)
        # Lock
        for pair in pending_segments:
            if pair[1] >= super()._timeout: # pair[1] corresponds
                self.send_segment(pair[0])
            else:
                pair[1] = time.time() - pair[1]
        # Unlock

    # Receiving thread: Receive ACKs, signal to the sending thread and delete ACKed segments from pending_segments
    def receiving_data(self, segments):
        while True:
            # wait for lossy_layer_input signal
            # signal ack_arrived to sending thread
            # TODO retrieve the ack_nr from ACK segment
            for i in range(len(pending_segments)):
                pass
                # if seq_nr of pending_segments[i] == ack_nr-1:   # is the ack_nr seq_nr+1?
                    # Lock
                    # del pending_segments[i]
                    # Unlock

    # Send segment and save it into pending_segments
    def send_segment(self, segment):
        seg_time_pair = []
        time_sent = time.time()
        seg_time_pair.append(segment, time_sent)
        # Lock
        pending_segments.append(seg_time_pair)
        # Unlock
        self._lossy_layer.send_segment(segment)

    # Perform a handshake to terminate a connection
    def disconnect(self):
        # Lets implement this after testing the connection establisment, so we dont waste time
        self.connected = False
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
