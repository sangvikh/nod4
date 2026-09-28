# NOD-4 Microprocessor Architecture & System Specification (v15.0 Master Core — Bitmapped Escapes & AE Stack Edition)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` Data Pointer / `[RegA:RegB]` Control-Flow Target Pointer)

**Fetch Mechanics:** Sequential Dual-Nibble Fetch (`OPCODE[3:0]`, `OPERAND[3:0]`)

**Physical Hierarchy:** 32-Pin Master Backplane Bus $\rightarrow$ Universal Base Cards (UBC) $\rightarrow$ Control Harnesses $\rightarrow$ Central Control Board (CCB) & Daughtercards

**Logic Standard:** Active-LOW discrete 2N7000 NMOS pass-transistors and depletion loads with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.

---

## 1. Electrical Standard, Clocking & Latch Mechanics

The NOD-4 operates on a two-phase micro-step sequence ($T_1 \dots T_6$) driven by the falling edge of the master clock (`CLK`).

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
                                            (Latch Open)            (Frozen on CLK Falling Edge)

```

### Level-Sensitive Write & OE/WE Timing Rules

* **Output Enable (`OE`):** Asserts continuously across the entire duration of a T-state step to allow passive pull-ups and dynamic bus capacitance ($C_g$) to charge and settle completely.
* **Write Enable (`WE`):** Strictly gated by **`CLK` LOW** ($\text{T\_step} \cdot \overline{\text{CLK}}$) to eliminate write-glitches, enforce data setup time, and freeze transparent latch contents on the trailing edge.

$$\text{LATCH\_ENABLE}_n = \overline{\text{\textasciitilde WE}_n} \lor \text{CLK}$$

$$\overline{\text{LATCH\_ENABLE}_n} = \text{\textasciitilde WE}_n \cdot \overline{\text{CLK}}$$

---

## 2. Register Architecture & Three-Pointer Model

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

Constructed using discrete 4-bit level-sensitive transparent latches. Registers $A/B$ and $C/D$ feature functional aliases reflecting their distinct pointer roles:

| Index (`[1:0]`) | Assembly Mnemonic | Functional Alias | Primary Function & Pointer Role |
| --- | --- | --- | --- |
| **`00`** | **`RegA`** | **`CPH`** (Control Pointer High) | Primary ALU Target / High Code Pointer Byte (`PCH_target`) |
| **`01`** | **`RegB`** | **`CPL`** (Control Pointer Low) | Working Register / Low Code Pointer Byte (`PCL_target`) |
| **`10`** | **`RegC`** | **`DPH`** (Data Pointer High) | High Data Memory Address Byte (`ADDR_H`) |
| **`11`** | **`RegD`** | **`DPL`** (Data Pointer Low) | Low Data Memory Address Byte (`ADDR_L`) |

### Bank 1: System Control Bank (`SYS = 1`)

Constructed using Master-Slave Universal Bit Cells (UBC) to prevent race conditions during updates.

| Index (`[1:0]`) | Mnemonic | Name | Primary Function | Special Hardware Action |
| --- | --- | --- | --- | --- |
| **`00`** | **`MEM`** | RAM Indirect Port | Indirect Data Access | Accesses external `RAM[RegC:RegD]` |
| **`01`** | **`STACK`** | Hardware Stack Port | Stack Push / Pop | Auto `DEC SP` on read, `INC SP` on write |
| **`10`** | **`SP`** | Stack Pointer | 4-Bit Stack Address Counter | Master-Slave Up/Down Counter (16-entry Return Stack) |
| **`11`** | **`RegFLAGS`** | Status Register | Machine Flags | Master-Slave Latch (`[CF, ZF, IE, UF]`) |

---

### The Three-Pointer Machine Model

The architecture establishes three independent, persistent pointers with clean functional isolation:

```text
       ┌─────────────────────────────────────────┐
       │                NOD-4 CPU                │
       ├─────────────────────────────────────────┤
       │  RegA:RegB (CPH:CPL) ──► Control Target │
       │  RegC:RegD (DPH:DPL) ──► Data Memory    │
       │  SP                  ──► Hardware Stack │
       └─────────────────────────────────────────┘

```

1. **`RegA:RegB` / `CPH:CPL` (Control-Flow Target Pointer):** Holds the persistent 8-bit destination address for `CALL [RegA:RegB]` and jump targets. Executing a subroutine call **uses** `RegA:RegB` as the target vector without altering its contents or disturbing `RegC:RegD`.
2. **`RegC:RegD` / `DPH:DPL` (Data-Memory Pointer):** Drives the active 8-bit external address bus (`ADDR_H[3:0]`, `ADDR_L[3:0]`) whenever `MEM` is referenced in Q0. A subroutine can call helper routines via `RegA:RegB` while preserving its active data memory index in `RegC:RegD`.
3. **`SP` (Hardware Stack Pointer):** Points to a dedicated internal 16-entry $\times$ 8-bit **Ascending Empty (AE)** return address stack (completely independent from the 256 $\times$ 4-bit unified RAM). Executing `ADDI SP, #1` or `SUBI SP, #1` in Q3 provides first-class, software-visible stack frame adjustments.

### Q0 Dual High-Bit Bank Matrix (`opr[3:2]`)

In Quadrant 0 (`00_2`), bit `opr[3]` sets destination bank (`DST_SYS`), and `opr[2]` sets source bank (`SRC_SYS`):

$$\text{Full Destination Register Address} = [\text{opr[3]}, \text{opr[1:0]}]$$

$$\text{Full Source Register Address} = [\text{opr[2]}, \text{opr[1:0]}]$$

* **Phase-Gated `SYS_SEL` Line:**
* During **$T_3$ / $T_4$ (Source Read):** Central Control Board asserts `opr[2]` onto internal `SYS_SEL` logic.
* During **$T_5$ / $T_6$ (Destination Write):** Central Control Board switches `SYS_SEL` to assert `opr[3]`.



| `opr[3]` (`DST_SYS`) | `opr[2]` (`SRC_SYS`) | Mode | Source Bank | Destination Bank | Example Mnemonic |
| --- | --- | --- | --- | --- | --- |
| **`0`** | **`0`** | **Gen $\rightarrow$ Gen** | General (`RegA`–`RegD`) | General (`RegA`–`RegD`) | `MOV RegA, RegB` |
| **`0`** | **`1`** | **Sys $\rightarrow$ Gen** | System (`MEM`–`RegFLAGS`) | General (`RegA`–`RegD`) | `MOV RegA, MEM` *(RAM Read)* |
| **`1`** | **`0`** | **Gen $\rightarrow$ Sys** | General (`RegA`–`RegD`) | System (`MEM`–`RegFLAGS`) | `MOV MEM, RegA` *(RAM Write)* |
| **`1`** | **`1`** | **Sys $\rightarrow$ Sys** | System (`MEM`–`RegFLAGS`) | System (`MEM`–`RegFLAGS`) | `MOV STACK, MEM` *(Direct Stack Push)* |

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

* **Bit 0 ($UF$ - User Flag):** Positioned at LSB to support zero-overhead conditional branching.
* **2-Cycle Conditional Branch Mechanism:**
1. Executing `SHR RegFLAGS` or `RCR RegFLAGS` ejects $UF$ directly out of Bit 0 into the Carry Flag ($CF$) in **1 cycle**.
2. The following instruction executes **`SC`** (Skip on Carry) or **`SNC`** (Skip on No Carry) in Q0 escapes to branch conditionally in **2 cycles** total, eliminating dedicated branch-steering logic.



---

## 4. 32-Pin Master Backplane Pinout & Hardware IRQ Handshake

The NOD-4 active backplane uses a 32-pin connector layout. All four machine flags (`CF`, `ZF`, `IE`, `UF`) and the hardware interrupt acknowledge line (`~IRQ_ACK`) are brought out directly to dedicated pins.

```text
 POWER, CLK & CTRL (01-06)         4-BIT FLAG RAIL (07-10)          MEMORY & PARALLEL BUSES (11-32)
[ 01-03 ] +5V, GND, CLK            [ 07 ] Carry Flag (CF)            [ 11-12 ] Memory OE / WE
[ 04 ] HALT_STAT Execution         [ 08 ] Zero Flag (ZF)             [ 13-16 ] Data Bus (BUS[3:0])
[ 05 ] ~IRQ Hardware Request       [ 09 ] Interrupt Enable (IE)      [ 17-20 ] Address High (ADDR_H[3:0])
[ 06 ] ~IRQ_ACK Hardware Acknowledge [ 10 ] User Flag (UF)            [ 21-24 ] Address Low (ADDR_L[3:0])
                                                                    [ 25-28 ] Opcode Rail (OPCODE[3:0])
                                                                    [ 29-32 ] Operand Rail (OPERAND[3:0])

```

| Pin # | Signal Name | Bus/Rail Group | Direction | Description |
| --- | --- | --- | --- | --- |
| **01** | `+5V` | Power Rail | System | Main Logic VCC Supply (+5V DC) |
| **02** | `GND` | Power Rail | System | Common System Circuit Ground |
| **03** | `CLK` | Master Clock | Input | Single-Phase Master Clock Drive |
| **04** | `HALT_STAT` | Status | Output | CPU Run/Halt & Trap State Line |
| **05** | `~IRQ` | Interrupt | Input | Active-LOW Hardware Interrupt Request Line |
| **06** | `~IRQ_ACK` | Interrupt | Output | Active-LOW Hardware Interrupt Acknowledge Strobe Pulse |
| **07** | `CF` | Flag Rail | Output | **Carry Flag** status output |
| **08** | `ZF` | Flag Rail | Output | **Zero Flag** status output |
| **09** | `IE` | Flag Rail | Output | **Interrupt Enable** status output |
| **10** | `UF` | Flag Rail | Output | **User Flag** status output (Direct LSB Branching) |
| **11** | `~MEM_OE` | Memory Control | Output | Active-LOW Memory Read Output Enable |
| **12** | `~MEM_WE` | Memory Control | Output | Active-LOW Memory Write Enable |
| **13–16** | `BUS[3:0]` | Data Bus | Bidirectional | Parallel 4-Bit Bidirectional Data Bus |
| **17–20** | `ADDR_H[3:0]` | High Address | Output | Upper 4-Bit Address Bus (`RegC` / `ADDR_H`) |
| **21–24** | `ADDR_L[3:0]` | Low Address | Output | Lower 4-Bit Address Bus (`RegD` / `ADDR_L`) |
| **25–28** | `OPCODE[3:0]` | Opcode Rail | Output | Pre-fetched Instruction Opcode Rail |
| **29–32** | `OPERAND[3:0]` | Operand Rail | Output | Pre-fetched Instruction Operand Control Rail (`OPERAND[3]` = Pin 29) |

### Explicit Hardware Interrupt Handshake Protocol

Hardware interrupt servicing utilizes an active pulse on `~IRQ_ACK` (Pin 06), decoupled from the status of the `IE` flag (Pin 09):

```text
~IRQ      (Pin 05) ────┐                                    ┌───────────────────────
                       └────────────────────────────────────┘ (Peripheral Releases)
~IRQ_ACK  (Pin 06) ──────────────────┐             ┌───────────────────────────────
                                     └─────────────┘ (1 T-step CPU Strobe)
IE        (Pin 09) ───────────┐
                              └────────────────────────────────────────────────────
                                (IE cleared in RegFLAGS by CPU)

```

1. **Request Assertion:** An external peripheral pulls `~IRQ` (Pin 05) LOW.
2. **Evaluation ($T_6$):** Central Control evaluates $\text{TRIGGER\_IRQ} = \overline{\text{\textasciitilde IRQ}} \cdot \text{IE}$.
3. **Acknowledge Pulse & State Update ($T_4 \dots T_5$):**
* Central Control drives a 1 T-step active-LOW pulse on `~IRQ_ACK` (Pin 06) to indicate CPU acceptance.
* Simultaneously, Central Control clears `IE` in `RegFLAGS` ($IE \leftarrow 0$), driving Pin 09 LOW to prevent nested interrupts.


4. **Peripheral Release:** The active-LOW pulse on `~IRQ_ACK` signals the peripheral to immediately release `~IRQ` (Pin 05).
5. **Vector Hijack & Return:** Return address `PCH:PCL` is saved to `STACK`, execution jumps to vector `0xF2`, and executing `RET` or `RETI` restores $IE \leftarrow 1$ (Pin 09 returns HIGH).

---

## 5. Quadrant Decoder Architecture & Master ISA Specification

Instruction execution utilizes two sequentially fetched 4-bit nibbles: `OPCODE[3:0]` and `OPERAND[3:0]`. In all ALU and Immediate modes, the destination register `dst[1:0]` is **strictly locked** inside `OPCODE[1:0]`.

```text
         OPCODE NIBBLE (Fetched First)               OPERAND NIBBLE (Fetched Second)
     ┌───────┬─────────┬─────────┬─────────┐     ┌───────────┬───────────┬───────────┬───────────┐
     │  IMM  │ ALU_EN  │  dst1   │  dst0   │     │ OPERAND[3]│ OPERAND[2]│ OPERAND[1]│ OPERAND[0]│
     └───────┴─────────┴─────────┴─────────┘     └───────────┴───────────┴───────────┴───────────┘
     ◄────── OP[3:2] ─► ◄── dst[1:0] ─────►       SYS Select   ADD/SUB or   EXT Mode    IMM1 or
        (Quadrant Select)   (ALWAYS HERE)        (0: General   Unary Op     (0: Arith   Unary SubOp
                                                  1: System)   Selector      1: Unary)   (0:#0, 1:#1)

```

### Master Quadrant Summary

| Quadrant | Binary (`OP[3:2]`) | Class | Operational Description |
| --- | --- | --- | --- |
| **Q0** | `00` | Data Moves & Control Escapes | Dual-bank register/memory moves (`opr[3:2]`). Diagonal opcodes ($dd == ss$) decode control escapes (`CALL`, `RET`, `RETK`, `NOP`, `SWI`, Skips) via bitmapped control primitives. |
| **Q1** | `01` | Reg-to-Reg Binary ALU | 4-function binary ALU (`ADD`, `SUB`, `XOR`, `AND`) targeting General Bank registers (`RegA`–`RegD`). |
| **Q2** | `10` | Load Immediate (`LDI`) | Drives 4-bit literal `#imm` payload directly from `OPERAND[3:0]` onto `BUS[3:0]` to target `dst[1:0]`. |
| **Q3** | `11` | Immediate ALU, Unary & Shifts | System/General 1-bit immediate math (`ADDI`/`SUBI` with `#imm1`), multi-nibble carry propagation (`ADC`/`SBB`), and fully orthogonal dual-bank unary matrix (`NOT`/`SHR`/`RCR`/`CLR`). |

---

### Quadrant 0: Data Moves & Diagonal Control Escapes (`OPCODE = 00_dd`)

#### 1. Standard Register & Memory Moves ($dd \neq ss$)

* **`OPCODE[3:0]`:** `[0, 0, dst1, dst0]`
* **`OPERAND[3:0]`:** `[DST_SYS, SRC_SYS, src1, src0]`

| Binary Pattern | Mnemonic | Operation | Description |
| --- | --- | --- | --- |
| `OP=00_dd, OPR=00_ss` | **`MOV dst, src`** | $dst_{\text{Gen}} \leftarrow src_{\text{Gen}}$ | General register to General register transfer |
| `OP=00_dd, OPR=01_ss` | **`LD dst, src`** | $dst_{\text{Gen}} \leftarrow \text{RAM}[src_{\text{Sys}}]$ | Memory / System read (`RegC:RegD` address) |
| `OP=00_dd, OPR=10_ss` | **`ST dst, src`** | $\text{RAM}[dst_{\text{Sys}}] \leftarrow src_{\text{Gen}}$ | Memory / System write (`RegC:RegD` address) |
| `OP=00_dd, OPR=11_ss` | **`MOV dst_sys, src_sys`** | $dst_{\text{Sys}} \leftarrow src_{\text{Sys}}$ | System register to System register transfer |

---

#### 2. Q0 Diagonal Bitmapped Control Escapes ($dd == ss$)

When destination register index matches source register index ($dst[1:0] == src[1:0]$ in $Q_0$), hardware completely suppresses standard register read/write enables (`DST_SYS` and `SRC_SYS` decoders are gated off). There is zero register collision.

Instead, the 4 active control bits—$dd[1:0]$ from `OPCODE[1:0]` and $cc[1:0]$ from `OPERAND[3:2]`—directly feed pass-gate control lines in a time-multiplexed, fixed 6-cycle ($T_1 \dots T_6$) control matrix.

$$\text{ESCAPE\_EN} = \text{IS\_Q0} \cdot (dd_1 \odot ss_1) \cdot (dd_0 \odot ss_0)$$

$$\text{STD\_REG\_DEC\_ENABLE} = \text{IS\_Q0} \cdot \overline{\text{ESCAPE\_EN}}$$

##### Direct Bitmapped Control Bit Allocations

$$\text{Control Vector} = \big[\, \underbrace{dd_1}_{\text{Stack Phase En}} \,,\, \underbrace{dd_0}_{\text{Phase 1 SubOp}} \,,\, \underbrace{cc_1}_{\text{Phase 2 Action / Flag Select}} \,,\, \underbrace{cc_0}_{\text{Target / Restore Select}} \,\big]$$

* **`dd1` (`OPCODE[1]` — Stack Operation Enable):**
* `0`: Non-Stack Control Operations (System Reset, Skips, PC Capture).
* `1`: Stack Control Operations (`RET`, `RETK`, `RETI`, `HALT`, `JU`, `CALL`, `PUSHPC`, `SWI`).


* **`dd0` (`OPCODE[0]` — Phase 1 Shared Sequence Selector):**
* When $dd_1 = 0$: `0` = Simple / System Ops, `1` = Conditional Flag Evaluation.
* When $dd_1 = 1$: `0` = **Shared Stack POP Sequence** ($SP--$, Read Stack $\rightarrow PC$), `1` = **Shared Stack PUSH Sequence** (Write $PC \rightarrow \text{Stack}$, $SP++$).


* **`cc1` (`OPERAND[3]` — Phase 2 Action / Flag Select):**
* Selects Phase 2 bus drive mode, or chooses condition flag (`0` = $ZF$, `1` = $CF$).


* **`cc0` (`OPERAND[2]` — Target Modifier / AE Restore Select):**
* Selects address drive target (`0` = `RegA:RegB`, `1` = Vector `0xF2`), condition invert, or $SP$ restore enable for `RETK`.



---

##### Fixed 6-Cycle Phase Composition ($T_1 \dots T_6$)

All 16 diagonal escape instructions run for a **uniform 6 T-steps** ($T_1 \dots T_6$), eliminating dynamic ring-counter reset logic and variable-length phase decoders:

```text
  T1        T2        T3          T4          T5          T6
┌─────────┬─────────┬───────────┬───────────┬───────────┬───────────┐
│ Fetch   │ Fetch   │  Phase 1  │  Phase 1  │  Phase 2  │  Phase 2  │
│ Opcode  │ Operand │  Step 1   │  Step 2   │  Step 1   │  Step 2   │
└─────────┴─────────┴───────────┴───────────┴───────────┴───────────┘
                     ◄── Stack / Eval Phase ──► ◄── Bus / Action Phase ─►
                                                         └── Reset @ T6

```

* **Fetch Phase ($T_1, T_2$):** Dual-nibble instruction fetch (`OPCODE` then `OPERAND`).
* **Phase 1 ($T_3, T_4$):** Dedicated to Stack operations (Push / Pop) or Flag condition sampling.
* **Phase 2 ($T_5, T_6$):** Dedicated to driving address vectors (`RegA:RegB` or Vector `0xF2`), performing $SP$ Ascending Empty restores (`RETK`), or asserting control resets/skips.

---

##### Ascending Empty (AE) Stack Mechanics & `RETK` Restore

The hardware return stack operates as **Ascending Empty (AE)**: $SP$ points to the next empty slot above valid data.

* **PUSH (`PUSHPC`, `CALL`, `SWI`):** Writes $PCH/PCL \rightarrow \text{STACK}[SP]$, then increments $SP$ ($SP \leftarrow SP + 1$ per nibble $\Rightarrow +2$ total).
* **POP (`RET`, `RETI`):** Decrements $SP$ ($SP \leftarrow SP - 1$ per nibble $\Rightarrow -2$ total), then reads $\text{STACK}[SP] \rightarrow PCH/PCL$.
* **Return & Keep Stack (`RETK`):** Uses the exact same shared POP sequence during $T_3, T_4$ ($SP--$, read stack into $PC$), and uses $T_5, T_6$ to increment $SP$ back up ($SP++, SP++$), restoring $SP$ to its original empty slot ($\text{Net } \Delta SP = 0$).

---

##### $4 \times 4$ Bitmapped Sub-Operation Layout

```text
                       OPERAND[3:2] SubOp Field (cc = cc1 cc0)
                   cc = 00         cc = 01         cc = 10         cc = 11
               ──────────────  ──────────────  ──────────────  ──────────────
dd = 00 (RegA) NOP    (0x00)   SKP    (0x04)   GETPC  (0x08)   SRESET (0x0C)
dd = 01 (RegB) SZ     (0x11)   SNZ    (0x15)   SC     (0x19)   SNC    (0x1D)
dd = 10 (RegC) RET    (0x22)   RETK   (0x26)   RETI   (0x2A)   HALT   (0x2E)
dd = 11 (RegD) JU     (0x33)   CALL   (0x37)   PUSHPC (0x3B)   SWI    (0x3F)

```

---

##### Master Q0 Bitmapped Diagonal Decode Matrix

| Binary (`OP_OPR`) | Hex Code | Mnemonic | Phase 1 Shared Action ($T_3, T_4$) | Phase 2 Shared Action ($T_5, T_6$) | Total T-Steps | Net $\Delta SP$ |
| --- | --- | --- | --- | --- | --- | --- |
| `00_00 0000` | **`0x00`** | **`NOP`** | Idle | Idle | **6** | 0 |
| `00_00 0100` | **`0x04`** | **`SKP`** | Idle | Unconditional Skip Pulse ($PC \leftarrow PC + 2$) | **6** | 0 |
| `00_00 1000` | **`0x08`** | **`GETPC`** | Idle | Latch $PCH:PCL \rightarrow RegA:RegB$ | **6** | 0 |
| `00_00 1100` | **`0x0C`** | **`SRESET`** | Idle | Assert Software System Reset Pulse | **6** | 0 |
| `00_01 0001` | **`0x11`** | **`SZ`** | Eval $ZF == 1$ | If True: Skip Pulse ($PC \leftarrow PC + 2$) | **6** | 0 |
| `00_01 0101` | **`0x15`** | **`SNZ`** | Eval $ZF == 0$ | If True: Skip Pulse ($PC \leftarrow PC + 2$) | **6** | 0 |
| `00_01 1001` | **`0x19`** | **`SC`** | Eval $CF == 1$ | If True: Skip Pulse ($PC \leftarrow PC + 2$) | **6** | 0 |
| `00_01 1101` | **`0x1D`** | **`SNC`** | Eval $CF == 0$ | If True: Skip Pulse ($PC \leftarrow PC + 2$) | **6** | 0 |
| `00_10 0010` | **`0x22`** | **`RET`** | **POP Sequence** ($SP--$, Read Stack $\rightarrow PC$) | Idle Phase 2 | **6** | **$-2$** |
| `00_10 0110` | **`0x26`** | **`RETK`** | **POP Sequence** ($SP--$, Read Stack $\rightarrow PC$) | **AE Restore Sequence** ($SP++, SP++$) | **6** | **0** |
| `00_10 1010` | **`0x2A`** | **`RETI`** | **POP Sequence** ($SP--$, Read Stack $\rightarrow PC$) | **Interrupt Enable** ($IE \leftarrow 1$) | **6** | **$-2$** |
| `00_10 1110` | **`0x2E`** | **`HALT`** | Idle Phase 1 | **Freeze Clock** (Assert `HALT_STAT`) | **6** | 0 |
| `00_11 0011` | **`0x33`** | **`JU`** | Idle Phase 1 | **Drive Target AB** (`RegA:RegB` $\rightarrow PC$) | **6** | 0 |
| `00_11 0111` | **`0x37`** | **`CALL`** | **PUSH Sequence** ($PC \rightarrow \text{Stack}$, $SP++$) | **Drive Target AB** (`RegA:RegB` $\rightarrow PC$) | **6** | **$+2$** |
| `00_11 1011` | **`0x3B`** | **`PUSHPC`** | **PUSH Sequence** ($PC \rightarrow \text{Stack}$, $SP++$) | Idle Phase 2 | **6** | **$+2$** |
| `00_11 1111` | **`0x3F`** | **`SWI`** | **PUSH Sequence** ($PC \rightarrow \text{Stack}$, $SP++$) | **Drive Target Vector** (Vector `0xF2` $\rightarrow PC$) | **6** | **$+2$** |

---

##### Discrete Control Pass-Gate Equations

1. **Shared Phase 1 Stack POP Enable (`RET`, `RETK`, `RETI`):**

$$\text{POP\_SEQ\_ENABLE} = \text{ESCAPE\_EN} \cdot (dd_1 \cdot \overline{dd_0}) \cdot \overline{cc_1 \cdot cc_0} \cdot (T_3 \lor T_4)$$


2. **Shared Phase 1 Stack PUSH Enable (`CALL`, `PUSHPC`, `SWI`):**

$$\text{PUSH\_SEQ\_ENABLE} = \text{ESCAPE\_EN} \cdot (dd_1 \cdot dd_0) \cdot (cc_1 \lor cc_0) \cdot (T_3 \lor T_4)$$


3. **Shared Phase 2 Address Bus Drive (`JU`, `CALL`, `SWI`):**

$$\text{DRIVE\_AB\_ENABLE} = \text{ESCAPE\_EN} \cdot (dd_1 \cdot dd_0) \cdot \overline{cc_1} \cdot (T_5 \lor T_6)$$


$$\text{DRIVE\_VEC\_ENABLE} = \text{ESCAPE\_EN} \cdot (dd_1 \cdot dd_0) \cdot (cc_1 \cdot cc_0) \cdot (T_5 \lor T_6)$$


4. **Shared Phase 2 Ascending Empty SP Restore (`RETK`):**

$$\text{SP\_RESTORE\_ENABLE} = \text{ESCAPE\_EN} \cdot (dd_1 \cdot \overline{dd_0}) \cdot (\overline{cc_1} \cdot cc_0) \cdot (T_5 \lor T_6)$$



---

### Quadrant 1: Register-to-Register Binary ALU (`OPCODE = 01_dd`)

Quadrant 1 operations configure the hardware ALU using a 2-bit control line `alu_op[1:0] = [carry_kill, inv_b]`.

```text
                      ALU CONTROL LINE MAPPING
           alu_op[1] ──────────────────► carry_kill
           alu_op[0] ──────────────────► inv_b (also forces Cin ◄─ ~Cin)

```

#### Ripple-Carry Hardware Mechanics

* **Input B Inversion (`inv_b`):** When `inv_b = 1`, input $B$ is bitwise inverted ($\overline{B}$), and the incoming carry line is inverted ($C_{in} \leftarrow \overline{C_{in}}$).
* **Carry Suppression (`carry_kill`):** When `carry_kill = 1`, carry propagation between adder stages is disabled, isolating individual bit-slice calculations.
* **AND Tap Extraction (`11`):** In `11` mode, carry is killed (`carry_kill = 1`), `inv_b` is forced to `0`, and the ALU multiplexer taps directly into the intermediate AND gates of the ripple-carry adder stages.

| `alu_op[1:0]` | Control Bits `[carry_kill, inv_b]` | Mnemonic | Hardware Logic / Arithmetic Equation | Flags |
| --- | --- | --- | --- | --- |
| **`00`** | `[0, 0]` | **`ADD dst, src`** | $dst \leftarrow A + B + C_{in}$ | $ZF, CF$ |
| **`01`** | `[0, 1]` | **`SUB dst, src`** | $dst \leftarrow A + \overline{B} + \overline{C_{in}}$ | $ZF, CF$ |
| **`10`** | `[1, 0]` | **`XOR dst, src`** | $dst \leftarrow A \oplus B$ *(Carry killed)* | $ZF$, $CF \leftarrow 0$ |
| **`11`** | `[1, 0]` *(Tap Mode)* | **`AND dst, src`** | $dst \leftarrow A \land B$ *(Tapped from adder AND gates)* | $ZF$, $CF \leftarrow 0$ |

---

### Quadrant 2: Load Immediate (`OPCODE = 10_dd`)

Loads a 4-bit literal value (`#imm[3:0]`, `#0..15`) directly into target register $dst[1:0]$.

* **`OPCODE[3:0]`:** `[1, 0, dst1, dst0]`
* **`OPERAND[3:0]`:** Literal 4-Bit Data (`#imm[3:0]`)

| Binary Pattern | Mnemonic | Hardware Action | Execution Cycle |
| --- | --- | --- | --- |
| `10_dd #imm` | **`LDI dst, #imm`** | $dst \leftarrow \text{OPERAND}[3:0]$ | Resets at $T_4$ |

---

### Quadrant 3: Immediate ALU, Carry Propagate & Unary/Shift Matrix (`OPCODE = 11_dd`)

In Quadrant 3, the `EXT` mode bit (`opr[1]`) determines whether execution uses the arithmetic path or routes to dedicated unary/shift multiplexers.

```text
                        Q3 OPERAND NIBBLE DECODING (opr[3:0])
  ┌──────────────┬──────────────┬──────────────┬──────────────┐
  │    opr[3]    │    opr[2]    │    opr[1]    │    opr[0]    │
  ├──────────────┼──────────────┼──────────────┼──────────────┤
  │   SYS_SEL    │  Arith Op    │   EXT MODE   │    inv_b /   │
  │ (0: General) │ (0: ADD/ADC) │ (0: Arith)   │  SubOp Bit   │
  │ (1: System)  │ (1: SUB/SBB) │ (1: Unary)   │   (0: #0)    │
  │              │              │              │   (1: #1)    │
  └──────────────┴──────────────┴──────────────┴──────────────┘

```

#### 1. Multi-Nibble Carry Routing Mechanics (`EXT = 0`)

When operating in **Arithmetic Mode (`EXT = 0`)**, bit `opr[0]` acts as a dual-function control: it selects between immediate payload values (`#0` vs. `#1`) and toggles the carry-in source ($C_{in}$):

* **Carry Propagation Mode (`opr[0] = 0` / Immediate `#0`):**
* **$B$-Bus Drive:** Sets $B = 0\text{x0}$ (for ADD) or $B = 0\text{xF}$ (for SUB).
* **$C_{in}$ Source Gate:** The control logic opens a pass-gate routing the **Carry Flag directly into Carry-In** ($C_{in} \leftarrow CF$).
* **Result:** Performs $dst \leftarrow dst + 0 + CF$ (`ADC`) or $dst \leftarrow dst + 0\text{xF} + CF$ (`SBB`), allowing clean 8-bit, 12-bit, or 16-bit chained arithmetic across multiple 4-bit nibble cycles.


* **Fixed Immediate Mode (`opr[0] = 1` / Immediate `#1`):**
* **$B$-Bus Drive:** Sets `inv_b = 1` ($B = 0\text{x1}$ for ADD, $B = 0\text{xE}$ for SUB).
* **$C_{in}$ Source Gate:** $C_{in}$ is derived statically through `inv_b` inversion ($C_{in} \leftarrow \overline{C_{in}}$), executing direct increment (`ADDI #1`) or decrement (`SUBI #1`) without inheriting prior Carry Flag states.



#### 2. Unary & Clear Modes (`EXT = 1`)

* **Shift / Invert Mode (`opr[2:0] = 010`, `011`, `100`):** Bypasses the binary adder to engage dedicated pass-gate shift networks (`NOT`, `SHR`, `RCR`).
* **Output Disable Clear Mode (`CLR`, `opr[2:0] = 111`):** Disables all ALU output pass-transistors, disconnecting the ALU from the internal bus. Passive $2.2\text{ k}\Omega$ pull-down/default logic forces `0x0` onto target register inputs while asserting $ZF \leftarrow 1$ and $CF \leftarrow 0$.

---

#### Master Q3 Decoding Table

| `opr[3]` (`SYS`) | `opr[2]` | `opr[1]` (`EXT`) | `opr[0]` | Mnemonic | $C_{in}$ Source & $B$-Bus State | Hardware Logic | Flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`0` / `1**` | `0` | **`0`** | `0` | **`ADC dst`** | **$C_{in} \leftarrow CF$**, $B = 0\text{x0}$ | $dst \leftarrow dst + 0 + CF$ | $ZF, CF$ |
| **`0` / `1**` | `0` | **`0`** | `1` | **`ADDI dst, #1`** | $C_{in}$ static (`inv_b = 1`), $B = 0\text{x1}$ | $dst \leftarrow dst + 1$ | $ZF, CF$ |
| **`0` / `1**` | `1` | **`0`** | `0` | **`SBB dst`** | **$C_{in} \leftarrow CF$**, $B = 0\text{xF}$ | $dst \leftarrow dst + 0\text{xF} + CF$ | $ZF, CF$ |
| **`0` / `1**` | `1` | **`0`** | `1` | **`SUBI dst, #1`** | $C_{in}$ static (`inv_b = 1`), $B = 0\text{xE}$ | $dst \leftarrow dst + 0\text{xE}$ | $ZF, CF$ |
| **`0` / `1**` | `0` | **`1`** | `0` | **`NOT dst`** | Unary Pass Gate | $dst \leftarrow \overline{dst}$ | $ZF$ |
| **`0` / `1**` | `0` | **`1`** | `1` | **`SHR dst`** | Shift Logic ($0 \rightarrow dst[3]$) | $dst[0] \rightarrow CF$ | $ZF, CF$ |
| **`0` / `1**` | `1` | **`1`** | `0` | **`RCR dst`** | Shift Logic ($CF \rightarrow dst[3]$) | $dst[0] \rightarrow CF$ | $ZF, CF$ |
| **`0` / `1**` | `1` | **`1`** | `1` | **`CLR dst`** | ALU Drivers Off | $dst \leftarrow 0\text{x0}$ | $ZF \leftarrow 1, CF \leftarrow 0$ |

---

## 6. Pipeline Timestep Matrix ($T_1 \dots T_6$)

| Instruction Class | $T_1$ (Addr Drive / Precharge) | $T_2$ (Fetch Opcode / PC+1) | $T_3$ (Phase 1 Step 1) | $T_4$ (Phase 1 Step 2) | $T_5$ (Phase 2 Step 1) | $T_6$ (Phase 2 Step 2 / Reset) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `opr[2]` $\rightarrow$ `SYS_SEL` | Assert `~OE1[src]` $\rightarrow$ `BUS` | Switch `SYS_SEL` $\rightarrow$ `opr[3]` | Assert `~WE[dst]` on `CLK` LOW |
| **Q0: Memory Read** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `RegC:RegD` $\rightarrow$ ADDR | Assert `~MEM_OE` $\rightarrow$ `BUS` | Switch `SYS_SEL` $\rightarrow$ `DST_SYS` | Assert `~WE[dst]` on `CLK` LOW |
| **Q0: Control Escape (Fixed 6-Cycle)** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Phase 1: Stack Push/Pop or Flag Sample | Phase 1: Stack Push/Pop or Flag Sample | Phase 2: Vector Drive / SP AE Restore | Phase 2: Vector Drive / Reset Pipeline |
| **Q1: Reg-Reg ALU** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `~OE1[src]` $\rightarrow$ `Latch_B` | Drive `~OE2[dst]` $\rightarrow$ `Latch_A` | Hold $C_g$ Compute State | Write `ALU_OUT` $\rightarrow$ `dst`, Sample Flags |
| **Q2: Load Immediate** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `OPERAND` $\rightarrow$ `BUS` | Assert `~WE[dst]` on `CLK` LOW | Reset Pipeline State | — |
| **Q3: Immediate ALU** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Sample `#imm1` / `EXT` $\rightarrow$ ALU Input B | Drive `~OE2[dst]` $\rightarrow$ `Latch_A` | Compute Result | Write `ALU_OUT` $\rightarrow$ `dst`, Sample Flags |
| **Hardware Interrupt** | Freeze `PC`, Force `NOP` | Fetch `NOP` Payload | Push $PCL_{\text{return}} \rightarrow$ STACK | Push $PCH_{\text{return}} \rightarrow$ STACK, Pulse `~IRQ_ACK` (Pin 06) | Clear $IE \leftarrow 0$ (Pin 09 LOW) | Load Vector `0xF2` $\rightarrow PCH:PCL$ |