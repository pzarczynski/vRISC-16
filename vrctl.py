import cmd
import shlex
import argparse
import socket
import serial
import struct
import os

from collections.abc import Buffer
from typing import Protocol, runtime_checkable, cast

from cobs import cobs


@runtime_checkable
class BinaryStream(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...
    def write(self, b: Buffer, /) -> int | None: ...
    def flush(self) -> None: ...
    def read_until(self, expected: bytes = b'\n') -> bytes: ...
    def close(self) -> None: ...


def serial_stream(dev: str, baud: int) -> BinaryStream:
    return serial.Serial(dev, baudrate=baud, timeout=0)


def net_stream(host: str, port: int) -> BinaryStream:
    sock = socket.create_connection((host, port))
    stream = sock.makefile('rwb', buffering=0)

    class _SocketIOWrapper(socket.SocketIO):
        def read_until(self, expected: bytes = b'\n') -> bytes:
            buf = bytearray()
            d = expected
            dl = len(d)
            while True:
                chunk = self.read(1)
                if not chunk: break
                buf += chunk
                if buf[-dl:] == d: break
            return bytes(buf)

    stream.__class__ = _SocketIOWrapper
    return cast(_SocketIOWrapper, stream)


def parse_hex(s: str) -> bytes:
    return bytes([int(b, base=16) for b in s.strip().split()])


def bytes_to_hex(b: bytes) -> str:
    return ' '.join(f'{x:02X}{y:02X}' for x, y in zip(b[::2], b[1::2]))


class Shell(cmd.Cmd):
    prompt = '(vrctl) '

    def __init__(self, stream: BinaryStream | None = None):
        super().__init__()
        self.stream = stream

    def send_packet(self, p: bytes):
        encoded = cobs.encode(p)
        if self.stream is None:
            print(bytes_to_hex(encoded + b'\x00'))
        else:
            self.stream.write(encoded + b'\x00')

    def do_load(self, arg):
        args = shlex.split(arg)
        with open(args[0], 'rb') as f: content = f.read()

        ptr = 0
        while ptr < len(content):
            addr, length = struct.unpack_from('>HH', content, ptr)
            ptr += 4

            if addr == 0xFFFF and length == 0:
                self.send_packet(struct.pack(">HH", 0xFFFF, 0))
                break

            data = content[ptr:ptr+length]
            ptr += length

            packet = struct.pack(">HH", addr, length) + data
            self.send_packet(packet)

            if self.stream is None:
                resp = parse_hex(input())
            else:
                resp = self.stream.read_until(b'\x00')

            if not resp:
                print("error: timeout")
                return

    def do_cls(self, arg):
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_exit(self, arg):
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", "-d", default=None, type=str)
    parser.add_argument("--host", "-i", default=None, type=str)
    parser.add_argument("--baud", "-b", default=115200, type=int)
    parser.add_argument("--port", "-p", default=5000, type=int)
    args = parser.parse_args()

    stream = None
    if args.dev:
        stream = serial_stream(args.dev, args.baud)
    elif args.host:
        stream = net_stream(args.host, args.port)

    shell = Shell(stream)
    print("vRISC-16 shell. Type 'exit' to quit.")
    shell.cmdloop()