from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
import numpy as np
import time
from threading import Lock, Event
import threading


# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        self.connected = False                  # Keeps track of the state, connected or not
        self.handshake_response = False         # Is true once server has done its part in the handshake
        self.termination_response = False       # Is true once server has done its part in termination
        self.declined = False                   # Is true if server does not respond to the client in handshake
        self.segments = []                      # Segments to be sent
        self.acknowledgements = []              # Received acknowledgements
        self.pending_segments = []              # Segments to be acked
        self.lock_segs = Lock()                 # Lock for segments
        self.lock_acks = Lock()                 # Lock for acknowledgements
        self.lock_pending = Lock()              # Lock for pending_segments
        self.ack_arrived = Event()              # Set when there is a new ack from the lossy layer
        self.send_more = Event()                # Set when more segments can be sent to the server
        self.sequence_nr = np.random.bytes(2)   # The sequence number, 2 bytes
        self.sequence_nr_server = None          # Sequence_nr of the server
        self.ack_nr = None                      # Ack_nr
        self.window_server = None               # Window buffer of the server
        # Threads:
        self.clock_conn = threading.Thread(target=self.clock_connected)
        self.sending = threading.Thread(target=self.sending_data)
        self.receiving = threading.Thread(target=self.receiving_data)

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # look for corresponding event in array, awaken event
        segment = segment[0]
        if self.check_cksum(segment):
            self.sequence_nr_server = segment[:2]
            #self.window_server = segment[5] TODO figure out window stuff
            self.ack_nr = segment[2:4]
            ACK, SYN, FIN = self.get_flags(segment[4])
            # ACK should always be set for the server, but lets check it for niceness?
            if self.connected:
                if ACK and not FIN:
                    # Add segment to acknowledgements
                    self.acknowledgements.append(segment)
                    self.ack_arrived.set()
                elif ACK and FIN:
                    # Signal disconnect
                    self.termination_response = True
            elif ACK and SYN and self.increment_bytes(self.sequence_nr) == self.ack_nr:
                # Server has done its part in the three-way handshake
                self.window_server = segment[5]
                self.handshake_response = True

    # Perform a three-way handshake to establish a connection
    def connect(self):
        segment1 = self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 1, 0, self._window, [])
        self._lossy_layer.send_segment(segment1)
        # Start clock thread to resend segment if necessary
        thread1 = threading.Thread(target=self.clock_disconnected, args=(segment1, time.time(), NR_OF_TRIES))
        thread1.start()
        thread1.join()
        # TODO should we have this if-statement also in send and disconnect so they dont do anything if handshake failed?
        if not self.declined:
            self.sequence_nr = self.increment_bytes(self.sequence_nr)
            # Send final segment of the handshake
            self._lossy_layer.send_segment(self.create_segment(
                self.sequence_nr, self.increment_bytes(self.sequence_nr_server), 1, 0, 0, self._window, []))
            # print(int.from_bytes(self.sequence_nr_server, 'big'), " is the seq nr of the server")
            self.connected = True
            self.handshake_response = False
            print("connected!!")

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        # Chop data into segments of size PAYLOAD_SIZE and save into segments list
        payload = list(self.slice_data(data))
        # Add headers to all segments in the list
        for i in payload:
            self.sequence_nr = self.increment_bytes(self.sequence_nr)
            seg = self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 0, 0, 0, i)
            self.segments.append(seg)
        # Send segments
        self.receiving.start()
        self.sending.start()
        # Kill threads
        self.sending.join()
        print("stop sending")
        self.receiving.join()
        print("stop receiving")
        self.clock_conn.join()
        print("stop clock")

    # Slice data into segments of size PAYLOAD_SIZE
    def slice_data(self, data):
        for i in range(0, len(data), PAYLOAD_SIZE):
            yield data[i:i + PAYLOAD_SIZE]

    # Sending thread: Start the clock and send all the data
    def sending_data(self):
        # Send first segments
        #self.lock_segs.acquire()
        #Start the clock
        self.clock_conn.start()
        print(len(self.segments))
        max_range = min(self.window_server, len(self.segments))
        for i in range(max_range):
            self.send_segment(self.segments[0])
            # print("CLIENT: sent segment with seq_nr: ", self.segments[0][:2], "and data", self.segments[0][10:])
            del self.segments[0]
        #self.lock_segs.release()
        print(len(self.segments))
        # Send all remaining segments
        while self.segments:  # while there is still stuff to send
            print("sending more")
            self.send_more.wait()
            self.send_more.clear()
            #self.lock_segs.acquire()
            max_range = min(self.window_server, len(self.segments))
            max_range = 1
            for i in range(max_range):
                self.send_segment(self.segments[0])
                # print("CLIENT: sent segment with seq_nr: ", self.segments[0][:2], "and data", self.segments[0][10:])
                del self.segments[0]
            #self.lock_segs.release()
        print("All data sent")

    # Decrement the timeout of the connecting or terminating segment, resend max NR_OF_TRIES times if timeout reached
    def clock_disconnected(self, segment, time_, nr_of_tries):
        while not self.declined and not self.handshake_response and not self.termination_response:
            time.sleep(.005)
            if time_ >= self._timeout and nr_of_tries > 0:
                nr_of_tries -= 1
                self.send_segment(segment, True, nr_of_tries)
            elif time_ >= self._timeout:
                print("Could not connect")
                self.declined = True
            else:
                time_ = int(round(time.time() * 1000)) - time_

    # Decrement each segments timeout every millisecond, resend max NR_OF_TRIES times if timeout reached
    def clock_connected(self):
        print("clock connected started")
        while self.pending_segments or self.segments:
            print(self.pending_segments)
            # Every 5 millis, decrease the time of each pending segment
            time.sleep(.005)
            self.lock_pending.acquire()
            for tuple in self.pending_segments:
                if tuple[1] >= self._timeout and tuple[2] > 0:
                    tuple[2] -= 1
                    self.send_segment(tuple[0], True, tuple[2])
                elif tuple[1] >= self._timeout:
                    print("Segment loss detected")
                    pass
                else:
                    tuple[1] = int(round(time.time() * 1000)) - tuple[1]
            self.lock_pending.release()

    # Receiving thread: Receive ACKs, signal to the sending thread and delete ACKed segments from pending_segments
    def receiving_data(self):
        while self.pending_segments or self.segments:
            # Wait for ack
            self.ack_arrived.wait()
            self.ack_arrived.clear()
            # Take the oldest ack and save its ack_nr, delete the ack from acknowledgement
            ack = self.acknowledgements[0]
            del self.acknowledgements[0]
            # TODO can more acks arrive that are not processed?
            self.ack_nr = ack[2:4]
            # Update the window and signal the send function to send more packets
            # TODO Find out about window
            self.window_server = ack[5]
            self.send_more.set()
            # Remove the acked segment from pending_segments
            self.lock_pending.acquire()
            print(self.pending_segments)
            for seg in self.pending_segments[:]:
                print("RECEIVED")
                print(seg[0][:2])
                print(self.ack_nr[:2])

                if self.increment_bytes(seg[0][:2]) == self.ack_nr[:2]:
                    print("CLIENT: Received an ACK: ", self.ack_nr[:2])
                    self.pending_segments.remove(seg)
            print(self.pending_segments)
            #self.pending_segments = [seg for seg in self.pending_segments if self.increment_bytes(seg[0][:2]) == self.ack_nr[:2]]
            self.lock_pending.release()

    # Send segment and save it into pending_segments
    def send_segment(self, segment, resend=False, nr_of_tries=None):
        if resend:
            # Keep the nr_of_tries bounded to this segment
            self.pending_segments.append([segment, int(round(time.time() * 1000)), nr_of_tries])
        else:
            # Send the packet and assign NR_OF_TRIES to it
            self.pending_segments.append([segment, int(round(time.time() * 1000)), NR_OF_TRIES])
        self._lossy_layer.send_segment(segment)

    # Perform a handshake to terminate a connection
    def disconnect(self):
        segment = self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 0, 1, self._window, [])
        self._lossy_layer.send_segment(segment)
        # Start clock thread to resend segment if necessary
        thread = threading.Thread(target=self.clock_disconnected, args=(segment, time.time(), NR_OF_TRIES))
        thread.start()
        thread.join()
        self.connected = False
        print("connection closed")

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
