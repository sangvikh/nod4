# NOD-4 Microprocessor

> A 4-bit cumulative discrete-NMOS microprocessor architecture with an 8-bit unified address space, dual-nibble instruction fetch, and hardware-managed control and data pointers.

## Overview

NOD-4 is a compact microprocessor design intended for implementation from discrete logic, pass-transistor NMOS devices, passive pull-ups, universal base cards, and a shared master backplane.

The architecture combines a 4-bit datapath with 8-bit pointers and a six-step microcycle. Its design emphasizes simple physical construction, deterministic timing, and direct visibility of processor state on the hardware bus.

## Key Features

- 4-bit cumulative ALU and register datapath
- 8-bit unified address space assembled from two 4-bit nibbles
- Sequential dual-nibble fetch:
  - `T0`: opcode nibble
  - `T1`: operand nibble
- Six-step, 0-indexed microcycle from `T0` through `T5`
- Separate control-target and data-memory pointers
- Dedicated 16-nibble ascending-empty hardware return stack
- Two register banks selected through the operand nibble
- Conditional skip instructions with zero-overhead flag branching
- Hardware interrupt request, acknowledge, vectoring, and return protocol
- 32-pin master backplane for power, timing, flags, memory, address, opcode, and operand signals
- Active-low discrete NMOS control signaling

## Architecture at a Glance

| Component | Width | Role |
| --- | ---: | --- |
| General register bank | 4 × 4-bit | `RegA`–`RegD`, including control and data pointer nibbles |
| System register bank | 4 × 4-bit | Memory port, stack port, stack pointer, and flags |
| Control target pointer | 8-bit | `RegA:RegB` / `CPH:CPL` for jumps and calls |
| Data-memory pointer | 8-bit | `RegC:RegD` / `DPH:DPL` for external RAM access |
| Hardware stack | 16 nibbles | Return-address storage, independent of external RAM |
| Instruction format | 2 nibbles | Opcode followed by operand |
| Microcycle | 6 steps | Fetch, execute, writeback, and reset timing |

## Register Banks

### General Bank (`SYS = 0`)

| Index | Register | Alias | Function |
| --- | --- | --- | --- |
| `00` | `RegA` | `CPH` | Control pointer high nibble / ALU target |
| `01` | `RegB` | `CPL` | Control pointer low nibble |
| `10` | `RegC` | `DPH` | Data pointer high nibble |
| `11` | `RegD` | `DPL` | Data pointer low nibble |

### System Bank (`SYS = 1`)

| Index | Register | Function |
| --- | --- | --- |
| `00` | `MEM` | Indirect access to `RAM[RegC:RegD]` |
| `01` | `STACK` | Hardware stack push/pop port |
| `10` | `SP` | 4-bit stack pointer |
| `11` | `RegFLAGS` | `{CF, ZF, IE, UF}` status register |

## Instruction Encoding

NOD-4 fetches one opcode nibble and one operand nibble per instruction.

```text
Opcode:  [ IMM | ALU_EN | dst1 | dst0 ]
Operand: [ SYS | ADD/SUB or Unary | EXT | IMM1/SubOp ]
```

The opcode selects one of four quadrants:

| Quadrant | Opcode | Purpose |
| --- | --- | --- |
| Q0 | `00_dd` | Register moves and diagonal control escapes |
| Q1 | `01_dd` | Register-to-register binary ALU operations |
| Q2 | `10_dd` | Load immediate |
| Q3 | `11_dd` | Immediate ALU, carry operations, unary and shift operations |

## Instruction Set Summary

### Data Movement and Control

`MOV`, `LDI`, `NOP`, `SKP`, `GETPC`, `SRESET`, `HALT`

### Conditional Skips

`SZ`, `SNZ`, `SC`, `SNC`

These instructions evaluate flags during the operand phase and either advance the program counter or reset the sequencer early.

### Arithmetic and Logic

`ADD`, `SUB`, `XOR`, `AND`, `ADC`, `ADDI`, `SBB`, `SUBI`, `NOT`, `CLR`

### Shifts and Control Transfer

`SHR`, `RCR`, `JU`, `CALL`, `RET`, `RETK`, `RETI`, `PUSHPC`, `SWI`

## Timing Model

Each instruction progresses through a six-step microcycle:

| Step | Primary activity |
| --- | --- |
| `T0` | Fetch opcode into the instruction register |
| `T1` | Fetch operand into the instruction register |
| `T2` | Phase 1, step 1: source/destination read, latch, or stack action |
| `T3` | Phase 1, step 2: second nibble action or conditional decision |
| `T4` | Phase 2, step 1: writeback, vectoring, or flag update |
| `T5` | Phase 2, step 2 and asynchronous sequencer reset |

The design uses level-sensitive writes gated by `CLK LOW`. Transparent latch contents become frozen on the rising clock edge, providing a defined data setup and latch window.

## Stack Behavior

The return stack uses an ascending-empty convention:

- Push writes to `STACK[SP]`, then increments `SP`.
- Pop reads from `STACK[SP - 1]`, then decrements `SP`.
- A two-nibble address adjustment consumes two micro-steps.
- `RETK` restores the stack pointer after reading a return address.

This asymmetric decode avoids an additional pre-decrement delay during stack reads.

## Flags and Branching

`RegFLAGS` contains four status bits:

| Bit | Flag | Meaning |
| ---: | --- | --- |
| 3 | `CF` | Carry |
| 2 | `ZF` | Zero |
| 1 | `IE` | Interrupt enable |
| 0 | `UF` | User flag |

`SHR RegFLAGS` and `RCR RegFLAGS` eject the user flag into carry. The following `SC` or `SNC` instruction can then conditionally skip in one cycle, enabling compact flag-driven control flow.

## Interrupt Protocol

The hardware interrupt interface uses two active-low signals:

- `~IRQ`: peripheral request input
- `~IRQ_ACK`: CPU acknowledgement output

When interrupts are enabled, the processor isolates the instruction bus, preserves the return program counter, pushes the return address, emits an acknowledgement pulse, clears `IE`, and loads the external interrupt vector. `RETI` restores the return address and re-enables interrupts.

## Hardware Interface

The 32-pin master backplane carries:

- Power and clock
- Halt and interrupt control
- Carry, zero, interrupt-enable, and user flags
- Memory output-enable and write-enable
- 4-bit bidirectional data bus
- 8-bit address bus
- 4-bit opcode and operand rails

The logic standard is active-low NMOS signaling: a pulled-up 5 V level represents inactive logic, while an NMOS pull-down to 0 V asserts the active state.

## Repository Guide

The full architecture and system specification is available in:

- [`nod-4-microprocessor-architecture.md`](nod-4-microprocessor-architecture.md)

That document contains the complete register maps, pinout, timing diagrams, quadrant decode tables, instruction timing, stack sequencing, and interrupt handshake details.

## Design Status

This repository documents the NOD-4 architecture and its intended discrete-logic implementation. Hardware realization, simulation, validation, and board-level verification can be added as the project develops.

## License

No license has been specified yet.
