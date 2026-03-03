import re
import argparse
import struct

from collections.abc import Iterator
from dataclasses import dataclass


TOKEN_REGEX = re.compile('|'.join([
    r"(?P<LBL>\w+)[^\S\n\r]*:",
    r"(?P<COM>,)",
    r"(?P<LBR>\[)",
    r"(?P<RBR>\])",     
    r"(?P<LPA>\()",   
    r"(?P<RPA>\))", 
    r"(?P<PLUS>\+)",
    r"(?P<MINUS>\-)",  
    r"#\s*(?P<COMM>.*)",
    r"(?P<ID>\.?\w+)",
    r"(?P<NL>[\n\r]+)",
    r"(?P<WS>[^\S\n\r]+)",
    r"(?P<UNK>.+)"
]))


OP_REGEX = re.compile('|'.join([
    r"r(?P<REG>\d+)",
    r"(?P<IMM>-?(?:0x[0-9a-fA-F]+|\d+))",
    r"(?P<SYM>\w+)",
]))


@dataclass
class Token:
    type: str
    val: str


@dataclass
class Mnemonic:
    opcode: int
    format: str

    def encode(self, *ops: int) -> list[int]:
        return FORMAT_SPEC[self.format](self.opcode, *ops)


Instruction = tuple[str | None, str | None, tuple[str, ...]]


MNEMONICS: dict[str, Mnemonic] = {
    'ADD':  Mnemonic(0x0, 'R'),
    'SUB':  Mnemonic(0x1, 'R'),
    'AND':  Mnemonic(0x2, 'R'),
    'OR':   Mnemonic(0x3, 'R'),
    'XOR':  Mnemonic(0x4, 'R'),

    'LD':   Mnemonic(0x5, 'M'),
    'ST':   Mnemonic(0x6, 'M'),

    'LHI':  Mnemonic(0x7, 'I'),
    'LLI':  Mnemonic(0x8, 'I'),

    'BZ':   Mnemonic(0x9, 'B'),
    'BNZ':  Mnemonic(0xA, 'B'),
    'BLT':  Mnemonic(0xB, 'B'),

    'JMP':  Mnemonic(0xC, 'JMP'),
    'JAL':  Mnemonic(0xD, 'JAL'),

    'SHL':  Mnemonic(0xE, 'S'),
    'SHR':  Mnemonic(0xF, 'S'),
}


FORMAT_SPEC = {
    'R':    lambda c, rd, r1, r2:   [c << 4 | rd,   r1 << 4 | r2],
    'M':    lambda c, r, rb, off:   [c << 4 | r,    rb << 4 | off],
    'I':    lambda c, rd, imm:      [c << 4 | rd,   imm],
    'B':    lambda c, rs, off:      [c << 4 | rs,   off],
    'JMP':  lambda c, rs:           [c << 4 | rs,   0x00],
    'JAL':  lambda c, rd, rs:       [c << 4 | rd,   rs << 4],
    'S':    lambda c, rd, rs, off:  [c << 4 | rd,   rs << 4 | off],
}


def lex(text: str) -> Iterator[Token]:
    for m in TOKEN_REGEX.finditer(text):
        type_ = m.lastgroup
        assert type_ is not None

        if type_ == 'WS': continue

        assert type_ != 'UNK', m.group(type_)

        yield Token(type_, m.group(type_))


def parse(text: str) -> Iterator[Instruction]:
    tokens = lex(text)

    for tok in tokens:
        if tok.type in ("COMM", "NL"):
            continue

        label = None
        if tok.type == "LBL":
            label = tok.val
            tok = next(tokens, None)

        while tok and tok.type in ("COMM", "NL"):
            tok = next(tokens, None)

        if tok and tok.type == "ID":
            yield (label, tok.val, tuple(parse_operands(tokens)))
        elif label:
            yield (label, None, ())


def parse_operands(tokens: Iterator[Token]) -> Iterator[str]:
    for tok in tokens:
        if tok.type in ("COMM", "NL"):
            break

        if tok.type == "ID" and tok.val in ("HIGH", "LOW"):
            mod = tok.val
            if next(tokens).type != "LPA": raise SyntaxError("Expected '('")
            sym = next(tokens)
            if sym.type != "ID": raise SyntaxError("Expected symbol in modifier")
            if next(tokens).type != "RPA": raise SyntaxError("Expected ')'")
            yield f"{mod}:{sym.val}"

        elif tok.type == "LBR":
            rb = next(tokens)
            if rb.type != "ID": raise SyntaxError("Expected base register")
            yield rb.val

            peek = next(tokens)
            if peek.type == "RBR": yield "0"
            elif peek.type in ("PLUS", "MINUS"):
                sign = "-" if peek.type == "MINUS" else ""
                off = next(tokens)
                if next(tokens).type != "RBR": raise SyntaxError("Expected ']'")
                yield f"{sign}{off.val}"
            else:
                raise SyntaxError("Invalid pointer syntax")

        elif tok.type == "ID":
            yield tok.val
        else:
            raise SyntaxError(f"Unexpected token in operands: {tok}")

        tok = next(tokens, None)
        if tok is None or tok.type in ("COMM", "NL"):
            break
        if tok.type != "COM":
            raise SyntaxError("Expected comma")

def resolve_symbols(program: list[Instruction]) -> dict[str, int]:
    lc = 0x0000
    sym = {}

    for label, name, ops in program:
        if label is not None:
            sym[label] = lc

        if name == '.org':
            if len(ops) != 1: raise SyntaxError(".org expects exactly 1 argument")
            lc = int(ops[0], base=0)
        elif name == '.word' or name in MNEMONICS: lc += 2
        elif name is None: continue
        else: raise SyntaxError(f"Unknown mnemonic or directive: '{name}'")

    return sym


def resolve_operand(op: str, symbols: dict[str, int]) -> int:
    if ":" in op:
        mod, sym = op.split(":", 1)
        val = symbols[sym] if sym in symbols else int(sym, 0)
        return (val >> 8) & 0xFF if mod == "HIGH" else val & 0xFF

    m = OP_REGEX.fullmatch(op)
    if not m: raise SyntaxError(f"Invalid operand syntax: {op}")

    kind = m.lastgroup
    if kind in ('IMM', 'REG'): return int(m.group(kind), 0)
    if kind == 'SYM': return symbols[m.group(kind)]

    raise ValueError(f"Unknown operand type for {op}")


def assemble(program: list[Instruction], symbols: dict[str, int]) -> Iterator[tuple[int, bytes]]:
    block_start = lc = 0x0000
    arr = bytearray()

    for _, name, ops in program:
        if name == '.org':
            if arr: yield block_start, bytes(arr)
            block_start = lc = int(ops[0], base=0)
            arr = bytearray()
            continue

        if name == '.word':
            arr.extend(int(ops[0]).to_bytes(2, 'big'))
        elif name in MNEMONICS:
            mn = MNEMONICS[name]
            ops = [resolve_operand(op, symbols) for op in ops]

            if mn.format == 'B':
                ops[1] = ops[1] - (lc + 2)
                if not (-128 <= ops[1] <= 127):
                    raise ValueError(f"Branch out of range: {ops[1]}")
                ops[1] = ops[1] & 0xFF

            arr.extend(mn.encode(*ops))
        elif name is None:
            continue

        lc += 2

    if arr: yield block_start, bytes(arr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str)
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="write binary output to file")
    args = parser.parse_args()

    with open(args.file, 'r') as f:
        content = f.read()

    program = list(parse(content))
    symbols = resolve_symbols(program)
    blocks = list(assemble(program, symbols))

    print("symbols:", {k: f"0x{v:04X}" for k, v in symbols.items()})
    for addr, data in blocks:
        print(f"block @ 0x{addr:04X}, size: {len(data)} B")

    if args.output:
        with open(args.output, 'wb') as f:
            for addr, data in blocks:
                header = struct.pack(">HH", addr, len(data)) 
                f.write(header)
                f.write(data)
            
            f.write(struct.pack(">HH", 0xFFFE, 0x0002))
            f.write(struct.pack(">H", symbols.get('main', 0x0000))) # reset vector

            f.write(struct.pack(">HH", 0xFFFF, 0x0000)) # EOF
            
        print(f"\n{args.output} generated succesfully")