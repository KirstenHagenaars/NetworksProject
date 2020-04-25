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
        # Chop data into segments of size PAYLOAD_SIZE and save into segments list
        segments = list(self.slice_data(self.data, self.PAYLOAD))
        # Add headers to all segments in the list
        for i in range(len(segments)):
            seg = BTCPSocket.create_segment(self, self.sequence_nr, [0x00, 0x00], 0, 0, 0, super()._window, segments[i])
            segments[i] = seg
            sequence_nr = BTCPSocket.increment_bytes(self, sequence_nr)
        # Send segments

    def slice_data(self, data, slice_length):
        for i in range(0, len(data), slice_length):
            yield data[i:i+slice_length]

    # Send segment and do selective repeat, using timer
    def send_segment(self, data):
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        # Lets implement this after testing the connection establisment, so we dont waste time
        self.connected = False
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
