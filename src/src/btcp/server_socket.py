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
        self.handshake = Event()
        self.end_handshake = False
        # Array of (sequenceNR, data) tuples, that have been received
        self.processed = []

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment = segment[0]
        if self.check_cksum(segment):
            self.sequence_nr_client = segment[:2]
            self.window_client = segment[5]
            ACK, SYN, FIN = self.get_flags(segment[4])
            if not self.connected and (SYN or ACK):
                if ACK and self.increment_bytes(self.sequence_nr) == segment[2:4]:
                    self.end_handshake = True
                # self.received.append(segment)
                self.handshake.set()
            else:
                if not FIN:
                    # Notify receiving thread
                    # self.received.append(segment)
                    self.seg_received.set()
                else:
                    # TODO Start termination, signal recv that it can process data, and send segment
                    pass

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        self.handshake.wait()
        self.handshake.clear()
        # Respond to SYN segment every time it arrives, until ACK segment arrives
        while not self.end_handshake:
            self._lossy_layer.send_segment(
                self.create_segment(self.sequence_nr, self.increment_bytes(self.sequence_nr_client), True, True, False,
                                    self._window, []))
            self.handshake.wait()
            self.handshake.clear()
        self.sequence_nr = self.increment_bytes(self.sequence_nr)
        self.connected = True
        print("connected!!")

    # Send any incoming data to the application layer
    def recv(self):
        # Receive segments and send corresponding ACKs
        _thread.start_new_thread(self.receiving_data(), ())
        _thread.start_new_thread(self.sending_data(), ())
        # for that warning^ we might need the same threads as lossy layer: threading.Thread(target=receiving_data)
        # TODO Wait for FIN and wait for threads with .join()
        # Sort the segments
        # Prepare data - strip segments from headers, concatenate and convert (not sure if convert needed)
        self.connected = False
        return self.prepare(self.sort(self.processed))

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
                # Add data to processed
                self.processed.append((seq_nr, seg[10:10+int.from_bytes(seg[6:8], 'big')]))
           #     self.lock_ack.acquire()
           #     del seg
           #     self.acknowledgements.append(ack)
           #     self.lock_ack.release()
           #     self.ack_present.set()
           #     self.lock_rec.release()

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
        window = self._window - len(self.received)
        return seq_nr, ack_nr, window

    # Sorts the segments in data based on their sequence number
    def sort(self, data):
        # Insertion sort
        self.processed = data # TODO change, this is for testing
        for i in range(1, len(self.processed)):
            current = self.processed[i]
            j = i - 1
            while j >= 0 and current[0] < self.processed[j][0]:
                self.processed[j + 1] = self.processed[j]
                j -= 1
            self.processed[j + 1] = current

        return self.processed

    # Converts the segments in data into a uft-8 string, removes duplicates and adds all data together
    def prepare(self, data):
        self.processed = data #change
        data = []
        previous = 0x0000 # TODO change, and debug
        for i in self.processed:
            # Removes duplicates
            if previous != i[0]:
                data.append(int.from_bytes(i[1],'big'))
                previous = i[0]
        # Concatenate all elements into a string
        return ''.join((map(chr, data)))

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
