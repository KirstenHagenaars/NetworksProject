class BTCPSocket:
    def __init__(self, window, timeout):
        self._window = window
        self._timeout = timeout
   
    # Return the Internet checksum of data
    @staticmethod
    def in_cksum(data):
        #should be array of 2 bytes
        pass

    # Receives data for 1 segment (max 1008 bytes), and all other segment values
    # all parameters are in bytes, except for ACK, SYN and FIN, which are booleans
    # returns entire segment (array of bytes)
    def create_segment(self, sequenceNr, ackNr, ACK, SYN, FIN, window, data):
        # TODO determine how we want to represent flags, & implement
        flags = 0x00

        # Compute data length in bytes, should be 2 bytes
        dataLength = len(data)
        # TODO convert datalength to 2 bytes
        segment = sequenceNr + ackNr + [flags] + [window] + dataLength + [0x00] + data
        # compute checksum, with checksum value set to 0x00
        checksum = self.in_cksum(segment)
        # insert checksum
        segment[8] = checksum[0]
        segment[9] = checksum[1]
        return segment
