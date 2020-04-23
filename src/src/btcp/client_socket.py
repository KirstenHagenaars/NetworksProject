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
        window = 0x00  # TODO change
        num_segments = data / PAYLOAD_SIZE  # TODO look into slicing up bytes objects
        for i in range(num_segments):
            BTCPSocket.create_segment(self, 0x00, 0x00, False, False, False, window, data[i])  # TODO pass "self"
        # for i in range(window):
            # send_segment(data[i])
            # advance the window
        # while last ack not received
            # advance the window
            # send_segment(data[something])
            # something++
        pass

    # Sends segment and does selective repeat, uses timer
    def send_segment(self, data):
        # set timeout, nr_of_tries
        # send data, decrease timeout and wait for ack
        # if ack not received and timeout == 0 and nr_of_tries != 0:
            # resend, restart timeout, nr_of_tries--
        # if nr_of_tries == 0:
            # print packet was lost or something, continue
        # if ack received
            # continue
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
