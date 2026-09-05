# NOD-4 Microprocessor Architecture & System Specification (v12.6)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Physical Hierarchy:** 50-Pin Passive Backplane Bus $\rightarrow$ Universal Base Cards (UBC) $\rightarrow$ Counter / Extended ALU / Interrupt Daughtercards

**Control Philosophy:** Tree-Based Quadrant Decoder (`OP[3]=IMM`, `OP[2]=ALU_EN`), Direct-Drive Unary/Shift Matrix, Zero-Decoder Destination Routing, Internal Decoder Self-Reset, Diagonal Control Escape ($dd == ss$), Bus-Hijack Interrupt Engine.

---

## 1. Electrical Standard, Clocking & Latch Mechanics

* **Logic Family:** Discrete NMOS pass-transistor and depletion-load logic using 2N7000 NMOS switches with active-LOW signal paths.
* **Signal Standard:** Active-LOW open-drain backplane rails with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.
* **Clocking Architecture & Phase Alignment:** Single-phase master clock (`CLK`). State transitions ($T_0 \dots T_5$) trigger on the falling edge of `CLK`.
* **Two-Phase Timestep Execution Model:**
1. **Phase 1: Setup & Drive (`CLK` LOW):** Control decoders evaluate and drive control rails (`~OE[src]` and `~WE[dst]`). Any combinational ripple or bus propagation occurs while `LATCH_ENABLE` is held off (`1`). Data on `BUS[3:0]` stabilizes cleanly during this window.
2. **Phase 2: Latch Window (`CLK` HIGH):** Control lines remain static. Active write pulsing occurs as `CLK` transitions HIGH, driving the target latch transparent for data capture.


* **Level-Sensitive Write Mechanics:**
Memory elements and register cells on Universal Base Cards are level-sensitive transparent latches. Write enables are gated locally on each card using active-LOW logic:

$$\text{LATCH\_ENABLE}_n = \text{\textasciitilde WE}_n \text{ OR } \text{\textasciitilde CLK}$$

$$\overline{\text{LATCH\_ENABLE}_n} = \overline{\text{\textasciitilde WE}_n} \cdot \text{CLK}$$

Data on `BUS[3:0]` must be stable prior to `CLK` rising. Latching occurs continuously while `CLK` is HIGH and freezes on the falling edge of `CLK` or upon de-assertion of `~WE[n]`.

* **Program Counter (PC) Auto-Increment Mechanics:**
$PC$ auto-increments twice per instruction cycle: on the rising edge of $T_1$ (after Opcode fetch in $T_0$) and on the rising edge of $T_2$ (after Operand fetch in $T_1$). By $T_2$, $PC$ naturally equals $PC_{\text{orig}} + 2$, providing the exact return address for `CALL`, `PUSHPC`, and hardware interrupts without auxiliary addition hardware.
$PC$ increment strobes are gated directly by the interrupt disable rail:

$$\text{PC\_INC\_ENABLE} = \text{INC\_STROBE} \cdot \overline{\text{IR\_DISABLE}}$$

* **Execution Flags:**
* $ZF$ (Zero Flag): Set if the 4-bit output of an operation equals $0\text{x0}$ (sampled on the trailing edge of $T_3$).
* $CF$ (Carry/Borrow Flag): Set on arithmetic carry-out or cleared on borrow using inverted-borrow logic (sampled on the trailing edge of $T_3$).
* $IE$ (Interrupt Enable Flag): Hardware latch on Interrupt Card (Set via `STI`/`RETI`, cleared via `CLI`/`IRQ` entry).



---

## 2. Tree-Based Top-Level Instruction Decoder (`OP[3:2]`)

Top-level decoding maps cleanly to `OP[3]` ($\text{IMM}$) and `OP[2]` ($\text{ALU\_EN}$).

```
                                [ OPCODE[3:2] ]
                                 (IMM, ALU_EN)
                                       |
                +----------------------+----------------------+
                |                                             |
           ALU_EN = 1                                    ALU_EN = 0
       (Q1 Reg-Reg, Q3 Immediate)                              |
                |                             +---------------+---------------+
        • Fixed 5-Step Pipeline               |                               |
        • Resets at T5                  IMM = 1 (Q2)                    IMM = 0 (Q0)
        • Hardwired ALU Sequence:      (Load Immediate)           (Moves & Control Escapes)
          - T2: Latch B (src/imm)             |                               |
          - T3: Latch A (dst) & Compute       • Fixed 3-Step                  • Moves: Reset at T3
          - T4: Write ALU_OUT -> dst          • Resets at T3                  • Untaken Branch: Reset at T2 (FAIL)
                                              • Direct OPERAND -> BUS         • Taken Branch / RET: Reset at T4
                                                                              • CALL / NOP / IRQ: Reset at T6

```

### Top-Level Quadrant Decode Table

| Quadrant | Binary (`OP[3:2]`) | Bit Flags (`IMM, ALU_EN`) | Functional Class | Micro-Control Routing & Timing |
| --- | --- | --- | --- | --- |
| **Q0** | `00` | `IMM = 0, ALU_EN = 0` | Data Moves & Control Escapes | Sub-decodes reset points. Supports diagonal control escapes ($dd == ss$). Resets at $T_2$ (untaken branch), $T_3$ (moves), $T_4$ (taken branch/RET), or $T_6$ (`CALL`/`NOP`/`~IRQ`). |
| **Q1** | `01` | `IMM = 0, ALU_EN = 1` | Reg-to-Reg Binary ALU | Hardwired 5-step pipeline. $T_2$: Latch $src \rightarrow ALU_B$; $T_3$: Latch $dst \rightarrow ALU_A$ & Compute; $T_4$: $ALU_{OUT} \rightarrow dst$. Resets at $T_5$. |
| **Q2** | `10` | `IMM = 1, ALU_EN = 0` | Load Immediate (`LDI`) | Zero decode logic. Drives `OPERAND[3:0]` directly to `BUS[3:0]`. Writes to `dst` at $T_2$. Fixed 3-step execution; resets at $T_3$. |
| **Q3** | `11` | `IMM = 1, ALU_EN = 1` | Immediate ALU & Shift Matrix | Hardwired 5-step pipeline. $T_2$: Latch $imm \rightarrow ALU_B$; $T_3$: Latch $dst \rightarrow ALU_A$ & Compute; $T_4$: $ALU_{OUT} \rightarrow dst$. Resets at $T_5$. |

---

## 3. Cycle Reset Engine (`~CYCLE_RESET`)

To prevent floating bus conditions, overlapping enable signals, and unintended register writes during multi-step executions, early cycle termination is governed by the active-LOW `~CYCLE_RESET` rail (Pin 04). Resets pulse `~CLR` on the TIMING board's state counter back to $T_0$.

### Reset Point Breakdown

* **$T_2 \cdot \text{FAIL}$:** Untaken branch (`Jcc` condition evaluates FALSE). Steering tree evaluates combinationally during $T_2$ and terminates the cycle instantly at $T_2$, leaving $PC$ perfectly aligned at $PC_0 + 2$.
* **$T_3 \cdot \text{Q2\_LDI}$:** Load Immediate (`LDI`) finishes writeback at $T_2$; resets at $T_3$ entry.
* **$T_3 \cdot \text{Q0\_MOVE}$:** Standard register/memory move (`MOV`, `LD`, `ST`) finishes writeback at $T_2$; resets at $T_3$ entry.
* **$T_4 \cdot \text{JMP\_RET}$:** Taken branch (`JMP`, `Jcc`) or Return (`RET`) loads $PCL$ at $T_2$ and $PCH$ at $T_3$; resets at $T_4$ entry.
* **$T_5 \cdot \text{ALU\_EN}$:** ALU operations (Q1 Reg-Reg & Q3 Immediate) read operands at $T_2$/$T_3$ and write back at $T_4$; resets at $T_5$ entry via `ALU_EN` (`OP[2] = 1`).
* **Internal $T_6$ Clear:** Subroutine Call (`CALL`), `NOP`, and Hardware Interrupt Hijack (`~IRQ`) run through $T_5$. The TIMING card self-resets at $T_6$ via direct hardware feedback ($\overline{T_6} \rightarrow \overline{\text{CLR}}$).

### Master Cycle Reset Rail Boolean Equation

$$\overline{\text{CYCLE\_RESET}} = \overline{(T_2 \cdot \text{FAIL}) \lor (T_3 \cdot \text{Q2\_LDI}) \lor (T_3 \cdot \text{Q0\_MOVE}) \lor (T_4 \cdot \text{JMP\_RET}) \lor (T_5 \cdot \text{ALU\_EN})}$$

---

## 4. Micro-Step Pipeline & Timing Matrix ($T_0 \dots T_5$)

### Detailed Pipeline Phase Definitions

* **$T_0$ (Opcode Fetch):** `~OE[PCH]` and `~OE[PCL]` drive $PC$ to `ADDR_H/L`. ROM asserts `~OE[MEM]`, driving opcode onto `BUS[3:0]`. Opcode is latched into `OPCODE[3:0]` when `CLK` goes HIGH.
* **$T_1$ (Operand Fetch):** On $T_1$ entry (`CLK` LOW), $PC$ increments ($PC \leftarrow PC_0 + 1$). ROM asserts `~OE[MEM]`, driving operand onto `BUS[3:0]`. Operand is latched into `OPERAND[3:0]` when `CLK` goes HIGH.
* **$T_2$ (Source Drive & Setup Phase / Early Branch Termination):** On $T_2$ entry (`CLK` LOW), $PC$ increments again ($PC \leftarrow PC_0 + 2$).
* *For Untaken Branch:* Steering tree evaluates `FAIL=1`. State counter receives `~CYCLE_RESET` immediately at $T_2$, aborting $T_3/T_4$ execution.
* *For Moves/LDI:* `~OE[src]` or `~OE[OPERAND]` drives source to `BUS[3:0]`.
* *For ALU Ops:* `~OE[src]` or `~OE[OPERAND]` drives operand into $ALU_B$ latch.


* **$T_3$ (Destination Latch / Compute Phase):**
* *For Moves/LDI:* Target asserts `~WE[dst]` simultaneously with `~OE[src]`; cycle resets at $T_3$ entry.
* *For ALU Ops:* `~OE[dst]` drives destination register into $ALU_A$ latch. ALU computes result and samples flags ($ZF, CF$) on the trailing edge of $T_3$.


* **$T_4$ (ALU Writeback & Branch Write):**
* *For ALU Ops:* $ALU_{OUT}$ drives `BUS[3:0]`, asserting `~WE[dst]` to store result.
* *For Control Ops:* Target high byte address is written to $PCH$.


* **$T_5$ (Reset State):** Output buffers release backplane lines, state machine settles, and `~CYCLE_RESET` resets step counter to $T_0$.

### Complete Micro-Step Timing Matrix

| Instruction Class | $T_0$ (Opcode Fetch) | $T_1$ (Operand Fetch, PC+1) | $T_2$ (Drive / Latch B, PC+2) | $T_3$ (Latch A / Compute / Write) | $T_4$ (ALU Writeback / PCH) | $T_5$ (Reset) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move** (`MOV dst, src`) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[SRC]` $\rightarrow$ `BUS` & `~WE[DST]` ($PC \leftarrow PC+1$) | Reset via `~CYCLE_RESET` | — | — |
| **Q0: Memory Store** (`ST MEM, src`) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Drive `RegC:RegD` to `ADDR`, Assert `~OE[SRC]` & `~WE[MEM]` ($PC \leftarrow PC+1$) | Reset via `~CYCLE_RESET` | — | — |
| **Q0: Memory Load** (`LD dst, MEM`) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Drive `RegC:RegD` to `ADDR`, Assert `~OE[MEM]` & `~WE[DST]` ($PC \leftarrow PC+1$) | Reset via `~CYCLE_RESET` | — | — |
| **Q0: Jump Untaken** (`Jcc` False) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Evaluate Steering Tree $\rightarrow$ `FAIL=1`, Terminate instantly at $T_2$ | — | — | — |
| **Q0: Jump Taken** (`JMP`, `Jcc` True) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[RegD]` $\rightarrow$ `BUS` & `~WE[PCL]` ($PC \leftarrow PC+1$) | Assert `~OE[RegC]` $\rightarrow$ `BUS` & `~WE[PCH]` | Reset via `~CYCLE_RESET` | — |
| **Q0: Call Subroutine** (`CALL`) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Push $PCL$ ($PC_0+2$) $\rightarrow \text{STK}$, Assert `~OE[RegD]` ($PC \leftarrow PC+1$) | Push $PCH$ ($PC_0+2$) $\rightarrow \text{STK}$, Assert `~OE[RegD]` & `~WE[PCL]` | Assert `~OE[RegC]` & `~WE[PCH]` | Hardware Self-Reset at $T_6$ |
| **Q0: Return** (`RET` / `RETI`) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Pop $\text{STK} \rightarrow PCH$ ($PC \leftarrow PC+1$) | Pop $\text{STK} \rightarrow PCL$ | Reset via `~CYCLE_RESET` | — |
| **Q1: Reg-Reg ALU** (`ADD`, `SUB`, etc.) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[SRC]` $\rightarrow$ Latch $ALU_B$ ($PC \leftarrow PC+1$) | Assert `~OE[DST]` $\rightarrow$ Latch $ALU_A$, Compute, Sample Flags | Assert $ALU_{OUT} \rightarrow \text{BUS}$ & `~WE[DST]` | Reset via `~CYCLE_RESET` |
| **Q2: Load Immediate** (`LDI dst, #imm`) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[OPERAND]` $\rightarrow$ `BUS` & `~WE[DST]` ($PC \leftarrow PC+1$) | Reset via `~CYCLE_RESET` | — | — |
| **Q3: Immediate ALU** (`ADDI`, `SUBI`, etc.) | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[OPERAND]` $\rightarrow$ Latch $ALU_B$ ($PC \leftarrow PC+1$) | Assert `~OE[DST]` $\rightarrow$ Latch $ALU_A$, Compute, Sample Flags | Assert $ALU_{OUT} \rightarrow \text{BUS}$ & `~WE[DST]` | Reset via `~CYCLE_RESET` |
| **Hardware Interrupt** (`~IRQ` Entry) | Freeze $PC$, `~IR_DISABLE` LOW | Push $PCL_{\text{return}}$ ($PC_0+2$) $\rightarrow \text{STK}$ | Push $PCH_{\text{return}}$ ($PC_0+2$) $\rightarrow \text{STK}$ | Drive Vector Low $\rightarrow \text{PCL}$ | Drive Vector High $\rightarrow \text{PCH}$ | Hardware Self-Reset at $T_6$, release `~IR_DISABLE` |

---

## 5. Master Backplane Pinout & Card Slot Mapping

```
   SYSTEM & CONTROL (01-06)         CONTROL RAILS (~WE / ~OE)          PARALLEL NIBBLE BUSES
[ 01-03 ] Power & Clock           [ 15-22 ] Write Enables (~WE)   --->   [ 31-34 ] Data Bus (BUS)
[ 04-06 ] Reset, Disable, IRQ     [ 23-30 ] Output Enables (~OE)         [ 35-38 ] Address High (ADDR_H)
[ 07-12 ] Timesteps (T0-T5)                                              [ 39-42 ] Address Low (ADDR_L)
                                                                         [ 43-46 ] Opcode Rail (OPCODE)
                                                                         [ 47-50 ] Operand Rail (OPERAND)

```

| Pin # | Signal | Domain | Description & Interconnect Target |
| --- | --- | --- | --- |
| **01** | `GND` | Power | System Ground Reference Return |
| **02** | `VCC` | Power | $+5\text{V}$ Power Rail |
| **03** | `CLK` | Timing | Single-Phase System Clock Input |
| **04** | `~CYCLE_RESET` | Control | Active-LOW Synchronous State Counter Reset |
| **05** | `~IR_DISABLE` | System | Active-LOW Interrupt Hijack / Halt NOP-Force Rail |
| **06** | `~IRQ` | System | Active-LOW Open-Drain Hardware Interrupt Request Rail |
| **07–12** | `~T0`–`~T5` | Timing | Execution Timesteps $0$ through $5$ |
| **13** | `~ZF` | Flag | Active-LOW Zero Flag Bus Rail |
| **14** | `~CF` | Flag | Active-LOW Carry / Borrow Flag Bus Rail |
| **15–22** | `~WE[0:7]` | Control | Write Enable Rails for Cards 0 through 7 |
| **23–30** | `~OE[0:7]` | Control | Output Enable Rails for Cards 0 through 7 |
| **31–34** | `BUS[0:3]` | Data | Bidirectional 4-Bit Data Bus |
| **35–38** | `ADDR_H[0:3]` | Address | Memory Address High Nibble |
| **39–42** | `ADDR_L[0:3]` | Address | Memory Address Low Nibble |
| **43–46** | `OPCODE[0:3]` | Control | Latched Instruction Opcode Nibble |
| **47–50** | `OPERAND[0:3]` | Control | Latched Instruction Operand Nibble |

### System Hardware Card Manifest

| Slot / Module | Board Type | Qty | Target Vector | Function & Backplane Connections |
| --- | --- | --- | --- | --- |
| **RegA** | Universal Base Card (UBC) | 1 | `000` (`0x0`) | Accumulator / General Register A (`BUS[3:0]`, `~WE[0]`, `~OE[0]`) |
| **RegB** | Universal Base Card (UBC) | 1 | `001` (`0x1`) | Accumulator / General Register B (`BUS[3:0]`, `~WE[1]`, `~OE[1]`) |
| **RegC** | Universal Base Card (UBC) | 1 | `010` (`0x2`) | High Pointer Nibble PTR_H (`BUS[3:0]`, `ADDR_H[3:0]`, `~WE[2]`, `~OE[2]`) |
| **RegD** | Universal Base Card (UBC) | 1 | `011` (`0x3`) | Low Pointer Nibble PTR_L (`BUS[3:0]`, `ADDR_L[3:0]`, `~WE[3]`, `~OE[3]`) |
| **MEM** | Memory Transceiver Board | 1 | `100` (`0x4`) | System RAM/ROM Interface (`ADDR_H/L`, `BUS[3:0]`, `~WE[4]`, `~OE[4]`) |
| **PCH** | UBC + Counter Daughtercard | 1 | `101` (`0x5`) | Program Counter High (`BUS[3:0]`, `ADDR_H[3:0]`, `~WE[5]`, `~OE[5]`) |
| **PCL** | UBC + Counter Daughtercard | 1 | `110` (`0x6`) | Program Counter Low (`BUS[3:0]`, `ADDR_L[3:0]`, `~WE[6]`, `~OE[6]`) |
| **STK** | UBC + Hardware Stack Core | 1 | `111` (`0x7`) | Hardware Stack Core & Pointer (`BUS[3:0]`, `~WE[7]`, `~OE[7]`) |
| **OPCODE** | Universal Base Card (UBC) | 1 | — | Opcode Latch (`BUS[3:0]`, `OPCODE[3:0]`, `~IR_DISABLE`) |
| **OPERAND** | Universal Base Card (UBC) | 1 | — | Operand Latch (`BUS[3:0]`, `OPERAND[3:0]`, `~IR_DISABLE`) |
| **ALU** | Custom Discrete Board | 1 | — | 4-Bit Binary Adder, Carry Tap (`BUS[3:0]`, `OPCODE[3:0]`, `OPERAND[3:0]`) |
| **EXT_ALU** | ALU Daughtercard | 1 | — | Shift Matrix & Unary Operations (Piggybacks on ALU Board) |
| **TIMING** | Custom Discrete Board | 1 | — | State Counter, Decoder, Flags (`CLK`, `~T0..~T5`, `~CYCLE_RESET`) |
| **INT** | Custom Discrete Board | 1 | — | Handshake, Vector Hijack, Halt (`~IRQ`, `~IR_DISABLE`, `BUS[3:0]`) |

---

## 6. Universal Base Card (UBC) & Daughtercard Architecture

```
+-----------------------------------------------------------------------------------+
|                            BACKPLANE (50 Pins)                                    |
+-----------------------------------------------------------------------------------+
       |                  |                |               |                |
       v                  v                v               v                v
    ~WE[0:7]          ~OE[0:7]            CLK           ~T0..~T5         BUS[3:0]
       |                  |                |               |                |
+------|------------------|----------------|---------------|----------------|-------+
|      v                  v                v               v                |       |
|  +-------+          +-------+      +-----------+                          |       |
|  | HDR 1 |          | HDR 2 |      | LOCAL WE  |                          |       |
|  | 2x14  |          | 2x14  |      | GATE LOGIC|                          |       |
|  +-------+          +-------+      +-----------+                          |       |
|      |                  |                |                                |       |
|   ~INT_WE            ~OE_MAIN            v                                |       |
|      |                  |         ~LATCH_ENABLE                           v       |
|      |                  |        (~WE OR ~CLK)                +----------------+  |
|      |                  |                |                    | 4x Discrete    |  |
|      +------------------+----------------+------------------->| Transparent    |  |
|                         |                                     | NMOS D-Latches |  |
|                         v                                     +----------------+  |
|               +-------------------+                                   |           |
|               | 2N7000 Output     |<==================================+           |
|               | Bus Buffers       |                                   |           |
|               +-------------------+                                   v           |
|                         |                                     +----------------+  |
|                         +====================================>| HDR 3          |  |
|                         |                                     | Direct Output  |  |
|                         v                                     +----------------+  |
|                     BUS[3:0]                                          |           |
|                         |                                             v           |
|                         |                                    ADDR_H / ADDR_L      |
|                         |                                                         |
|                         +==================================+                      |
|                                                            v                      |
|                                              [ 13-Pin Daughtercard Socket ]       |
+-----------------------------------------------------------------------------------+

```

---

## 7. Quadrant Instruction Matrix & Sub-Operations

### Quadrant 0 (`OP[3:2] = 00`): Data Moves & Diagonal Control Escapes

Standard Moves (`00 dd cc ss` where $dd \neq ss$ or $cc \neq 00$):

* $\text{DST} = \{cc[1], dd\}$, $\text{SRC} = \{cc[0], ss\}$.
* $cc = 00$: `MOV reg, reg` | $cc = 01$: `ST sys, reg` | $cc = 10$: `LD reg, sys` | $cc = 11$: `MOV sys, sys`

#### Diagonal Control Escapes ($cc = 00$ and $dd == ss$)

```
5-Transistor Branch Steering Tree (FAIL Logic):
Let P1 = OPERAND[1] and P0 = OPERAND[0].

FAIL = ~P0 . (~P1 . ~ZF | P1 . ~CF)  |  P0 . (~P1 . ZF)

```

| Opcode Pattern | Binary | Hex | Mnemonic | Operational Logic & Micro-Steps |
| --- | --- | --- | --- | --- |
| **`00 00 00 00`** | `00000000` | `0x00` | `NOP` | System Idle; forced during `~IR_DISABLE` assertion. Runs full 6 steps; resets at $T_6$. |
| **`00 01 00 01`** | `00010001` | `0x11` | `CLI` | Clear Interrupt Enable Flag ($IE \leftarrow 0$). Resets at $T_3$. |
| **`00 01 01 01`** | `00010101` | `0x15` | `STI` | Set Interrupt Enable Flag ($IE \leftarrow 1$). Resets at $T_3$. |
| **`00 01 10 01`** | `00011001` | `0x19` | `RETI` | Return from Interrupt: Pop $PCH:PCL$ from stack, set $IE \leftarrow 1$. Resets at $T_4$. |
| **`00 01 11 01`** | `00011101` | `0x1D` | `HALT` | Asserts Halt Latch and drives `~IR_DISABLE` LOW until reset or IRQ. |
| **`00 10 00 10`** | `00100010` | `0x22` | `JZ` / `JE` | Branch to `RegC:RegD` if $ZF = 1$. Resets at $T_2$ (FAIL) or $T_4$ (Taken). |
| **`00 10 01 10`** | `00100110` | `0x26` | `JC` / `JAE` | Branch to `RegC:RegD` if $CF = 1$. Resets at $T_2$ (FAIL) or $T_4$ (Taken). |
| **`00 10 10 10`** | `00101010` | `0x2A` | `JNZ` / `JNE` | Branch to `RegC:RegD` if $ZF = 0$. Resets at $T_2$ (FAIL) or $T_4$ (Taken). |
| **`00 10 11 10`** | `00101110` | `0x2E` | `JMP` | Unconditional Branch to `RegC:RegD`. Resets at $T_4$. |
| **`00 11 00 11`** | `00110011` | `0x33` | `CALL` | Push $PCL$, Push $PCH$, load `RegC:RegD` into `PCH:PCL`. Resets at $T_6$. |
| **`00 11 01 11`** | `00110111` | `0x37` | `RET` | Pop $PCH$, Pop $PCL$ from stack into `PCH:PCL`. Resets at $T_4$. |
| **`00 11 10 11`** | `00111011` | `0x3B` | `PUSHPC` | Push current $PCL$ then $PCH$ ($PC_0+2$) to stack. Resets at $T_4$. |

---

### Quadrant 1 (`OP[3:2] = 01`): Reg-to-Reg Binary ALU

Opcode Format: `01 op1 op0 dd` (`OPERAND[1:0]` = Source Register `ss`). Target `dst` acts as dynamic accumulator (`OP[1:0]`). Fixed 5-step execution (resets at $T_5$).

| Opcode Pattern | Mnemonic | ALU Function | Operational Pipeline Sequence | Flag Updates |
| --- | --- | --- | --- | --- |
| **`01 00 00 dd`** | `ADD dst, src` | Binary Addition | $T_2$: $src \rightarrow ALU_B$; $T_3$: $dst \rightarrow ALU_A$, Compute; $T_4$: $ALU_{OUT} \rightarrow dst$ | $ZF, CF$ |
| **`01 01 00 dd`** | `SUB dst, src` | Binary Subtraction | $T_2$: $src \rightarrow ALU_B$; $T_3$: $dst \rightarrow ALU_A$, Compute; $T_4$: $ALU_{OUT} \rightarrow dst$ | $ZF, CF$ |
| **`01 10 00 dd`** | `AND dst, src` | Bitwise AND | $T_2$: $src \rightarrow ALU_B$; $T_3$: $dst \rightarrow ALU_A$, Compute; $T_4$: $ALU_{OUT} \rightarrow dst$ | $ZF$ ($CF \leftarrow 0$) |
| **`01 11 00 dd`** | `OR dst, src` | Bitwise OR | $T_2$: $src \rightarrow ALU_B$; $T_3$: $dst \rightarrow ALU_A$, Compute; $T_4$: $ALU_{OUT} \rightarrow dst$ | $ZF$ ($CF \leftarrow 0$) |
| **`01 00 01 dd`** | `XOR dst, src` | Bitwise XOR | $T_2$: $src \rightarrow ALU_B$; $T_3$: $dst \rightarrow ALU_A$, Compute; $T_4$: $ALU_{OUT} \rightarrow dst$ | $ZF$ ($CF \leftarrow 0$) |
| **`01 01 01 dd`** | `CMP dst, src` | Compare (No Write) | $T_2$: $src \rightarrow ALU_B$; $T_3$: $dst \rightarrow ALU_A$, Compute, Sample Flags; $T_4$: Writeback Inhibited | $ZF, CF$ |

---

### Quadrant 2 (`OP[3:2] = 10`): Load Immediate (`LDI`)

Opcode Format: `10 dd cc 00` (`OPERAND[3:0]` = 4-Bit Immediate Data). Fixed 3-step execution (resets at $T_3$).

| Opcode (`OPCODE[3:0]`) | Mnemonic | Destination Target | Execution Sequence ($T_2$) |
| --- | --- | --- | --- |
| **`10 00 00 00` (`0x80`)** | `LDI RegA, #imm` | RegA (Slot 0) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[0]` |
| **`10 01 00 00` (`0x90`)** | `LDI RegB, #imm` | RegB (Slot 1) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[1]` |
| **`10 10 00 00` (`0xA0`)** | `LDI RegC, #imm` | RegC (Slot 2) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[2]` |
| **`10 11 00 00` (`0xB0`)** | `LDI RegD, #imm` | RegD (Slot 3) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[3]` |
| **`10 00 01 00` (`0x84`)** | `LDI MEM, #imm` | RAM[`RegC:RegD`] | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[4]` |
| **`10 01 01 00` (`0x94`)** | `LDI PCH, #imm` | PCH (Slot 5) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[5]` |
| **`10 10 01 00` (`0xA4`)** | `LDI PCL, #imm` | PCL (Slot 6) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[6]` |
| **`10 11 01 00` (`0xB4`)** | `LDI STK, #imm` | Stack Core (Slot 7) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[7]` |

---

### Quadrant 3 (`OP[3:2] = 11`): Immediate ALU & Shift Matrix

Opcode Format: `11 op1 op0 dd`. `OPERAND[3:0]` decodes immediate operation and carry settings. Fixed 5-step execution (resets at $T_5$).

$$\text{OPERAND}[3:0] = [\text{EXT} \mid \text{ALU\_OP1} \mid \text{ALU\_OP0} \mid \text{IMM0}]$$

| `EXT` | `ALU_OP[1:0]` | `IMM0` | Mnemonic | Operational Pipeline Sequence & Carry Logic |
| --- | --- | --- | --- | --- |
| **`0`** | `00` | `0` | `ADC dst` | Add with Carry: $dst \leftarrow dst + 0 + CF$ ($C_{in} = CF$) |
| **`0`** | `00` | `1` | `INC dst` | Increment: $dst \leftarrow dst + 1$ ($C_{in} = 0$) |
| **`0`** | `01` | `0` | `SBB dst` | Subtract with Borrow: $dst \leftarrow dst - 0 - (1 - CF)$ |
| **`0`** | `01` | `1` | `DEC dst` | Decrement: $dst \leftarrow dst - 1$ ($C_{in} = 1$) |
| **`0`** | `10` | `0` | `XORI dst, 0` | Bitwise XOR with 0 (Preserves value, updates $ZF$) |
| **`0`** | `10` | `1` | `XORI dst, 1` | Bitwise XOR with 1 (Flips Bit 0) |
| **`0`** | `11` | `0` | `ANDI dst, 0` | Bitwise AND with 0 (Clears register to $0\text{x0}$, sets $ZF$) |
| **`0`** | `11` | `1` | `ANDI dst, 1` | Bitwise AND with 1 (Isolates Bit 0) |
| **`1`** | `00` | `x` | `NOT dst` | Bitwise Invert via NMOS pull-down array |
| **`1`** | `01` | `x` | `SHR dst` | Logical Shift Right: $D_3 \leftarrow 0, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |
| **`1`** | `10` | `x` | `RCR dst` | Rotate Right thru Carry: $D_3 \leftarrow CF, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |
| **`1`** | `11` | `x` | `ASR dst` | Arithmetic Shift Right: $D_3 \leftarrow D_3, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |

---

## 8. Hardware Vector Hijack Subsystem (Interrupt Engine)

When `~IRQ` fires while $IE = 1$, the Interrupt Card forces `~IR_DISABLE` LOW at $T_0$, freezing program counter auto-increments ($PC$ remains fixed at $PC_{\text{return}} = PC_0 + 2$) and executing a 6-step hardware vector hijack:

* **$T_0$ — Hijack Entry & Lock:** `~IR_DISABLE` asserts LOW, $PC$ auto-increment disabled ($PC$ locked at $PC_{\text{return}}$), $IE \leftarrow 0$, `IRQ_REQ` cleared, `HIJACK_RUN` set. Forced `0x00` NOP into instruction pipeline.
* **$T_1$ — Push $PCL$:** Interrupt card drives $PCL$ ($PC_{\text{return}}$ Low) onto `BUS[3:0]` and asserts `~WE[7]` (`STK_PUSH`, $SP \leftarrow SP - 1$).
* **$T_2$ — Push $PCH$:** Interrupt card drives $PCH$ ($PC_{\text{return}}$ High) onto `BUS[3:0]` and asserts `~WE[7]` (`STK_PUSH`, $SP \leftarrow SP - 1$).
* **$T_3$ — Load Vector Low:** Interrupt card drives Hardware Vector Low nibble onto `BUS[3:0]` and asserts `~WE[6]` (`PCL_WRITE`).
* **$T_4$ — Load Vector High:** Interrupt card drives Hardware Vector High nibble onto `BUS[3:0]` and asserts `~WE[5]` (`PCH_WRITE`).
* **$T_5 \dots T_6$ — Release & Settle:** Interrupt card un-drives bus, releases `~IR_DISABLE`, clears `HIJACK_RUN`, and allows state counter to hit $T_6$ to trigger internal board clear back to $T_0$. Fetch resumes at the ISR vector address at the next $T_0$.

---

## 9. Architectural Power-On Reset State Vector

Upon assertion of `~CYCLE_RESET` (Pin 04) LOW during power-on reset:

* `PCH:PCL` $\leftarrow 0\text{x00}$ (`PCH = 0x0`, `PCL = 0x0`)
* `SP` $\leftarrow 0\text{xF}$ (Top of internal hardware stack matrix)
* `ZF`, `CF` $\leftarrow 0$ (Flags cleared)
* `IE` $\leftarrow 1$ (Interrupts enabled by default)
* `HIJACK_RUN` $\leftarrow 0$ (Interrupt hijack inactive)
* `HALT_LATCH` $\leftarrow 0$ (Halt state cleared)
* `TIMING` $\leftarrow T_0$ (State counter initialized to step 0)
* `RegA..RegD` $\leftarrow$ Unspecified (Preserves power-up bistable state)
