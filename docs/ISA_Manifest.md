# NOD-4 Microprocessor Architecture & System Specification (v15.5)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` Data Pointer / `[RegA:RegB]` Control Target Pointer)

**Fetch Mechanics:** Sequential Dual-Nibble Fetch (`OPCODE[3:0]` at $T_0$, `OPERAND[3:0]` at $T_1$)

**Physical Hierarchy:** 32-Pin Master Backplane Bus $→$ Universal Base Cards (UBC) $→$ Control Harnesses $→$ Central Control Board (CCB) & Daughtercards

**Logic Standard:** Active-LOW discrete 2N7000 NMOS pass-transistors and passive pull-up resistors to +5V. Logic levels: 5V = 0 (inactive/pull-up), 0V = 1 (active/NMOS pull-down).

---

## 1. Electrical Standard, Clocking & Latch Mechanics

The NOD-4 operates on a 6-step 0-indexed micro-step sequence ($T_0 … T_5$) driven by the falling edge of the master clock (`CLK`).

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

* **Output Enable ($OE$):** Asserts continuously across the active $T$-state step to allow passive pull-ups and dynamic bus capacitance ($C_g$) to charge and settle completely.
* **Write Enable ($WE$):** Strictly gated by **`CLK` LOW** ($T\_step · ~CLK$) to eliminate write-glitches, enforce data setup time, and freeze transparent latch contents on the **`CLK` rising edge** as `CLK` transitions from LOW to HIGH.
* **Asynchronous Next-State Reset Rule:** All instruction-driven sequencer resets trigger asynchronously upon entering the **next** (otherwise unused) $T$-state step. An operation concluding its execution phase in $T_n$ asserts the asynchronous reset at the start of $T_{n+1}$, recycling the ring counter back to $T_0$.

$$LATCH\_ENABLE_n = ~~ WE_n \lor CLK$$

$$~LATCH\_ENABLE_n = ~ WE_n · ~CLK$$

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
                        DST SYS     ALU / EXT      Operation /
                        Select      Selector       Register Index

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
3. **`SP` (Hardware Stack Pointer & Asymmetric Decoded Stack Controller):** Points to a dedicated internal 16-nibble **Ascending Empty (AE)** return stack (independent from 256 $×$ 4-bit RAM).
* **Hardware Address Decoding Scheme:** To eliminate pre-decrement delay cycles during stack reads, the Stack Controller Card decodes control lines directly as:
* **Write Enable ($WE$):** Decoded directly to location **$SP$** ($STACK[SP] ← Data$).
* **Output Enable ($OE$):** Decoded directly to location **$SP - 1$** ($Data ← STACK[SP - 1]$).


* **2-Step Pointer Adjustments (1 T-step per single-nibble adjustment):** Modifying $SP$ by two 4-bit nibbles consumes **2 $T$-steps**:
* **Push Sequence (Phase 1: $T_2, T_3$):** Writes upper/lower nibbles to $STACK[SP]$ ($WE$ at $SP$) with sequential increments ($T_2: SP ← SP + 1$; $T_3: SP ← SP + 1$).
* **Pop Sequence (Phase 1: $T_2, T_3$):** Reads upper/lower nibbles from $STACK[SP-1]$ ($OE$ at $SP-1$) with sequential decrements ($T_2: SP ← SP - 1$; $T_3: SP ← SP - 1$).
* **`RETK` (Return & Keep) Restore (Phase 2: $T_4, T_5$):** Following a two-nibble pop in $T_2, T_3$, phase 2 executes two sequential single-step increments ($T_4: SP ← SP + 1$; $T_5: SP ← SP + 1$), restoring $SP$ back to its initial offset.





---

### Q0 Dual High-Bit Bank Matrix (`opr[3:2]`)

Bit `opr[3]` sets destination bank (`DST_SYS`), and `opr[2]` sets source bank (`SRC_SYS`):

$$Full Destination Register Address = [opr[3], opr[1:0]]$$

$$Full Source Register Address = [opr[2], opr[1:0]]$$

* **Phase-Gated `SYS_SEL` Line:** Asserted with `opr[2]` during $T_2$ (Source Read), and switched to `opr[3]` during writeback.

| `opr[3]` (`DST`) | `opr[2]` (`SRC`) | Mode | Source Bank | Destination Bank | Mnemonic | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`0`** | **`0`** | **Gen $→$ Gen** | General (`RegA`–`RegD`) | General (`RegA`–`RegD`) | `MOV RegA, RegB` | $T_0 … T_2$ | Resets asynchronously at $T_3$ |
| **`0`** | **`1`** | **Sys $→$ Gen** | System (`MEM`–`RegFLAGS`) | General (`RegA`–`RegD`) | `MOV RegA, MEM` | $T_0 … T_2$ | Resets asynchronously at $T_3$ |
| **`1`** | **`0`** | **Gen $→$ Sys** | General (`RegA`–`RegD`) | System (`MEM`–`RegFLAGS`) | `MOV MEM, RegA` | $T_0 … T_2$ | Resets asynchronously at $T_3$ |
| **`1`** | **`1`** | **Sys $→$ Sys** | System (`MEM`–`RegFLAGS`) | System (`MEM`–`RegFLAGS`) | `MOV STACK, MEM` | $T_0 … T_2$ | Resets asynchronously at $T_3$ |

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
1. Executing `SHR RegFLAGS` ejects bit 0 ($UF$) into Carry ($CF$) in **1 cycle**.
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
| **06** | `~IRQ_ACK` | Interrupt | Output | Active-LOW Hardware Interrupt Acknowledge / IRQ-Active Level |
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
                                     └─────────────┘ (IRQ_ACTIVE acknowledge window)
IE        (Pin 09) ───────────┐
                              └────────────────────────────────────────────────────
                                (IE cleared by IRQ ack at T0)

```

1. The peripheral asserts `~IRQ`. If `IE = 1` and no IRQ is active, the
   IRQ card asynchronously sets its master latch.

2. At `T0`, the master latch transfers to the slave:
   `IRQ_ACTIVE ← 1`, `IE ← 0`, and `PC_INC_DISABLE` is asserted.
   `IRQ_ACTIVE` causes the main decoder to assert `IR_DISABLE`; the disabled
   IR outputs passively decode as `NOP`.

3. The main decoder performs the IRQ entry sequence:

   - `T2`: `PCH → STACK`, `SP++`
   - `T3`: `PCL → STACK`, `SP++`
   - `T4`: `IRQ_VECTOR_H → PCH`
   - `T5`: `IRQ_VECTOR_L → PCL`

   The master latch clears during `T5` while `CLK` is LOW. After `T5`, the
   slave latch clears during the safe opposite clock phase.

4. The slave latch drives the internal `IRQ_ACTIVE` signal. An inverter
   drives the external active-low `~IRQ_ACK` line. The peripheral releases
   `~IRQ` when it observes the acknowledge level. `RETI` restores `IE`;
   `RET` preserves it.

### Interrupt-Enable Ownership

Interrupt-enable state belongs to the hardware IRQ entry/return protocol:

```text
Hardware IRQ entry: IE ← 0 at T0
RETI:               IE ← 1
RET:                IE unchanged
SWI:                IE unchanged
```

`SWI` is therefore usable both as a software trap while interrupts remain
enabled and as a polling/trap mechanism while software has previously
cleared `IE`. A polling handler returns with `RET`, preserving the disabled
state. A hardware IRQ handler returns with `RETI`, explicitly re-enabling
hardware interrupts.

The shared line is defined as:

```text
~IRQ_ACK = NOT(IRQ_ACTIVE)

The internal `IRQ_ACTIVE` signal is logical 1 while the CPU is accepting the
interrupt. An inverter drives the active-LOW backplane acknowledge line. The
same internal state is therefore both the decoder's IRQ-entry input and the
peripheral's acknowledge level.
```

It is an acknowledge level to the peripheral and the active-interrupt input
to the main decoder; no separate IRQ-active wire is required.

---

## 5. Unified Quadrant Decoder & Master ISA Specification

```text
         OPCODE NIBBLE (Fetched at T0)               OPERAND NIBBLE (Fetched at T1)
     ┌───────┬─────────┬─────────┬─────────┐     ┌───────────┬───────────┬───────────┬───────────┐
     │  IMM  │ ALU_EN  │  dst1   │  dst0   │     │ OPERAND[3]│ OPERAND[2]│ OPERAND[1]│ OPERAND[0]│
     └───────┴─────────┴─────────┴─────────┘     └───────────┴───────────┴───────────┴───────────┘
     ◄────── OP[3:2] ─► ◄── dst[1:0] ─────►       SYS Select   LOGIC/EXT    INV_B or    CF/0 or
        (Quadrant Select)   (ALWAYS HERE)        (0: General   Selector      Unary Op    Unary SubOp
                                                  1: System)   (Q1/Q3)      Selector    Selector)

The `SYS` selector is universal for destination decoding in Q1 and Q3. It is
suppressed only in Q2, where `opr[3]` remains part of the four-bit immediate
operand:

$$SYS\_DST = opr[3] \land \lnot Q2$$

```

---

### Quadrant 0: Data Moves & Diagonal Control Escapes (`OPCODE = 00_dd`)

#### 1. Standard Moves ($dd ≠ ss$)

Executes standard transfers in $T_2$. **Resets asynchronously at $T_3$**.

#### 2. Q0 Diagonal Bitmapped Escapes ($dd == ss$)

When $dst[1:0] == src[1:0]$, standard register decoders are suppressed and the 4 active control bits ($d_1, d_0$ from `OPCODE[1:0]` and $c_1, c_0$ from `OPERAND[3:2]`) drive the control matrix directly.

$$ESCAPE\_EN = IS\_Q0 · (dd_1 ⊙ ss_1) · (dd_0 ⊙ ss_0)$$

$$Control Vector = [d_1 (Stack En),\, d_0 (Jump/Seq),\, c_1 (Action/Flag),\, c_0 (Target/Mod)]$$

##### Master Q0 Diagonal Decode Matrix & Timing Schedule

All escapes fetch opcode at $T_0$ and operand at $T_1$. Flag conditions are evaluated at $T_1$.

| Hex Code | Mnemonic | $d_1 d_0 c_1 c_0$ | Active Phase 1 ($T_2, T_3$) | Active Phase 2 ($T_4, T_5$) | Active Steps | Asynchronous Reset Step | Net $\Delta SP$ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`0x00`** | **`NOP`** | `0 0 0 0` | Passive Idle | Passive Idle | $T_0 … T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | 0 |
| **`0x04`** | **`SKP`** | `0 0 0 1` | `PC_INC` ($PC ← PC + 2$) | Idle | $T_0 … T_3$ | Resets asynchronously at $T_4$ | 0 |
| **`0x08`** | **`GETPC`** | `0 0 1 0` | `PCH:PCL → RegA:RegB` | Idle | $T_0 … T_3$ | Resets asynchronously at $T_4$ | 0 |
| **`0x0C`** | **`SRESET`** | `0 0 1 1` | Assert System Reset Rail | Idle | $T_0 … T_2$ | Resets asynchronously at $T_3$ | 0 |
| **`0x11`** | **`SZ`** | `0 1 0 0` | Match: `PC_INC` ($T_2 … T_3$) | Fail: Trigger Reset | True: $T_0 … T_3$ / Fail: $T_0 … T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x15`** | **`SNZ`** | `0 1 0 1` | Match: `PC_INC` ($T_2 … T_3$) | Fail: Trigger Reset | True: $T_0 … T_3$ / Fail: $T_0 … T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x19`** | **`SC`** | `0 1 1 0` | Match: `PC_INC` ($T_2 … T_3$) | Fail: Trigger Reset | True: $T_0 … T_3$ / Fail: $T_0 … T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x1D`** | **`SNC`** | `0 1 1 1` | Match: `PC_INC` ($T_2 … T_3$) | Fail: Trigger Reset | True: $T_0 … T_3$ / Fail: $T_0 … T_1$ | True: $T_4$ / Fail: $T_2$ | 0 |
| **`0x22`** | **`RET`** | `1 0 0 0` | `STACK → PCH:PCL` & $SP ← SP - 2$ | Idle | $T_0 … T_3$ | Resets asynchronously at $T_4$ | $-2$ |
| **`0x26`** | **`RETK`** | `1 0 0 1` | `STACK → PCH:PCL` & $SP ← SP - 2$ | AE Restore ($SP ← SP + 2$ in $T_4 … T_5$) | $T_0 … T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | **0** |
| **`0x2A`** | **`RETI`** | `1 0 1 0` | `STACK → PCH:PCL` & $SP ← SP - 2$ | $IE ← 1$ ($T_4$) | $T_0 … T_4$ | Resets asynchronously at $T_5$ | $-2$ |
| **`0x2E`** | **`HALT`** | `1 0 1 1` | Freeze Clock (`HALT_STAT`) | Idle | $T_0 … T_2$ | Resets asynchronously at $T_3$ / Halt | 0 |
| **`0x33`** | **`JU`** | `1 1 0 0` | `RegA:RegB → PCH:PCL` ($T_2 … T_3$) | Idle | $T_0 … T_3$ | Resets asynchronously at $T_4$ | 0 |
| **`0x37`** | **`CALL`** | `1 1 0 1` | `PCH:PCL → STACK` & $SP ← SP + 2$ | `RegA:RegB → PCH:PCL` ($T_4 … T_5$) | $T_0 … T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | $+2$ |
| **`0x3B`** | **`PUSHPC`** | `1 1 1 0` | `PCH:PCL → STACK` & $SP ← SP + 2$ | Idle | $T_0 … T_3$ | Resets asynchronously at $T_4$ | $+2$ |
| **`0x3F`** | **`SWI`** | `1 1 1 1` | `PCH:PCL → STACK` & $SP ← SP + 2$ | Fixed SWI Vector $→ PC$ ($T_4 … T_5$) | $T_0 … T_5$ | Resets asynchronously at $T_0$ (Natural $T_5$) | $+2$ |

---

### Quadrant 1: Implicit-`RegA` Binary ALU (`OPCODE = 01_dd`)

Q1 uses `RegA` as the implicit second operand. The opcode destination field
selects the low two destination bits, while `opr[3]` selects the destination
bank. Thus Q1 can target every general or system destination without needing a
separate source-register field:

$$Destination = [opr[3], OPCODE[1:0]]$$

$$Source = RegA$$

The Q1 ALU operation is selected by the three-bit `ALU_OP` formed from
`opr[2:0]`. Its bitmap is deliberately arranged so the arithmetic/logic mode
and the dedicated `OR` path have simple decoder terms:

| `ALU_OP` | `LOGIC` | `OP1` | `OP0` | Mnemonic | Operation |
| --- | ---: | ---: | ---: | --- | --- |
| `000` | 0 | 0 | 0 | **`ADD dst, A`** | $dst \leftarrow dst + RegA$ |
| `001` | 0 | 0 | 1 | **`ADC dst, A`** | $dst \leftarrow dst + RegA + CF$ |
| `010` | 0 | 1 | 0 | **`SUB dst, A`** | $dst \leftarrow dst + ~RegA + 1$ |
| `011` | 0 | 1 | 1 | **`SBB dst, A`** | $dst \leftarrow dst + ~RegA + ~CF$ |
| `100` | 1 | 0 | 0 | **`XOR dst, A`** | $dst \leftarrow dst \oplus RegA$ |
| `101` | 1 | 0 | 1 | **`OR dst, A`** | $dst \leftarrow dst \lor RegA$ |
| `110` | 1 | 1 | 0 | **`AND dst, A`** | $dst \leftarrow dst \land RegA$ |
| `111` | 1 | 1 | 1 | **`ANDN dst, A`** | $dst \leftarrow dst \land ~RegA$ |

`LOGIC` is the physical `carry_kill` control. In arithmetic mode, `OP1`
controls `inv_b` and `OP0` selects the carry source. In logic mode, `OP1:OP0`
select the logic function. `OR` is routed through its dedicated NMOS logic
path; `AND` and `ANDN` share the AND tap, with `inv_b` selecting whether the
`RegA` input is inverted.

The following control lines are generated by a dedicated ALU decoder:

| Control line | Function |
| --- | --- |
| `carry_kill` | Disables carry propagation and forces the effective carry-in to `0` |
| `inv_b` | Inverts operand `B` and the selected carry-in |
| `tap_select` | Selects the shared `AND`/`ANDN` tap |
| `carry_source` | Selects `CF` or logical `0` as the carry source |

The effective carry-in is `CF XOR inv_b` when `carry_source` selects `CF`.
When `carry_source` selects `0`, it is `0 XOR inv_b`. `carry_kill`
overrides both cases and forces the effective carry-in to `0`.
Operation target follows $Dst ← Dst\;op\;RegA$.

#### Strict Timestep Execution Sequence:

For ALU operations, the main decoder selects the ALU B-source bus:

- **Q1:** `RegA → ALU B-source bus`
- **Q3 arithmetic:** `zero_extend(opr[0]) → ALU B-source bus`
- **Q3 unary:** the bus is unused; the dedicated unary path uses **Latch A**

* **$T_0$:** Fetch Opcode $→ IR$
* **$T_1$:** Fetch Operand $→ IR$
* **$T_2$:** Latch bus into **Latch B**. Keep the destination decoder disabled.
* **$T_3$:** Latch $Dst$ contents into **Latch A**. Route $Dst$ address to $Src$ decoder, disable $Dst$ decoder.
* **$T_4$:** Writeback $ALU\_OUT → Dst$. Disable the destination write-enable path.
* **$T_5$:** Asynchronous Sequencer Reset triggers at the start of $T_5$, returning execution state to $T_0$.

| Control lines `[carry_kill, inv_b, tap_select, carry_source]` | Mnemonic | Hardware Logic / Arithmetic Equation | Flags Updated | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- | --- |
| `[0, 0, 0, 0]` | **`ADD dst, A`** | $dst ← A (dst) + B (RegA) + 0$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[0, 1, 0, 0]` | **`SUB dst, A`** | $dst ← A (dst) + ~B (RegA) + 1$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[0, 0, 0, 1]` | **`ADC dst, A`** | $dst ← A (dst) + B (RegA) + CF$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[0, 1, 0, 1]` | **`SBB dst, A`** | $dst ← A (dst) + ~B (RegA) + ~CF$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[1, 0, 0, 0]` | **`XOR dst, A`** | $dst ← A (dst) ⊕ B (RegA)$ | $ZF$, $CF ← 0$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[1, 0, 0, 0]` + `OR_SELECT` | **`OR dst, A`** | $dst ← A (dst) ∨ B (RegA)$ (dedicated OR path) | $ZF$, $CF ← 0$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[1, 0, 1, 0]` | **`AND dst, A`** | $dst ← A (dst) ∧ B (RegA)$ (shared AND tap) | $ZF$, $CF ← 0$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| `[1, 1, 1, 1]` | **`ANDN dst, A`** | $dst ← A (dst) ∧ ~B (RegA)$ (shared AND tap with inverted B) | $ZF$, $CF ← 0$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |

---

### Quadrant 2: Load Immediate (`OPCODE = 10_dd`)

Loads 4-bit literal `#imm[3:0]` directly into target $dst[1:0]$ in $T_2$.
Q2 ignores `opr[3]` so that the operand remains a full 4-bit immediate. The
universal system-destination signal is therefore:

$$SYS\_DST = opr[3] \land \lnot Q2$$

**Resets asynchronously at $T_3$**.

| Binary Pattern | Mnemonic | Hardware Action | Flags | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- |
| `10_dd #imm` | **`LDI dst, #imm`** | $dst ← OPERAND[3:0]$ | None | $T_0 … T_2$ | Resets asynchronously at $T_3$ |

---

### Quadrant 3: Immediate ALU, Carry Propagate & Unary/Shift Matrix (`OPCODE = 11_dd`)

`LOGIC/EXT` (`opr[2]`) selects the shared arithmetic mode or, in Q3, the
dedicated unary/shift path. With `opr[2] = 0`, Q3 uses the same arithmetic
control convention as Q1, but latches the one-bit immediate `opr[0]` into
Latch B as a zero-extended value (`B = 0x0` or `B = 0x1`). With
`opr[2] = 1`, `opr[1:0]` select the unary operation. These operations use
Latch A only; Latch B is not part of the unary/shift data path:

| `opr[1:0]` | Mnemonic | Hardware Logic |
| --- | --- | --- |
| `00` | **`NOT dst`** | $dst \leftarrow ~dst$ |
| `01` | **`SHR dst`** | $dst \leftarrow dst >> 1$; $dst[3] \leftarrow 0$; $CF \leftarrow dst[0]$ |
| `10` | **`SHL dst`** | $dst \leftarrow dst << 1$; $dst[0] \leftarrow 0$; $CF \leftarrow dst[3]$ |
| `11` | **`CLR dst`** | $dst \leftarrow 0x0$ |

The dedicated path does not use the normal arithmetic carry chain.

#### Strict Timestep Execution Sequence:

For ALU operations, the main decoder selects the ALU B-source bus:

- **Q1:** `RegA → ALU B-source bus`
- **Q3 arithmetic:** `zero_extend(opr[0]) → ALU B-source bus`
- **Q3 unary:** the bus is unused; the dedicated unary path uses **Latch A**

* **$T_0$:** Fetch Opcode $→ IR$
* **$T_1$:** Fetch Operand $→ IR$
* **$T_2$:** Latch bus into **Latch B**. Keep the destination decoder disabled.
* **$T_3$:** Latch $Dst$ contents into **Latch A**. Route $Dst$ address to $Src$ decoder, disable $Dst$ decoder.
* **$T_4$:** Writeback $ALU\_OUT → Dst$. Disable the destination write-enable path.
* **$T_5$:** Asynchronous Sequencer Reset triggers at the start of $T_5$, returning execution state to $T_0$.

| `opr[3]` (`SYS`) | `opr[2]` (`LOGIC/EXT`) | `opr[1]` (`INV_B` / unary op) | `opr[0]` (`CF/0` / unary op) | Mnemonic | $C_{in}$ Source & $B$-Bus State | Hardware Logic | Flags Updated | Active Steps | Asynchronous Reset Step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`0` / `1`** | `0` | `0` | `0` | **`ADC dst`** | **$C_{in} ← CF$**, $B = zero\text{-}extend(opr[0]) = 0x0$ | $dst ← dst + 0 + CF$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `0` | `0` | `1` | **`ADDI dst, #1`** | $C_{in} ← 0$, $B = zero\text{-}extend(opr[0]) = 0x1$ | $dst ← dst + 1$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `0` | `1` | `0` | **`SBB dst`** | **$C_{in} ← CF$**, $B = zero\text{-}extend(opr[0]) = 0x0$ | $dst ← dst + ~0 + ~CF$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `0` | `1` | `1` | **`SUBI dst, #1`** | $C_{in} ← 0$, $B = zero\text{-}extend(opr[0]) = 0x1$ | $dst ← dst + ~1 + 1$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `1` | `0` | `0` | **`NOT dst`** | Dedicated inverter path | $dst ← ~dst$ | $ZF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `1` | `0` | `1` | **`SHR dst`** | Wired logical right shift | $dst ← dst >> 1$; $dst[3] ← 0$; $CF ← dst[0]$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `1` | `1` | `0` | **`SHL dst`** | Wired logical left shift | $dst ← dst << 1$; $dst[0] ← 0$; $CF ← dst[3]$ | $ZF, CF$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |
| **`0` / `1`** | `1` | `1` | `1` | **`CLR dst`** | ALU drivers disabled | $dst ← 0x0$ | $ZF ← 1, CF ← 0$ | $T_0 … T_4$ | Resets asynchronously at $T_5$ |

---

### Flag Update Timing

`CF` and `ZF` are updated only during ALU writeback at `T4`.

During `T2` and `T3`, the ALU uses the slave-visible flag values as stable
inputs. The ALU result and newly generated flag values are written into the
master flag latch during the `T4` writeback window. The slave flag latch is
updated only after that writeback window, so the new `CF`/`ZF` values cannot
feed back into the ALU during the same operation.

Consequently:

* ALU inputs see the flags from the preceding completed instruction;
* `CF` and `ZF` become architecturally visible after `T4`;
* non-ALU instructions preserve flags unless explicitly targeting `RegFLAGS`;
* master/slave flag storage prevents carry and zero-detection race conditions
  during writeback.

---

## 6. Master Pipeline & Timestep Schedule ($T_0 … T_5$)

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
| **Q0: Register Move** | Fetch Opcode $→ IR$ | Fetch Operand $→ IR$ | Drive Bus & Writeback | Asynchronous Reset at $T_3$ | — | — |
| **Q0: Memory Access** | Fetch Opcode $→ IR$ | Fetch Operand $→ IR$ | Drive `RAM[RegC:RegD]` | Asynchronous Reset at $T_3$ | — | — |
| **Q0: Passive `NOP` (`0x00`)** | Fetch Opcode $→ IR$ | Fetch `0x0` Payload | Passive Idle (Buses Off) | Passive Idle (Buses Off) | Passive Idle (Buses Off) | Asynchronous Reset at $T_0$ (Natural $T_5$) |
| **Q0: Single-Phase Escape** | Fetch Opcode $→ IR$ | Fetch Operand $→ IR$ | Execute Phase 1 Step 1 | Execute Phase 1 Step 2 | Asynchronous Reset at $T_4$ | — |
| **Q0: Multi-Phase Escape** | Fetch Opcode $\rightarrow IR$ | Fetch Operand $\rightarrow IR$ | Phase 1: Stack Push/Pop (`SP ± 1`) | Phase 1: Stack Push/Pop (`SP ± 1`) | Phase 2: Vector high-nibble transfer / AE restore step 1 (`SP + 1`) | Phase 2: Vector low-nibble transfer / AE restore step 2 (`SP + 1`); asynchronous reset at next `T0` |
| **Q1 / Q3: ALU Operations** | Fetch Opcode → `IR` | Fetch Operand → `IR` | **Latch `Dst` → Latch A** (Q1/Q3 destination selected by `SYS_DST`) | **`IMM = 0`: hardwired `RegA` → Latch B; `IMM = 1`: zero-extended `opr[0]` → Latch B; Q3 unary: Latch B unused** | **Write back `ALU_OUT` → `Dst`; update master `CF/ZF` latch** | Asynchronous reset at `T5`; slave flags update after `T4` |
| **Q2: Load Immediate** | Fetch Opcode $→ IR$ | Fetch Immediate $→ IR$ | Drive `#imm` $→ dst$ | Asynchronous Reset at $T_3$ | — | — |
| **Hardware Interrupt** | Master latch captures qualified `~IRQ ∧ IE ∧ ¬IRQ_ACTIVE` asynchronously; at `T0`, transfer to `IRQ_ACTIVE`, clear `IE`, and assert `PC_INC_DISABLE` | `IRQ_ACTIVE` causes `IR_DISABLE`; decoder enters IRQ sequence | Push $PCH_{return} \rightarrow STACK[SP]$, $SP \leftarrow SP + 1$ | Push $PCL_{return} \rightarrow STACK[SP]$, $SP \leftarrow SP + 1$; `~IRQ_ACK` remains asserted | Load `IRQ_VECTOR_H \rightarrow PCH`; `~IRQ_ACK` remains asserted | Load `IRQ_VECTOR_L \rightarrow PCL`; clear master during `T5` low phase and clear slave after `T5` |
