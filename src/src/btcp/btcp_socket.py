from btcp.constants import *

class BTCPSocket:
    def __init__(self, window, timeout):
        self._window = window
        self._timeout = timeout

    # Return the Internet checksum of data
    @staticmethod
    def in_cksum(data):
        sum = 0
        for i in range(0, len(data), 2):
            # Take 2 bytes and add them to the sum, take only final byte in case of uneven nr of bytes
            if i == len(data)-1:
                x = data[i] * 256
            else:
                x = data[i] * 256 + data[i + 1]
            intermediate = sum + x
            # Wraparound carry
            sum = (intermediate & 0xffff) + (intermediate >> 16)
        return ~sum & 0xffff

    # Returns true if the checksum corresponds to the segment
    def check_cksum(self, segment):
        return 0 == self.in_cksum(segment)

    # Receives data for 1 segment (max 1008 bytes), and other segment values
    # Returns entire segment (array of bytes)
    def create_segment(self, sequenceNr, ackNr, ACK, SYN, FIN, window, data):
        # Flags are represented as 0 0 0 0 0 ACK SYN FIN
        flags = ACK*4+SYN*2+FIN*1
        flags = flags.to_bytes(1, 'big')
        dataLength = len(data)
        # Convert dataLength to 2 bytes
        dataLength = dataLength.to_bytes(2, 'big')
        # Create segment
        segment = sequenceNr + ackNr + flags + window.to_bytes(1, 'big') + dataLength + (0).to_bytes(2, 'big') + bytes(data)
        # Compute checksum, with checksum value set to 0x00
        checksum = self.in_cksum(segment)
        # Insert checksum
        segment = sequenceNr + ackNr + flags + window.to_bytes(1, 'big') + dataLength + checksum.to_bytes(2, 'big') + bytes(data)
        return segment

    # Slice data into segments of size PAYLOAD_SIZE
    def slice_data(self, data):
        for i in range(0, len(data), PAYLOAD_SIZE):
            yield data[i:i + PAYLOAD_SIZE]

    # Takes array of 2 bytes and increments its value by 1, useful for sequenceNr
    def increment_bytes(self, bytes):
        increasedValue = int.from_bytes(bytes, 'big') + 1
        return increasedValue.to_bytes(2, 'big')

    # Takes flags byte and returns 3 booleans corresponding to the flags, in the order of ACK SYN FIN
    def get_flags(self, flags):
        return flags&4 != 0, flags&2 != 0, flags&1 != 0
