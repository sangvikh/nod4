# NOD-4 Microprocessor Architecture & System Specification (v13.1)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Fetch Mechanics:** Dual-Nibble Sequential Fetch (`OPCODE[3:0]`, `OPERAND[3:0]`)

**Physical Hierarchy:** 30-Pin Passive Backplane Bus $\rightarrow$ Universal Base Cards (UBC) $\rightarrow$ Point-to-Point Control Harnesses $\rightarrow$ Counter / Extended ALU / Interrupt Daughtercards

**Control Philosophy:** Centralized Control & Read-Select Multiplexing, Tree-Based Quadrant Decoder (`OP[3]=IMM`, `OP[2]=ALU_EN`), Direct-Drive Unary/Shift Matrix, Zero-Decoder Destination Routing, Internal Decoder Self-Reset, Diagonal Control Escape (`dd == ss`), Handshaked Bus-Hijack Interrupt Engine.

---

## 1. Electrical Standard, Clocking & Latch Mechanics

* **Logic Family:** Discrete NMOS pass-transistor and depletion-load logic using 2N7000 NMOS switches with active-LOW signal paths.
* **Signal Standard:** Active-LOW open-drain backplane rails with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.
* **Clocking Architecture & Phase Alignment:** Single-phase master clock (`CLK`). State transitions ($T_0 \dots T_5$) trigger on the falling edge of `CLK`.

### Two-Phase Timestep Execution Model

* **Phase 1: Setup & Drive (`CLK` LOW):** Central control decoders evaluate opcode and drive point-to-point control wires (`~OE1`, `~OE2`, `~WE`, `Latch_A`, `Latch_B`). Any combinational ripple or bus propagation occurs while `LATCH_ENABLE` is held off ($1$). Data on `BUS[3:0]` stabilizes cleanly during this window.
* **Phase 2: Latch Window (`CLK` HIGH):** Control lines remain static. Active write pulsing occurs as `CLK` transitions HIGH, driving the target latch transparent for data capture.

```text
               PHASE 1: SETUP & DRIVE         PHASE 2: LATCH WINDOW
CLK          ────────┐                       ┌───────────────────────┐
                     └───────────────────────┘                       └────────
~T[n]        ────────────────┐
 (Timestep)                  └────────────────────────────────────────────────
BUS[3:0]     ═══════════<   STABLE DATA WINDOW   >════════════════════════════
~WE[n]       ────────┐
 (Driven T_n)        └────────────────────────────────────────────────────────
LATCH_ENABLE ────────────────────────────────┐
 (~WE or ~CLK)                               └───────────────────────┘
                                             ▲                       ▲
                                             Data Transparent        Data Latched
                                             (Latch Open)            (Frozen on CLK Falling Edge)

```

### Level-Sensitive Write Mechanics

Memory elements and register cells on Universal Base Cards are level-sensitive transparent latches. Execution cards receive point-to-point control signals directly from the Central Control Board. Write enables are gated locally on each card using active-LOW logic:

$$\text{LATCH\_ENABLE}_n = \overline{\text{\textasciitilde WE}_n} \lor \overline{\text{CLK}}$$

$$\overline{\text{LATCH\_ENABLE}_n} = \text{\textasciitilde WE}_n \cdot \text{CLK}$$

Data on `BUS[3:0]` must be stable prior to `CLK` rising. Latching occurs continuously while `CLK` is HIGH and freezes on the falling edge of `CLK` or upon de-assertion of `~WE[n]`.

### Program Counter (PC) Auto-Increment Mechanics

`PC` auto-increments twice per instruction cycle: on the rising edge of $T_1$ (after Opcode fetch in $T_0$) and on the rising edge of $T_2$ (after Operand fetch in $T_1$). By $T_2$, `PC` naturally equals $\text{PC}_{\text{orig}} + 2$, providing the exact return address for `CALL`, `PUSHPC`, and hardware interrupts without auxiliary addition hardware. `PC` increment strobes are gated locally via point-to-point control harnesses during interrupt hijacks (`IR_DISABLE`).

$$\text{PC\_INC\_ENABLE} = \text{INC\_STROBE} \cdot \overline{\text{IR\_DISABLE}}$$

### Execution Flags

* **$ZF$ (Zero Flag):** Set if the 4-bit output of an operation equals $0\text{x0}$ (sampled on the trailing edge of $T_4$).
* **$CF$ (Carry/Borrow Flag):** Set on arithmetic carry-out or cleared on borrow using inverted-borrow logic (sampled on the trailing edge of $T_4$).
* **$IE$ (Interrupt Enable Flag):** Hardware latch on Interrupt Card (Set via `STI`/`RETI`, cleared via `CLI`/`IRQ` entry).

---

## 2. Canonical Instruction Encoding & Tree-Based Top-Level Decoder

Instruction execution relies on two 4-bit nibbles fetched sequentially:

* **OPCODE (`OP[3:0]`):** `[imm, alu_en, dst1, dst0]`
* **OPERAND (`OPERAND[3:0]`):**
* Moves / Escapes (`Q0`): `[code1, code0, src1, ss0]` (i.e., `[cc1, cc0, ss1, ss0]`)
* Reg-Reg ALU (`Q1`): `[alu_op1, alu_op0, ss1, ss0]`
* Load Immediate (`Q2`): `[imm3, imm2, imm1, imm0]`
* Immediate ALU / Shift (`Q3`): `[alu_op1, alu_op0, ext, imm0]`



```text
                                [ OPCODE[3:2] ]
                                 (IMM, ALU_EN)
                                       |
                +----------------------+----------------------+
                |                                             |
           ALU_EN = 1                                    ALU_EN = 0
       (Q1 Reg-Reg, Q3 Immediate)                             |
                |                               +---------------+---------------+
         • Fixed 5-Step Pipeline                |                               |
         • Resets at T5                    IMM = 1 (Q2)                    IMM = 0 (Q0)
         • Hardwired ALU Sequence:       (Load Immediate)           (Moves & Control Escapes)
           - T2: Latch B (src/imm)              |                               |
           - T3: Latch A (dst) & Compute        • Fixed 3-Step                  • Moves: Reset at T3
           - T4: Write ALU_OUT -> dst           • Resets at T3                  • Untaken Branch: Reset at T2 (FAIL)
                                                • Direct OPERAND -> BUS         • Taken Branch / RET: Reset at T4
                                                                                • CALL / NOP / IRQ: Reset at T6

```

### Top-Level Quadrant Decode Table

| Quadrant | Binary (`OP[3:2]`) | Bit Flags (`IMM`, `ALU_EN`) | Functional Class | Micro-Control Routing & Timing |
| --- | --- | --- | --- | --- |
| **Q0** | `00` | `IMM = 0`, `ALU_EN = 0` | Data Moves & Control Escapes | Sub-decodes reset points. Supports diagonal control escapes ($dd == ss$). Resets at $T_2$ (untaken branch), $T_3$ (moves/LDI writeback done at $T_2$), $T_4$ (taken branch/RET), or $T_6$ (CALL/NOP/~IRQ). |
| **Q1** | `01` | `IMM = 0`, `ALU_EN = 1` | Reg-to-Reg Binary ALU | Hardwired 5-step pipeline. $T_2$: Latch $src \rightarrow \text{ALU}_B$; $T_3$: Read Mux toggles to $dst \rightarrow \text{ALU}_A$ & Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$. Resets at $T_5$. |
| **Q2** | `10` | `IMM = 1`, `ALU_EN = 0` | Load Immediate (`LDI`) | Drives `OPERAND[3:0]` directly to `BUS[3:0]`. Writes to $dst$ at $T_2$. Fixed 3-step execution; resets at $T_3$. |
| **Q3** | `11` | `IMM = 1`, `ALU_EN = 1` | Immediate ALU & Shift Matrix | Hardwired 5-step pipeline. $T_2$: Latch $imm \rightarrow \text{ALU}_B$; $T_3$: Read Mux toggles to $dst \rightarrow \text{ALU}_A$ & Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$. Resets at $T_5$. |

### 5-Transistor Branch Steering Tree (`FAIL` Logic)

```text
                     OPERAND[1:0] Bits (P1, P0) & Flag Inputs
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
   P0 = 0 (~P0)                                                      P0 = 1 (P0)
   (Check Zero / Carry)                                             (Check Not Zero)
        │                                                                 │
  ┌─────┴─────┐                                                           │
  ▼           ▼                                                           ▼
P1 = 0      P1 = 1                                                      P1 = 0
(~P1)       (P1)                                                        (~P1)
  │           │                                                           │
  ▼           ▼                                                           ▼
~ZF = 1     ~CF = 1                                                     ZF = 1
  │           │                                                           │
  └─────┬─────┘                                                           │
        ▼                                                                 ▼
    [ PASS 1 ]                                                        [ PASS 2 ]
        │                                                                 │
        └────────────────────────────────┬────────────────────────────────┘
                                         ▼
                                  OR Gate Terminal
                                         │
                                         ▼
                                   FAIL Output ───► Triggers ~CYCLE_RESET at T2 Jumper

```

$$\text{Let } P_1 = \text{OPERAND}[1] \text{ and } P_0 = \text{OPERAND}[0]$$

$$\text{FAIL} = \overline{P_0} \cdot (\overline{P_1} \cdot \overline{ZF} \lor P_1 \cdot \overline{CF}) \lor P_0 \cdot (\overline{P_1} \cdot ZF)$$

---

## 3. Centralized Decoder & Point-to-Point Harness Routing

To minimize backplane pin count to 30 pins, peripheral execution cards contain zero local timestep decoding or clock-gating logic. All state decoding and phase-multiplexing occur centrally on the Control/Decoder Board and are routed to peripheral execution units via point-to-point control harnesses.

```text
                             ┌─────────────────────────┐
                             │     Central Decoder     │
                             │  (Read Mux: SRC vs DST) │
                             └────┬───────────────┬────┘
                                  │               │
            Point-to-Point        │               │ Point-to-Point
            Control Harness       │               │ Control Harness
                                  ▼               ▼
                       ┌──────────────┐       ┌──────────────┐
                       │ Register Card│       │   ALU Card   │
                       └──────────────┘       └──────────────┘
                       • ~WE                  • Latch_A (Dst)
                       • ~OE1 (Src Select)    • Latch_B (Src)
                       • ~OE2 (Dst Select)    • Writeback (ALU_OE)

```

### Point-to-Point Harness Signal Definitions

* **Register Cards (`RegA..RegD`):**
* `~WE`: Level-sensitive write enable driven directly during writeback ($T_2$ for MOV/LDI, $T_4$ for ALU).
* `~OE1`: Read Port 1 Output Enable (driven when register is selected as SRC during $T_2$).
* `~OE2`: Read Port 2 Output Enable (driven when register is selected as DST during $T_3$).


* **ALU Card:**
* `Latch_B`: Clock strobe to latch source operand from `BUS[3:0]` into Input Buffer B at $T_2$.
* `Latch_A`: Clock strobe to latch destination operand from `BUS[3:0]` into Input Buffer A at $T_3$.
* `Writeback`: Asserts ALU tri-state bus driver (`ALU_OUT` $\rightarrow$ `BUS[3:0]`) during $T_4$.


* **Control / Timing Cards:**
* `IR_DISABLE`: Point-to-point harness wire freezing `PC` auto-increment and forcing `0x00` (`NOP`) into execution latches during interrupt hijacks.


* **Register Read-Select Multiplexing:**
* $T_2$ (Default Read Phase): Read-decoder routes `OPERAND[1:0]` (`SRC`) to activate `~OE1` on the source register.
* $T_3$ (Muxed Destination Phase): Central Decoder toggles the read-select mux to target `OPCODE[1:0]` (`DST`), activating `~OE2` on the target destination register for ALU latching.



---

## 4. Cycle Reset Engine & Termination Points

Early cycle termination is governed by combinational state logic on the Central Control/Decoder Board routing directly to the TIMING board's `~CLR` line.

### Reset Point Breakdown

* **$T_2 \cdot \text{FAIL}$:** Untaken branch (`Jcc` condition evaluates FALSE). Steering tree evaluates combinationally during $T_2$ and terminates the cycle instantly at $T_2$, leaving `PC` perfectly aligned at $\text{PC}_0 + 2$.
* **$T_3 \cdot \text{Q2\_LDI}$:** Load Immediate (`LDI`) finishes writeback at $T_2$; resets at $T_3$ entry.
* **$T_3 \cdot \text{Q0\_MOVE}$:** Standard register/memory move (`MOV`, `LD`, `ST`) finishes writeback at $T_2$; resets at $T_3$ entry.
* **$T_4 \cdot \text{JMP\_RET}$:** Taken branch (`JMP`, `Jcc`) or Return (`RET`) loads `PCL` at $T_2$ and `PCH` at $T_3$; resets at $T_4$ entry.
* **$T_5 \cdot \text{ALU\_EN}$:** ALU operations (`Q1` Reg-Reg & `Q3` Immediate) read operands at $T_2$/$T_3$ and write back at $T_4$; resets at $T_5$ entry via `ALU_EN` (`OP[2] = 1`).
* **Internal $T_6$ Clear:** Subroutine Call (`CALL`), `NOP`, and Hardware Interrupt Hijack (`~IRQ`) run through $T_5$. The TIMING card self-resets at $T_6$ via direct hardware feedback ($\overline{T_6} \rightarrow \overline{\text{CLR}}$).

---

## 5. Micro-Step Pipeline & Timing Matrix ($T_0 \dots T_6$)

### Detailed Pipeline Phase Definitions

* **$T_0$ (Opcode Fetch):** `~OE[PCH]` and `~OE[PCL]` drive `PC` to `ADDR_H/L`. Memory asserts `~MEM_OE`, driving opcode onto `BUS[3:0]`. Opcode is latched into `OPCODE[3:0]` when `CLK` goes HIGH.
* **$T_1$ (Operand Fetch):** On $T_1$ entry (`CLK` LOW), `PC` increments ($\text{PC} \leftarrow \text{PC}_0 + 1$). Memory asserts `~MEM_OE`, driving operand onto `BUS[3:0]`. Operand is latched into `OPERAND[3:0]` when `CLK` goes HIGH.
* **$T_2$ (Source Drive / Setup / Early Branch Termination):** On $T_2$ entry (`CLK` LOW), `PC` increments again ($\text{PC} \leftarrow \text{PC}_0 + 2$).
* *Untaken Branch:* Steering tree evaluates $\text{FAIL}=1$. State counter resets immediately at $T_2$, aborting execution.
* *MOV dst, src:* Central decoder asserts `~OE1[src]` and `~WE[dst]` simultaneously. Operation completes writeback at $T_2$.
* *ALU Ops:* Central decoder asserts `~OE1[src]` (or `~OE[OPERAND]`), asserting `Latch_B` to capture source into ALU Input B.
* *Interrupt / CALL:* Pushes $\text{PCL}_{\text{return}}$ ($\text{PC}_0+2$) to Stack.


* **$T_3$ (Muxed Destination Read / Compute Phase):**
* *Moves / LDI:* State counter resets at $T_3$ entry.
* *ALU Ops:* Central decoder toggles read mux to target DST, asserting `~OE2[dst]` and `Latch_A` to capture destination into ALU Input A. ALU computes result asynchronously.
* *Interrupt / CALL:* Pushes $\text{PCH}_{\text{return}}$ ($\text{PC}_0+2$) to Stack.


* **$T_4$ (ALU Writeback / ISR Page Load):**
* *ALU Ops:* Central decoder asserts ALU Writeback (drives `BUS[3:0]`) and `~WE[dst]`. Flags ($ZF, CF$) are sampled on the trailing edge of $T_4$.
* *Hardware Interrupt:* Central Interrupt Card drives fixed ISR Page Vector (e.g., `0xF`) onto `BUS[3:0]` and strobes `~WE_PCH`.


* **$T_5$ (Reset State / ISR Offset Vector Load):**
* *ALU Ops:* State machine settles, state counter resets to $T_0$.
* *Hardware Interrupt:* Central Controller asserts `~IRQ_ACK` (Pin 07) + `~WE_PCL`. Active Requesting I/O Card drives its 4-bit offset vector (e.g., `0x2`) onto `BUS[3:0]`. Resets to $T_0$ at $T_6$.



### Complete Micro-Step Timing Matrix

| Instruction Class | $T_0$ (Opcode Fetch) | $T_1$ (Operand Fetch, PC+1) | $T_2$ (Drive / Latch B, PC+2) | $T_3$ (Latch A / Compute) | $T_4$ (ALU Writeback / ISR Page) | $T_5$ (Reset / ISR Offset) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move** (`MOV dst, src`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE1[src]` $\rightarrow$ BUS & `~WE[dst]` ($\text{PC} \leftarrow \text{PC}+1$) | Reset state | — | — |
| **Q0: Memory Store** (`ST MEM, src`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Drive RegC:RegD to ADDR, Assert `~OE1[src]` & `~MEM_WE` ($\text{PC} \leftarrow \text{PC}+1$) | Reset state | — | — |
| **Q0: Memory Load** (`LD dst, MEM`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Drive RegC:RegD to ADDR, Assert `~MEM_OE` & `~WE[dst]` ($\text{PC} \leftarrow \text{PC}+1$) | Reset state | — | — |
| **Q0: Jump Untaken** (`Jcc False`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Evaluate Steering Tree $\rightarrow$ FAIL=1, Terminate instantly at $T_2$ | — | — | — |
| **Q0: Jump Taken** (`JMP`, `Jcc True`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE1[RegD]` $\rightarrow$ BUS & `~WE[PCL]` ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE1[RegC]` $\rightarrow$ BUS & `~WE[PCH]` | Reset state | — |
| **Q0: Subroutine Call** (`CALL`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Push $PCL$ ($\text{PC}_0+2$) $\rightarrow \text{STK}$ ($\text{PC} \leftarrow \text{PC}+1$) | Push $PCH$ ($\text{PC}_0+2$) $\rightarrow \text{STK}$ | Assert `~OE1[RegD]` & `~WE[PCL]` | Assert `~OE1[RegC]` & `~WE[PCH]` (Self-Reset $T_6$) |
| **Q0: Return** (`RET` / `RETI`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Pop $\text{STK} \rightarrow PCH$ ($\text{PC} \leftarrow \text{PC}+1$) | Pop $\text{STK} \rightarrow PCL$ | Reset state | — |
| **Q1: Reg-Reg ALU** (`ADD`, `SUB`, etc.) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE1[src]` $\rightarrow$ `Latch_B` ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE2[dst]` $\rightarrow$ `Latch_A`, Compute | Assert Writeback $\rightarrow \text{BUS}$ & `~WE[dst]`, Sample Flags | Reset state |
| **Q2: Load Immediate** (`LDI dst, #imm`) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE[OPERAND]` $\rightarrow$ BUS & `~WE[dst]` ($\text{PC} \leftarrow \text{PC}+1$) | Reset state | — | — |
| **Q3: Immediate ALU** (`ADDI`, etc.) | Fetch Opcode $\rightarrow$ OPCODE | Fetch Operand $\rightarrow$ OPERAND ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE[OPERAND]` $\rightarrow$ `Latch_B` ($\text{PC} \leftarrow \text{PC}+1$) | Assert `~OE2[dst]` $\rightarrow$ `Latch_A`, Compute | Assert Writeback $\rightarrow \text{BUS}$ & `~WE[dst]`, Sample Flags | Reset state |
| **Hardware Interrupt** (`~IRQ Entry`) | Freeze $PC$, force NOP via `IR_DISABLE` | Fetch NOP Operand (`IR_DISABLE` LOW) | Push $PCL_{\text{return}}$ ($\text{PC}_0+2$) $\rightarrow \text{STK}$ | Push $PCH_{\text{return}}$ ($\text{PC}_0+2$) $\rightarrow \text{STK}$ | Interrupt Card drives Page $\rightarrow PCH$ (`~WE_PCH`) | Assert `~IRQ_ACK` (Pin 07), Requesting I/O drives Offset $\rightarrow PCL$ (`~WE_PCL`) |

---

## 6. Master Backplane Pinout & Card Slot Mapping

```text
 SYSTEM & CONTROL (01-07)          FLAGS & MEMORY (08-11)          PARALLEL NIBBLE BUSES (12-30)
[ 01-03 ] Power & Clock           [ 08-09 ] Flags (ZF, CF)        [ 12-15 ] Data Bus (BUS)
[ 04-05 ] OPERAND[3], HALT_STAT   [ 10-11 ] Memory OE / WE  --->  [ 16-19 ] Address High (ADDR_H)
[ 06-07 ] IRQ Request & ACK                                       [ 20-23 ] Address Low (ADDR_L)
                                                                  [ 24-27 ] Opcode Rail (OPCODE)
                                                                  [ 28-30 ] Operand Rail (OPERAND[0:2])

```

### Exact 30-Pin Backplane Pinout Table

| Pin # | Signal Name | Domain | Description & Interconnect Target |
| --- | --- | --- | --- |
| **01** | `GND` | Power | System Ground Reference Return |
| **02** | `VCC` | Power | $+5\text{V}$ Main Power Rail |
| **03** | `CLK` | Timing | Single-Phase Master System Clock Input |
| **04** | `OPERAND[3]` | Control | Latched Instruction Operand Nibble Bus (Bit 3) |
| **05** | `~HALT_STAT` | System | Active-LOW Hardware Halt / Wait-For-Interrupt Status Rail |
| **06** | `~IRQ` | System | Active-LOW Open-Drain Hardware Interrupt Request Rail |
| **07** | `~IRQ_ACK` | System | Active-LOW Interrupt Acknowledge Broadcast Rail (Asserted $T_5$) |
| **08** | `~ZF` | Flag | Active-LOW Zero Flag Bus Rail |
| **09** | `~CF` | Flag | Active-LOW Carry / Borrow Flag Bus Rail |
| **10** | `~MEM_WE` | Memory | Shared Memory Write Enable Control Rail |
| **11** | `~MEM_OE` | Memory | Shared Memory Output Enable Control Rail |
| **12–15** | `BUS[0:3]` | Data | Bidirectional 4-Bit Main System Data Bus |
| **16–19** | `ADDR_H[0:3]` | Address | Memory Address High Nibble Bus |
| **20–23** | `ADDR_L[0:3]` | Address | Memory Address Low Nibble Bus |
| **24–27** | `OPCODE[0:3]` | Control | Latched Instruction Opcode Nibble Bus |
| **28–30** | `OPERAND[0:2]` | Control | Latched Instruction Operand Nibble Bus (Bits 0–2) |

---

## 7. Universal Base Card (UBC) & Harness Interfaces

```text
                      30-PIN PASSIVE BACKPLANE BUS
 ───────────────────────────────────┬───────────────────────────────────
   BUS[3:0]  ADDR_H/L  OPCODE/OPERAND  CLK  ~HALT_STAT  ~IRQ  ~IRQ_ACK
      │         │            │          │        │        │       │
 ┌────┼─────────┼────────────┼──────────┼────────┼────────┼───────┼───┐
 │    │         │            │          │        │        │       │   │
 │    ▼         │            │          │        │        │       │   │
 │ ┌──────┐     │            │          │        │        │       │UBC│
 │ │Bus   │     │            │          │        │        │       │CARD
 │ │Buffer│     │            │          │        │        │       │   │
 │ └──┬───┘     │            │          │        │        │       │   │
 │    │         │            │          │        │        │       │   │
 │    │         │            ▼          │        │        │       │   │
 │    │         │    POINT-TO-POINT     │        │        │       │   │
 │    │         │    CONTROL HARNESS    │        │        │       │   │
 │    │         │  (~WE, ~OE1, ~OE2)    │        │        │       │   │
 │    │         │         │             │        │        │       │   │
 │    │         │         ▼             │        │        │       │   │
 │ ┌──┴─────────┴───────────┐           │        │        │       │   │
 │ │ 4x Discrete NMOS       │◄──────────┘        │        │       │   │
 │ │ Transparent D-Latches  │                    │        │       │   │
 │ └────────────┬───────────┘                    │        │       │   │
 │              │ Direct Output                  │        │       │   │
 │              ├─────────────────┐              │        │       │   │
 │              ▼                 ▼              │        │       │   │
 │       ADDR_H / ADDR_L    ┌───────────┐        │        │       │   │
 │                          │ HDR 3     │        │        │       │   │
 │                          │ External  │        │        │       │   │
 │                          └───────────┘        │        │       │   │
 │                                               │        │       │   │
 │   13-PIN DAUGHTERCARD INTERFACE SOCKET        │        │       │   │
 │ ┌─────────────────────────────────────────────┴────────┴───────┴─┐ │
 │ │ Pins 1-2: VCC / GND                                                │ │
 │ │ Pins 3-4: Direct Control Lines (e.g. Counter Increment Strobes)     │ │
 │ │ Pin 5:    ~COUNT_LATCH (Base Card Internal Latch Pulse)            │ │
 │ │ Pins 6-9: D[0:3] Data Inputs  │  Pins 10-13: Q[0:3] Latch Outputs │ │
 │ └────────────────────────────────────────────────────────────────────┘ │
 └────────────────────────────────────────────────────────────────────────┘

```

---

## 8. Quadrant Instruction Matrix & Sub-Operations

### Quadrant 0 (`OP[3:2] = 00`): Data Moves & Diagonal Control Escapes

#### 1. Standard Data Moves ($dd \neq ss$)

* **Format:** `OPCODE[3:0] = 00 dd`, `OPERAND[3:0] = cc ss`
* $\text{DST Slot} = \{cc[1], dd[1:0]\}$, $\text{SRC Slot} = \{cc[0], ss[1:0]\}$
* `cc = 00`: `MOV reg, reg` (Reg $0..3 \rightarrow$ Reg $0..3$)
* `cc = 01`: `ST sys, reg` (Reg $0..3 \rightarrow$ Sys $4..7$)
* `cc = 10`: `LD reg, sys` (Sys $4..7 \rightarrow$ Reg $0..3$)
* `cc = 11`: `MOV sys, sys` (Sys $4..7 \rightarrow$ Sys $4..7$)



#### 2. Diagonal Control Escapes ($dd == ss$)

When source register index equals destination register index (`OP[1:0] == OPERAND[1:0]`), the standard move path is bypassed, interpreting $dd == ss$ as the escape class and $cc = \text{OPERAND}[3:2]$ as the sub-operation.

| Opcode | Operand | Hex | Mnemonic | Escape Class & Operational Logic |
| --- | --- | --- | --- | --- |
| `0000` | `0000` | `0x00` | `NOP` | System ($dd=00, ss=00, cc=00$): Forced during `IR_DISABLE`. Resets at $T_6$. |
| `0001` | `0001` | `0x11` | `CLI` | Flags ($dd=01, ss=01, cc=00$): Clear Interrupt Enable Flag ($IE \leftarrow 0$). Resets at $T_3$. |
| `0001` | `0101` | `0x15` | `STI` | Flags ($dd=01, ss=01, cc=01$): Set Interrupt Enable Flag ($IE \leftarrow 1$). Resets at $T_3$. |
| `0001` | `1001` | `0x19` | `RETI` | Flags ($dd=01, ss=01, cc=10$): Return from IRQ: Pop $PCH:PCL$, $IE \leftarrow 1$. Resets at $T_4$. |
| `0001` | `1101` | `0x1D` | `HALT` | Flags ($dd=01, ss=01, cc=11$): Asserts Halt Latch, gates master clock, asserts `~HALT_STAT` (Pin 05). |
| `0010` | `0010` | `0x22` | `JZ` / `JE` | Branch ($dd=10, ss=10, cc=00$): Branch to RegC:RegD if $ZF=1$. $\text{FAIL} = \overline{ZF}$. |
| `0010` | `0110` | `0x26` | `JNZ` / `JNE` | Branch ($dd=10, ss=10, cc=01$): Branch to RegC:RegD if $ZF=0$. $\text{FAIL} = ZF$. |
| `0010` | `1010` | `0x2A` | `JC` / `JAE` | Branch ($dd=10, ss=10, cc=10$): Branch to RegC:RegD if $CF=1$. $\text{FAIL} = \overline{CF}$. |
| `0010` | `1110` | `0x2E` | `JMP` | Branch ($dd=10, ss=10, cc=11$): Unconditional Branch. $\text{FAIL} = 0$. Resets at $T_4$. |
| `0011` | `0011` | `0x33` | `CALL` | Stack ($dd=11, ss=11, cc=00$): Push $PCL, PCH$, load RegC:RegD into PCH:PCL. Resets at $T_6$. |
| `0011` | `0111` | `0x37` | `RET` | Stack ($dd=11, ss=11, cc=01$): Pop $PCH, PCL$ from stack into PCH:PCL. Resets at $T_4$. |
| `0011` | `1011` | `0x3B` | `PUSHPC` | Stack ($dd=11, ss=11, cc=10$): Push current $PCL, PCH$ ($PC_0+2$) to stack. Resets at $T_4$. |

---

### Quadrant 1 (`OP[3:2] = 01`): Reg-to-Reg Binary ALU

* **Opcode Format:** `OPCODE[3:0] = 01 dd` ($dd$ = Target Register `RegA..RegD`)
* **Operand Format:** `OPERAND[3:0] = alu_op1 alu_op0 ss1 ss0` ($ss$ = Source Register `RegA..RegD`)
* **Execution:** Fixed 5-step execution (resets at $T_5$). Uses the 4-op control model (`invert_b`, `carry_kill`, and dedicated `AND` tap).

| Opcode | Operand | Mnemonic | ALU Function | Operational Pipeline Sequence | Flag Updates |
| --- | --- | --- | --- | --- | --- |
| `01 dd` | `00 ss` | `ADD dst, src` | Binary Addition ($C_{in}=0, \text{invert\_b}=0$) | $T_2$: $src \rightarrow \text{Latch}_B$; $T_3$: $dst \rightarrow \text{Latch}_A$, Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$ | $ZF, CF$ |
| `01 dd` | `01 ss` | `SUB dst, src` | Binary Subtraction ($C_{in}=1, \text{invert\_b}=1$) | $T_2$: $src \rightarrow \text{Latch}_B$; $T_3$: $dst \rightarrow \text{Latch}_A$, Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$ | $ZF, CF$ |
| `01 dd` | `10 ss` | `XOR dst, src` | Bitwise XOR ($\text{carry\_kill}=1$) | $T_2$: $src \rightarrow \text{Latch}_B$; $T_3$: $dst \rightarrow \text{Latch}_A$, Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$ | $ZF$ ($CF \leftarrow 0$) |
| `01 dd` | `11 ss` | `AND dst, src` | Bitwise AND (Dedicated Tap) | $T_2$: $src \rightarrow \text{Latch}_B$; $T_3$: $dst \rightarrow \text{Latch}_A$, Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$ | $ZF$ ($CF \leftarrow 0$) |

---

### Quadrant 2 (`OP[3:2] = 10`): Load Immediate (`LDI`)

* **Opcode Format:** `OPCODE[3:0] = 10 dd` ($dd$ = Target Register `RegA..RegD`)
* **Operand Format:** `OPERAND[3:0] = imm3 imm2 imm1 imm0` (4-Bit Immediate Value `#imm`)
* **Execution:** Fixed 3-step execution (resets at $T_3$).

| Opcode | Operand | Mnemonic | Target Register | Execution Sequence ($T_2$) |
| --- | --- | --- | --- | --- |
| `10 00` | `imm[3:0]` | `LDI RegA, #imm` | `RegA` (Slot 0) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[0]` |
| `10 01` | `imm[3:0]` | `LDI RegB, #imm` | `RegB` (Slot 1) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[1]` |
| `10 10` | `imm[3:0]` | `LDI RegC, #imm` | `RegC` (Slot 2) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[2]` |
| `10 11` | `imm[3:0]` | `LDI RegD, #imm` | `RegD` (Slot 3) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~OE[OPERAND]` & `~WE[3]` |

---

### Quadrant 3 (`OP[3:2] = 11`): Immediate ALU & Shift Matrix

* **Opcode Format:** `OPCODE[3:0] = 11 dd` ($dd$ = Target Register `RegA..RegD`)
* **Operand Format:** `OPERAND[3:0] = [ALU_OP1, ALU_OP0, EXT, IMM0]`

$$\text{OPERAND}[3:0] = [\text{ALU\_OP1} \mid \text{ALU\_OP0} \mid \text{EXT} \mid \text{IMM0}]$$

| ALU_OP[1:0] | EXT | IMM0 | Binary Mnemonic | Operational Pipeline Sequence & Carry Logic |
| --- | --- | --- | --- | --- |
| `00` | `0` | `0` | `ADCI dst` | Add with Carry: $dst \leftarrow dst + 0 + CF$ ($C_{in} = CF$) |
| `00` | `0` | `1` | `INCI dst` | Increment: $dst \leftarrow dst + 1$ ($C_{in} = 0$) |
| `01` | `0` | `0` | `SBBI dst` | Subtract with Borrow: $dst \leftarrow dst - 0 - (1 - CF)$ |
| `01` | `0` | `1` | `DECI dst` | Decrement: $dst \leftarrow dst - 1$ ($C_{in} = 1$) |
| `10` | `0` | `0` | `XORII dst, 0` | Bitwise XOR with 0 (Preserves value, updates $ZF$) |
| `10` | `0` | `1` | `XORII dst, 1` | Bitwise XOR with 1 (Flips Bit 0) |
| `11` | `0` | `0` | `ANDII dst, 0` | Bitwise AND with 0 (Clears register to $0\text{x0}$, sets $ZF$) |
| `11` | `0` | `1` | `ANDII dst, 1` | Bitwise AND with 1 (Isolates Bit 0) |
| `00` | `1` | `x` | `NOT dst` | Bitwise Invert via NMOS pull-down array |
| `01` | `1` | `x` | `SHR dst` | Logical Shift Right: $D_3 \leftarrow 0, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |
| `10` | `1` | `x` | `RCR dst` | Rotate Right thru Carry: $D_3 \leftarrow CF, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |
| `11` | `1` | `x` | `ASR dst` | Arithmetic Shift Right: $D_3 \leftarrow D_3, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |

---

## 9. Hardware Vector Hijack Subsystem & Handshaked Vector Injection

```text
                        ~IRQ Assertion (Pin 06 = LOW)
                                     │
                                     ▼
                            [ Latch IRQ_REQ ]
                                     │
                        Sampled at T0 Entry (if IE=1)
                                     │
                                     ▼
                      Assert IR_DISABLE Harness LOW
                     ┌────────────────────────────────┐
                     │ • Freeze PC Increment Logic    │
                     │ • Force NOP (0x00) to Pipeline │
                     │ • Clear IE Flag (IE = 0)       │
                     └────────────────┬───────────────┘
                                      │
       ┌──────────────────────────────┴──────────────────────────────┐
       │                                                             │
       ▼                                                             ▼
  [ Timestep T0..T1 ]                                           [ Timestep T2 ]
  Fetch Forced NOP                                              Push PCL_return -> STK
  (PC frozen at PC0 + 2)                                        (Stack Write ~WE_STK)
       │                                                             │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
       ┌──────────────────────────────┴──────────────────────────────┐
       │                                                             │
       ▼                                                             ▼
  [ Timestep T3 ]                                               [ Timestep T4 ]
  Push PCH_return -> STK                                        Interrupt Card Drives Page Address
  (Stack Write ~WE_STK)                                         PCH Latch (~WE_PCH)
       │                                                             │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                                [ Timestep T5 ]
                         Assert ~IRQ_ACK (Pin 07 LOW)
                       Requesting I/O Drives Offset Vector
                             PCL Latch (~WE_PCL)
                                      │
                                      ▼
                         [ Timestep T6: Self-Reset ]
                         Counter clears to T0, resumes
                         execution at ISR vector address.

```
