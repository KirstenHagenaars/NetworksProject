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
        self.segments = []                      # Segments to be sent
        self.pending_segments = []              # Segments to be acked
        self.resent_segments = []               # Segments that need to be resent
        self.lock_segs = Lock()                 # Lock for segments
        self.lock_acks = Lock()                 # Lock for acknowledgements
        self.lock_pending = Lock()              # Lock for pending_segments
        self.sequence_nr = np.random.bytes(2)   # The sequence number, 2 bytes
        self.last_sent = 0                      # The index of last sent segment
        self.sequence_nr_server = None          # Sequence_nr of the server
        self.ack_nr = None                      # Ack_nr
        self.nr_acked = 0
        self.window_server = None               # Window buffer of the server
        self.init_seq_nr = self.increment_bytes(self.increment_bytes(self.sequence_nr))     # The initial sequence number
        # Threads:
        self.clock_conn = threading.Thread(target=self.clock_connected)
        self.sending = threading.Thread(target=self.sending_data)
        # self.receiving = threading.Thread(target=self.receiving_data)

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # look for corresponding event in array, awaken event
        segment = segment[0]
        if self.check_cksum(segment):
            self.sequence_nr_server = segment[:2]
            self.window_server = segment[5]
            self.ack_nr = segment[2:4]
            SYN, ACK, FIN = self.get_flags(segment[4])
            # ACK should always be set for the server, but lets check it for niceness?
            if self.connected:
                if ACK and not FIN:
                    print("CLIENT: Received an ACK: ", self.ack_nr)
                    # Remove acknowledged segment from the pending segments
                    self.lock_pending.acquire()
                    self.pending_segments = [seg for seg in self.pending_segments if seg[0] != self.ack_nr]
                    self.nr_acked += 1
                    self.lock_pending.release()
                elif ACK and FIN:
                    # Signal disconnect
                    self.termination_response = True
            elif ACK and SYN and self.increment_bytes(self.sequence_nr) == self.ack_nr:
                # Server has done its part in the three-way handshake
                self.handshake_response = True
            #print(self.nr_acked)

    # Perform a three-way handshake to establish a connection
    def connect(self):
        segment1 = self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 1, 0, self._window, [])
        self._lossy_layer.send_segment(segment1)
        # Start clock thread to resend segment if necessary
        thread1 = threading.Thread(target=self.clock_disconnected, args=(segment1, int(round(time.time() * 1000)), NR_OF_TRIES))
        thread1.start()
        thread1.join()
        # TODO check if declined
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
        print("we need to send ", len(self.segments), " segments")
        # Send segments
        self.sending.start()
        self.clock_conn.start()
        self.sending.join()
        self.clock_conn.join()

    # Slice data into segments of size PAYLOAD_SIZE
    def slice_data(self, data):
        for i in range(0, len(data), PAYLOAD_SIZE):
            yield data[i:i + PAYLOAD_SIZE]

    # Sending thread: Start the clock and send all the data
    def sending_data(self):
        # Send first segments
        self.lock_segs.acquire()
        max_range = min(self.window_server, len(self.segments))
        for i in range(max_range):
            self.send_segment(self.segments[i][:2])  # We pass the sequence number
            self.last_sent += 1
        self.lock_segs.release()
        # Start the clock

        # Send all remaining segments
        while self.last_sent < len(self.segments) or self.resent_segments or self.pending_segments:  # while there is still stuff to send
            window = self.window_server - len(self.pending_segments)-1
            # Segments to be resent have a priority
            if self.resent_segments:
                max_range = (min(window, len(self.resent_segments)))
                for i in range(max_range):
                    # TODO decrement nr of tries
                    resent = self.resent_segments.pop(0)
                    print("resent: ", resent[0])
                    self.send_segment(resent[0], resent[2])
            # No segments to be resend, we can send fresh segments
            elif self.last_sent < len(self.segments):
                max_range = (min(window, (len(self.segments) - self.last_sent)))
                for i in range(max_range):
                    self.last_sent = self.last_sent + 1
                    self.send_segment(self.segments[self.last_sent][:2])

    # Decrement the timeout of the connecting or terminating segment, resend max NR_OF_TRIES times if timeout reached
    def clock_disconnected(self, segment, time_, nr_of_tries):
        print("clock disconnected started")
        declined = False
        while not declined and not self.handshake_response and not self.termination_response:
            time.sleep(.005)
            time_ = int(round(time.time() * 1000)) - time_
            if time_ >= self._timeout and nr_of_tries > 0:
                nr_of_tries -= 1
                lst = (segment, nr_of_tries)
                self.send_segment(segment[:2], nr_of_tries)
            elif time_ >= self._timeout:
                print("Could not connect")
                declined = True

    # Decrement each segments timeout every millisecond, resend max NR_OF_TRIES times if timeout reached
    def clock_connected(self):
        print("clock connected started")
        while self.pending_segments or self.resent_segments or self.last_sent < len(self.segments):
            # Every 5 millis, decrease the time of each pending segment
            # Tuple[0] = seq_nr, tuple[1] = orig_time, tuple[2] = timeout, tuple[3] = nr_or_tries
            time.sleep(.005)
            sent = []
            self.lock_pending.acquire()
            for tuple in self.pending_segments:
                # print("segment ", tuple[0])
                # print("timeout original: ", tuple[2])
                tuple[2] = int(round(time.time() * 1000)) - tuple[1]
                # print("new timeout: ", tuple[2])
                if tuple[2] >= self._timeout and tuple[3] > 0:
                    self.resent_segments.append(tuple)
                elif tuple[2] >= self._timeout:
                    print("Segment loss detected")
                else:
                    sent.append(tuple)
            self.pending_segments = sent
            self.lock_pending.release()

    # Send segment and save it into
    def send_segment(self, seq_nr, nr_of_tries=NR_OF_TRIES):
        # TODO check bounds?
        index = int.from_bytes(seq_nr, 'big') - int.from_bytes(self.init_seq_nr, 'big')
        segment = self.segments[index]
        self.pending_segments.append([seq_nr, int(round(time.time() * 1000)), 0,  nr_of_tries])
        self._lossy_layer.send_segment(segment)

    # Perform a handshake to terminate a connection
    def disconnect(self):
        segment = self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 0, 1, self._window, [])
        self._lossy_layer.send_segment(segment)
        # Start clock thread to resend segment if necessary
        thread = threading.Thread(target=self.clock_disconnected, args=(segment, int(round(time.time() * 1000)), NR_OF_TRIES))
        thread.start()
        print('START')
        thread.join()
        print('END')
        self.connected = False
        print("connection closed succesfully")

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
