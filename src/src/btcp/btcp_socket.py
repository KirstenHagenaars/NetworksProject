from btcp.constants import *


class BTCPSocket:
    def __init__(self, window, timeout):
        self._window = window
        self._timeout = timeout

    # Return the Internet checksum of data
    @staticmethod
    def in_cksum(data):
        #should be array of 2 bytes
        return 0

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
        if dataLength < 1008:
            diff = PAYLOAD_SIZE - dataLength
            data += bytes(diff)
        # Convert dataLength to 2 bytes
        dataLength = dataLength.to_bytes(2, 'big')
        # Create segment
        segment = sequenceNr + ackNr + [flags] + [window] + dataLength + [0x00] + data
        # Compute checksum, with checksum value set to 0x00
        checksum = self.in_cksum(segment)
        # Insert checksum
        segment[8] = checksum[0]
        segment[9] = checksum[1]
        return segment

    # Takes array of 2 bytes and increments its value by 1, useful for sequenceNr
    def increment_bytes(self, bytes):
        increasedValue = int.from_bytes(bytes, 'big') + 1
        return increasedValue.to_bytes(2, 'big')
