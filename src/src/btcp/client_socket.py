from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
import numpy as np
import time


# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # I think we get here if it receives a segment, which we might have to read here and react accordingly
        # turn off timer/ complete handshake
        pass

    # Perform a three-way handshake to establish a connection
    def connect(self):
        window = 0x00  # TODO change
        self._lossy_layer.send_segment(self.create_segment(np.random.bytes(2), [0x00, 0x00], 0, 1, 0, window, []))
        # wait for response somehow
        start_time = time.time()
        # TODO discuss wait for handshake vs wait for normal ack
        pass

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        # notice i put the create_segment function in btcp_socket, since server_socket will also use it
        pass

    # Sends segment and does selective repeat, uses timer
    def send_segment(self, data):
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
