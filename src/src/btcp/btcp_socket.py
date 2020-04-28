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
            # Take 2 bytes and add them to the sum
            x = data[i] * 256 + data[i + 1]
            intermediate = sum + x
            # Wraparound carry
            sum = (intermediate & 0xffff) + (intermediate >> 16)
        print(~sum & 0xffff)
        return ~sum & 0xffff

    # Returns true if the checksum corresponds to the segment
    def check_cksum(self, segment):
        return 0 == ~self.in_cksum(segment) & 0xffff

    # Receives data for 1 segment (max 1008 bytes), and all other segment values
    # all parameters are in bytes, except for ACK, SYN and FIN, which are booleans
    # returns entire segment (array of bytes)
    def create_segment(self, sequenceNr, ackNr, ACK, SYN, FIN, window, data):
        # Flags are represented as 0 0 0 0 0 ACK SYN FIN
        flags = ACK*4+SYN*2+FIN*1
        flags = flags.to_bytes(1, 'big')
        # Compute data length in bytes, should be 2 bytes
        dataLength = len(data)
        # Add padding to segment data shorter than 1008
        if dataLength < PAYLOAD_SIZE:
            diff = PAYLOAD_SIZE - dataLength
            data += bytes(diff)
        # Convert dataLength to 2 bytes
        dataLength = dataLength.to_bytes(2, 'big')
        # Create segment
        segment = sequenceNr + ackNr + flags + window.to_bytes(1, 'big') + dataLength + 0x00.to_bytes(2, 'big') + bytes(data)
        #print(segment)
        # Compute checksum, with checksum value set to 0x00
        checksum = self.in_cksum(segment)
        # Insert checksum
        segment = sequenceNr + ackNr + flags + window.to_bytes(1, 'big') + dataLength + checksum.to_bytes(2, 'big') + bytes(data)
        return segment

    # Takes array of 2 bytes and increments its value by 1, useful for sequenceNr
    def increment_bytes(self, bytes):
        increasedValue = int.from_bytes(bytes, 'big') + 1
        return increasedValue.to_bytes(2, 'big')

    # Takes flags byte and returns 3 booleans corresponding to the flags
    def get_flags(self, flags):
        pass
