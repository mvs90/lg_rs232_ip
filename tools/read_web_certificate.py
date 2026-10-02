#!/usr/bin/env python3
"""Read a Signage HTTPS certificate fingerprint; sends no login or commands.

Initial discovery only: compare the result with the certificate shown by your
browser on the trusted device network before storing it in integration options.
"""
import argparse
import hashlib
import socket
import ssl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, choices=(3737, 3777), default=3777)
    args = parser.parse_args()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        with context.wrap_socket(connection, server_hostname=args.host) as tls:
            print(hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest())


if __name__ == "__main__":
    main()
