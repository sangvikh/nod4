# NOD-4 Microprocessor

> A 4-bit cumulative discrete-NMOS microprocessor architecture with an 8-bit unified address space, dual-nibble instruction fetch, and hardware-managed control and data pointers.

## Overview

NOD-4 is a compact microprocessor design intended for implementation from discrete logic, pass-transistor NMOS devices, passive pull-ups, universal base cards, and a shared master backplane.

The architecture combines a 4-bit datapath with 8-bit pointers and a six-step microcycle. Its design emphasizes simple physical construction, deterministic timing, and direct visibility of processor state on the hardware bus.

## Key Features

- 4-bit cumulative ALU and register datapath
- 8-bit unified address space addressing 256 4-bit nibbles
- Sequential dual-nibble fetch:
  - `T0`: opcode nibble
  - `T1`: operand nibble
- Six-step, 0-indexed microcycle from `T0` through `T5`
- Separate control-target and data-memory pointers
- Dedicated ascending-empty hardware return stack, typically up to 8 nibbles deep
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
| Hardware stack | Implementation-dependent | Return-address storage, independent of external RAM |
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
Operand: [ SYS | LOGIC/EXT | INV_B or Unary | CF/0 or Unary ]
```

`opr[3]` selects the system destination bank in Q1 and Q3. Q2 suppresses
that selection so all four operand bits remain available to `LDI`:

```text
SYS_DST = opr[3] AND NOT Q2
```

Q1 uses `RegA` as its implicit second operand. The Q1 operation bitmap is:

| `ALU_OP` | Operation |
| --- | --- |
| `000` | `ADD dst, A` |
| `001` | `ADC dst, A` |
| `010` | `SUB dst, A` |
| `011` | `SBB dst, A` |
| `100` | `XOR dst, A` |
| `101` | `OR dst, A` |
| `110` | `AND dst, A` |
| `111` | `ANDN dst, A` |

In Q3 arithmetic mode, the main decoder routes `opr[0]` to the ALU B-source
bus as a zero-extended one-bit operand. Q3 logic/EXT mode selects `NOT`,
`SHR`, `SHL`, or `CLR`. The ALU itself only latches the selected B-source
bus; immediate routing is handled by the main decoder.

| Quadrant | Opcode | Purpose |
| --- | --- | --- |
| Q0 | `00_dd` | Register moves and diagonal control escapes |
| Q1 | `01_dd` | Implicit-`RegA` binary ALU operations |
| Q2 | `10_dd` | Load immediate |
| Q3 | `11_dd` | Immediate ALU, carry operations, unary and shift operations |

## Instruction Set Summary

### Data Movement and Control

`MOV`, `LDI`, `NOP`, `SKP`, `GETPC`, `SRESET`, `HALT`

### Conditional Skips

`SZ`, `SNZ`, `SC`, `SNC`

These instructions evaluate flags during the operand phase and either advance the program counter or reset the sequencer early.

### Arithmetic and Logic

`ADD`, `ADC`, `SUB`, `SBB`, `XOR`, `OR`, `AND`, `ANDN`, `ADDI`, `SUBI`, `NOT`, `CLR`

### Shifts and Control Transfer

`SHL`, `SHR`, `JU`, `CALL`, `RET`, `RETK`, `RETI`, `PUSHPC`, `SWI`

## Timing Model

Each instruction progresses through a six-step microcycle:

| Step | Primary activity |
| --- | --- |
| `T0` | Fetch opcode into the instruction register |
| `T1` | Fetch operand into the instruction register |
| `T2` | Q0: latch selected source; ALU: latch selected B-source bus into Latch B; Q2: complete `LDI`; or first stack nibble |
| `T3` | ALU: latch `Dst` into Latch A and disable its decoder; or second stack nibble |
| `T4` | Phase 2, step 1: ALU writeback, flag-master update, or vector high nibble |
| `T5` | Phase 2, step 2: vector low nibble, final restore, and sequencer reset |

The design uses level-sensitive writes gated by `CLK LOW`. Transparent latch contents become frozen on the rising clock edge, providing a defined data setup and latch window.

## Stack Behavior

The return stack uses an ascending-empty convention:

- Push writes to `STACK[SP]`, then increments `SP`.
- Pop reads from `STACK[SP - 1]`, then decrements `SP`.
- A two-nibble address adjustment consumes two micro-steps.
- `RETK` restores the stack pointer after reading a return address.

The physical stack depth is an implementation choice. A practical implementation may use up to eight nibbles, with the unused or high stack-pointer bit available for underflow/overflow indication.

## Flags and Branching

`RegFLAGS` contains four status bits:

| Bit | Flag | Meaning |
| ---: | --- | --- |
| 3 | `CF` | Carry |
| 2 | `ZF` | Zero |
| 1 | `IE` | Interrupt enable |
| 0 | `UF` | User flag |

`SHR RegFLAGS` ejects the user flag (`UF`) into carry, while `SHL RegFLAGS`
ejects the most-significant flag bit (`CF`) into carry. The following `SC` or
`SNC` instruction can then conditionally skip in one cycle, enabling compact
flag-driven control flow.

`CF` and `ZF` are committed to the master flag latch during ALU writeback at `T4`. The slave flag latch becomes visible only after the writeback window, preventing flag feedback or race conditions during the same ALU operation.

## Interrupt Protocol

The hardware interrupt interface uses two active-low signals:

- `~IRQ`: peripheral request input
- `~IRQ_ACK`: CPU acknowledgement level

When `IE = 1` and no interrupt is active, the IRQ card asynchronously captures the request in its master latch. At the next `T0` boundary, the request transfers to the slave latch as `IRQ_ACTIVE`.

At `T0`, `IRQ_ACTIVE`:

1. inhibits the normal PC increment;
2. disables the instruction-register outputs, causing passive `NOP` decode;
3. clears `IE`;
4. causes the main decoder to enter the IRQ sequence.

The IRQ entry sequence then:

- `T2`: pushes `PCH` to the stack;
- `T3`: pushes `PCL` to the stack;
- `T4`: loads the external vector high nibble into `PCH`;
- `T5`: loads the external vector low nibble into `PCL`.

`IRQ_ACTIVE` drives the external active-low `~IRQ_ACK` line through an inverter. The acknowledgement remains asserted throughout IRQ entry and releases after `T5`, when the IRQ master/slave latch reset sequence completes.

`RETI` restores the return address and sets `IE`. Ordinary `RET` preserves `IE`. `SWI` does not modify `IE`, so it can be used either with interrupts enabled or as a polling/trap mechanism while interrupts are disabled.

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

- [`ISA_Manifest.md`](docs/ISA_Manifest.md)

That document contains the complete register maps, pinout, timing diagrams, quadrant decode tables, instruction timing, stack sequencing, and interrupt handshake details.

## Design Status

This repository documents the NOD-4 architecture and its intended discrete-logic implementation. Hardware realization, simulation, validation, and board-level verification can be added as the project develops.

## License

[`MIT License`](LICENSE)
