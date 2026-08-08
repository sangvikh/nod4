#!/usr/bin/env python3
"""
μ-Core Parameterized Two-Pass Assembler (Conforms to ISA v1.0.0 & ABI v1.0.0)
Supports both μ4 (4-bit) and μ8 (8-bit) hardware architectures.
"""

import sys
import os
import re
import argparse

OPCODES = {
    'NOP': 0x0, 'MOV': 0x1, 'LOAD': 0x2, 'STORE': 0x3,
    'ALU': 0x4, 'JMP': 0x5, 'JZ': 0x6,   'JC': 0x7,
    'CALL': 0x8, 'RET': 0x9, 'PUSH': 0xA,  'POP': 0xB,
    'IO': 0xC,  'EXEC': 0xD, 'RSVD': 0xE, 'HLT': 0xF
}

ALU_OPS = {
    'ADD': 0x0, 'SUB': 0x1, 'ADC': 0x2, 'SBB': 0x3,
    'AND': 0x4, 'OR': 0x5,  'XOR': 0x6, 'NOT': 0x7,
    'INC': 0x8, 'DEC': 0x9, 'SHL': 0xA, 'SHR': 0xB,
    'ROL': 0xC, 'ROR': 0xD, 'CMP': 0xE, 'TST': 0xF
}

REG_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'FLAGS': 4}

# Architecture Target Configuration
TARGET_CONFIGS = {
    'mu4': {
        'word_size': 4,
        'mask': 0x0F,
        'page_size': 16,            # 16 nibbles per page
        'literal_start': 0x0E,      # Literal pool at $E..$F
        'literal_max': 0x0F,
        'stack_depth': 4,           # N=4 Hardware Stack Depth
    },
    'mu8': {
        'word_size': 8,
        'mask': 0xFF,
        'page_size': 256,           # 256 bytes per page
        'literal_start': 0xF0,      # Literal pool at $F0..$FE
        'literal_max': 0xFF,
        'stack_depth': 16,          # N=16 Hardware Stack Depth
    }
}

class MicroCoreAssembler:
    def __init__(self, target='mu8'):
        self.config = TARGET_CONFIGS[target]
        self.target = target
        self.symbol_table = {}
        self.literal_pool = {}
        self.literal_next_offset = self.config['literal_start']

    def parse_number(self, val_str):
        val_str = val_str.strip()
        if val_str.startswith('$'):
            val = int(val_str[1:], 16)
        elif val_str.startswith('0x'):
            val = int(val_str[2:], 16)
        else:
            val = int(val_str)
        
        if val > self.config['mask']:
            raise ValueError(f"Value '{val_str}' (0x{val:X}) exceeds {self.target} max limit of 0x{self.config['mask']:X}")
        return val

    def assemble(self, source_text):
        lines = source_text.splitlines()
        cleaned_tokens = []
        pc = 0

        # --- PASS 1: Symbol Resolution & Pseudo-Instruction Expansion ---
        for line in lines:
            line = line.split(';')[0].strip()
            if not line:
                continue

            if ':' in line:
                label, rest = line.split(':', 1)
                self.symbol_table[label.strip()] = pc
                line = rest.strip()
                if not line:
                    continue

            tokens = re.split(r'[\s,]+', line)
            mnemonic = tokens[0].upper()

            if mnemonic == 'LI':
                val = self.parse_number(tokens[2].replace('#', ''))
                if val not in self.literal_pool:
                    self.literal_pool[val] = self.literal_next_offset
                    self.literal_next_offset += 1
                    if self.literal_next_offset > self.config['literal_max']:
                        raise MemoryError(f"Literal Pool Overflow in {self.target} Data Page!")
                
                lit_offset = self.literal_pool[val]
                cleaned_tokens.append(('LOAD', [f"${lit_offset:02X}"], pc))
                pc += 2
            else:
                cleaned_tokens.append((mnemonic, tokens[1:], pc))
                pc += 2

            if pc > self.config['page_size']:
                raise MemoryError(f"Program exceeds maximum single-page size for {self.target} ({self.config['page_size']} words)")

        # --- PASS 2: Code Generation ---
        binary_image = bytearray(self.config['page_size'])

        for item in cleaned_tokens:
            mnemonic, args, pc = item
            opcode = OPCODES[mnemonic]
            operand = 0

            if mnemonic in ['NOP', 'RET', 'HLT']:
                operand = 0x00

            elif mnemonic == 'MOV':
                dst = REG_MAP[args[0].upper()]
                src = REG_MAP[args[1].upper()]
                operand = (dst << 2) | src

            elif mnemonic in ['PUSH', 'POP']:
                operand = REG_MAP[args[0].upper()]

            elif mnemonic in ['LOAD', 'STORE']:
                arg = args[0].upper()
                if arg == '[D]':
                    operand = self.config['mask']
                elif arg in self.symbol_table:
                    operand = self.symbol_table[arg]
                else:
                    operand = self.parse_number(arg)

            elif mnemonic in ['JMP', 'JZ', 'JC', 'CALL', 'EXEC']:
                target = args[0]
                if target in self.symbol_table:
                    operand = self.symbol_table[target]
                else:
                    operand = self.parse_number(target)

            elif mnemonic == 'ALU':
                operand = ALU_OPS[args[0].upper()]

            elif mnemonic == 'IO':
                port = self.parse_number(args[0])
                direction = 1 if args[1].upper() == 'OUT' else 0
                operand = (direction << 3) | (port & 0x07)

            binary_image[pc] = opcode & 0x0F
            binary_image[pc + 1] = operand & self.config['mask']

        literal_init_bytes = {offset: val for val, offset in self.literal_pool.items()}
        return bytes(binary_image), literal_init_bytes

def main():
    parser = argparse.ArgumentParser(description="μ-Core Assembler (Supports μ4 and μ8)")
    parser.add_argument("source", help="Path to assembly source file")
    parser.add_argument("-o", "--output", help="Output binary path")
    parser.add_argument("-t", "--target", choices=['mu4', 'mu8'], default='mu8', help="Target hardware architecture (default: mu8)")

    args = parser.parse_args()
    out_path = args.output if args.output else os.path.splitext(args.source)[0] + f"_{args.target}.bin"

    with open(args.source, 'r') as f:
        src_text = f.read()

    asm = MicroCoreAssembler(target=args.target)
    code_bin, lit_bytes = asm.assemble(src_text)

    with open(out_path, 'wb') as f:
        f.write(code_bin)

    print(f"Successfully assembled for [{args.target.upper()}]: {args.source} -> {out_path}")
    print("\n=== ASSIGNED SYMBOL TABLE ===")
    for label, addr in asm.symbol_table.items():
        print(f"  {label:<12} -> 0x{addr:02X}")

    if lit_bytes:
        print(f"\n=== GENERATED LITERAL DATA POOL ({args.target.upper()}) ===")
        for offset, val in lit_bytes.items():
            print(f"  Data RAM [0x{offset:02X}] = 0x{val:02X} ({val})")

if __name__ == '__main__':
    main()
