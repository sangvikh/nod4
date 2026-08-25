# NOD-4 Architectural Manifest & System Specification

The **NOD-4** is a discrete NMOS 4-bit processor built on an active-LOW open-drain backplane architecture. System control is divided between a central pass-FET exception matrix and opcode-ignorant modular peripheral cards.

This document serves as the master hardware and architectural specification for the NOD-4 engine, incorporating the **Centralized $\overline{\text{OE}} / \overline{\text{WE}}$ Backplane Routing**, **8-Slot Unified Addressing Matrix**, and **Extended Bus Selection Logic**.

---

## 1. Centralized Bus Control Model

Rather than placing 3-bit address comparators and decode gates on every circuit board, NOD-4 centralizes all slot address decoding onto the **Central Control Card**.

```text
               ┌──────────────────────────────────────────────┐
               │         CENTRAL CONTROL CARD                 │
               │  • 3-to-8 SRC Decoder  • $T_2/T_3$ Gating    │
               │  • 3-to-8 DST Decoder  • Pass-FET Exception  │
               └──────────────┬───────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         │ 16-Line Active-LOW Control Bus          │
         │ (8× ~OE[7:0] Read  •  8× ~WE[7:0] Write)│
         └────┬───────────────┬───────────────┬────┘
              │               │               │
        ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
        │ Reg Cards │   │ PC Cards  │   │ Stack Card│
        │ (Slots0-3)│   │ (Slots4-5)│   │ (Slot 6)  │
        │ 0 Decoders│   │ 0 Decoders│   │ 0 Decoders│
        └───────────┘   └───────────┘   └───────────┘

```

### System Benefits

* **Transistor Economy:** Replaces ~14 address-matching transistors per peripheral card with a single central 3-to-8 decoder pair (~16–20 NMOS transistors total for the system), saving ~60 hand-soldered FETs.
* **Passive Dumb Cards:** Peripheral cards require zero clock taps ($T_0\text{--}T_3$), ring-counter logic, or identity comparators. Cards simply expose open-drain N-FET drivers hooked to $\overline{\text{OE}}$ and input latches hooked to $\overline{\text{WE}}$.
* **100% Slot Interchangeability:** Cards can be plugged into any physical backplane edge slot; identity is assigned via an on-card 8-position jumper header connected to the shared $\overline{\text{OE}_n} / \overline{\text{WE}_n}$ traces.

---

## 2. Unified 8-Slot Address Matrix

The 3-bit slot address space (`000` through `111`) maps all standard data registers, system pointers, self-indexing hardware counters, and memory latches.

| Slot ID (`ADDR[2:0]`) | Mnemonic | Read Action ($\overline{\text{OE}_n} = 0$) | Write Action ($\overline{\text{WE}_n} = 0$) | Card Description |
| --- | --- | --- | --- | --- |
| **`000` (0)** | `REG_A` | Drives `Reg A` onto `BUS[3:0]` | Latches `BUS[3:0]` into `Reg A` | Standard 4-bit storage register |
| **`001` (1)** | `REG_B` | Drives `Reg B` onto `BUS[3:0]` | Latches `BUS[3:0]` into `Reg B` | Standard 4-bit storage register |
| **`010` (2)** | `REG_C` | Drives `Reg C` onto `BUS[3:0]` | Latches `BUS[3:0]` into `Reg C` | Storage / RAM Pointer High |
| **`011` (3)** | `REG_D` | Drives `Reg D` onto `BUS[3:0]` | Latches `BUS[3:0]` into `Reg D` | Storage / RAM Pointer Low |
| **`100` (4)** | `PCH` | Drives `PC_H` onto `BUS[3:0]` | Latches `BUS[3:0]` into `PC_H` | Program Counter High Nibble |
| **`101` (5)** | `PCL` | Drives `PC_L` onto `BUS[3:0]` | Latches `BUS[3:0]` into `PC_L` | Program Counter Low Nibble |
| **`110` (6)** | `STK` | Drives `RAM[SP]` onto `BUS[3:0]`<br>

<br>*(Auto-decrements $SP$ on $T_2\to T_3$)* | Latches `BUS[3:0]` into `RAM[SP]`<br>

<br>*(Auto-increments $SP$ on $T_2\to T_3$)* | Self-Indexing 16-Nibble Hardware Stack Card |
| **`111` (7)** | `NULL` / `RAM` | External RAM Read (`RAM_OE`) | External RAM Write (`RAM_WE`) / Suppress Write | RAM Interface / Open-Drain Drain Sink |

---

## 3. Bus Timings & Central Strobe Gating

Execution is structured across a 4-phase 1-hot ring counter ($T_0\text{--}T_3$). The Central Control Card gates the 3-to-8 decoder outputs directly with $T_2$ and $CLK$.

```text
CLK    ──┐   ┌───┐   ┌───┐   ┌───┐   ┌───
         └───┘   └───┘   └───┘   └───┘
Phase  │  T0   │  T1   │  T2   │  T3   │
       ├───────┼───────┼───────┼───────┤
~OE_x  ─────────────────┐       ───────── (Active-LOW Read: Phase T2)
                        └───────
~WE_y  ─────────────────────┐   ───────── (Active-LOW Write: Phase T2 & CLK=0)
                            └───

```

### Signal Equations

$$\overline{\text{OE}_x} = \neg \left( \text{Decode}(SRC\_ADDR = x) \land T_2 \right)$$

$$\overline{\text{WE}_y} = \neg \left( \text{Decode}(DST\_ADDR = y) \land T_2 \land \overline{CLK} \right)$$

1. **Phase $T_0$ (Opcode Fetch):** $PC$ owns address bus (`ADDR_H:ADDR_L`). `RAM_OE` pulled LOW. $IR_{OP}$ latches `BUS[3:0]`.
2. **Phase $T_1$ (Operand Fetch):** $PC$ owns address bus. `RAM_OE` pulled LOW. $IR_{OPER}$ latches `BUS[3:0]`.
3. **Phase $T_2$ (Execution & Data Transfer):**
* Selected $\overline{\text{OE}_x}$ goes LOW for the entire duration of $T_2$, turning on the open-drain N-FET output drivers of slot $x$.
* Selected $\overline{\text{WE}_y}$ goes LOW strictly while $T_2 \land \overline{CLK}$ is active, latching data safely into slot $y$ on the falling edge of $CLK$.


4. **Phase $T_3$ (Bus Recovery & State Increment):**
* All $\overline{\text{OE}}$ and $\overline{\text{WE}}$ lines return to $+5\text{V}$ (High-Z).
* Sequential counters (e.g., $SP$ on `STK` slot `110`) execute internal increment/decrement state transitions.



---

## 4. Extended Instruction Set Architecture (ISA)

The 4-bit opcode is split into 4 structural quadrants (`0x0` through `0xF`).

```text
                      OPCODE QUADRANTS (OP[3:0])
  ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
  │  00xx (0x0-0x3)  │  01xx (0x4-0x7)  │  10xx (0x8-0xB)  │  11xx (0xC-0xF)  │
  │  Data Movement & │  Immediate Data  │  Primary ALU     │  Extended ALU &  │
  │   Flow Control   │    (LDI A-D)     │ (ADD/SUB/AND/OR) │  Subops (UNARY)  │
  └──────────────────┴──────────────────┴──────────────────┴──────────────────┘

```

### Extended `LD` / `ST` Encodings (Bank Switching via $ADDR[2]$)

Standard `MOV` instructions operate within Bank 0 ($ADDR[2] = 0$, selecting slots `000`–`011` for Regs A–D).

`LD` (`0x1`) and `ST` (`0x2`) harvest unused operand bits to set $ADDR[2] = 1$, unlocking instant access to system slots `100` (`PCH`), `101` (`PCL`), and `110` (`STK`).

#### Extended `LD` Opcode (`0x1`) — `OPERAND[3:2]` = $dst$ (Regs A–D), `OPERAND[1:0]` = Mode

| Operand Binary | Mnemonic | Hardware Action | Execution Encoding |
| --- | --- | --- | --- |
| `dst : 00` | `LD dst` | Read `RAM[C:D]` into `dst` | $SRC = \text{Slot } 7\text{ (RAM)}$, $DST = dst$ |
| `dst : 01` | `MOV dst, PCH` | Read `PC_H` into `dst` | $SRC = \text{Slot } 4\text{ (PCH)}$, $DST = dst$ |
| `dst : 10` | `MOV dst, PCL` | Read `PC_L` into `dst` | $SRC = \text{Slot } 5\text{ (PCL)}$, $DST = dst$ |
| `dst : 11` | `POP dst` | Pop top of `STK` into `dst` | $SRC = \text{Slot } 6\text{ (STK)}$, $DST = dst$ |

#### Extended `ST` Opcode (`0x2`) — `OPERAND[3:2]` = Mode, `OPERAND[1:0]` = $src$ (Regs A–D)

| Operand Binary | Mnemonic | Hardware Action | Execution Encoding |
| --- | --- | --- | --- |
| `00 : src` | `ST src` | Store `src` to `RAM[C:D]` | $SRC = src$, $DST = \text{Slot } 7\text{ (RAM)}$ |
| `01 : src` | `PUSH src` | Push `src` ($A, B, C, D$) to `STK` | $SRC = src$, $DST = \text{Slot } 6\text{ (STK)}$ |
| `10 : 00` | `PUSH PCH` | Push `PC_H` directly to `STK` | $SRC = \text{Slot } 4\text{ (PCH)}$, $DST = \text{Slot } 6\text{ (STK)}$ |
| `11 : 00` | `PUSH PCL` | Push `PC_L` directly to `STK` | $SRC = \text{Slot } 5\text{ (PCL)}$, $DST = \text{Slot } 6\text{ (STK)}$ |

---

## 5. Subroutine & Stack Calling Conventions

With the Slot `110` Auto-Indexing Stack Card and readable Program Counter slots (`100`/`101`), subroutine calls and returns execute cleanly without destroying $C:D$ RAM pointers.

### Subroutine Call (`CALL target`)

```assembly
PUSH PCH        ; Opcode 0x2 0x8 (Push return address high nibble)
PUSH PCL        ; Opcode 0x2 0xC (Push return address low nibble)
SET_CD MY_SUB   ; Load target address into C:D
JMP             ; Jump to subroutine

```

### Subroutine Return (`RET`)

```assembly
POP D           ; Opcode 0x1 0xF (Pop saved PC_L into Reg D)
POP C           ; Opcode 0x1 0xB (Pop saved PC_H into Reg C)
JMP             ; Jump back to caller (PCH <- C, PCL <- D)

```

---

## 6. Standard Card Pinout Specification

All peripheral cards (Registers A–D, PC, Stack) interface with the backplane via a standardized 8-pin edge connector matrix.

```text
               ┌───────────────────────────────┐
               │    NOD-4 PERIPHERAL CARD      │
               │                               │
               │  [8-Position Jumper Block]    │
               │  Selects OE_n and WE_n Trace  │
               │                               │
               └─┬───┬───┬───┬───┬───┬───┬───┬─┘
                 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │
                 └───┴───┴───┴───┴───┴───┴───┴───┘
                  BUS0 BUS1 BUS2 BUS3 ~OE ~WE VCC GND

```

| Pin | Signal | Direction | Description |
| --- | --- | --- | --- |
| **1** | `BUS[0]` | I/O | Active-LOW Open-Drain Data Bit 0 |
| **2** | `BUS[1]` | I/O | Active-LOW Open-Drain Data Bit 1 |
| **3** | `BUS[2]` | I/O | Active-LOW Open-Drain Data Bit 2 |
| **4** | `BUS[3]` | I/O | Active-LOW Open-Drain Data Bit 3 |
| **5** | $\overline{\text{OE}}$ | Input | Active-LOW Read Strobe (Enables output N-FET drivers) |
| **6** | $\overline{\text{WE}}$ | Input | Active-LOW Write Strobe (Opens input transparent latches) |
| **7** | $V_{CC}$ | Power | $+5\text{V}$ Power Rail |
| **8** | $GND$ | Power | $0\text{V}$ Ground Return |

---

## 7. Backplane Trace Assignment (37-Pin Matrix)

```text
Pin  Signal       Pin  Signal       Pin  Signal       Pin  Signal
──────────────────────────────────────────────────────────────────
 1   GND           11  BUS[2]        21  ~OE[3]        31  ~WE[3]
 2   VCC (+5V)     12  BUS[3]        22  ~OE[4] (PCH)  32  ~WE[4] (PCH)
 3   CLK           13  ~OE[0] (RegA) 23  ~OE[5] (PCL)  33  ~WE[5] (PCL)
 4   CLK_n         14  ~OE[1] (RegB) 24  ~OE[6] (STK)  34  ~WE[6] (STK)
 5   T0            15  ~OE[2] (RegC) 25  ~OE[7] (RAM)  35  ~WE[7] (RAM)
 6   T1            16  ADDR_H[0]     26  ADDR_L[0]     36  ~RESET
 7   T2            17  ADDR_H[1]     27  ADDR_L[1]     37  ~HALT
 8   T3            18  ADDR_H[2]     28  ADDR_L[2]         
 9   BUS[0]        19  ADDR_H[3]     29  ADDR_L[3]         
10   BUS[1]        20  ~WE[0] (RegA) 30  ~WE[1] (RegB)     

```