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

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        if not self.connected:
            # TODO check if SYN flag is set, but ACK for 2nd message
            self.received = self.received.append(segment)
            handshake.set()
            # TODO store window size
        pass

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        global handshake
        handshake = threading.Event()
        handshake.wait()
        x = self.received[0] + self.received[1] # sequenceNr of incoming segment
        self.received.pop(0)
        y = np.random.bytes(2)
        self._lossy_layer.send_segment(
            self.create_segment(y, self.increment_bytes(x), True, True, False, super()._window, []))
        handshake.wait()
        if self.increment_bytes(y) == self.received[0] + self.received[1]:
            self.connected = True

    # Send any incoming data to the application layer
    def recv(self):
        # I think this should return all the data

        self.connected = False
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
