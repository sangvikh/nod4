# NOD-4 Microprocessor Architecture & System Specification (v13.3)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Fetch Mechanics:** Dual-Nibble Sequential Fetch (`OPCODE[3:0]`, `OPERAND[3:0]`)

**Physical Hierarchy:** 30-Pin Passive Backplane Bus $\rightarrow$ Dual-Register Universal Base Cards (UBC) $\rightarrow$ Point-to-Point Control Harnesses $\rightarrow$ Counter / Extended ALU / Interrupt Daughtercards

**Control Philosophy:** Centralized Control & Read-Select Multiplexing, Tree-Based Quadrant Decoder (`OP[3]`=IMM, `OP[2]`=ALU_EN), Direct-Drive Unary/Shift Matrix, Zero-Decoder Destination Routing, Internal Decoder Self-Reset, Diagonal Control Escape ($dd == ss$) with Read/Write Decoder Suppression, Handshaked Bus-Hijack Interrupt Engine.

---

## 1. Electrical Standard, Clocking & Latch Mechanics

### Logic Family & Signal Standard

* **Logic Family:** Discrete NMOS pass-transistor and depletion-load logic using 2N7000 NMOS switches with active-LOW signal paths.
* **Signal Standard:** Active-LOW open-drain backplane rails with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.

### Physical Register Layout (Dual-Register Cards)

To optimize backplane harness routing and PCB real estate, registers are grouped **2 per Universal Base Card (UBC)**:

* **Register Card 1 (UBC-REG1):** Houses **RegA** (`00`) and **RegB** (`01`).
* **Register Card 2 (UBC-REG2):** Houses **RegC** (`10`) and **RegD** (`11`). Also drives the 8-bit Address Rails (`ADDR_H` from RegC, `ADDR_L` from RegD).

```
   +-------------------------------------------------------------------+
   |                    CENTRAL CONTROL BOARD                          |
   +-------------------------------------------------------------------+
       |               |                           |               |
   Harness 1       Harness 2                   Harness 3       Harness 4
       |               |                           |               |
       v               v                           v               v
+--------------+ +--------------+           +--------------+ +--------------+
|   UBC-REG1   | |   UBC-REG2   |           |   ALU CARD   | | TIMING/IRQC  |
| RegA | RegB  | | RegC | RegD  |           | Latch A/B    | | 8-Level Stack|
+--------------+ +--------------+           +--------------+ +--------------+

```

### Clocking Architecture & Phase Alignment

Single-phase master clock (CLK). State transitions ($T_0 \dots T_5$) trigger on the falling edge of CLK.

#### Two-Phase Timestep Execution Model

* **Phase 1: Setup & Drive (CLK HIGH):** Central control decoders evaluate opcode and drive point-to-point control wires (`~OE1`, `~OE2`, `~WE`, `Latch_A`, `Latch_B`). Any combinational ripple or bus propagation occurs while `LATCH_ENABLE` is held off ($1$). Data on `BUS[3:0]` stabilizes cleanly during this window. Active-LOW logic on interfaces simplifies discrete routing, minimizing inverter count.
* **Phase 2: Latch Window (CLK LOW):** Control lines remain static. Active write pulsing occurs as CLK transitions LOW, driving the target level-sensitive transparent latch into transparent state for data capture.

```
               PHASE 1: SETUP & DRIVE         PHASE 2: LATCH WINDOW
             ┌───────────────────────┐                       ┌────────
CLK          │                       └───────────────────────┘
~T[n]        ────────────────┐ (Timestep)
             └────────────────────────────────────────────────────────
BUS[3:0]     ═══════════<   STABLE DATA WINDOW   >════════════════════════════
~WE[n]       ────────┐ (Driven T_n)
                     └────────────────────────────────────────────────────────
LATCH_ENABLE ────────────────────────────────┐ (~WE or CLK)
                                             └───────────────────────┘
                                             ▲                       ▲
                                             Data Transparent        Data Latched
                                             (Latch Open)            (Frozen on CLK Rising Edge)

```

### Level-Sensitive Write Mechanics

Memory elements and register cells on Universal Base Cards are level-sensitive transparent latches. Execution cards receive point-to-point control signals directly from the Central Control Board. Write enables are gated locally on each card with CLK LOW using active-LOW logic:

$$\text{LATCH\_ENABLE}_n = \overline{\text{\textasciitilde WE}_n} \cdot \overline{\text{CLK}}$$

$$\overline{\text{LATCH\_ENABLE}_n} = \text{\textasciitilde WE}_n \lor \text{CLK}$$

Data on `BUS[3:0]` must be stable prior to CLK falling. Latching occurs continuously while CLK is LOW and freezes on the rising edge of CLK or upon de-assertion of `~WE[n]`.

### Program Counter (PC) Auto-Increment Mechanics

PC auto-increments twice per instruction cycle: on the rising edge of $T_1$ (after Opcode fetch in $T_0$) and on the rising edge of $T_2$ (after Operand fetch in $T_1$). By $T_2$, PC naturally equals $\text{PC}_{\text{orig}} + 2$, providing the exact return address for `CALL`, `PUSHPC`, and hardware interrupts without auxiliary addition hardware. PC increment strobes are gated locally via point-to-point control harnesses during interrupt hijacks (`IR_DISABLE`).

$$\text{PC\_INC\_ENABLE} = \text{INC\_STROBE} \cdot \overline{\text{IR\_DISABLE}}$$

### Execution Flags & Secondary Shadow Latches

* **$ZF$ (Zero Flag):** Set if the 4-bit output of an operation equals `0x0` (sampled on the trailing edge of $T_4$).
* **$CF$ (Carry/Borrow Flag):** Set on arithmetic carry-out or cleared on borrow using inverted-borrow logic (sampled on the trailing edge of $T_4$).
* **$IE$ (Interrupt Enable Flag):** Hardware latch on Interrupt Card (Set via `STI`/`RETI`, cleared via `CLI`/IRQ entry).
* **Secondary Shadow Flag Latches ($ZF_{\text{shadow}}$, $CF_{\text{shadow}}$):** Hardware-managed secondary flag latches automatically back up $ZF$ and $CF$ upon hardware interrupt acknowledgment (`~IRQ_ACK`) and restore them automatically upon executing `RETI`. This preserves processor flags across interrupts without consuming opcode space or requiring explicit push/pop flag instructions.

---

## 2. Canonical Instruction Encoding & Top-Level Decoder

Instruction execution relies on two 4-bit nibbles fetched sequentially:

* **OPCODE (`OP[3:0]`):** `[imm, alu_en, dst1, dst0]`
* **OPERAND (`OPERAND[3:0]`):**
* **Moves / Escapes / Skips (Q0):** `[cc1, cc0, ss1, ss0]`
* **Reg-Reg ALU (Q1):** `[alu_op1, alu_op0, ss1, ss0]`
* **Load Immediate (Q2):** `[imm3, imm2, imm1, imm0]`
* **Immediate ALU / Shift (Q3):** `[alu_op1, alu_op0, ext, imm0]`



```
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
         • Hardwired ALU Sequence:       (Load Immediate)           (Moves, Control Escapes,
           - T2: Latch B (src/imm)              |                    & Conditional Skips)
           - T3: Latch A (dst) & Compute        • Fixed 3-Step                  |
           - T4: Write ALU_OUT -> dst           • Resets at T3           • Moves: Reset at T3
                                                • Direct OPERAND -> BUS  • Untaken SKP: Reset at T2
                                                                         • Taken SKP: Reset at T3 (2nd PC_INC)
                                                                         • JU / GETPC / RET / DROP: Reset at T4
                                                                         • CALL / NOP / SRESET / IRQ: Reset at T6

```

### Top-Level Quadrant Decode Table

| Quadrant | Binary (`OP[3:2]`) | Bit Flags (`IMM, ALU_EN`) | Functional Class | Micro-Control Routing & Timing |
| --- | --- | --- | --- | --- |
| **Q0** | `00` | `IMM = 0, ALU_EN = 0` | Data Moves, Conditional Skips (`SZ/SNZ/SC/SNC`), System Control Escapes | Sub-decodes reset points. Supports diagonal control escapes ($dd == ss$) with Read/Write decoder suppression. Resets at $T_2$ (untaken skip), $T_3$ (moves / taken skip), $T_4$ (`JU`/`GETPC`/`RET`/`DROP`), or $T_6$ (`CALL`/`NOP`/`SRESET`/`~IRQ`). |
| **Q1** | `01` | `IMM = 0, ALU_EN = 1` | Reg-to-Reg Binary ALU | Hardwired 5-step pipeline. $T_2$: Latch $src \rightarrow \text{ALU}_B$; $T_3$: Read Mux toggles to $dst \rightarrow \text{ALU}_A$ & Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$. Resets at $T_5$. |
| **Q2** | `10` | `IMM = 1, ALU_EN = 0` | Load Immediate (`LDI`) | Drives `OPERAND[3:0]` directly to `BUS[3:0]`. Writes to $dst$ at $T_2$. Fixed 3-step execution; resets at $T_3$. |
| **Q3** | `11` | `IMM = 1, ALU_EN = 1` | Immediate ALU & Shift Matrix | Hardwired 5-step pipeline. $T_2$: Latch $imm \rightarrow \text{ALU}_B$; $T_3$: Read Mux toggles to $dst \rightarrow \text{ALU}_A$ & Compute; $T_4$: $\text{ALU}_{\text{OUT}} \rightarrow dst$. Resets at $T_5$. |

---

## 3. Quadrant 0 Decoder Suppression & Master Diagonal Escape Matrix (`dd == ss`)

When an instruction in Quadrant 0 (`OP[3:2] = 00`) matches the diagonal bitmask (`OPCODE[1:0] == OPERAND[1:0]` / $dd == ss$), standard 2-to-4 $SRC$ (`~OE1`) and $DST$ (`~WE`) register decoders are suppressed (`DEC_DISABLE = 1`).

The sub-operation selector $cc$ (`OPERAND[3:2]`) routes execution directly to peripheral sub-modules via point-to-point harness lines.

```
          +---------------------------------------------------+
          | Quadrant 0 Instruction Decoder (OP[3:2] = 00)     |
          +---------------------------------------------------+
                                    |
                            [ Is dd == ss? ]
                             /            \
                           YES             NO
                           /                 \
            +-------------------+       +-----------------------+
            | Suppress Decoder  |       | Standard Reg-to-Reg   |
            | Execute Diagonal  |       | Transfer Operations   |
            +-------------------+       +-----------------------+
                     |
      +--------------+--------------+--------------+
      |              |              |              |
  RegA (00)      RegB (01)      RegC (10)      RegD (11)
  System &       Conditional    Interrupts &   Stack & Frame
  PC Control     Skips (ALU)    System State   Operations

```

### Master Diagonal Escape Matrix Table ($dd == ss$)

| Diagonal ($dd = ss$) | $cc$ (`OPERAND[3:2]`) | Hex Code | Mnemonic | Operational Behavior |
| --- | --- | --- | --- | --- |
| **RegA Diagonal** (`00`)<br>

<br>*System & PC Control* | `00` | `0x00` | **`NOP`** | **No Operation.** Safe idle/reset state. Resets at $T_6$. |
|  | `01` | `0x04` | **`JU`** | **Unconditional Jump.** Branch to address vector in `[RegC:RegD]`. |
|  | `10` | `0x08` | **`GETPC`** | **Get Program Counter.** Copy current $PC$ into `[RegC:RegD]`. |
|  | `11` | `0x0C` | **`SRESET`** | **Software Reset.** Clear $PC \leftarrow 0x00$, clear $SP$, restart at $T_0$. |
| **RegB Diagonal** (`01`)<br>

<br>*Conditional Skips* | `00` | `0x11` | **`SZ`** | **Skip if Zero.** If $ZF = 1$, pulse $PC$ increment again in $T_2/T_3$. |
|  | `01` | `0x15` | **`SNZ`** | **Skip if Not Zero.** If $ZF = 0$, pulse $PC$ increment again in $T_2/T_3$. |
|  | `10` | `0x19` | **`SC`** | **Skip if Carry.** If $CF = 1$, pulse $PC$ increment again in $T_2/T_3$. |
|  | `11` | `0x1D` | **`SNC`** | **Skip if Not Carry.** If $CF = 0$, pulse $PC$ increment again in $T_2/T_3$. |
| **RegC Diagonal** (`10`)<br>

<br>*Interrupts & System* | `00` | `0x22` | **`CLI`** | **Clear Interrupt Enable.** Disables hardware IRQ lines ($IE \leftarrow 0$). |
|  | `01` | `0x26` | **`STI`** | **Set Interrupt Enable.** Enables hardware IRQ lines ($IE \leftarrow 1$). |
|  | `10` | `0x2A` | **`RETI`** | **Return from Interrupt.** Pop $PC$, restore $ZF/CF$ from shadow, $IE \leftarrow 1$. |
|  | `11` | `0x2E` | **`HALT`** | **Halt CPU.** Suspends clocking until hard reset or external IRQ. |
| **RegD Diagonal** (`11`)<br>

<br>*Stack & Routine Frames* | `00` | `0x33` | **`CALL`** | **Subroutine Call.** Push $PC$ to stack, branch to `[RegC:RegD]`. |
|  | `01` | `0x37` | **`RET`** | **Return.** Pop address from 8-level hardware stack into $PC$. |
|  | `10` | `0x3B` | **`PUSHPC`** | **Push Program Counter.** Push current $PC$ onto hardware stack. |
|  | `11` | `0x3F` | **`DROP`** | **Drop Stack Frame.** Rewind $SP$ by 1 without loading $PC$. |

---

## 4. Centralized Decoder & Point-to-Point Harness Routing

To minimize backplane pin count to 30 pins, peripheral execution cards contain zero local timestep decoding or clock-gating logic. All state decoding and phase-multiplexing occur centrally on the Control/Decoder Board and are routed to peripheral execution units via point-to-point control harnesses.

```
                             ┌─────────────────────────┐
                             │     Central Decoder     │
                             │  (Read Mux: SRC vs DST) │
                             └────┬──────────────┬─────┘
                                  │              │
            Point-to-Point        │              │ Point-to-Point
            Harness 1             │              │ Harness 2
                                  ▼              ▼
                       ┌──────────────┐      ┌──────────────┐
                       │   UBC-REG1   │      │   UBC-REG2   │
                       │ (RegA / RegB)│      │ (RegC / RegD)│
                       └──────────────┘      └──────────────┘
                       • ~WE_RegA/B          • ~WE_RegC/D
                       • ~OE1_RegA/B         • ~OE1_RegC/D
                       • ~OE2_RegA/B         • ~OE2_RegC/D

```

### Harness Signal Definitions by Daughtercard

#### Dual-Register Card 1 (`UBC-REG1` — RegA / RegB)

* `~WE_RegA`, `~WE_RegB`: Level-sensitive write enables gated with CLK LOW.
* `~OE1_RegA`, `~OE1_RegB`: Read Port 1 Output Enable (driven when selected as SRC during $T_2$).
* `~OE2_RegA`, `~OE2_RegB`: Read Port 2 Output Enable (driven when selected as DST during $T_3$).

#### Dual-Register Card 2 (`UBC-REG2` — RegC / RegD)

* `~WE_RegC`, `~WE_RegD`: Level-sensitive write enables.
* `~OE1_RegC`, `~OE1_RegD`: Read Port 1 Output Enable.
* `~OE2_RegC`, `~OE2_RegD`: Read Port 2 Output Enable.
* `~OE_ADDR`: Asserts `RegC` onto `ADDR_H` and `RegD` onto `ADDR_L` during memory access cycles.

#### ALU Card

* `Latch_B`: Clock strobe to latch source operand from `BUS[3:0]` into Input Buffer B at $T_2$.
* `Latch_A`: Clock strobe to latch destination operand from `BUS[3:0]` into Input Buffer A at $T_3$.
* `Writeback`: Asserts ALU tri-state bus driver ($\text{ALU}_{\text{OUT}} \rightarrow \text{BUS}[3:0]$) during $T_4$.

#### Timing / Interrupt Card

* `IR_DISABLE`: Freezes PC auto-increment and forces `0x00` (`NOP`) into execution latches during interrupt hijacks.
* `~STACK_PUSH`, `~STACK_POP`, `~STACK_DROP`: Point-to-point strobes driving the 3-bit hardware Stack Pointer ($SP$) and internal memory array.

---

## 5. Control Flow Mechanics & Hardware Execution

### A. Zero-Fetch Skip Execution (`SKP`)

Unlike architectures that fetch target instructions and suppress write-backs (wasting memory bandwidth), the NOD-4 implements conditional skips directly via the main decoder's $PC$ increment logic.

$$\text{PC\_INC\_ENABLE} = \text{FETCH\_STROBE} \lor (\text{IS\_SKP} \land \text{COND\_EVAL} \land T_2)$$

When a skip condition evaluates to **TRUE**, the control logic holds `PC_INC` HIGH for an extra clock pulse during $T_2/T_3$. Because all instructions in the NOD-4 are uniformly 1 byte (2 nibbles), this single extra increment cleanly jumps over the subsequent instruction byte in silicon without performing a memory read cycle.

### B. Position-Independent Code (PIC) Zero-Register Loop Idiom

By pairing `PUSHPC` with `SKP`, `RET`, and `DROP`, the NOD-4 executes loops without requiring pre-loaded vector addresses in `[RegC:RegD]`. This keeps all 4 general-purpose registers completely free for computation inside the loop body.

```assembly
; =========================================================================
; NOD-4 Zero-Register, Position-Independent Loop Structure
; =========================================================================
LoopStart:
    PUSHPC      ; Hardware Stack [SP] <- Address of LoopStart
    
    ; ---------------------------------------------------------------------
    ; LOOP BODY: RegA, RegB, RegC, and RegD are 100% available
    ; ---------------------------------------------------------------------
    
    SZ          ; Check exit condition (ZF == 1)
                ; - If ZF == 0 (False): PC does NOT double-increment -> executes RET
                ; - If ZF == 1 (True) : PC double-increments -> skips RET -> executes DROP
                
    RET         ; Iteration path: Pop PC from stack, jump to LoopStart (1 cycle)
    
    DROP        ; Exit path: Discard LoopStart address from stack frame

```

### C. Synthesized Long Conditional Branches

When absolute/indirect conditional branching to an address in `[RegC:RegD]` is required, `SKP` instructions pair with `JU` to form 2-byte synthesized jumps without specialized hardware decoders:

| Target Operation | Combination | Execution Logic |
| --- | --- | --- |
| **`JZ [RegC:RegD]`** | `SNZ` + `JU` | Skip `JU` if $ZF = 0$. If $ZF = 1$, fall through to `JU`. |
| **`JNZ [RegC:RegD]`** | `SZ` + `JU` | Skip `JU` if $ZF = 1$. If $ZF = 0$, fall through to `JU`. |
| **`JC [RegC:RegD]`** | `SNC` + `JU` | Skip `JU` if $CF = 0$. If $CF = 1$, fall through to `JU`. |
| **`JNC [RegC:RegD]`** | `SC` + `JU` | Skip `JU` if $CF = 1$. If $CF = 0$, fall through to `JU`. |

---

## 6. Cycle Reset Engine & Termination Points

Early cycle termination is governed by combinational state logic on the Central Control/Decoder Board routing directly to the TIMING board's `~CLR` line.

### Reset Point Breakdown

* **$T_2 \cdot \text{SKP\_FAIL}$:** Untaken conditional skip ($ZF/CF$ condition evaluates FALSE). State counter resets immediately at $T_2$, leaving PC incremented by 1 byte.
* **$T_3 \cdot \text{SKP\_PASS}$:** Taken conditional skip ($ZF/CF$ condition evaluates TRUE). State counter completes second $PC$increment during$T_2/T_3$and resets at$T_3 entry.
* **$T_3 \cdot \text{Q2\_LDI}$:** Load Immediate (`LDI`) finishes writeback at $T_2$; resets at $T_3 entry.
* **$T_3 \cdot \text{Q0\_MOVE}$:** Standard register/memory move (`MOV`, `LD`, `ST`) finishes writeback at $T_2$; resets at $T_3 entry.
* **$T_4 \cdot \text{JMP\_RET\_DROP}$:** Taken branch (`JU`), `GETPC`, `DROP`, or Return (`RET`/`RETI`) completes execution (loads target address into PCH:PCL or updates stack pointer); resets at $T_4 entry.
* **$T_5 \cdot \text{ALU\_EN}$:** ALU operations (Q1 Reg-Reg & Q3 Immediate) read operands at $T_2$/$T_3$ and write back at $T_4$; resets at $T_5 entry via `ALU_EN` (`OP[2] = 1`).
* **Internal $T_6$ Clear:** Subroutine Call (`CALL`), `NOP`, `SRESET`, and Hardware Interrupt Hijack (`~IRQ`) run through $T_5$. The TIMING card self-resets at $T_6 via direct hardware feedback ($\overline{T_6} \rightarrow \overline{\text{CLR}}$).

---

## 7. Complete Micro-Step Pipeline & Timing Matrix ($T_0 \dots T_6$)

| Instruction Class | $T_0$ (Opcode Fetch) | $T_1$ (Operand Fetch, $PC+1$) | $T_2$ (Drive / Latch B, $PC+2$) | $T_3$ (Latch A / Compute) | $T_4$ (ALU Writeback / ISR Page) | $T_5$ (Reset / ISR Offset) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move (`MOV dst, src`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE1[src]` $\rightarrow$ `BUS` & `~WE[dst]` ($PC \leftarrow PC+1$) | Reset state | — | — |
| **Q0: Memory Store (`ST MEM, src`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Drive `RegC:RegD` to `ADDR`, Assert `~OE1[src]` & `~MEM_WE` ($PC \leftarrow PC+1$) | Reset state | — | — |
| **Q0: Memory Load (`LD dst, MEM`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Drive `RegC:RegD` to `ADDR`, Assert `~MEM_OE` & `~WE[dst]` ($PC \leftarrow PC+1$) | Reset state | — | — |
| **Q0: Conditional Skip (`SKP False`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Evaluate Condition $\rightarrow$ FALSE. Normal $PC+1$. Reset instantly at $T_2$. | — | — | — |
| **Q0: Conditional Skip (`SKP True`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Evaluate Condition $\rightarrow$ TRUE. Pulse $PC+1$ again in $T_2$. | Complete 2nd $PC$ increment. Reset state at $T_3$. | — | — |
| **Q0: Jump Unconditional (`JU`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE1[RegD]` $\rightarrow$ `BUS` & `~WE[PCL]` ($PC \leftarrow PC+1$) | Assert `~OE1[RegC]` $\rightarrow$ `BUS` & `~WE[PCH]` | Reset state | — |
| **Q0: Get PC (`GETPC`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE1[PCL]` $\rightarrow$ `BUS` & `~WE[RegD]` ($PC \leftarrow PC+1$) | Assert `~OE1[PCH]` $\rightarrow$ `BUS` & `~WE[RegC]` | Reset state | — |
| **Q0: Software Reset (`SRESET`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `CLEAR_PC` ($PC \leftarrow 0x00$) | Assert `CLEAR_SP` ($SP \leftarrow 0$) | Assert `CLEAR_FLAGS` | Self-Reset at $T_6$ |
| **Q0: Subroutine Call (`CALL`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Push $PCL$ ($PC_0+2$) $\rightarrow \text{STK}$ ($PC \leftarrow PC+1$) | Push $PCH$ ($PC_0+2$) $\rightarrow \text{STK}$ | Assert `~OE1[RegD]` & `~WE[PCL]` | Assert `~OE1[RegC]` & `~WE[PCH]` (Self-Reset $T_6$) |
| **Q0: Return (`RET / RETI`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Pop $\text{STK} \rightarrow PCH$ ($PC \leftarrow PC+1$) | Pop $\text{STK} \rightarrow PCL$ | Restore shadow flags (`RETI`); Reset state | — |
| **Q0: Drop Frame (`DROP`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Strobe `~STACK_DROP` (Rewind $SP$ by 1, suppress $PC$ write) | Reset state | — | — |
| **Q1: Reg-Reg ALU (`ADD, SUB, etc.`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE1[src]` $\rightarrow$ `Latch_B` ($PC \leftarrow PC+1$) | Assert `~OE2[dst]` $\rightarrow$ `Latch_A`, Compute | Assert `Writeback` $\rightarrow \text{BUS}$ & `~WE[dst]`, Sample Flags | Reset state |
| **Q2: Load Immediate (`LDI dst, #imm`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[OPERAND]` $\rightarrow$ `BUS` & `~WE[dst]` ($PC \leftarrow PC+1$) | Reset state | — | — |
| **Q3: Immediate ALU (`ADDI, etc.`)** | Fetch Opcode $\rightarrow$ `OPCODE` | Fetch Operand $\rightarrow$ `OPERAND` ($PC \leftarrow PC+1$) | Assert `~OE[OPERAND]` $\rightarrow$ `Latch_B` ($PC \leftarrow PC+1$) | Assert `~OE2[dst]` $\rightarrow$ `Latch_A`, Compute | Assert `Writeback` $\rightarrow \text{BUS}$ & `~WE[dst]`, Sample Flags | Reset state |
| **Hardware Interrupt (`~IRQ Entry`)** | Freeze $PC$, force `NOP` via `IR_DISABLE` | Fetch `NOP` Operand (`IR_DISABLE` LOW) | Push $PCL_{\text{return}}$ ($PC_0+2$) $\rightarrow \text{STK}$ | Push $PCH_{\text{return}}$ ($PC_0+2$) $\rightarrow \text{STK}$ | Save flags to shadow latches; Interrupt Card drives Page $\rightarrow PCH$ (`~WE_PCH`) | Assert `~IRQ_ACK` (Pin 07), Requesting I/O drives Offset $\rightarrow PCL$ (`~WE_PCL`) |

---

## 8. Master Backplane Pinout & Card Slot Mapping

```
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
| **03** | `CLK` | Timing | Single-Phase Master Clock ($T_n$ transitions on falling edge, write latches open on CLK LOW) |
| **04** | `HALT_STAT` | Control Bus | System Halt Status / Manual Single-Step Freeze Line |
| **05** | `~IRQ_REQ` | Interrupts | Active-LOW Open-Drain Hardware Interrupt Request Rail |
| **06** | `~IRQ_ACK` | Interrupts | Active-LOW Interrupt Acknowledge Strobe from Control Board |
| **07** | `ZF` | Status Flags | Zero Flag Status Rail (Sampled trailing edge $T_4$; auto-shadowed on IRQ) |
| **08** | `CF` | Status Flags | Carry/Borrow Flag Status Rail (Sampled trailing edge $T_4$; auto-shadowed on IRQ) |
| **09** | `~MEM_OE` | Memory Control | Active-LOW Memory Output Enable (Bus Drive) |
| **10** | `~MEM_WE` | Memory Control | Active-LOW Memory Write Enable (RAM Store) |
| **11** | `BUS[0]` | Data Bus | Bit 0 of Main Parallel 4-Bit Data Bus |
| **12** | `BUS[1]` | Data Bus | Bit 1 of Main Parallel 4-Bit Data Bus |
| **13** | `BUS[2]` | Data Bus | Bit 2 of Main Parallel 4-Bit Data Bus |
| **14** | `BUS[3]` | Data Bus | Bit 3 of Main Parallel 4-Bit Data Bus |
| **15** | `ADDR_H[0]` | High Address | Bit 0 of High Address Rail (`RegC` / `PCH`) |
| **16** | `ADDR_H[1]` | High Address | Bit 1 of High Address Rail (`RegC` / `PCH`) |
| **17** | `ADDR_H[2]` | High Address | Bit 2 of High Address Rail (`RegC` / `PCH`) |
| **18** | `ADDR_H[3]` | High Address | Bit 3 of High Address Rail (`RegC` / `PCH`) |
| **19** | `ADDR_L[0]` | Low Address | Bit 0 of Low Address Rail (`RegD` / `PCL`) |
| **20** | `ADDR_L[1]` | Low Address | Bit 1 of Low Address Rail (`RegD` / `PCL`) |
| **21** | `ADDR_L[2]` | Low Address | Bit 2 of Low Address Rail (`RegD` / `PCL`) |
| **22** | `ADDR_L[3]` | Low Address | Bit 3 of Low Address Rail (`RegD` / `PCL`) |
| **23** | `OPCODE[0]` | Opcode Rail | Bit 0 of Fetched Instruction Opcode (`dst0`) |
| **24** | `OPCODE[1]` | Opcode Rail | Bit 1 of Fetched Instruction Opcode (`dst1`) |
| **25** | `OPCODE[2]` | Opcode Rail | Bit 2 of Fetched Instruction Opcode (`ALU_EN`) |
| **26** | `OPCODE[3]` | Opcode Rail | Bit 3 of Fetched Instruction Opcode (`IMM`) |
| **27** | `OPERAND[0]` | Operand Rail | Bit 0 of Fetched Instruction Operand (`ss0` / `imm0`) |
| **28** | `OPERAND[1]` | Operand Rail | Bit 1 of Fetched Instruction Operand (`src1` / `ext`) |
| **29** | `OPERAND[2]` | Operand Rail | Bit 2 of Fetched Instruction Operand (`code0` / `alu_op0`) |
| **30** | `OPERAND[3]` | Operand Rail | Bit 3 of Fetched Instruction Operand (`cc1` / `alu_op1` / `imm3`) |

---

## 9. Universal Base Card (UBC) Output Architecture

Each Universal Base Card (UBC) provides two gated output drivers per register cell: a primary output (~OE1) for the main data bus, and a secondary output (~OE2) routed to a 4-pin jumper header. 

```
                +-------------------------------------------------------+
                |           UNIVERSAL BASE CARD (UBC-REG)               |
                |                                                       |
                |   +-----------+   ~OE1 (Driven by Decoder Harness)    |
                |   | Register  | ------------------------------------> | BUS[3:0]
                |   |   Cell    |                                       |
                |   |           |   ~OE2 (Driven by Decoder Harness)    |
                |   +-----------+ ------------------------------------> | 4-Pin Header
                +-------------------------------------------------------+      |
                                                                               v
                                                                  Jumpered to: ADDR_H / ADDR_L /
                                                                               OPCODE / OPERAND

```

### Bus Driving & Secondary Rail Routing

* **Primary Bus Drive (`~OE1`):** Driven by external decoder lines (`~OE_RegA`, `~OE_RegB`, etc.) to gate register contents onto the main data bus (`BUS[3:0]`).
* **Secondary Rail Bridge (`~OE2`):** Driven by secondary decoder lines (`~OE_RegC_ADDR`, etc.) to drive non-data backplane rails. The 4 output pins of `~OE2` pass to a physical 4-pin header, bridged directly to target backplane rail pins (`ADDR_H`, `ADDR_L`, `OPCODE`, or `OPERAND`).

---

## 10. Hardware Configuration

The UBC PCB contains no onboard decoding, address switches, or termination resistors. The only hardware configuration on the card is the physical 4-pin Secondary Port Route Header.

```
                     SECONDARY PORT ROUTE HEADER
                     [o o o o] Secondary Output Pins
                        | | | |
                        v v v v  (Bridge wires / 4-pin jumper cable)
                     [ADDR / OP / OPERAND Rail Pins]

```

### Configuration Summary

| Interface | Connection | Operational Function |
| --- | --- | --- |
| **Secondary Port Header** | **4-Pin Wire / Jumper Bridge** | Bridges 4-bit `~OE2` outputs directly to target backplane rail pins.<br>

<br>• `UBC Slot 2`: Jumpered to **`ADDR_H`** (RegC port) and **`ADDR_L`** (RegD port).<br>

<br>• Optional expansion: Bridge to `OPCODE[3:0]` or `OPERAND[3:0]`. |

---

### Standard Slot Setup Guide

* **UBC Slot 1 (`UBC-REG1` — RegA / RegB Harness):**
* **Control Harness:** Connected to Decoder lines `~OE_RegA`, `~OE_RegB`, `~WE_RegA`, `~WE_RegB`.
* **Secondary Port:** Unpopulated / Open.


* **UBC Slot 2 (`UBC-REG2` — RegC / RegD Harness):**
* **Control Harness:** Connected to Decoder lines `~OE_RegC`, `~OE_RegD`, `~WE_RegC`, `~WE_RegD`.
* **Secondary Port:** Jumpered directly to **`ADDR_H`** (RegC) and **`ADDR_L`** (RegD) backplane pins.
