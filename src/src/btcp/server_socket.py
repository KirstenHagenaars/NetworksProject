from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from threading import Event
import threading
import numpy as np
from diffiehellman.diffiehellman import DiffieHellman
from cryptography.fernet import Fernet
import base64

# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.encryption_mode = False              # Is true if encryption should be used
        self.recv_data = True                     # Is false during key exchange
        self.connected = False                    # Keeps track of state
        self.received = []                        # Received segments that still need to be processed and acknowledged
        self.processed = []                       # List of (sequenceNR, data) tuples, that have been received
        self.handshake = Event()                  # Set when client requests a handshake
        self.end_handshake = False                # True when the last segment of handshake has arrived
        self.sequence_nr = np.random.bytes(2)     # Server's sequence number
        self.sequence_nr_client = None            # Client's sequence number
        # Diffie-Hellman:
        self.DH = DiffieHellman(key_length=200)


    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment = segment[0]
        if self.check_cksum(segment):
            ACK, SYN, FIN = self.get_flags(segment[4])
            if not self.connected and (SYN or ACK):
                # Perform handshake
                if ACK and self.increment_bytes(self.sequence_nr) == segment[2:4]:
                    self.end_handshake = True
                elif segment[10]&1 != 0:
                    # Read encryption mode and generate keys
                    self.encryption_mode = True
                    self.DH.generate_private_key()
                    self.DH.generate_public_key()
                self.sequence_nr_client = segment[:2]
                self.handshake.set()
            elif self.connected:
                if not FIN:
                    # Process segment
                    if not self.recv_data and segment[5] == 0:
                        # Stop key exchange
                        self.recv_data = True
                    self.received.append(segment)
                    self.processed.append((int.from_bytes(segment[:2], 'big'), segment[10:]))
                else:
                    # Start termination
                    print("All data has arrived")
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
        self.sequence_nr_client = self.increment_bytes(self.sequence_nr_client)
        self.connected = True
        print("Connected")

    # Send any incoming data to the application layer
    def recv(self):
        if self.encryption_mode:
            # Perform key exchange
            self.recv_data = False
            exchange = threading.Thread(target=self.key_exchange())
            exchange.start()
            exchange.join()
        print("Start receiving")
        t1 = threading.Thread(target=self.receiving_data)
        t1.start()
        # Wait for termination to start
        t1.join()
        # Now termination has started
        self.close_connection()
        print("Connection closed")
        # Remove duplicates, sort the segments and concatenate the data
        self.processed = sorted(list(set(self.processed)))
        if self.encryption_mode:
            # Retrieve client's public key from first 3 segments and compute shared key
            self.DH.generate_shared_secret(
                int(b''.join([text for (seq_num, text) in self.processed[:3]]).decode()))
            self.processed = self.processed[4:]
        self.processed = b''.join([text for (seq_num, text) in self.processed])
        if self.encryption_mode:
            # Decrypt, there occurs an error here
            f = Fernet(base64.b64encode(self.DH.shared_key.encode()[:32]))
            self.processed = f.decrypt(self.processed)
        return self.processed

    def key_exchange(self):
        key_fragments = list(self.slice_data(str(self.DH.public_key).encode()))
        key = []
        for f in key_fragments:
            key.append((self.sequence_nr_client, f))
            self.sequence_nr_client = self.increment_bytes(self.sequence_nr_client)
        while not self.recv_data:
            if self.received:
                if self.received[0][5] == 0:
                    self.recv_data = True
                else:
                    segment = self.received.pop(0)
                    data = None
                    for tuple in key:
                        if tuple[0] == segment[:2]:
                            data = tuple[1]
                    ack = self.create_segment((0).to_bytes(2, 'big'), segment[:2], 1, 0, 0,
                                              max(0, (self._window - len(self.received))), data)
                    self._lossy_layer.send_segment(ack)

    # Receiving thread:
    # Wait for a segment from lossy layer, send an ACK segment in response
    def receiving_data(self):
        while self.connected:
            if self.received:
                segment = self.received.pop(0)
                ack = self.create_segment((0).to_bytes(2, 'big'), segment[:2], 1, 0, 0,
                                          max(0, (self._window - len(self.received))), [])
                self._lossy_layer.send_segment(ack)

    def close_connection(self):
        # Send response to FIN segment
        self._lossy_layer.send_segment(
            self.create_segment((0).to_bytes(2, 'big'), (0).to_bytes(2, 'big'), 1, 0, 1, 0, []))

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
