#!/usr/local/bin/python3

import argparse
from btcp.server_socket import BTCPServerSocket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=100)
    parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=100)
    parser.add_argument("-o", "--output", help="Where to store the file", default="output.file")
    args = parser.parse_args()

    # Create a bTCP server socket
    s = BTCPServerSocket(args.window, args.timeout)
    # TODO Write your file transfer server code here using your BTCPServerSocket's accept, and recv methods.

    # Clean up any state
    s.close()


main()
