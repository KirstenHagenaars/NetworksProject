#!/usr/local/bin/python3

import argparse
from btcp.client_socket import BTCPClientSocket
import numpy as np
from ftplib import FTP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=10)
    parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=10)
    parser.add_argument("-i", "--input", help="File to send", default="inputsmall.file")
    args = parser.parse_args()

    # Create a bTCP client socket with the given window size and timeout value
    s = BTCPClientSocket(args.window, args.timeout)
    # TODO Write your file transfer clientcode using your implementation of BTCPClientSocket's connect, send, and disconnect methods.
    # convert data to array of bytes, might be done implicitly

    s.connect()
    with open(args.input, 'r') as file:
        contents = file.read()
    s.send(contents.encode())
    s.disconnect()
    # Clean up any state
    s.close()


main()
