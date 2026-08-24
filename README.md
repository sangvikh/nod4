---

# NOD-4 (NMOS Open-Drain 4-Bit Core)

```text
                  ┌──────────────────────────────────────────────┐
                  │   NOD-4 DISCRETE NMOS ARCHITECTURE ENGINE    │
                  │  Active-LOW • Open-Drain • Central Override  │
                  └──────────────────────┬───────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   │        37-Pin System Backplane Bus        │
                   └───┬─────────────┬─────────────┬───────────┘
                       │             │             │
                 ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
                 │ Reg Cards │ │ PC Cards  │ │ Central   │
                 │  (A-D)    │ │ (PC_H/L)  │ │ Control   │
                 │ "Dumb"    │ │ "Dumb"    │ │ ~27 FETs  │
                 └───────────┘ └───────────┘ └───────────┘

```

The **NOD-4** is a modular, discrete NMOS 4-bit processor built on a minimalist architectural principle: **Active-LOW open-drain physics at the edges, minimal overrides at the center.**

Rather than duplicating instruction-decoding logic across multiple circuit boards, NOD-4 isolates all storage and datapath operations on completely ignorant "dumb" latch cards. Exceptional instruction behavior (`LDI`, `LD`/`ST`, conditional branches, `UNARY`) is handled exclusively by a central pass-FET exception handler containing roughly **27 transistors**.

---

## Key Architectural Invariants

* **Active-LOW Open-Drain Bus:** Every backplane trace defaults to $+5\text{V}$ ($V_{CC}$) via pull-up resistors. Cards interact with the system strictly by pulling traces to $GND$. Tri-stating requires zero active drivers—disabling a card simply means turning off its pull-down N-FETs.
* **0-Transistor Address Bus Ownership:** Address bus routing requires no multiplexers. Timestep signals ($T_0\text{--}T_1$ for Fetch; $T_2\text{--}T_3$ for Execution) and hardwired slot pinouts dictate whether $PC$ or Regs $C:D$ drive `ADDR_H:ADDR_L`.
* **Hardware $ALU\_ENABLE$ ($OP[3]$):** Instructions with $OP[3] = 0$ (`0x0`–`0x7`) freeze ALU flags and tri-state ALU drivers automatically, preserving flag state across data transfers without extra control logic.
* **Destructive Write Prevention (`111` NULL):** Instructions that generate no register writeback (`CMP`, `ST`) override `DEST_ADDR` to `111`. No card responds, allowing data on `BUS[3:0]` to dissipate safely.
* **Memory-Safe $0x00 = \text{NOP}$:** Opcode `0x00` decodes naturally to `MOV A, A`. Uninitialized or erased memory ranges ($0x00$) execute safely as non-destructive identity moves.

---

## Engine Specifications

| Parameter | Specification |
| --- | --- |
| **Datapath Width** | 4-bit parallel data bus (`BUS[3:0]`) |
| **Address Space** | 8-bit pointer address space (`ADDR_H:ADDR_L`, 256 nibbles) |
| **Instruction Set** | 16 opcodes split into 4 structural quadrants |
| **Clocking / Execution** | Single $CLK$ driving a 4-step 1-hot ring counter ($T_0\text{--}T_3$) |
| **Backplane Interconnect** | 37-pin edge connector matrix |
| **Logic Family** | Discrete NMOS / Pass-Transistor Logic (PTL) |

---

## ISA Quick Reference

| Opcode Quadrant | Operations | Special Behavior |
| --- | --- | --- |
| **`00xx` (`0x0`–`0x3`)** | `MOV`, `LD`, `ST`, `BRANCH` | Data movement & flow control. Flags remain frozen. |
| **`01xx` (`0x4`–`0x7`)** | `LDI A`, `LDI B`, `LDI C`, `LDI D` | Direct bitmapped destination targeting via $OP[1:0]$. |
| **`10xx` (`0x8`–`0xB`)** | `ADD`, `SUB`, `AND`, `OR` | Direct $OP[1:0] \to F_1, F_0$ ALU function line mapping. |
| **`11xx` (`0xC`–`0xF`)** | `XOR`, `UNARY`, `NOT`, `CMP` | Extended ALU. Opcode `0xD` swizzles subops (`INC/DEC/INCC/DECC`). |

*For complete electrical timing, signal equations, and backplane pinouts, see [`docs/ISA_Manifest.md`](https://www.google.com/search?q=docs/ISA_Manifest.md).*

---

## Repository Structure

```text
.
├── build/                 # Generated binary artifacts, ROM dumps, and build logs
├── docs/                  # Architectural documentation and hardware specifications
│   └── ISA_Manifest.md    # Master architectural manifesto and signal equations
├── examples/              # Sample NOD-4 assembly programs and test vectors
├── toolchain/             # Assembler, simulator, and build tools
├── LICENSE                # Open-source hardware license
└── README.md              # System overview

```

---

## Toolchain & Usage

The `toolchain/` directory contains tools for assembling NOD-4 assembly programs into binary ROM images and running cycle-accurate software simulations.

### Assembling a Program

```bash
python3 toolchain/hasm.py examples/pointer_demo.asm -o build/pointer_demo.bin

```

### Running the Simulator

```bash
python3 toolchain/nod4_sim.py build/pointer_demo.bin --trace

```

---

## License

This project is released under the **MIT License**. See `LICENSE` for details.
