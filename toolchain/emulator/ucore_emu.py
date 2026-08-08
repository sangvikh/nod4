#!/usr/bin/env python3
"""
μ-Core Interactive Reference Emulator (Conforms to ISA v1.0.0 & ABI v1.0.0)
Simulates a μ-Core CPU with full instruction execution, hardware stack, and CLI debugger.
"""

import sys
import os

class MicroCoreCPU:
    def __init__(self):
        # Programmer Registers (8-bit)
        self.A = 0
        self.B = 0
        self.C = 0
        self.D = 0

        # Special Registers
        self.PC = 0           # Program Counter (8-bit)
        self.PR = 0           # Page Register (8-bit)
        self.SP = 0           # Hardware Stack Pointer (0..15)
        self.D_stack = 0      # Logical Stack Depth (0..16)
        self.ZF = False       # Zero Flag
        self.CF = False       # Carry Flag
        self.halted = False   # HLT state

        # Memory Spaces
        self.code_pages = {i: bytearray(256) for i in range(256)}  # 256 pages x 256 bytes
        self.data_ram = {i: bytearray(256) for i in range(256)}    # 256 pages x 256 bytes
        self.stack = [0] * 16                                      # 16-entry Hardware Stack
        self.io_ports = [0] * 8                                    # 8 Peripheral I/O ports

    def reset(self):
        self.PR = 0
        self.PC = 0
        self.SP = 0
        self.D_stack = 0
        self.ZF = False
        self.CF = False
        self.halted = False

    def push_stack(self, val):
        self.stack[self.SP] = val & 0xFF
        self.SP = (self.SP + 1) % 16
        if self.D_stack < 16:
            self.D_stack += 1

    def pop_stack(self):
        if self.D_stack == 0:
            return 0  # Underflow returns 0
        self.SP = (self.SP - 1 + 16) % 16
        self.D_stack -= 1
        return self.stack[self.SP]

    def step(self):
        if self.halted:
            return

        code = self.code_pages[self.PR]
        opcode = code[self.PC] & 0x0F
        operand = code[self.PC + 1]
        next_pc = (self.PC + 2) & 0xFF

        # -------------------------------------------------------------
        # INSTRUCTION DECODER
        # -------------------------------------------------------------
        if opcode == 0x0: # NOP
            self.PC = next_pc

        elif opcode == 0x1: # MOV
            src_id = operand & 0x03
            dst_id = (operand >> 2) & 0x03
            vals = [self.A, self.B, self.C, self.D]
            src_val = vals[src_id]
            if dst_id == 0: self.A = src_val
            elif dst_id == 1: self.B = src_val
            elif dst_id == 2: self.C = src_val
            elif dst_id == 3: self.D = src_val
            self.PC = next_pc

        elif opcode == 0x2: # LOAD
            addr = self.D if operand == 0xFF else operand
            self.A = self.data_ram[self.C][addr]
            self.PC = next_pc

        elif opcode == 0x3: # STORE
            addr = self.D if operand == 0xFF else operand
            self.data_ram[self.C][addr] = self.A
            self.PC = next_pc

        elif opcode == 0x4: # ALU
            sub_op = operand & 0x0F
            a_orig = self.A
            b = self.B

            if sub_op == 0x0: # ADD
                res = a_orig + b
                self.A = res & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (res >= 256)

            elif sub_op == 0x1: # SUB
                res = a_orig - b
                self.A = res & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (a_orig >= b) # No-borrow

            elif sub_op == 0x2: # ADC
                carry_in = 1 if self.CF else 0
                res = a_orig + b + carry_in
                self.A = res & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (res >= 256)

            elif sub_op == 0x3: # SBB
                borrow_in = 0 if self.CF else 1
                res = a_orig - b - borrow_in
                self.A = res & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (a_orig >= (b + borrow_in))

            elif sub_op == 0x4: # AND
                self.A = (a_orig & b) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0x5: # OR
                self.A = (a_orig | b) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0x6: # XOR
                self.A = (a_orig ^ b) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0x7: # NOT
                self.A = (~a_orig) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0x8: # INC (Preserves CF!)
                self.A = (a_orig + 1) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0x9: # DEC (Preserves CF!)
                self.A = (a_orig - 1) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0xA: # SHL
                old_msb = (a_orig >> 7) & 1
                self.A = (a_orig << 1) & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (old_msb == 1)

            elif sub_op == 0xB: # SHR
                old_lsb = a_orig & 1
                self.A = (a_orig >> 1) & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (old_lsb == 1)

            elif sub_op == 0xC: # ROL
                old_cf = 1 if self.CF else 0
                self.CF = bool((a_orig >> 7) & 1)
                self.A = ((a_orig << 1) | old_cf) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0xD: # ROR
                old_cf = 1 if self.CF else 0
                self.CF = bool(a_orig & 1)
                self.A = ((a_orig >> 1) | (old_cf << 7)) & 0xFF
                self.ZF = (self.A == 0)

            elif sub_op == 0xE: # CMP
                res = a_orig - b
                self.ZF = ((res & 0xFF) == 0)
                self.CF = (a_orig >= b)

            elif sub_op == 0xF: # TST
                self.ZF = (a_orig == 0)

            self.PC = next_pc

        elif opcode == 0x5: # JMP
            self.PC = operand

        elif opcode == 0x6: # JZ
            self.PC = operand if self.ZF else next_pc

        elif opcode == 0x7: # JC
            self.PC = operand if self.CF else next_pc

        elif opcode == 0x8: # CALL
            self.push_stack(next_pc)
            self.PC = operand

        elif opcode == 0x9: # RET
            self.PC = self.pop_stack()

        elif opcode == 0xA: # PUSH
            target = operand & 0x07
            if target == 0: val = self.A
            elif target == 1: val = self.B
            elif target == 2: val = self.C
            elif target == 3: val = self.D
            elif target == 4: val = (1 if self.ZF else 0) | ((1 if self.CF else 0) << 1)
            else: val = 0
            self.push_stack(val)
            self.PC = next_pc

        elif opcode == 0xB: # POP
            val = self.pop_stack()
            target = operand & 0x07
            if target == 0: self.A = val
            elif target == 1: self.B = val
            elif target == 2: self.C = val
            elif target == 3: self.D = val
            elif target == 4:
                self.ZF = bool(val & 1)
                self.CF = bool((val >> 1) & 1)
            self.PC = next_pc

        elif opcode == 0xC: # IO
            port = operand & 0x07
            direction = (operand >> 3) & 1
            if direction == 0: # IN
                self.A = self.io_ports[port]
            else: # OUT
                self.io_ports[port] = self.A
            self.PC = next_pc

        elif opcode == 0xD: # EXEC
            self.PR = operand
            self.PC = 0x00

        elif opcode == 0xE: # RSVD (NOP)
            self.PC = next_pc

        elif opcode == 0xF: # HLT
            self.halted = True

    def dump_state(self):
        flags = f"ZF={'1' if self.ZF else '0'} CF={'1' if self.CF else '0'}"
        status = "HALTED" if self.halted else "RUNNING"
        print(f"[{status}] PR:0x{self.PR:02X} PC:0x{self.PC:02X} | A:0x{self.A:02X} B:0x{self.B:02X} C:0x{self.C:02X} D:0x{self.D:02X} | {flags} | SP:{self.SP} Depth:{self.D_stack}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ucore_emu.py <code.bin> [page_id]")
        sys.exit(1)

    bin_path = sys.argv[1]
    page_id = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    cpu = MicroCoreCPU()
    
    with open(bin_path, 'rb') as f:
        data = f.read()
        cpu.code_pages[page_id][:len(data)] = data

    print(f"Loaded {len(data)} bytes into Instruction Page 0x{page_id:02X}")
    print("Commands: [s]tep, [c]ontinue, [r]eset, [d]ump RAM, [q]uit")

    while True:
        cpu.dump_state()
        cmd = input("> ").strip().lower()
        if cmd == 's' or cmd == '':
            cpu.step()
        elif cmd == 'c':
            while not cpu.halted:
                cpu.step()
        elif cmd == 'r':
            cpu.reset()
        elif cmd == 'd':
            print(f"--- Data RAM Page C=0x{cpu.C:02X} (First 32 Bytes) ---")
            for i in range(0, 32, 8):
                chunk = cpu.data_ram[cpu.C][i:i+8]
                print(f"  [{i:02X}..{i+7:02X}]: " + " ".join(f"{b:02X}" for b in chunk))
        elif cmd == 'q':
            break

if __name__ == '__main__':
    main()
