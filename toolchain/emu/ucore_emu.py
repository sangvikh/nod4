#!/usr/bin/env python3
"""
μ-Core Interactive Reference Emulator (Conforms to ISA v1.1.0 & ABI v1.1.0)
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

        # Special Control Registers
        self.PC = 0           # Program Counter (8-bit)
        self.PR = 0           # Page Register (8-bit)
        self.SP = 0           # Stack Pointer (0..15)
        self.D_stack = 0      # Logical Stack Depth Counter (0..16)
        self.ZF = False       # Zero Flag
        self.CF = False       # Carry Flag
        self.halted = False   # CPU_State (HALTED / NORMAL)

        # Namespaces
        self.code_pages = {i: bytearray(256) for i in range(256)}  # Instruction Space
        self.data_ram = {i: bytearray(256) for i in range(256)}    # Data Space
        self.stack = [0] * 16                                      # Hardware Stack Array (N=16)
        self.io_ports = [0] * 8                                    # 8 Peripheral I/O ports

    def reset(self):
        """Hardware RESET Signal"""
        self.PR = 0
        self.PC = 0
        self.SP = 0
        self.D_stack = 0
        self.halted = False

    def push_stack(self, val):
        self.stack[self.SP] = val & 0xFF
        self.SP = (self.SP + 1) % 16
        if self.D_stack < 16:
            self.D_stack += 1

    def pop_raw(self):
        """Unified Stack Pop Primitive (used by POP and RET)"""
        if self.D_stack > 0:
            self.SP = (self.SP - 1 + 16) % 16
            self.D_stack -= 1
            return self.stack[self.SP]
        return 0  # Underflow returns 0; SP and D_stack remain 0

    def step(self):
        if self.halted:
            return

        if self.PC % 2 != 0:
            raise RuntimeError(f"Architecturally Invalid Operation: Odd PC target ({self.PC})")

        # Phase T0 & T1: Instruction Fetch
        code = self.code_pages[self.PR]
        opcode_su = code[self.PC] & 0x0F
        operand_su = code[self.PC + 1]

        # Evaluate Canonical Sequential PC
        pc_raw = self.PC + 2
        next_pc = pc_raw & 0xFF
        next_pr = (self.PR + 1) & 0xFF if pc_raw >= 256 else self.PR

        # Phase T2 & T3: Execution & Atomic Commit
        if opcode_su == 0x0: # NOP
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x1: # MOV
            src_id = (operand_su >> 2) & 0x03
            dst_id = operand_su & 0x03
            vals = [self.A, self.B, self.C, self.D]
            src_val = vals[src_id]
            if dst_id == 0: self.A = src_val
            elif dst_id == 1: self.B = src_val
            elif dst_id == 2: self.C = src_val
            elif dst_id == 3: self.D = src_val
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x2: # LOAD
            addr = self.D if operand_su == 0xFF else operand_su
            self.A = self.data_ram[self.C][addr]
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x3: # STORE
            addr = self.D if operand_su == 0xFF else operand_su
            self.data_ram[self.C][addr] = self.A
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x4: # ALU
            sub_op = operand_su & 0x0F
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
                self.CF = (a_orig >= b) # No-borrow convention

            elif sub_op == 0x2: # ADC
                carry_in = 1 if self.CF else 0
                res = a_orig + b + carry_in
                self.A = res & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (res >= 256)

            elif sub_op == 0x3: # SBB
                subtrahend = b + (0 if self.CF else 1)
                res = a_orig - subtrahend
                self.A = res & 0xFF
                self.ZF = (self.A == 0)
                self.CF = (a_orig >= subtrahend)

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

            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x5: # JMP
            if operand_su == 0xFF:
                self.PR, self.PC = self.C, self.D
            else:
                self.PC, self.PR = operand_su, self.PR

        elif opcode_su == 0x6: # JZ
            if self.ZF:
                if operand_su == 0xFF: self.PR, self.PC = self.C, self.D
                else: self.PC, self.PR = operand_su, self.PR
            else: self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x7: # JC
            if self.CF:
                if operand_su == 0xFF: self.PR, self.PC = self.C, self.D
                else: self.PC, self.PR = operand_su, self.PR
            else: self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0x8: # CALL
            if next_pr != self.PR:
                raise RuntimeError("Architecturally Invalid Operation: CALL across page boundary")
            self.push_stack(next_pc)
            self.PC, self.PR = operand_su, self.PR

        elif opcode_su == 0x9: # RET
            self.PC = self.pop_raw()
            # PR remains unchanged (page-local return)

        elif opcode_su == 0xA: # PUSH
            target = operand_su & 0x07
            if target < 5:
                vals = [self.A, self.B, self.C, self.D, (1 if self.ZF else 0) | ((1 if self.CF else 0) << 1)]
                self.push_stack(vals[target])
            # Target IDs 5, 6, 7 act strictly as NOP (no state change)
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0xB: # POP
            target = operand_su & 0x07
            if target < 5:
                val = self.pop_raw()
                if target == 0: self.A = val
                elif target == 1: self.B = val
                elif target == 2: self.C = val
                elif target == 3: self.D = val
                elif target == 4:
                    self.ZF = bool(val & 1)
                    self.CF = bool((val >> 1) & 1)
            # Target IDs 5, 6, 7 act strictly as NOP (no stack pop, no pointer change)
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0xC: # IO
            port = operand_su & 0x07
            direction = (operand_su >> 3) & 1
            if direction == 0: # IN
                self.A = self.io_ports[port]
            else: # OUT
                self.io_ports[port] = self.A
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su in (0xD, 0xE): # RSVD1, RSVD2 (Strict NOPs)
            self.PC, self.PR = next_pc, next_pr

        elif opcode_su == 0xF: # HLT
            self.halted = True

    def dump_state(self):
        flags = f"ZF={'1' if self.ZF else '0'} CF={'1' if self.CF else '0'}"
        status = "HALTED" if self.halted else "RUNNING"
        
        # Format active stack items for easy inspection
        active_stack = []
        for idx in range(self.D_stack):
            stk_idx = (self.SP - 1 - idx + 16) % 16
            active_stack.append(f"0x{self.stack[stk_idx]:02X}")
        stk_str = f"[{', '.join(active_stack)}]" if active_stack else "[]"
        
        print(f"[{status}] PR:0x{self.PR:02X} PC:0x{self.PC:02X} | A:0x{self.A:02X} B:0x{self.B:02X} C:0x{self.C:02X} D:0x{self.D:02X} | {flags} | SP:{self.SP} Depth:{self.D_stack} Stack:{stk_str}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ucore_emu.py <code.bin[:page_id]> [code2.bin:page_id ...]")
        print("Example: python3 ucore_emu.py main.bin worker.bin:1")
        sys.exit(1)

    cpu = MicroCoreCPU()

    for arg in sys.argv[1:]:
        if ':' in arg and not os.path.exists(arg):
            bin_path, page_str = arg.rsplit(':', 1)
            page_id = int(page_str, 0)
        else:
            bin_path = arg
            page_id = 0

        with open(bin_path, 'rb') as f:
            data = f.read()
            cpu.code_pages[page_id][:len(data)] = data
            print(f"Loaded {len(data)} bytes into Instruction Page 0x{page_id:02X} ({bin_path})")

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
