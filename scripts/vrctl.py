import cmd
import shlex
import argparse
import socket
import serial
import struct
import os

from collections.abc import Buffer
from typing import Protocol, runtime_checkable

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
    sock.settimeout(2.0)

    class _SocketStream:
        def __init__(self, sock: socket.socket):
            self._sock = sock

        def read(self, size: int = -1) -> bytes:
            try:
                return self._sock.recv(size if size > 0 else 4096)
            except socket.timeout:
                return b''

        def write(self, b: Buffer) -> int | None:
            return self._sock.sendall(bytes(b))  # type: ignore

        def flush(self) -> None:
            pass

        def read_until(self, expected: bytes = b'\n') -> bytes:
            buf = bytearray()
            dl = len(expected)
            while True:
                chunk = self.read(1)
                if not chunk: break
                buf += chunk
                if buf[-dl:] == expected: break
            return bytes(buf)

        def close(self) -> None:
            self._sock.close()

    return _SocketStream(sock)


def parse_hex(s: str) -> bytes:
    return bytes([int(b, base=16) for b in s.strip().split()])


def bytes_to_hex(b: bytes) -> str:
    return ' '.join(f'{x:02X}{y:02X}' for x, y in zip(b[::2], b[1::2]))


def decode_dump_bytes(b: bytes) -> str:
    d = cobs.decode(b.strip(b'\x00'))
    s = f'PC @ {d[32:].hex().upper()}\n'
    s += '-' * 26 + '\n'
    for i in range(8):
        s += f'R{i:<2} = {d[2*i:2*i+2].hex().upper()}\t'
        s += f'R{i+8:<2} = {d[2*i+16:2*i+18].hex().upper()}\n'
    s += '-' * 26
    return s


class Shell(cmd.Cmd):
    prompt = '(vrctl) '

    def __init__(self, stream: BinaryStream | None = None):
        super().__init__()
        self.stream = stream

    def read(self):
        if self.stream is None:
            return parse_hex(input())
        
        return self.stream.read_until(b'\x00')

    def send_packet(self, ptype: int, param1=0, param2=0, data=b''):
        raw = struct.pack(">BHH", ptype, param1, param2) + data
        encoded = cobs.encode(raw) + b'\x00'
        if self.stream is None:
            print(bytes_to_hex(encoded))
        else:
            self.stream.write(encoded)

    def do_load(self, arg):
        args = shlex.split(arg)
        with open(args[0], 'rb') as f: content = f.read()

        ptr = 0
        while ptr < len(content):
            addr, length = struct.unpack_from('>HH', content, ptr)
            ptr += 4

            if addr == 0xFFFF and length == 0:
                self.send_packet(0x01, 0xFFFF)
                self.read()  # drain EOF ack
                break

            data = content[ptr:ptr+length]
            ptr += length

            self.send_packet(0x01, addr, length, data)

            if not self.read():
                print("error: timeout")
                return
            
    def do_dump(self, arg) -> None:
        self.send_packet(0x02, ord('d'))
        print(decode_dump_bytes(self.read()))

    def do_step(self, arg) -> None:
        self.send_packet(0x02, ord('s'))
        print(decode_dump_bytes(self.read()))
        
    def do_halt(self, arg) -> None:
        self.send_packet(0x02, ord('h'))

    def do_run(self, arg) -> None:
        self.send_packet(0x02, ord('r'))

    def do_clear(self, arg):
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