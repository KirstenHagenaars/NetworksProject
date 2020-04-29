import socket
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
import threading
import numpy as np


# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.connected = False
        # Contains all arrived segments that still need to be processed and acknowledged
        self.received = []
        self.sequence_nr = np.random.bytes(2)
        self.sequence_nr_client = None
        self.window_client = None
        # Array of (sequenceNR, data) tuples, that have been received
        self.processed = []

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment = segment[0]
        if self.check_cksum(segment):
            self.sequence_nr_client = segment[:2]
            self.window_client = segment[5]

            if not self.connected:
                # TODO check if SYN flag is set, but ACK for 2nd message
                self.received.append(segment)
                handshake.set()
            else:
                # TODO check if FIN is set to start termination
                # receive data
                pass

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        global handshake
        handshake = threading.Event()
        handshake.wait()
        handshake.clear()
        # insert while loop, condition is correct flags
        segment = self.received[0]
        self.received.pop(0)
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, self.increment_bytes(self.sequence_nr_client), True, True, False, self._window, []))
        self.sequence_nr = self.increment_bytes(self.sequence_nr)
        handshake.wait()
        segment = self.received[0]
        # TODO check this if
        if self.sequence_nr == segment[2:4]:
            self.connected = True
            print("connected!!")

    # Send any incoming data to the application layer
    def recv(self):
        global ack, lock_ack, lock_rec_data # ACK segment to be sent, lock on the segment and lock on the received segs
        lock_ack = threading.Lock
        lock_rec_data = threading.Lock
        # Receive segments and send corresponding ACKs
        threading.start_new_thread(self.receiving_data())
        threading.start_new_thread(self.sending_data())
        # Sort the segments
        rec_data = self.sort(self.received)
        # Prepare data - strip segments from headers, concatenate and convert (not sure if convert needed)
        data = self.prepare(self.received)
        self.connected = False
        return data

    # Receiving thread:
    # Wait for a segment from lossy layer, create ACK segment and signal to the sending thread to send this ACK
    def receiving_data(self):
        pass

    # Sending thread: Wait for signal from receiving thread, send ACK segment
    def sending_data(self):
        # add tuple to processed
        pass

    # Sorts the segments in data based on their sequence number
    def sort(self, data):
        # Remove duplicates, sort processed, insertion or merge
        return data

    # Converts the segments in data into a uft-8 string
    def prepare(self, data):
        # Do stuff
        return data

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
