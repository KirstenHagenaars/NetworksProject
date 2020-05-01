from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
import numpy as np
import time
from threading import Lock, Event
import _thread


# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        self.connected = False                  # Keeps track of the state, connected or not
        self.segments = []                      # Segments to be sent
        self.acknowledgements = []              # Received acknowledgements
        self.pending_segments = []              # Segments to be acked
        self.lock_segs = Lock()                 # Lock for segments
        self.lock_acks = Lock()                 # Lock for acknowledgements
        self.lock_pending = Lock()              # Lock for pending_segments
        self.ack_arrived = Event()              # Set when there is a new ack from the lossy layer
        self.send_more = Event()                # Set when more segments can be sent to the server
        self.sequence_nr = np.random.bytes(2)   # The sequence number, 2 bytes
        self.sequence_nr_server = None
        self.ack_nr = None
        self.window_server = None

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # look for corresponding event in array, awaken event
        segment = segment[0]
        # TODO debug checksum
        if self.check_cksum(segment):
            self.sequence_nr_server = segment[:2]
            self.window_server = segment[5]
            self.ack_nr = segment[2:4]

            if self.connected:
                # Add segment to acknowledgements
                self.lock_acks.acquire()
                self.acknowledgements.append(segment)
                self.lock_acks.release()
                self.ack_arrived.set()
            else:
                # TODO check if SYN and ACK are set, and check x+1
                handshake.set()

    # Perform a three-way handshake to establish a connection
    def connect(self):
        global handshake
        handshake = Event()
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 1, 0, self._window, []))
        handshake.wait()
        # todo make loop/ use clock, read segment
        self.sequence_nr = self.increment_bytes(self.sequence_nr)
        self._lossy_layer.send_segment(self.create_segment(
            self.sequence_nr, self.increment_bytes(self.sequence_nr_server), 1, 0, 0, self._window, []))
        self.connected = True
        print("connected!!")

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        # Chop data into segments of size PAYLOAD_SIZE and save into segments list
        self.segments = list(self.slice_data(data))
        # Add headers to all segments in the list
        for i in range(len(self.segments)):
            seg = self.create_segment(self.sequence_nr, (0).to_bytes(2, 'big'), 0, 0, 0, self._window, self.segments[i])
            self.segments[i] = seg
            self.sequence_nr = self.increment_bytes(self.sequence_nr)
        # Send segments
        _thread.start_new_thread(self.sending_data(), ())
        _thread.start_new_thread(self.receiving_data(), ())
        # TODO finish

    # Slice data into segments of size PAYLOAD_SIZE
    def slice_data(self, data):
        for i in range(0, len(data), PAYLOAD_SIZE):
            yield data[i:i+PAYLOAD_SIZE]

    # Sending thread: Start the clock and send all the data
    def sending_data(self):
        # Send first segments
        window = self.window_server
        print("window size\n")
        print(window)
        for i in range(min(window, len(self.segments))):
            self.lock_segs.acquire()
            self.send_segment(self.segments[i])
            del self.segments[i]
            self.lock_segs.release()
        # Start the clock
        _thread.start_new_thread(self.clock_connected(), ())
        # Send all remaining segments
        # TODO Do we need a lock in the while condition?
        while self.segments or self.pending_segments: # while there is still stuff to send
            self.send_more.wait()
            self.send_more.clear()
            # Acquire the new window and send as many segments as possible
            window = self.window_server
            for i in range(window):
                self.lock_segs.acquire()
                self.send_segment(self.segments[i])
                del self.segments[i]
                self.lock_segs.release()

    # Created an extra clock for the handshake and termination, this one does not need a lock or a for loop
    # Decrement the timeout of the connecting or terminating segment, resend max NR_OF_TRIES times if timeout reached
    def clock_disconnected(self, segment):
        declined = False
        while not declined or not self.connected:
            time.sleep(.100)
            if segment[1] >= self._timeout and segment[2] > 0:
                segment[2] -= 1
                self.send_segment(segment[0], True, segment[2])
            elif segment[1] >= self._timeout:
                print ("Could not connect")
                declined = True
            else:
                segment[1] = time.time() - segment[1]

    # Decrement each segments timeout every millisecond, resend max NR_OF_TRIES times if timeout reached
    def clock_connected(self):
        while self.pending_segments or self.segments:
            # Every 100 millis, decrease the time of each pending segment
            time.sleep(.100)
            self.lock_pending.acquire()
            for tuple in self.pending_segments:
                if tuple[1] >= self._timeout and tuple[2] > 0:
                    tuple[2] -= 1
                    self.send_segment(tuple[0], True, tuple[2])
                elif tuple[1] >= self._timeout:
                    print("Segment loss detected")
                else:
                    tuple[1] = time.time() - tuple[1]
            self.lock_pending.release()

    # Receiving thread: Receive ACKs, signal to the sending thread and delete ACKed segments from pending_segments
    def receiving_data(self):
        while self.pending_segments or self.segments:
            self.ack_arrived.wait()
            self.ack_arrived.clear()
            # Notify sending thread to send more segments
            self.send_more.set()
            # Take the oldest ack, save its ack_nr and delete it from the acknowledgements
            self.lock_acks.acquire()
            ack = self.acknowledgements[0]
            del self.acknowledgements[0]
            self.lock_acks.release()
            ack_nr = ack[2:4]
            # Remove the acked segment from pending_segments
            self.lock_pending.acquire()
            for seg in self.pending_segments:
                if seg[0] == ack_nr[0] and seg[1] == ack_nr[1]:
                    del seg
            self.lock_pending.release()

    # Send segment and save it into pending_segments
    def send_segment(self, segment, resend=False, nr_of_tries=None):
        self.lock_pending.acquire()
        if resend:
            self.pending_segments.append([segment, time.time(), nr_of_tries])
        else:
            self.pending_segments.append([segment, time.time(), NR_OF_TRIES])
        self.lock_pending.release()
        self._lossy_layer.send_segment(segment)

    # Perform a handshake to terminate a connection
    def disconnect(self):
        # Lets implement this after testing the connection establisment, so we dont waste time
        self._lossy_layer.send_segment(
            self.create_segment(self.sequence_nr, [0x00, 0x00], 0, 0, 1, super()._window, []))
        # wait for response with ack and fin, try some amount of times before giving up
        self.connected = False
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
