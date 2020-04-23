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
        # Create an array of all segments
        num_segments = data / PAYLOAD_SIZE  # TODO look into slicing up bytes objects
        for i in range(num_segments):
            segments = []
            seg = BTCPSocket.create_segment(self, 0x00, 0x00, False, False, False, window, data[i])  # TODO pass "self"
            segments[i] = seg

        # Send all segments
        # We get the window size from the three way handshake for the first round of packets
        # As soon as the first packet was acked, we look into that ack for a new window size & send more packets

        # seg_ack = the ack segment of the three-way handshake
        last_acked = 0
        while last_acked != num_segments:  # while the last segment hasn't been acked
            # window = get_window_size(seg_ack)
            # send not-yet-sent packets up to 'window'
            # wait for ack
            # seg_ack = last ack segment
            pass
        pass

    # Send segment and do selective repeat, using timer
    def send_segment(self, data):
        # set timeout, nr_of_tries
        # send data, decrease timeout and wait for ack
        # if ack not received and timeout == 0 and nr_of_tries != 0:
            # resend, restart timeout, nr_of_tries--
        # if nr_of_tries == 0:
            # print packet was lost or something, continue
        # if ack received:
            # continue
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
