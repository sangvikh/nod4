# NOD-4 Microprocessor Architecture & System Specification (v14.1)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** Decoupled Dual 8-Bit Pointers — RAM Data Pointer (`[RegC:RegD]`), Code Execution Pointer (`[RegA:RegB]`), 4-Bit Hardware Stack Pointer (`RegSP`)

**Fetch Mechanics:** Dual-Nibble Sequential Fetch (`OPCODE[3:0]`, `OPERAND[3:0]`)

**Physical Hierarchy:** 31-Pin Passive Backplane Bus $\rightarrow$ 6× Universal Base Cards (UBCs) $\rightarrow$ Control Harnesses $\rightarrow$ Central Control / ALU Daughtercards

**Control Philosophy:** Centralized Control & Read-Select Multiplexing, Tree Decoder (`OP[3]`=IMM, `OP[2]`=ALU_EN), Direct-Drive Unary/Shift Matrix, Diagonal Control Escape ($dd == ss$) with Decoder Suppression, Implicit-ACK Interrupt Engine.

---

## 1. Electrical Standard, Latch Mechanics & 6-UBC Layout

### Logic Family & Physical Layout

* **Logic Family:** Discrete NMOS pass-transistor & depletion-load logic (2N7000 NMOS switches, active-LOW signal paths).
* **Signal Standard:** Active-LOW open-drain backplane rails with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.
* **6× Universal Base Card (UBC) Slot Allocation:**
* **UBC-1 (Slot 1): `A:B**` — Houses **RegA** (`00`) and **RegB** (`01`). Level-sensitive transparent latches. Serves as the **Code/Execution Pointer** (`JU`, `CALL`, `GETPC`).
* **UBC-2 (Slot 2): `C:D**` — Houses **RegC** (`10`) and **RegD** (`11`). Level-sensitive transparent latches. Hardwired to drive 8-bit RAM Address Rails (`ADDR_H` from RegC, `ADDR_L` from RegD). Serves as the dedicated **RAM Data Pointer**.
* **UBC-3 (Slot 3): `PCH**` — High nibble Program Counter. Master-Slave counter card. Drives `ADDR_H` during fetch.
* **UBC-4 (Slot 4): `PCL**` — Low nibble Program Counter. Master-Slave counter card. Drives `ADDR_L` during fetch.
* **UBC-5 (Slot 5): `SP**` — Master-Slave 4-Bit Stack Pointer (`RegSP`).
* **UBC-6 (Slot 6): `FLAGS**` — 4-bit Status & Interrupt Register (`RegFLAGS`: `[IP, CF, ZF, IE]`). Level-sensitive transparent latch.



```
   +---------------------------------------------------------------------------------------------------------+
   |                                      CENTRAL CONTROL BOARD                                              |
   +---------------------------------------------------------------------------------------------------------+
       |           |           |           |           |           |                   |               |
    Harness 1   Harness 2   Harness 3   Harness 4   Harness 5   Harness 6          Harness 7       Harness 8
       v           v           v           v           v           v                   v               v
   +-------+   +-------+   +-------+   +-------+   +-------+   +-------+           +-------+       +-------+
   | UBC-1 |   | UBC-2 |   | UBC-3 |   | UBC-4 |   | UBC-5 |   | UBC-6 |           |  ALU  |       | TIMING|
   | RegA  |   | RegC  |   |  PCH  |   |  PCL  |   | RegSP |   | FLAGS |           |CARD   |       |  /IRQ |
   | RegB  |   | RegD  |   |(M-S)  |   |(M-S)  |   |(M-S)  |   |(IP,CF,|           |Latch A|       | Step  |
   |(Code) |   |(ADDR) |   |       |   |       |   |       |   | ZF,IE)|           |Latch B|       | Engine|
   +-------+   +-------+   +-------+   +-------+   +-------+   +-------+           +-------+       +-------+

```

---

### Latch Mechanics: Master-Slave Counters vs. Transparent Registers

Master-Slave latching is used **strictly for counter modules** where in-place increments and decrements occur within a single clock cycle. General registers and flags use level-sensitive transparent latches.

```
                 PHASE 1: SAMPLE / GATE              PHASE 2: TRANSFER / LATCH
               ┌───────────────────────────┐                       ┌──────── CLK
               │                           └───────────────────────┘
LEVEL-SENS.    ────────────────────────────┐ (Transparent while CLK LOW)
LATCH ENABLE                               └────────────────────────────────
MASTER_GATE    ────────────────────────────┐ (Sample while CLK HIGH)
(Counters)                                 └────────────────────────────────
SLAVE_GATE                                 ┌──────────────────────────────── (Transfer on
(Counters)     ────────────────────────────┘                                  CLK LOW)

```

1. **Counter Modules (`PCH`, `PCL`, `RegSP`) — Master-Slave:** In-place operations ($PC \leftarrow PC + 1$ or $SP \leftarrow SP \pm 1$) require isolation between current state and updated count.
* **Master Phase ($\text{CLK}$ HIGH):** Samples input state while isolating the output.
* **Slave Phase ($\text{CLK}$ LOW):** On falling edge of $\text{CLK}$, Master locks state and transfers it to the Slave latch to stably drive the bus/address rails.


2. **General Registers & Flags (`RegA`–`RegD`, `RegFLAGS`) — Level-Sensitive:** Rely on external pipeline steps (ALU computes in $T_3$, writes back in $T_4$), eliminating in-place feedback loops. Active write pulsing occurs while $\text{CLK}$ is LOW:

$$\text{LATCH\_ENABLE}_n = \overline{\text{WE}_n} \cdot \overline{\text{CLK}}$$

---

### Execution & Interrupt Flags (UBC-6: RegFLAGS)

`RegFLAGS` is mapped directly to `BUS[3:0]` as a standard 4-bit register. All 4 bits are exposed directly to dedicated backplane pins (06–09) for immediate peripheral handshaking and LED diagnostic monitoring.

```
  Bit 3 (Pin 09)   Bit 2 (Pin 08)   Bit 1 (Pin 07)   Bit 0 (Pin 06)
┌────────────────┬────────────────┬────────────────┬────────────────┐
│ IP (Pending)   │   CF (Carry)   │   ZF (Zero)    │  IE (Enable)   │
└────────────────┴────────────────┴────────────────┴────────────────┘

```

* **Bit 3 (`IP` - Interrupt Pending, Pin 09):** Latches to `1` on external `~IRQ` falling edge or direct software write (`MOV FLAGS, A`). Cleared when `RETI` executes or via software write. **Serves as implicit IRQ ACK to external hardware.**
* **Bit 2 (`CF` - Carry Flag, Pin 08):** Updated by ALU writeback ($T_4$) or direct software write.
* **Bit 1 (`ZF` - Zero Flag, Pin 07):** Updated by ALU writeback ($T_4$) or direct software write.
* **Bit 0 (`IE` - Interrupt Enable, Pin 06):** Cleared automatically by hardware IRQ entry, restored on `RETI` or set/cleared via standard ALU/immediate software writes (`XOR FLAGS, #0x01`).

$$\text{IRQ\_TRIGGER} = \text{IP} \cdot \text{IE} \cdot T_0$$

---

## 2. Decoupled Dual-Pointer Paradigm

NOD-4 enforces a functional decoupling between execution targets and RAM memory access:

```
Caller / Data Pipeline                        Subroutine Context
┌──────────────────────┐                    ┌──────────────────────┐
│ A:B = Code Pointer   │ ──[Latched to PC]─►│ A:B = FREED SCRATCH  │ (Scratch / Math)
│ C:D = RAM Pointer    │ ─────[Preserved]──►│ C:D = DATA CONTEXT   │ (Active RAM Pointer)
└──────────────────────┘                    └──────────────────────┘

```

* **`[RegA:RegB]` (Code Execution Pointer):** Target for `JU` and `CALL`, destination for `GETPC`. Transient target—once latched into $PC$, `RegA` and `RegB` are immediately available as scratch registers inside subroutines.
* **`[RegC:RegD]` (RAM Memory Pointer):** Hardwired to `ADDR_H` and `ADDR_L`. Exclusively used for `LD` and `ST`. Preserves RAM parameter pointers across `CALL` boundaries without stack push/pop overhead.

---

## 3. Canonical Instruction Encoding & Top-Level Decoder

Instructions consist of two 4-bit nibbles fetched sequentially:

* **OPCODE (`OP[3:0]`):** `[imm, alu_en, dst1, dst0]`
* **OPERAND (`OPERAND[3:0]`):** `[cc1, cc0, ss1, ss0]` (Q0) / `[alu_op, ss]` (Q1) / `[imm3..0]` (Q2) / `[alu_op, ext, imm0]` (Q3)

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
                                                                         • Untaken SKP: Reset at T2
                                                                         • Taken SKP: Reset at T3
                                                                         • JU / RETK / GETPC / RET / DROP: Reset at T4
                                                                         • CALL / NOP / SRESET / IRQ: Reset at T6

```

---

## 4. Master Diagonal Escape Matrix ($dd == ss$)

When $dd == ss$ (`OPCODE[1:0] == OPERAND[1:0]`) in Quadrant 0, standard register decoders are suppressed (`DEC_DISABLE = 1`). $cc$ (`OPERAND[3:2]`) routes control directly to peripheral sub-modules via point-to-point harness lines.

| Diagonal ($dd = ss$) | $cc$ (`OPERAND[3:2]`) | Hex | Mnemonic | Operational Behavior |
| --- | --- | --- | --- | --- |
| **UBC-1: RegA (`00`)**<br>

<br>

<br>*System & Skips* | `00` | `0x00` | **`NOP`** | **No Operation.** Fixed 6-step delay line ($T_0 \dots T_5$). Resets at $T_6$. |
|  | `01` | `0x04` | **`SKP`** | **Unconditional Skip.** Pulse $PC$ increment again in $T_2/T_3$. |
|  | `10` | `0x08` | **`GETPC`** | **Get Program Counter.** Copy current $PC$ (`[PCH:PCL]`) into `[RegA:RegB]`. |
|  | `11` | `0x0C` | **`SRESET`** | **Software Reset.** Clear $PC \leftarrow 0x00$, clear $SP \leftarrow 0$, restart at $T_0$. |
| **UBC-1: RegB (`01`)**<br>

<br>

<br>*Branching Skips* | `00` | `0x11` | **`SZ`** | **Skip if Zero.** If $ZF = 1$, pulse $PC$ increment again in $T_2/T_3$. |
|  | `01` | `0x15` | **`SNZ`** | **Skip if Not Zero.** If $ZF = 0$, pulse $PC$ increment again in $T_2/T_3$. |
|  | `10` | `0x19` | **`SC`** | **Skip if Carry.** If $CF = 1$, pulse $PC$ increment again in $T_2/T_3$. |
|  | `11` | `0x1D` | **`SNC`** | **Skip if Not Carry.** If $CF = 0$, pulse $PC$ increment again in $T_2/T_3$. |
| **UBC-2: RegC (`10`)**<br>

<br>

<br>*Branch & Control* | `00` | `0x22` | **`JU`** | **Unconditional Jump.** Branch to 8-bit vector in `[RegA:RegB]`. |
|  | `01` | **`0x26`** | **`RETK`** | **Return & Keep Stack Frame.** Read 8-bit vector from top of stack into $PC$ without changing $SP$ (net $\Delta SP = 0$). |
|  | `10` | `0x2A` | **`RETI`** | **Return from IRQ.** Pop $PCH, PCL$ from stack, set $IE \leftarrow 1$, clear $IP \leftarrow 0$. |
|  | `11` | `0x2E` | **`HALT`** | **Halt CPU.** Suspends clocking until hard reset or external `~IRQ`. |
| **UBC-2: RegD (`11`)**<br>

<br>

<br>*Stack Control* | `00` | `0x33` | **`CALL`** | **Subroutine Call.** Push $PCL, PCH$ to stack, branch to `[RegA:RegB]`. |
|  | `01` | `0x37` | **`RET`** | **Return.** Pop 8-bit address ($PCH, PCL$) from stack into `[PCH:PCL]`. |
|  | `10` | `0x3B` | **`PUSHPC`** | **Push PC.** Push current 8-bit $PC$ ($PCL, PCH$) onto stack ($\Delta SP = +2$). |
|  | `11` | `0x3F` | **`DROP`** | **Drop Stack Nibble.** Decrement $SP$ by 1 nibble ($SP \leftarrow SP - 1$). |

---

## 5. Micro-Step Timing Matrix ($T_0 \dots T_6$)

| Instruction / Event | $T_0$ | $T_1$ | $T_2$ | $T_3$ | $T_4$ | $T_5$ | Reset |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Move (`MOV`/`LD`/`ST`)** | Fetch Op | Fetch Opnd ($PC+1$) | Bus Transfer ($src \rightarrow dst$) | Reset state | — | — | $T_3$ |
| **Q2 `LDI**` | Fetch Op | Fetch Opnd ($PC+1$) | `OPERAND` $\rightarrow dst$ | Reset state | — | — | $T_3$ |
| **Q1/Q3 ALU Ops** | Fetch Op | Fetch Opnd ($PC+1$) | Latch $src/imm \rightarrow \text{ALU}_B$ | Latch $dst \rightarrow \text{ALU}_A$, Compute | Writeback $\text{ALU}_{\text{OUT}} \rightarrow dst$ | Reset state | $T_5$ |
| **Untaken `SKP` / Skip** | Fetch Op | Fetch Opnd ($PC+1$) | Eval Cond (False) | Reset state | — | — | $T_2$ |
| **Taken `SKP` / Skip** | Fetch Op | Fetch Opnd ($PC+1$) | Eval Cond (True), $PC+1$ | $PC$ Inc complete | Reset state | — | $T_3$ |
| **`JU` / `GETPC**` | Fetch Op | Fetch Opnd ($PC+1$) | Read/Latch `RegA:RegB` | Write $PC$ / Latch $PC$ | Reset state | — | $T_4$ |
| **`RETK` (`0x26`)** | Fetch Op | Fetch Opnd ($PC+1$) | Read RAM $[SP] \rightarrow PCH$, $SP-1$ | Read RAM $[SP] \rightarrow PCL$, $SP+1$ | Update $PC$ (Net $\Delta SP = 0$) | Reset state | $T_4$ |
| **`PUSHPC` / `DROP**` | Fetch Op | Fetch Opnd ($PC+1$) | Push/Drop $PCL$ ($SP \pm 1$) | Push $PCH$ ($SP+1$) | Reset state | — | $T_4$ |
| **`CALL` (`0x33`)** | Fetch Op | Fetch Opnd ($PC+1$) | Push $PCL \rightarrow \text{STK}$ ($SP+1$) | Push $PCH \rightarrow \text{STK}$ ($SP+1$) | Load `RegA:RegB` $\rightarrow PC$ | Reset state | $T_6$ |
| **`RET` / `RETI**` | Fetch Op | Fetch Opnd ($PC+1$) | Pop $\text{STK} \rightarrow PCH$ ($SP-1$) | Pop $\text{STK} \rightarrow PCL$ ($SP-1$) | Update $PC$ (Set $IE=1$ if RETI) | Reset state | $T_4$ |
| **`NOP` / `SRESET**` | Fetch Op | Fetch Opnd ($PC+1$) | Idle Delay / Assert Clear | Clear $PC, SP$ | Reset state | — | $T_6$ |
| **Hardware `~IRQ**` | Sample `~IRQ` | Latch Vector Addr | Push $PCL \rightarrow \text{STK}$ ($SP+1$) | Push $PCH \rightarrow \text{STK}$ ($SP+1$) | $PC \leftarrow 0xF$, $IE \leftarrow 0$, Set $IP \leftarrow 1$ | Reset state | $T_6$ |

---

## 6. 31-Pin Backplane Pinout Table

```
 SYSTEM & CONTROL (01-05)        STATUS / FLAGS (06-09)        MEM & PARALLEL BUSES (10-31)
[ 01-03 ] Power & Clock        [ 06-06 ] IE (Interrupt Enable)[ 10-11 ] Memory OE / WE
[ 04-04 ] HALT_STAT            [ 07-07 ] ZF (Zero Flag)       [ 12-15 ] Data Bus (BUS)
[ 05-05 ] ~IRQ Request         [ 08-08 ] CF (Carry Flag)      [ 16-19 ] Address High (ADDR_H)
                               [ 09-09 ] IP (Interrupt Pending)[ 20-23 ] Address Low (ADDR_L)
                                                              [ 24-27 ] Opcode Rail (OPCODE)
                                                              [ 28-31 ] Operand Rail (OPERAND)

```

| Pin # | Signal Name | Type | Active Level | Functional Description |
| --- | --- | --- | --- | --- |
| **01** | `VCC` | Power | $+5\text{V}$ | Main System Power Rail |
| **02** | `GND` | Ground | $0\text{V}$ | System Signal and Power Ground |
| **03** | `CLK` | Input | Falling Edge | Master System Clock Input |
| **04** | `HALT_STAT` | Output | Active-HIGH | Processor Halted Indicator |
| **05** | `~IRQ` | Input | Active-LOW | Asynchronous External Interrupt Request |
| **06** | `IE` | Output | Active-HIGH | **Interrupt Enable Flag Output** |
| **07** | `ZF` | Output | Active-HIGH | **Zero Flag Status Line Output** |
| **08** | `CF` | Output | Active-HIGH | **Carry/Borrow Flag Status Line Output** |
| **09** | `IP` | Output | Active-HIGH | **Interrupt Pending Flag Output** (Implicit IRQ ACK to peripherals) |
| **10** | `~OE_MEM` | Output | Active-LOW | Unified Memory Read / Output Enable |
| **11** | `~WE_MEM` | Output | Active-LOW | Unified Memory Write Enable Strobe |
| **12-15** | `BUS[3:0]` | Bidirectional | Active-LOW | Main 4-Bit Data Bus |
| **16-19** | `ADDR_H[3:0]` | Output | Active-LOW | High Address Nibble (Driven by `RegC` or `PCH`) |
| **20-23** | `ADDR_L[3:0]` | Output | Active-LOW | Low Address Nibble (Driven by `RegD` or `PCL`) |
| **24-27** | `OPCODE[3:0]` | Input/Output | Active-LOW | Opcode Rail (Captured on $T_0$) |
| **28-31** | `OPERAND[3:0]` | Input/Output | Active-LOW | Operand Rail (Captured on $T_1$) |