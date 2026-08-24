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
                 │ Identity  │ │ Timestep  │ │ Pass-FET  │
                 │  Match    │ │ Isolated  │ │  ~27 FETs │
                 └───────────┘ └───────────┘ └───────────┘

```

The **NOD-4** is a modular, discrete NMOS 4-bit processor built around a core principle of hardware efficiency: **Active-LOW open-drain physics at the edges, minimal overrides at the center.**

Rather than scattering instruction decoders across every circuit board, NOD-4 delegates datapath operations to **opcode-ignorant cards**. Storage and latching cards perform basic 3-bit slot identity matching (`Card_ID == SRC` or `DST`), remaining completely blind to the actual instruction being executed. Exceptional instruction behavior (`LDI`, `LD`/`ST`, conditional branches, `UNARY`) is resolved exclusively by a central pass-FET exception handler containing roughly **27 transistors**.

---

## Architectural Principles & Physics

* **Active-LOW Open-Drain Bus Physics:** Every backplane trace defaults to $+5\text{V}$ ($V_{CC}$) via pull-up resistors. Cards interact with the backplane strictly by pulling lines to $GND$. Tri-stating is free—disabling a card driver simply means turning off its pull-down N-FETs.
* **Opcode-Ignorant Datapath Modules:** Datapath cards contain zero instruction-decoding logic. Register modules only match their hardwired 3-bit address against `SRC[2:0]` to drive `BUS[3:0]`, or `DST[2:0]` to latch data on $\overline{CLK}$.
* **Zero-Transistor Address Bus Ownership:** Address bus multiplexing requires no gates. Timestep signals ($T_0\text{--}T_1$ for Fetch; $T_2\text{--}T_3$ for Execution) and hardwired slot pinouts dictate whether $PC$ or Regs $C:D$ drive `ADDR_H:ADDR_L`.
* **Hardware $ALU\_ENABLE$ ($OP[3]$):** Instructions with $OP[3] = 0$ (`0x0`–`0x7`) freeze ALU flags and tri-state ALU drivers automatically, preserving flag state across data transfers without extra control logic.
* **Destructive Write Prevention (`111` NULL):** Instructions that produce no register writeback (`CMP`, `ST`) direct `DEST_ADDR` to `111`. No card responds, letting data on `BUS[3:0]` dissipate harmlessly.
* **Memory-Safe $0x00 = \text{NOP}$:** Opcode `0x00` decodes naturally to `MOV A, A`. Uninitialized or erased memory blocks ($0x00$) execute safely as non-destructive identity moves.

---

## System Module Matrix

| Module Type | Cards | Internal Logic | Decodes / Responds To |
| --- | --- | --- | --- |
| **Register Modules** | $A, B, C, D$ | 3-bit identity comparator | Matches `SRC[2:0]` (to drive `BUS`) & `DST[2:0]` (to latch `BUS`). Zero opcode awareness. |
| **Instruction Regs** | $IR_{OP}, IR_{OPER}$ | Dedicated latch drivers | Direct latching on $T_0 \land \overline{CLK}$ ($IR_{OP}$) and $T_1 \land \overline{CLK}$ ($IR_{OPER}$). |
| **Program Counter** | $PC_H, PC_L$ | Discrete 4-bit ripple-incrementer | Drives address bus on $T_0 \lor T_1$; isolated during $T_2 \lor T_3$. Direct branch override on $\overline{LOAD\_PC}$. |
| **Central Control** | Central Override | ~27 Pass-FET Matrix | Opcode overrides (`LDI`, `CMP`, `ST`, `BRANCH`), subop swizzling (`UNARY`), and active-LOW memory enables. |

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

## ISA Quadrant Summary

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

The `toolchain/` directory provides tools for assembling NOD-4 assembly source code into binary ROM images and running cycle-accurate hardware simulations.

### Assembling a Program

```bash
python3 toolchain/hasm.py examples/pointer_demo.asm -o build/pointer_demo.bin

```

### Running the Bus-Level Simulator

```bash
python3 toolchain/nod4_sim.py build/pointer_demo.bin --trace

```

---

## License

This project is licensed under the **MIT License**. See `LICENSE` for details.
