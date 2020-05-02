import socket
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from threading import Lock, Event
import threading
import _thread
import numpy as np


# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.connected = False
        self.received = []                        # Received segments that still need to be processed and acknowledged
        self.lock_rec = Lock()                    # Lock on received segments
        self.seg_received = Event()               # Set when there is a new segment in received segments
        self.acknowledgements = []                # List of acks to be sent
        self.lock_ack = Lock()                    # Lock on acks to be sent
        self.ack_present = Event()                # Set when ack is ready
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
            if self.connected:
                # TODO check if FIN is set to start termination
                # if nor FIN: notify the receiving thread
                self.received.append(segment)
                self.seg_received.set()
            else:
                # TODO check if SYN flag is set, but ACK for 2nd message
                self.received.append(segment)
                handshake.set()

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        global handshake
        handshake = Event()
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
        del self.received[0]

    # Send any incoming data to the application layer
    def recv(self):
        # Receive segments and send corresponding ACKs
        t1 = threading.Thread(target=self.receiving_data)
        t1.start()
        # Sort the segments
        rec_data = self.sort(self.received)
        # Prepare data - strip segments from theaders, concatenate and convert (not sure if convert needed)
        data = self.prepare(self.received)
        # TODO finish threads
        return data

    # Receiving thread:
    # Wait for a segment from lossy layer, create ACK segment, save into received list
    # and signal to the sending thread that there is an ack
    def receiving_data(self):
        t2 = threading.Thread(target=self.sending_data)
        t2.start()
        while True: # TODO fix
            self.seg_received.wait()
            self.seg_received.clear()
            self.lock_rec.acquire()
            for seg in self.received:
                print("SERVER: Received segment with seq_nr: ", (seg[:2]), "and data is: ", seg[10:])
                seq_nr, ack_nr, window = self.get_ack_attributes(seg)
                ack = self.create_segment(seq_nr, ack_nr, 0, 1, 0, window, [])
                self.lock_ack.acquire()
                del seg
                self.acknowledgements.append(ack)
                if self.lock_ack.locked():
                    self.lock_ack.release()
                self.ack_present.set()
            if self.lock_rec.locked():
                self.lock_rec.release()

    # Sending thread: Wait for signal from receiving thread, send ACK segment
    def sending_data(self):
        while True:
            self.ack_present.wait()
            self.ack_present.clear()
            self.lock_ack.acquire()
            if self.acknowledgements:
                for ack in self.acknowledgements:
                    self._lossy_layer.send_segment(ack)
                    print("SERVER: sending ack:", ack[2:4])
                    del ack
            if self.lock_ack.locked():
                self.lock_ack.release()

    # Return sequence number, ack number and window of segment
    def get_ack_attributes(self, segment):
        seq_nr = segment[:2]
        ack_nr = segment[2:4]
        if not self.lock_rec.locked():
            self.lock_rec.acquire()
        window = self._window - len(self.received)
        if self.lock_rec.locked():
            self.lock_rec.release()
        return seq_nr, ack_nr, window

    # Sorts the segments in data based on their sequence number, and removes duplicates
    def sort(self, data):
        # Insertion sort
        self.processed = data
        for i in range(1, len(self.processed)):
            if i >= len(self.processed):
                break
            #print(self.processed)
            current = self.processed[i]
            j = i - 1
            dup = False
            while j >= 0 and current[0] <= self.processed[j][0] and not dup:
                if current[0] == self.processed[j][0]:
                    # TODO Remove duplicate
                    pass
                    #self.processed.pop(i)
                    #dup = True
                    #i -= 1
                else:
                    self.processed[j + 1] = self.processed[j]
                j -= 1
            if not dup:
                self.processed[j + 1] = current

        return self.processed

    # Converts the segments in data into a uft-8 string
    def prepare(self, data):
        # Do stuff
        return data

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
