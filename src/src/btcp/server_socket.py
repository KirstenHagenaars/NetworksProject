import socket
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from threading import Lock, Event
import threading
import numpy as np

# https://packetlife.net/blog/2010/jun/7/understanding-tcp-sequence-acknowledgment-numbers/
# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.connected = False
        self.received = []                        # Received segments that still need to be processed and acknowledged
        self.processed = []                       # List of (sequenceNR, data) tuples, that have been received
        self.acknowledgements = []                # List of acks to be sent
        self.lock_rec = Lock()                    # Lock on received
        self.lock_ack = Lock()                    # Lock on acks to be sent
        self.seg_received = Event()               # Set when there is a new segment in received segments
        self.ack_present = Event()                # Set when ack is ready
        self.handshake = Event()                  # Set when client requests a handshake
        self.end_handshake = False                # True when the last segment of handshake arrived from client's side
        self.sequence_nr = np.random.bytes(2)
        self.sequence_nr_client = None
        self.window_client = None

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
                self.handshake.set()
            elif self.connected:
                if not FIN:
                    # Notify receiving thread
                    self.received.append(segment)
                    self.processed.append((int.from_bytes(segment[:2], 'big'), segment[10:]))
                else:
                    # Start termination
                    self.connected = False

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
        #while self.connected:
         #   if self.received:
                #ack = self.create_segment((0).to_bytes(2, 'big'), self.received[0][:2], 0, 1, 0,
                                          #max(0, self._window - len(self.received)), [])
          #      print("sending ack, ", self.received[0][:2])
           #     self._lossy_layer.send_segment(self.create_segment((0).to_bytes(2, 'big'), self.received[0][:2], 0, 1, 0,
                                          #max(0, self._window - len(self.received)), []))
            #    del self.received[0]
                #self.processed.append((self.received[0][:2], self.received[0][10:10+int.from_bytes(self.received[0][6:8], 'big')]))
        t1 = threading.Thread(target=self.receiving_data)
        #t2 = threading.Thread(target=self.sending_data)
        t1.start()
        #t2.start()
        # Wait for termination to start
        t1.join()
        #t2.join()
        # Now termination has started
        self.close_connection()
        # Sort the segments and concatenate the data
        self.processed = list(set(self.processed))  # remove all the duplicates
        self.processed = b''.join([text for (seq_num, text) in sorted(self.processed)])  # sort and join all bytes
        print(self.processed)
        return self.processed
        # return self.prepare(self.sort(self.processed))

    # Receiving thread:
    # Wait for a segment from lossy layer, create ACK segment, save into received list
    # and signal to the sending thread that there is an ack
    def receiving_data(self):
        while self.connected:
            if self.received:
                segment = self.received.pop(0)
                ack = self.create_segment((0).to_bytes(2, 'big'), segment[:2], 1, 0, 0,
                                          max(0, (self._window - len(self.received))), [])
                self._lossy_layer.send_segment(ack)

            #for seg in self.received:
                #print("SERVER: Received segment with seq_nr: ", (seg[:2]), "and data is: ", seg[10:])
                # print(self._window)
                # print(len(self.received))
                # TODO change once we have window working
                # print("self window - self.received ", self._window - len(self.received))

                # ack = self.create_segment((0).to_bytes(2, 'big'), seg[:2], 0, 1, 0, 1, [])
                # Add data to processed
             #   self.processed.append((seg[:2], seg[10:10+int.from_bytes(seg[6:8], 'big')]))
              #  del seg
               # self.acknowledgements.append(ack)
                #self.ack_present.set()
            # wait for other received segments
           # self.seg_received.wait()
            #self.seg_received.clear()

    # Sending thread: Wait for signal from receiving thread, send ACK segment
    #def sending_data(self):
     #   while self.connected:
      #      self.ack_present.wait()
       #     self.ack_present.clear()
        #    for ack in self.acknowledgements:
         #       self._lossy_layer.send_segment(ack)
                #print("SERVER: sending ack:", ack[2:4])
          #      del ack

    def close_connection(self):
        # Send response to FIN segment
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 1, 0, 1, 0, []))

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
        self.processed = data  # change
        data = []
        previous = 0x0000 # TODO change, and debug
        for i in self.processed:
            # Removes duplicates
            if previous != i[0]:
                data.append(int.from_bytes(i[1], 'big'))
                previous = i[0]
        # Concatenate all elements into a string
        return ''.join((map(chr, data)))

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
