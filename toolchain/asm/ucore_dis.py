#!/usr/bin/env python3
"""
μ-Core Parameterized Disassembler (Conforms to ISA v1.1.0 & ABI v1.1.0)
Decodes μ-Core binary images into human-readable assembly instructions.
"""

import sys
import argparse

OPCODES = {
    0x0: 'NOP',   0x1: 'MOV',   0x2: 'LOAD',  0x3: 'STORE',
    0x4: 'ALU',   0x5: 'JMP',   0x6: 'JZ',    0x7: 'JC',
    0x8: 'CALL',  0x9: 'RET',   0xA: 'PUSH',  0xB: 'POP',
    0xC: 'IO',    0xD: 'RSVD1', 0xE: 'RSVD2', 0xF: 'HLT'
}

ALU_OPS = {
    0x0: 'ADD', 0x1: 'SUB', 0x2: 'ADC', 0x3: 'SBB',
    0x4: 'AND', 0x5: 'OR',  0x6: 'XOR', 0x7: 'NOT',
    0x8: 'INC', 0x9: 'DEC', 0xA: 'SHL', 0xB: 'SHR',
    0xC: 'ROL', 0xD: 'ROR', 0xE: 'CMP', 0xF: 'TST'
}

REG_LOOKUP = {0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'FLAGS'}

def decode_instruction(pc, op_byte, operand_byte):
    opcode = op_byte & 0x0F
    mnemonic = OPCODES.get(opcode, 'UNKNOWN')
    args_str = ""

    if mnemonic in ['NOP', 'RET', 'RSVD1', 'RSVD2', 'HLT']:
        args_str = ""

    elif mnemonic == 'MOV':
        dst_id = operand_byte & 0x03
        src_id = (operand_byte >> 2) & 0x03
        dst_reg = REG_LOOKUP.get(dst_id, f"R{dst_id}")
        src_reg = REG_LOOKUP.get(src_id, f"R{src_id}")
        args_str = f"{dst_reg}, {src_reg}"

    elif mnemonic in ['PUSH', 'POP']:
        target_id = operand_byte & 0x07
        reg_name = REG_LOOKUP.get(target_id, f"RSVD_{target_id}")
        args_str = reg_name

    elif mnemonic in ['LOAD', 'STORE']:
        if operand_byte == 0xFF:
            args_str = "[D]"
        else:
            args_str = f"${operand_byte:02X}"

    elif mnemonic in ['JMP', 'JZ', 'JC']:
        if operand_byte == 0xFF:
            args_str = "[D]"
        else:
            args_str = f"${operand_byte:02X}"

    elif mnemonic == 'CALL':
        args_str = f"${operand_byte:02X}"

    elif mnemonic == 'ALU':
        sub_op = operand_byte & 0x0F
        alu_name = ALU_OPS.get(sub_op, f"0x{sub_op:X}")
        args_str = alu_name

    elif mnemonic == 'IO':
        port = operand_byte & 0x07
        direction = "OUT" if ((operand_byte >> 3) & 1) else "IN"
        args_str = f"{port}, {direction}"

    formatted_asm = f"{mnemonic:<6} {args_str}".strip()
    return formatted_asm

def main():
    parser = argparse.ArgumentParser(description="μ-Core Binary Disassembler (ISA v1.1.0 & ABI v1.1.0)")
    parser.add_argument("binary", help="Path to binary instruction image (.bin)")
    parser.add_argument("-b", "--base", type=lambda x: int(x, 0), default=0, help="Base PC address offset (default: 0)")

    args = parser.parse_args()

    with open(args.binary, "rb") as f:
        data = f.read()

    print(f"=== DISASSEMBLY: {args.binary} ({len(data)} bytes) ===")
    print(f"{'OFFSET':<8} {'HEX':<8} {'INSTRUCTION'}")
    print("-" * 35)

    for i in range(0, len(data), 2):
        if i + 1 >= len(data):
            break

        pc = args.base + i
        op = data[i]
        operand = data[i + 1]

        # Stop printing long trailing runs of zeroes (uninitialized page bytes)
        if op == 0x00 and operand == 0x00 and i >= 32 and all(b == 0 for b in data[i:]):
            print(f"{'...':<8} {'':<8} [Uninitialized Page Padding]")
            break

        disasm = decode_instruction(pc, op, operand)
        hex_str = f"{op:02X} {operand:02X}"
        print(f"0x{pc:02X}:     {hex_str:<8} {disasm}")

if __name__ == "__main__":
    main()
