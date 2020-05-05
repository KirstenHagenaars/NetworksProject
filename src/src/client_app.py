#!/usr/local/bin/python3

import argparse
from btcp.client_socket import BTCPClientSocket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=10)
    parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=100)
    parser.add_argument("-i", "--input", help="File to send", default="input.file")
    args = parser.parse_args()

    # Create a bTCP client socket with the given window size and timeout value
    s = BTCPClientSocket(args.window, args.timeout)

    if s.connect():
        with open(args.input, 'r') as inputfile:
            contents = inputfile.read()
        s.send(contents.encode())
        s.disconnect()
    # Clean up any state
    s.close()


main()
