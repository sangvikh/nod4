# NOD-4 Microprocessor Architecture & System Specification (v15.5)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` Data Pointer / `[RegA:RegB]` Control Target Pointer)

**Fetch Mechanics:** Sequential Dual-Nibble Fetch (`OPCODE[3:0]` at $T_0$, `OPERAND[3:0]` at $T_1$)

**Physical Hierarchy:** 32-Pin Master Backplane Bus $\rightarrow$ Universal Base Cards (UBC) $\rightarrow$ Control Harnesses $\rightarrow$ Central Control Board (CCB) & Daughtercards

**Logic Standard:** Active-LOW discrete 2N7000 NMOS pass-transistors and passive pull-up resistors to +5V. Logic levels: 5V = 0 (inactive/pull-up), 0V = 1 (active/NMOS pull-down).

---

## 1. Electrical Standard, Clocking & Latch Mechanics

The NOD-4 operates on a 6-step 0-indexed micro-step sequence ($T_0 \dots T_5$) driven by the falling edge of the master clock (`CLK`).

```text
                PHASE 1: SETUP & DRIVE                PHASE 2: LATCH WINDOW
CLK         ────────┐                             ┌───────────────────────┐
                    └─────────────────────────────┘                       └───────
~T[n]       ────────────────┐ (Timestep)
                    └─────────────────────────────────────────────────────
BUS[3:0]    ═══════════<     STABLE DATA WINDOW     >═════════════════════════════
~WE[n]      ────────┐ (Driven full T-step)
                    └─────────────────────────────────────────────────────────────
LATCH_ENABLE ──────────────────────────────────────┐ (~WE and CLK LOW)
                                                   └───────────────────────┘
                                                   ▲                       ▲
                                            Data Transparent        Data Latched
                                            (Latch Open)            (Frozen on CLK Rising Edge)

```

### Level-Sensitive Write, OE/WE & Asynchronous Reset Rules

* **Output Enable ($\text{OE}$):** Asserts continuously across the active $T$-state step to allow passive pull-ups and dynamic bus capacitance ($C_g$) to charge and settle completely.
* **Write Enable ($\text{WE}$):** Strictly gated by **`CLK` LOW** ($\text{T\_step} \cdot \overline{\text{CLK}}$) to eliminate write-glitches, enforce data setup time, and freeze transparent latch contents on the **`CLK` rising edge** as `CLK` transitions from LOW to HIGH.
* **Asynchronous Next-State Reset Rule:** All instruction-driven sequencer resets trigger asynchronously upon entering the **next** (otherwise unused) $T$-state step. An operation concluding its execution phase in $T_n$ asserts the asynchronous reset at the start of $T_{n+1}$, recycling the ring counter back to $T_0$.

$$\text{LATCH\_ENABLE}_n = \overline{\text{\textasciitilde WE}_n} \lor \text{CLK}$$

$$\overline{\text{LATCH\_ENABLE}_n} = \text{\textasciitilde WE}_n \cdot \overline{\text{CLK}}$$

---

## 2. Register Architecture, Three-Pointer Model & Stack Hardware

The processor contains two 4-slot register banks: **General Bank (`SYS = 0`)** and **System Bank (`SYS = 1`)**.

```text
                        Q0 Operand Nibble (opr[3:0])
                    ┌───────────┬───────────┬───────────────┐
                    │   opr[3]  │   opr[2]  │   opr[1:0]    │
                    └───────────┴───────────┴───────────────┘
                          │           │               │
                          ▼           ▼               ▼
                        DST SYS     SRC SYS     Register Index
                        Select      Select          [1:0]

```

### Bank 0: General Register Bank (`SYS = 0`)

Constructed using discrete 4-bit level-sensitive transparent latches. Registers $A/B$ and $C/D$ feature functional aliases reflecting their 4-bit nibble pointer components:

| Index (`[1:0]`) | Mnemonic | Functional Alias | Primary Function & Pointer Role |
| --- | --- | --- | --- |
| **`00`** | **`RegA`** | **`CPH`** (Control Pointer High) | Primary ALU Target / Upper 4-Bit Code Pointer Nibble (`PCH_target`) |
| **`01`** | **`RegB`** | **`CPL`** (Control Pointer Low) | Working Register / Lower 4-Bit Code Pointer Nibble (`PCL_target`) |
| **`10`** | **`RegC`** | **`DPH`** (Data Pointer High) | Upper 4-Bit Data Memory Address Nibble (`ADDR_H`) |
| **`11`** | **`RegD`** | **`DPL`** (Data Pointer Low) | Lower 4-Bit Data Memory Address Nibble (`ADDR_L`) |

### Bank 1: System Control Bank (`SYS = 1`)

Constructed using Master-Slave Universal Bit Cells (UBC) to prevent race conditions during updates.

| Index (`[1:0]`) | Mnemonic | Name | Primary Function | Special Hardware Action |
| --- | --- | --- | --- | --- |
| **`00`** | **`MEM`** | RAM Indirect Port | Indirect Data Access | Accesses external `RAM[RegC:RegD]` |
| **`01`** | **`STACK`** | Hardware Stack Port | Stack Push / Pop | Automatic stack-pointer update on read/write |
| **`10`** | **`SP`** | Stack Pointer | 4-Bit Stack Nibble Counter | Master-Slave Up/Down Counter (16-nibble Return Stack) |
| **`11`** | **`RegFLAGS`** | Status Register | Machine Flags | Master-Slave Latch (`[CF, ZF, IE, UF]`) |

---

### Three-Pointer Machine Model & Stack Controller Hardware

```text
       ┌─────────────────────────────────────────┐
       │                NOD-4 CPU                │
       ├─────────────────────────────────────────┤
       │  RegA:RegB (CPH:CPL) ──► Control Target │
       │  RegC:RegD (DPH:DPL) ──► Data Memory    │
       │  SP                  ──► Hardware Stack │
       └─────────────────────────────────────────┘

```

1. **`RegA:RegB` / `CPH:CPL` (Control Target Pointer):** Persistent 8-bit target vector (formed by two 4-bit nibbles `CPH` and `CPL`) for `CALL [RegA:RegB]` and jumps without altering its contents or disturbing `RegC:RegD`.
2. **`RegC:RegD` / `DPH:DPL` (Data Memory Pointer):** Drives active 8-bit address bus (`ADDR_H[3:0]`, `ADDR_L[3:0]`) using 4-bit upper nibble `DPH` and 4-bit lower nibble `DPL` whenever `MEM` is referenced.
3. **`SP` (Hardware Stack Pointer & Asymmetric Decoded Stack Controller):** Points to a dedicated internal 16-nibble **Ascending Empty (AE)** return stack (independent from 256 $\times$ 4-bit RAM).
* **Hardware Address Decoding Scheme:** To eliminate pre-decrement delay cycles during stack reads, the Stack Controller Card decodes control lines directly as:
* **Write Enable ($\text{WE}$):** Decoded directly to location **$\text{SP}$** ($\text{STACK}[\text{SP}] \leftarrow \text{Data}$).
* **Output Enable ($\text{OE}$):** Decoded directly to location **$\text{SP} - 1$** ($\text{Data} \leftarrow \text{STACK}[\text{SP} - 1]$).


* **2-Step Pointer Adjustments (1 T-step per single-nibble adjustment):** Modifying $\text{SP}$ by two 4-bit nibbles consumes **2 $T$-steps**:
* **Push Sequence (Phase 1: $T_2, T_3$):** Writes upper/lower nibbles to $\text{STACK}[\text{SP}]$ ($\text{WE}$ at $\text{SP}$) with sequential increments ($T_2: \text{SP} \leftarrow \text{SP} + 1$; $T_3: \text{SP} \leftarrow \text{SP} + 1$).
* **Pop Sequence (Phase 1: $T_2, T_3$):** Reads upper/lower nibbles from $\text{STACK}[\text{SP}-1]$ ($\text{OE}$ at $\text{SP}-1$) with sequential decrements ($T_2: \text{SP} \leftarrow \text{SP} - 1$; $T_3: \text{SP} \leftarrow \text{SP} - 1$).
* **`RETK` (Return & Keep) Restore (Phase 2: $T_4, T_5$):** Following a two-nibble pop in $T_2, T_3$, phase 2 executes two sequential single-step increments ($T_4: \text{SP} \leftarrow \text{SP} + 1$; $T_5: \text{SP} \leftarrow \text{SP} + 1$), restoring $\text{SP}$ back to its initial offset.





---

### Q0 Dual High-Bit Bank Matrix (`opr[3:2]`)

Bit `opr[3]` sets destination bank (`DST_SYS`), and `opr[2]` sets source bank (`SRC_SYS`):

$$\text{Full Destination Register Address} = [\text{opr[3]}, \text{opr[1:0]}]$$

$$\text{Full Source Register Address} = [\text{opr[2]}, \text{opr[1:0]}]$$

* **Phase-Gated `SYS_SEL` Line:** Asserted with `opr[2]` during $T_2$ (Source Read), and switched to `opr[3]` during writeback.

| `opr[3]` (`DST`) | `opr[2]` (`SRC`) | Mode | Source Bank | Destination Bank | Mnemonic | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`0`** | **`0`** | **Gen $\rightarrow$ Gen** | General (`RegA`–`RegD`) | General (`RegA`–`RegD`) | `MOV RegA, RegB` | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ |
| **`0`** | **`1`** | **Sys $\rightarrow$ Gen** | System (`MEM`–`RegFLAGS`) | General (`RegA`–`RegD`) | `MOV RegA, MEM` | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ |
| **`1`** | **`0`** | **Gen $\rightarrow$ Sys** | General (`RegA`–`RegD`) | System (`MEM`–`RegFLAGS`) | `MOV MEM, RegA` | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ |
| **`1`** | **`1`** | **Sys $\rightarrow$ Sys** | System (`MEM`–`RegFLAGS`) | System (`MEM`–`RegFLAGS`) | `MOV STACK, MEM` | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ |

---

## 3. Status Register (`RegFLAGS`) & LSB Ejection Branching

```text
                    Bit 3      Bit 2      Bit 1      Bit 0
                  ┌──────────┬──────────┬──────────┬──────────┐
                  │    CF    │    ZF    │    IE    │    UF    │
                  └──────────┴──────────┴──────────┴──────────┘
                    Carry      Zero   Interrupt   User Flag
                     Flag      Flag     Enable    (LSB Eject)

```

* **Zero-Overhead 2-Cycle Conditional Branching:**
1. Executing `SHR RegFLAGS` or `RCR RegFLAGS` ejects bit 0 ($UF$) into Carry ($CF$) in **1 cycle**.
2. The next instruction executes `SC` (Skip on Carry) or `SNC` (Skip on No Carry) in Q0 escapes in **1 cycle** (resets asynchronously at $T_2$ on fail / $T_4$ on success), eliminating dedicated branch-steering logic.



---

## 4. 32-Pin Master Backplane Pinout & Hardware IRQ Handshake

```text
 POWER, CLK & CTRL (01-06)         4-BIT FLAG RAIL (07-10)          MEMORY & PARALLEL BUSES (11-32)
[ 01-03 ] +5V, GND, CLK            [ 07 ] Carry Flag (CF)            [ 11-12 ] Memory OE / WE
[ 04 ] HALT_STAT Execution         [ 08 ] Zero Flag (ZF)             [ 13-16 ] Data Bus (BUS[3:0])
[ 05 ] ~IRQ Hardware Request       [ 09 ] Interrupt Enable (IE)      [ 17-20 ] Address High (ADDR_H[3:0])
[ 06 ] ~IRQ_ACK Hardware Acknowledge [ 10 ] User Flag (UF)            [ 21-24 ] Address Low (ADDR_L[3:0])
                                                                    [ 25-28 ] Opcode Rail (OPCODE[3:0])
                                                                    [ 29-32 ] Operand Rail (OPERAND[3:0])

```

| Pin # | Signal Name | Group | Direction | Description |
| --- | --- | --- | --- | --- |
| **01–03** | `+5V`, `GND`, `CLK` | Power / Clock | Input / System | Main Power Rail (+5V DC), Circuit Ground, Master Clock |
| **04** | `HALT_STAT` | Status | Output | CPU Run/Halt & Trap State Line |
| **05** | `~IRQ` | Interrupt | Input | Active-LOW Hardware Interrupt Request Line |
| **06** | `~IRQ_ACK` | Interrupt | Output | Active-LOW Hardware Interrupt Acknowledge Pulse |
| **07–10** | `CF`, `ZF`, `IE`, `UF` | Flags | Output | Carry, Zero, Interrupt Enable, and User Flag status lines |
| **11–12** | `~MEM_OE`, `~MEM_WE` | Control | Output | Active-LOW Memory Read Output Enable / Write Enable |
| **13–16** | `BUS[3:0]` | Data Bus | Bidirectional | Parallel 4-Bit Bidirectional Data Bus |
| **17–24** | `ADDR_H/L[3:0]` | Address Bus | Output | Upper (`RegC`/`DPH`) and Lower (`RegD`/`DPL`) 4-Bit Address Nibble Buses |
| **25–32** | `OPCODE`, `OPERAND` | Instruction | Output | Pre-fetched Opcode (`OPCODE[3:0]`) and Operand (`OPERAND[3:0]`) rails |

### Hardware IRQ Handshake & Vectoring Protocol

```text
~IRQ      (Pin 05) ────┐                                    ┌───────────────────────
                       └────────────────────────────────────┘ (Peripheral Releases)
~IRQ_ACK  (Pin 06) ──────────────────┐             ┌───────────────────────────────
                                     └─────────────┘ (1 T-step CPU Strobe at T3)
IE        (Pin 09) ───────────┐
                              └────────────────────────────────────────────────────
                                (IE cleared in RegFLAGS by CPU at T4)

```

1. **Assertion:** Peripheral pulls `~IRQ` LOW (Pin 05), setting internal `ir_pending`.
2. **Takeover & Bus Isolation ($T_0$):** At instruction boundary $T_0$, if $IE = 1$, Central Control asserts `IR_DISABLE` (forcing `NOP` on instruction lines via passive pull-down) and asserts `PC_INC_DISABLE` to hold current return PC stable.
3. **Execution & Acknowledgment ($T_2 \dots T_5$):**
* Phase 1 ($T_2, T_3$): CPU pushes return address `PCH:PCL` to `STACK` ($T_2: \text{STACK}[\text{SP}] \leftarrow \text{PCH}$, $T_3: \text{STACK}[\text{SP}] \leftarrow \text{PCL}$), and Central Control drives a 1 $T$-step active-LOW pulse on `~IRQ_ACK` (Pin 06) at $T_3$.
* Phase 2 ($T_4, T_5$): Clears $IE \leftarrow 0$ (Pin 09 goes LOW) at $T_4$, and loads external hardware vector `IRQ_VECTOR[7:0] → PCH:PCL` at $T_5$. Resets asynchronously at $T_0$.


4. **Release & Return:** Peripheral detects `~IRQ_ACK` pulse and releases `~IRQ`. Executing `RETI` pops return address and restores $IE \leftarrow 1$.

---

## 5. Unified Quadrant Decoder & Master ISA Specification

```text
         OPCODE NIBBLE (Fetched at T0)               OPERAND NIBBLE (Fetched at T1)
     ┌───────┬─────────┬─────────┬─────────┐     ┌───────────┬───────────┬───────────┬───────────┐
     │  IMM  │ ALU_EN  │  dst1   │  dst0   │     │ OPERAND[3]│ OPERAND[2]│ OPERAND[1]│ OPERAND[0]│
     └───────┴─────────┴─────────┴─────────┘     └───────────┴───────────┴───────────┴───────────┘
     ◄────── OP[3:2] ─► ◄── dst[1:0] ─────►       SYS Select   ADD/SUB or   EXT Mode    IMM1 or
        (Quadrant Select)   (ALWAYS HERE)        (0: General   Unary Op     (0: Arith   Unary SubOp
                                                  1: System)   Selector      1: Unary)   (0:#0, 1:#1)

```

---

### Quadrant 0: Data Moves & Diagonal Control Escapes (`OPCODE = 00_dd`)

#### 1. Standard Moves ($dd \neq ss$)

Executes standard transfers in $T_2$. **Resets asynchronously at $T_3$**.

#### 2. Q0 Diagonal Bitmapped Escapes ($dd == ss$)

When $dst[1:0] == src[1:0]$, standard register decoders are suppressed and the 4 active control bits ($d_1, d_0$ from `OPCODE[1:0]` and $c_1, c_0$ from `OPERAND[3:2]`) drive the control matrix directly.

$$\text{ESCAPE\_EN} = \text{IS\_Q0} \cdot (dd_1 \odot ss_1) \cdot (dd_0 \odot ss_0)$$

$$\text{Control Vector} = [d_1 (\text{Stack En}),\, d_0 (\text{Jump/Seq}),\, c_1 (\text{Action/Flag}),\, c_0 (\text{Target/Mod})]$$

##### Master Q0 Diagonal Decode Matrix & Timing Schedule

All escapes fetch opcode at $T_0$ and operand at $T_1$. Flag conditions are evaluated at $T_1$.

| Hex Code | Mnemonic | $d_1 d_0 c_1 c_0$ | Active Phase 1 ($T_2, T_3$) | Active Phase 2 ($T_4, T_5$) | Active Steps | Asynchronous Reset Step | Net $\Delta SP$ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`0x00`** | **`NOP`** | `0 0 0 0` | Passive Idle | Passive Idle | $T_0 \dots T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | 0 |
| **`0x04`** | **`SKP`** | `0 0 0 1` | `PC_INC` ($PC \leftarrow PC + 2$) | Idle | $T_0 \dots T_3$ | Resets asynchronously at $T_4$ | 0 |
| **`0x08`** | **`GETPC`** | `0 0 1 0` | `PCH:PCL → RegA:RegB` | Idle | $T_0 \dots T_3$ | Resets asynchronously at $T_4$ | 0 |
| **`0x0C`** | **`SRESET`** | `0 0 1 1` | Assert System Reset Rail | Idle | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ | 0 |
| **`0x11`** | **`SZ`** | `0 1 0 0` | Match: `PC_INC` ($T_2 \dots T_3$) | Fail: Trigger Reset | True: $T_0 \dots T_3$ / Fail: $T_0 \dots T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x15`** | **`SNZ`** | `0 1 0 1` | Match: `PC_INC` ($T_2 \dots T_3$) | Fail: Trigger Reset | True: $T_0 \dots T_3$ / Fail: $T_0 \dots T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x19`** | **`SC`** | `0 1 1 0` | Match: `PC_INC` ($T_2 \dots T_3$) | Fail: Trigger Reset | True: $T_0 \dots T_3$ / Fail: $T_0 \dots T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x1D`** | **`SNC`** | `0 1 1 1` | Match: `PC_INC` ($T_2 \dots T_3$) | Fail: Trigger Reset | True: $T_0 \dots T_3$ / Fail: $T_0 \dots T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x22`** | **`RET`** | `1 0 0 0` | `STACK → PCH:PCL` & $SP \leftarrow SP - 2$ | Idle | $T_0 \dots T_3$ | Resets asynchronously at $T_4$ | $-2$ |
| **`0x26`** | **`RETK`** | `1 0 0 1` | `STACK → PCH:PCL` & $SP \leftarrow SP - 2$ | AE Restore ($SP \leftarrow SP + 2$ in $T_4 \dots T_5$) | $T_0 \dots T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | **0** |
| **`0x2A`** | **`RETI`** | `1 0 1 0` | `STACK → PCH:PCL` & $SP \leftarrow SP - 2$ | $IE \leftarrow 1$ ($T_4$) | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ | $-2$ |
| **`0x2E`** | **`HALT`** | `1 0 1 1` | Freeze Clock (`HALT_STAT`) | Idle | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ / Halt | 0 |
| **`0x33`** | **`JU`** | `1 1 0 0` | `RegA:RegB → PCH:PCL` ($T_2 \dots T_3$) | Idle | $T_0 \dots T_3$ | Resets asynchronously at $T_4$ | 0 |
| **`0x37`** | **`CALL`** | `1 1 0 1` | `PCH:PCL → STACK` & $SP \leftarrow SP + 2$ | `RegA:RegB → PCH:PCL` ($T_4 \dots T_5$) | $T_0 \dots T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | $+2$ |
| **`0x3B`** | **`PUSHPC`** | `1 1 1 0` | `PCH:PCL → STACK` & $SP \leftarrow SP + 2$ | Idle | $T_0 \dots T_3$ | Resets asynchronously at $T_4$ | $+2$ |
| **`0x3F`** | **`SWI`** | `1 1 1 1` | `PCH:PCL → STACK` & $SP \leftarrow SP + 2$ | Fixed SWI Vector $\rightarrow PC$ ($T_4 \dots T_5$) | $T_0 \dots T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | $+2$ |

---

### Quadrant 1: Register-to-Register Binary ALU (`OPCODE = 01_dd`)

Configures the ALU via 2-bit line `alu_op[1:0] = [carry_kill, inv_b]`. Operation target follows $\text{Dst} \leftarrow \text{Dst} + \text{Src}$ (or $\text{Dst} \leftarrow \text{Src} + \text{Dst}$).

#### Strict Timestep Execution Sequence:

* **$T_0$:** Fetch Opcode $\rightarrow \text{IR}$
* **$T_1$:** Fetch Operand $\rightarrow \text{IR}$
* **$T_2$:** Latch $\text{Dst}$ contents into **Latch A**. Route $\text{Dst}$ address decoder to $\text{Src}$ decoder, then disable $\text{Dst}$ decoder.
* **$T_3$:** Latch $\text{Src}$ contents into **Latch B**. Keep $\text{Dst}$ decoder disabled.
* **$T_4$:** Writeback $\text{ALU\_OUT} \rightarrow \text{Dst}$. Disable $\text{Src}$ decoder.
* **$T_5$:** Asynchronous Sequencer Reset triggers at the start of $T_5$, returning execution state to $T_0$.

| `alu_op[1:0]` | Control `[carry_kill, inv_b]` | Mnemonic | Hardware Logic / Arithmetic Equation | Flags Updated | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- | --- |
| **`00`** | `[0, 0]` | **`ADD dst, src`** | $dst \leftarrow A (\text{dst}) + B (\text{src}) + C_{in}$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`01`** | `[0, 1]` | **`SUB dst, src`** | $dst \leftarrow A (\text{dst}) + \overline{B (\text{src})} + \overline{C_{in}}$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`10`** | `[1, 0]` | **`XOR dst, src`** | $dst \leftarrow A (\text{dst}) \oplus B (\text{src})$ *(Carry killed)* | $ZF$, $CF \leftarrow 0$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`11`** | `[1, 0]` *(Tap Mode)* | **`AND dst, src`** | $dst \leftarrow A (\text{dst}) \land B (\text{src})$ *(Tapped from adder AND gates)* | $ZF$, $CF \leftarrow 0$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |

---

### Quadrant 2: Load Immediate (`OPCODE = 10_dd`)

Loads 4-bit literal `#imm[3:0]` directly into target $dst[1:0]$ in $T_2$. **Resets asynchronously at $T_3$**.

| Binary Pattern | Mnemonic | Hardware Action | Flags | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- |
| `10_dd #imm` | **`LDI dst, #imm`** | $dst \leftarrow \text{OPERAND}[3:0]$ | None | $T_0 \dots T_2$ | Resets asynchronously at $T_3$ |

---

### Quadrant 3: Immediate ALU, Carry Propagate & Unary/Shift Matrix (`OPCODE = 11_dd`)

`EXT` bit (`opr[1]`) selects Arithmetic Mode (`EXT = 0`) or Dedicated Unary/Shift Path (`EXT = 1`).

#### Strict Timestep Execution Sequence:

* **$T_0$:** Fetch Opcode $\rightarrow \text{IR}$
* **$T_1$:** Fetch Operand $\rightarrow \text{IR}$
* **$T_2$:** Latch $\text{Dst}$ contents into **Latch A**. Route $\text{Dst}$ address decoder to $\text{Src}$ decoder, then disable $\text{Dst}$ decoder.
* **$T_3$:** Latch Immediate / Constant operand into **Latch B**. Keep $\text{Dst}$ decoder disabled.
* **$T_4$:** Writeback $\text{ALU\_OUT} \rightarrow \text{Dst}$. Disable $\text{Src}$ decoder.
* **$T_5$:** Asynchronous Sequencer Reset triggers at the start of $T_5$, returning execution state to $T_0$.

| `opr[3]` (`SYS`) | `opr[2]` | `opr[1]` (`EXT`) | `opr[0]` | Mnemonic | $C_{in}$ Source & $B$-Bus State | Hardware Logic | Flags Updated | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`0` / `1**` | `0` | **`0`** | `0` | **`ADC dst`** | **$C_{in} \leftarrow CF$**, $B = 0\text{x0}$ | $dst \leftarrow dst + 0 + CF$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `0` | **`0`** | `1` | **`ADDI dst, #1`** | $C_{in}$ static (`inv_b = 1`), $B = 0\text{x1}$ | $dst \leftarrow dst + 1$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `1` | **`0`** | `0` | **`SBB dst`** | **$C_{in} \leftarrow CF$**, $B = 0\text{xF}$ | $dst \leftarrow dst + 0\text{xF} + CF$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `1` | **`0`** | `1` | **`SUBI dst, #1`** | $C_{in}$ static (`inv_b = 1`), $B = 0\text{xE}$ | $dst \leftarrow dst + 0\text{xE}$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `0` | **`1`** | `0` | **`NOT dst`** | Unary Pass Gate | $dst \leftarrow \overline{dst}$ | $ZF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `0` | **`1`** | `1` | **`SHR dst`** | Shift Logic ($0 \rightarrow dst[3]$) | $dst[0] \rightarrow CF$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `1` | **`1`** | `0` | **`RCR dst`** | Shift Logic ($CF \rightarrow dst[3]$) | $dst[0] \rightarrow CF$ | $ZF, CF$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1**` | `1` | **`1`** | `1` | **`CLR dst`** | ALU Drivers Disabled | $dst \leftarrow 0\text{x0}$ | $ZF \leftarrow 1, CF \leftarrow 0$ | $T_0 \dots T_4$ | Resets asynchronously at $T_5$ |

---

## 6. Master Pipeline & Timestep Schedule ($T_0 \dots T_5$)

```text
  T0        T1        T2          T3          T4          T5
┌─────────┬─────────┬───────────┬───────────┬───────────┬───────────┐
│ Fetch   │ Fetch   │ Phase 1   │ Phase 1   │ Phase 2   │ Phase 2   │
│ Opcode  │ Operand │ Latch A   │ Latch B   │ Writeback │ Resets    │
└─────────┴─────────┴───────────┴───────────┴───────────┴───────────┘
 ◄─ Fetch Phase ─►   ◄────── ALU Execution ──────► ◄─ Writeback/Reset ─►

```

| Instruction Class | $T_0$ (Fetch Op) | $T_1$ (Fetch Opr) | $T_2$ (Phase 1 Step 1) | $T_3$ (Phase 1 Step 2) | $T_4$ (Phase 2 Step 1) | $T_5$ (Phase 2 Step 2 / Reset) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch Operand $\rightarrow \text{IR}$ | Drive Bus & Writeback | Asynchronous Reset at $T_3$ | — | — |
| **Q0: Memory Access** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch Operand $\rightarrow \text{IR}$ | Drive `RAM[RegC:RegD]` | Asynchronous Reset at $T_3$ | — | — |
| **Q0: Passive `NOP` (`0x00`)** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch `0x0` Payload | Passive Idle (Buses Off) | Passive Idle (Buses Off) | Passive Idle (Buses Off) | Asynchronous Reset at $T_0$ (Natural $T_5$) |
| **Q0: Single-Phase Escape** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch Operand $\rightarrow \text{IR}$ | Execute Phase 1 Step 1 | Execute Phase 1 Step 2 | Asynchronous Reset at $T_4$ | — |
| **Q0: Multi-Phase Escape** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch Operand $\rightarrow \text{IR}$ | Phase 1: Stack Push/Pop ($SP \pm 1$) | Phase 1: Stack Push/Pop ($SP \pm 1$) | Phase 2: Vector / AE Restore ($SP + 1$) | AE Restore ($SP + 1$) / Async Reset @ $T_0$ |
| **Q1 / Q3: ALU Operations** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch Operand $\rightarrow \text{IR}$ | **Latch $\text{Dst} \rightarrow \text{Latch A}$** (Route $\text{Dst} \rightarrow \text{Src}$ decoder, disable $\text{Dst}$) | **Latch $\text{Src/\#imm} \rightarrow \text{Latch B}$** (Disable $\text{Dst}$ decoder) | **Writeback $\text{ALU\_OUT} \rightarrow \text{Dst}$** (Disable $\text{Src}$ decoder) | Asynchronous Reset at $T_5$ |
| **Q2: Load Immediate** | Fetch Opcode $\rightarrow \text{IR}$ | Fetch Immediate $\rightarrow \text{IR}$ | Drive `#imm` $\rightarrow \text{dst}$ | Asynchronous Reset at $T_3$ | — | — |
| **Hardware Interrupt** | Eval `ir_pending`; assert `IR_DISABLE` & `PC_INC_DISABLE` | Accept IRQ Sequence | Push $PCH_{\text{return}} \rightarrow \text{STACK}[\text{SP}]$, $SP \leftarrow SP + 1$ | Push $PCL_{\text{return}} \rightarrow \text{STACK}[\text{SP}]$, $SP \leftarrow SP + 1$, Pulse `~IRQ_ACK` | Clear $IE \leftarrow 0$ (Pin 09 LOW) | Load `IRQ_VECTOR[7:0] → PCH:PCL` |