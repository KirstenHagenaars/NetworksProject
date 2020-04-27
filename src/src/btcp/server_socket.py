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

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        if not self.connected:
            # TODO check if SYN flag is set, but ACK for 2nd message
            self.received.append(segment[0])
            handshake.set()
            # TODO store window size
        pass

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        global handshake
        handshake = threading.Event()
        handshake.wait()
        handshake.clear()
        segment = self.received[0]
        x = segment[:2] # sequenceNr of incoming segment
        self.received.pop(0)
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, self.increment_bytes(x), True, True, False, self._window, []))
        self.sequence_nr = self.increment_bytes(self.sequence_nr)
        handshake.wait()
        segment = self.received[0]
        # TODO check this if
        if self.sequence_nr == segment[:2]:
            self.connected = True
            print("connected!!")

    # Send any incoming data to the application layer
    def recv(self):
        # I think this should return all the data

        self.connected = False
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
