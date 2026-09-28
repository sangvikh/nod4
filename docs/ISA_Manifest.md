# NOD-4 Microprocessor Architecture & System Specification (v15.1 Master Core — Passive NOP & Slot-Aligned Escapes Edition)



**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` Data Pointer / `[RegA:RegB]` Control-Flow Target Pointer)

**Fetch Mechanics:** Sequential Dual-Nibble Fetch (`OPCODE[3:0]`, `OPERAND[3:0]`)

**Physical Hierarchy:** 32-Pin Master Backplane Bus $\rightarrow$ Universal Base Cards (UBC) $\rightarrow$ Control Harnesses $\rightarrow$ Central Control Board (CCB) & Daughtercards

**Logic Standard:** Active-LOW discrete 2N7000 NMOS pass-transistors and passive pull-up resistors to +5V. Logic levels: 5V = 0 (inactive/pull-up), 0V = 1 (active/NMOS pull-down).

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
| **`00`** | **`RegA`** | **`CPH`** (Control Pointer High) | Primary ALU Target / High Code Pointer Byte (`PCH_target`)

 |
| **`01`** | **`RegB`** | **`CPL`** (Control Pointer Low) | Working Register / Low Code Pointer Byte (`PCL_target`)

 |
| **`10`** | **`RegC`** | **`DPH`** (Data Pointer High) | High Data Memory Address Byte (`ADDR_H`)

 |
| **`11`** | **`RegD`** | **`DPL`** (Data Pointer Low) | Low Data Memory Address Byte (`ADDR_L`)

 |

### Bank 1: System Control Bank (`SYS = 1`)



Constructed using Master-Slave Universal Bit Cells (UBC) to prevent race conditions during updates.

| Index (`[1:0]`) | Mnemonic | Name | Primary Function | Special Hardware Action |
| --- | --- | --- | --- | --- |
| **`00`** | **`MEM`** | RAM Indirect Port | Indirect Data Access | Accesses external `RAM[RegC:RegD]`<br> |
| **`01`** | **`STACK`** | Hardware Stack Port | Stack Push / Pop | Automatic stack-pointer update on read/write

 |
| **`10`** | **`SP`** | Stack Pointer | 4-Bit Stack Nibble Counter | Master-Slave/ripple Up/Down Counter (16-nibble Return Stack)

 |
| **`11`** | **`RegFLAGS`** | Status Register | Machine Flags | Master-Slave Latch (`[CF, ZF, IE, UF]`)

 |

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


3. **`SP` (Hardware Stack Pointer):** Points to a dedicated internal 16-nibble **Ascending Empty (AE)** return stack (completely independent from the 256 $\times$ 4-bit unified RAM). Two stack nibbles hold one return address. Executing `ADDI SP, #1` or `SUBI SP, #1` in Q3 provides software-visible stack-frame adjustments.



### Q0 Dual High-Bit Bank Matrix (`opr[3:2]`)



In Quadrant 0 (`00_2`), bit `opr[3]` sets destination bank (`DST_SYS`), and `opr[2]` sets source bank (`SRC_SYS`):

$$\text{Full Destination Register Address} = [\text{opr[3]}, \text{opr[1:0]}]$$

$$\text{Full Source Register Address} = [\text{opr[2]}, \text{opr[1:0]}]$$

* **Phase-Gated `SYS_SEL` Line:**

* During **$T_3$ / $T_4$ (Source Read):** Central Control Board asserts `opr[2]` onto internal `SYS_SEL` logic.


* During **$T_5$ / $T_6$ (Destination Write):** Central Control Board switches `SYS_SEL` to assert `opr[3]`.





| `opr[3]` (`DST_SYS`) | `opr[2]` (`SRC_SYS`) | Mode | Source Bank | Destination Bank | Example Mnemonic |
| --- | --- | --- | --- | --- | --- |
| **`0`** | **`0`** | **Gen $\rightarrow$ Gen** | General (`RegA`–`RegD`) | General (`RegA`–`RegD`) | `MOV RegA, RegB`<br> |
| **`0`** | **`1`** | **Sys $\rightarrow$ Gen** | System (`MEM`–`RegFLAGS`) | General (`RegA`–`RegD`) | `MOV RegA, MEM` *(RAM Read)*<br> |
| **`1`** | **`0`** | **Gen $\rightarrow$ Sys** | General (`RegA`–`RegD`) | System (`MEM`–`RegFLAGS`) | `MOV MEM, RegA` *(RAM Write)*<br> |
| **`1`** | **`1`** | **Sys $\rightarrow$ Sys** | System (`MEM`–`RegFLAGS`) | System (`MEM`–`RegFLAGS`) | `MOV STACK, MEM` *(Direct Stack Push)*<br> |

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
| **01** | `+5V` | Power Rail | System | Main Logic VCC Supply (+5V DC)

 |
| **02** | `GND` | Power Rail | System | Common System Circuit Ground

 |
| **03** | `CLK` | Master Clock | Input | Single-Phase Master Clock Drive

 |
| **04** | `HALT_STAT` | Status | Output | CPU Run/Halt & Trap State Line

 |
| **05** | `~IRQ` | Interrupt | Input | Active-LOW Hardware Interrupt Request Line

 |
| **06** | `~IRQ_ACK` | Interrupt | Output | Active-LOW Hardware Interrupt Acknowledge Strobe Pulse

 |
| **07** | `CF` | Flag Rail | Output | **Carry Flag** status output

 |
| **08** | `ZF` | Flag Rail | Output | **Zero Flag** status output

 |
| **09** | `IE` | Flag Rail | Output | **Interrupt Enable** status output

 |
| **10** | `UF` | Flag Rail | Output | **User Flag** status output (Direct LSB Branching)

 |
| **11** | `~MEM_OE` | Memory Control | Output | Active-LOW Memory Read Output Enable

 |
| **12** | `~MEM_WE` | Memory Control | Output | Active-LOW Memory Write Enable

 |
| **13–16** | `BUS[3:0]` | Data Bus | Bidirectional | Parallel 4-Bit Bidirectional Data Bus

 |
| **17–20** | `ADDR_H[3:0]` | High Address | Output | Upper 4-Bit Address Bus (`RegC` / `ADDR_H`)

 |
| **21–24** | `ADDR_L[3:0]` | Low Address | Output | Lower 4-Bit Address Bus (`RegD` / `ADDR_L`)

 |
| **25–28** | `OPCODE[3:0]` | Opcode Rail | Output | Pre-fetched Instruction Opcode Rail

 |
| **29–32** | `OPERAND[3:0]` | Operand Rail | Output | Pre-fetched Instruction Operand Control Rail (`OPERAND[3]` = Pin 29)

 |

### Hardware Interrupt Handshake Protocol



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


5. **Vector Hijack & Return:** Return address `PCH:PCL` is saved to `STACK`, execution jumps to the externally supplied IRQ vector, and executing `RETI` restores `IE ← 1` (Pin 09 returns HIGH). Ordinary `RET` preserves `IE`.

The IRQ vector is an 8-bit value supplied by the IRQ card or its associated
vector hardware. DIP switches may select the vector address. The selected
address may point to ROM, RAM, or MMIO; a RAM target can therefore contain a
software-configurable IRQ trampoline.

At the instruction-boundary takeover point (`T0`, called `T1` in the
one-indexed timing tables), the PC already contains the next instruction
address. IRQ therefore inhibits the normal PC increment while saving the
return address; it does not increment the PC again.



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
| **Q0** | `00` | Data Moves & Control Escapes | Dual-bank register/memory moves (`opr[3:2]`). Diagonal opcodes ($dd == ss$) decode control escapes (`CALL`, `RET`, `RETK`, `NOP`, `SWI`, Skips) via bitmapped control primitives.

 |
| **Q1** | `01` | Reg-to-Reg Binary ALU | 4-function binary ALU (`ADD`, `SUB`, `XOR`, `AND`) targeting General Bank registers (`RegA`–`RegD`).

 |
| **Q2** | `10` | Load Immediate (`LDI`) | Drives 4-bit literal `#imm` payload directly from `OPERAND[3:0]` onto `BUS[3:0]` to target `dst[1:0]`.

 |
| **Q3** | `11` | Immediate ALU, Unary & Shifts | System/General 1-bit immediate math (`ADDI`/`SUBI` with `#imm1`), multi-nibble carry propagation (`ADC`/`SBB`), and fully orthogonal dual-bank unary matrix (`NOT`/`SHR`/`RCR`/`CLR`).

 |

---

### Quadrant 0: Data Moves & Diagonal Control Escapes (`OPCODE = 00_dd`)



#### 1. Standard Register & Memory Moves ($dd \neq ss$)



* **`OPCODE[3:0]`:** `[0, 0, dst1, dst0]`

* **`OPERAND[3:0]`:** `[DST_SYS, SRC_SYS, src1, src0]`


| Binary Pattern | Mnemonic | Operation | Description |
| --- | --- | --- | --- |
| `OP=00_dd, OPR=00_ss` | **`MOV dst, src`** | $dst_{\text{Gen}} \leftarrow src_{\text{Gen}}$ | General register to General register transfer

 |
| `OP=00_dd, OPR=01_ss` | **`LD dst, src`** | $dst_{\text{Gen}} \leftarrow \text{RAM}[src_{\text{Sys}}]$ | Memory / System read (`RegC:RegD` address)

 |
| `OP=00_dd, OPR=10_ss` | **`ST dst, src`** | $\text{RAM}[dst_{\text{Sys}}] \leftarrow src_{\text{Gen}}$ | Memory / System write (`RegC:RegD` address)

 |
| `OP=00_dd, OPR=11_ss` | **`MOV dst_sys, src_sys`** | $dst_{\text{Sys}} \leftarrow src_{\text{Sys}}$ | System register to System register transfer

 |

---

#### 2. Q0 Diagonal Bitmapped Control Escapes ($dd == ss$)



When destination register index matches source register index ($dst[1:0] == src[1:0]$ in $Q_0$), hardware suppresses standard register read/write enables (`DST_SYS` and `SRC_SYS` decoders are gated off).

The 4 active control bits—$d_1, d_0$ from `OPCODE[1:0]` and $c_1, c_0$ from `OPERAND[3:2]`—directly drive pass-gate control lines in a time-multiplexed, slot-aligned control matrix.

$$\text{ESCAPE\_EN} = \text{IS\_Q0} \cdot (dd_1 \odot ss_1) \cdot (dd_0 \odot ss_0)$$

$$\text{STD\_REG\_DEC\_ENABLE} = \text{IS\_Q0} \cdot \overline{\text{ESCAPE\_EN}}$$

### Control-Flow Transfer Primitives

Diagonal escapes compose a small set of fixed transfers. These are the
authoritative architectural operations; individual escape instructions are
combinations of them rather than unrelated special cases.

| Primitive | Transfer |
| --- | --- |
| `PC_TO_STACK` | `PCH:PCL → STACK` |
| `STACK_TO_PC` | `STACK → PCH:PCL` |
| `TARGET_TO_PC` | `RegA:RegB → PCH:PCL` |
| `PC_TO_TARGET` | `PCH:PCL → RegA:RegB` |
| `SWI_VECTOR_TO_PC` | Fixed SWI vector → `PCH:PCL` |
| `IRQ_VECTOR_TO_PC` | External `IRQ_VECTOR[7:0]` → `PCH:PCL` |
| `PC_INC` | `PC ← PC + 2` |
| `IE_SET` | `IE ← 1` |
| `IE_CLEAR` | `IE ← 0` |
| `SP_RESTORE` | `SP ← SP + 2` |

The paired control-pointer transfers are explicit: `JU` is `RegA:RegB →
PCH:PCL`, while `GETPC` is the reverse transfer. The data pointer `RegC:RegD`
is not implicitly involved in control-flow operations.

The principal compositions are:

```text
JU     = TARGET_TO_PC
GETPC  = PC_TO_TARGET
CALL   = PC_TO_STACK + TARGET_TO_PC
PUSHPC = PC_TO_STACK
RET    = STACK_TO_PC
RETI   = STACK_TO_PC + IE_SET
RETK   = STACK_TO_PC + SP_RESTORE
SWI    = PC_TO_STACK + SWI_VECTOR_TO_PC
IRQ    = PC_TO_STACK + IE_CLEAR + IRQ_VECTOR_TO_PC
```

##### Direct Bitmapped Control Bit Allocations



$$\text{Control Vector} = \big[\, \underbrace{d_1}_{\text{Stack Enable}} \,,\, \underbrace{d_0}_{\text{Jump / PC Enable}} \,,\, \underbrace{c_1}_{\text{Action / Flag Select}} \,,\, \underbrace{c_0}_{\text{Target / Restore Select}} \,\big]$$

* **`d1` (`OPCODE[1]` — Stack Operation Enable):**

* `0`: Non-Stack Control Operations (`NOP`, `SKP`, `GETPC`, `SRESET`, Conditional Skips `SZ/SNZ/SC/SNC`).
* `1`: Stack Control Operations (`RET`, `RETK`, `RETI`, `HALT`, `JU`, `CALL`, `PUSHPC`, `SWI`).


* **`d0` (`OPCODE[0]` — Jump / Shared Sequence Selector):**

* When $d_1 = 0$: `0` = Subop / Idle Row (`NOP`, `SKP`, `GETPC`, `SRESET`), `1` = Conditional Flag Evaluation.
* When $d_1 = 1$: `0` = Shared Stack POP Sequence ($SP--$, Read Stack $\rightarrow PC$), `1` = Shared Stack PUSH Sequence (Write $PC \rightarrow \text{Stack}$, $SP++$).


* **`c1` (`OPERAND[3]` — Phase 2 Action / Flag Select):** Selects Phase 2 bus drive mode, or chooses condition flag (`0` = $ZF$, `1` = $CF$).


* **`c0` (`OPERAND[2]` — Target Modifier / AE Restore Select):** Selects
  address-drive target (`0` = `RegA:RegB`, `1` = the fixed SWI vector),
  condition invert, or $SP$ restore enable for `RETK`. Hardware IRQ entry
  uses the separate externally supplied `IRQ_VECTOR` source.



---

##### Timestep Boundaries ($T_1 \dots T_6$) & Passive `NOP` Mechanics



Operations execute across time-step slots with standard micro-step resets ($T_2$, $T_4$, or natural $T_6$):

```text
  T1        T2        T3          T4          T5          T6
┌─────────┬─────────┬───────────┬───────────┬───────────┬───────────┐
│ Fetch   │ Fetch   │  Phase 1  │  Phase 1  │  Phase 2  │  Phase 2  │
│ Opcode  │ Operand │  Step 1   │  Step 2   │  Step 1   │  Step 2   │
└─────────┴─────────┴───────────┴───────────┴───────────┴───────────┘
                     ◄── Stack / Eval Phase ──► ◄── Bus / Action Phase ─►

```

* **Passive `NOP` Execution (`0x00`):** `NOP` ($d_1=0, d_0=0, c_1=0, c_0=0$) requires **zero subop decoding logic and zero early-reset gates**. Because all action enable lines ($d_1, d_0$) sit at $0\text{ V}$ (passive inactive state), the machine steps passively through $T_3 \dots T_6$ doing nothing. At $T_6$, the natural shift register pulse resets the ring counter back to $T_1$.
* **Phase 1 ($T_3, T_4$):** Handles Stack operations (Push / Pop) or Flag condition sampling. Single-phase subops reset at $T_4$.


* **Phase 2 ($T_5, T_6$):** Drives address vectors (`RegA:RegB`, the fixed
  SWI vector, or the externally supplied `IRQ_VECTOR`), or performs $SP$
  Ascending Empty restores (`RETK`). Multi-phase subops reset at $T_6$.



---

##### Ascending Empty (AE) Stack Mechanics & `RETK` Restore



The hardware return stack operates as **Ascending Empty (AE)**: `SP` points to the next empty nibble above valid data. It contains 16 nibbles, so it can hold eight return-address bytes, or four complete 8-bit return addresses. The stack wraps modulo 16 nibbles.

* **PUSH (`PUSHPC`, `CALL`, `SWI`):** Writes $PCH/PCL \rightarrow \text{STACK}[SP]$, then increments $SP$ ($SP \leftarrow SP + 1$ per nibble $\Rightarrow +2$ total).


* **POP (`RET`, `RETI`):** Decrements `SP` once per nibble for two nibbles, then reads the resulting pair into `PCH:PCL`.


* **Return & Keep Stack (`RETK`):** Performs the normal two-nibble pop, then increments `SP` twice during phase 2. Net stack-pointer change is zero.

The same stack convention is used by ordinary `CALL` and hardware IRQ entry.
`RET` preserves `IE`; `RETI` sets `IE` after restoring the PC. The apparent
`PCL`-then-`PCH` order during POP is a consequence of the ascending-empty
stack; the stored return address remains `PCH:PCL`.

The physical two-cycle sequences are authoritative:

```text
PUSH (CALL, PUSHPC, SWI, IRQ):
    Tn:   STACK[SP] ← PCH ; SP ← SP + 1
    Tn+1: STACK[SP] ← PCL ; SP ← SP + 1

POP (RET, RETI, RETK):
    Tn:   SP ← SP - 1 ; PCL ← STACK[SP]
    Tn+1: SP ← SP - 1 ; PCH ← STACK[SP]
```



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



| Binary (`OP_OPR`) | Hex Code | Mnemonic | Phase 1 Shared Action ($T_3, T_4$) | Phase 2 Shared Action ($T_5, T_6$) | Total T-Steps | Early Reset Step | Net $\Delta SP$ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `00_00 0000` | **`0x00`** | **`NOP`** | Passive Idle | Passive Idle | **6** | **$T_6$ (Natural)** | 0 |
| `00_00 0100` | **`0x04`** | **`SKP`** | Drive `PC_INC` ($PC \leftarrow PC + 2$) | Idle Phase 2 | **4** | **$T_4$** | 0 |
| `00_00 1000` | **`0x08`** | **`GETPC`** | Latch $PCH:PCL \rightarrow RegA:RegB$ | Idle Phase 2 | **4** | **$T_4$** | 0 |
| `00_00 1100` | **`0x0C`** | **`SRESET`** | Assert System Reset Rail | Idle Phase 2 | **2** | **$T_2$** | 0 |
| `00_01 0001` | **`0x11`** | **`SZ`** | Eval $ZF == 1$ | True: `PC_INC` / False: Early Reset | **4 / 2** | **$T_4$ (True) / $T_2$ (False)** | 0 |
| `00_01 0101` | **`0x15`** | **`SNZ`** | Eval $ZF == 0$ | True: `PC_INC` / False: Early Reset | **4 / 2** | **$T_4$ (True) / $T_2$ (False)** | 0 |
| `00_01 1001` | **`0x19`** | **`SC`** | Eval $CF == 1$ | True: `PC_INC` / False: Early Reset | **4 / 2** | **$T_4$ (True) / $T_2$ (False)** | 0 |
| `00_01 1101` | **`0x1D`** | **`SNC`** | Eval $CF == 0$ | True: `PC_INC` / False: Early Reset | **4 / 2** | **$T_4$ (True) / $T_2$ (False)** | 0 |
| `00_10 0010` | **`0x22`** | **`RET`** | **POP Sequence** ($SP--$, Read Stack $\rightarrow PC$) | Idle Phase 2 | **4** | **$T_4$** | **$-2$** |
| `00_10 0110` | **`0x26`** | **`RETK`** | **POP Sequence** ($SP--$, Read Stack $\rightarrow PC$) | **AE Restore Sequence** ($SP++, SP++$) | **6** | **$T_6$ (Natural)** | **0** |
| `00_10 1010` | **`0x2A`** | **`RETI`** | **POP Sequence** ($SP--$, Read Stack $\rightarrow PC$) | **Interrupt Enable** ($IE \leftarrow 1$) | **4** | **$T_4$** | **$-2$** |
| `00_10 1110` | **`0x2E`** | **`HALT`** | Freeze Clock (Assert `HALT_STAT`) | Idle Phase 2 | **2** | **$T_2$** | 0 |
| `00_11 0011` | **`0x33`** | **`JU`** | **Drive Target AB** (`RegA:RegB` $\rightarrow PC$) | Idle Phase 2 | **4** | **$T_4$** | 0 |
| `00_11 0111` | **`0x37`** | **`CALL`** | **PUSH Sequence** ($PC \rightarrow \text{Stack}$, $SP++$) | **Drive Target AB** (`RegA:RegB` $\rightarrow PC$) | **6** | **$T_6$ (Natural)** | **$+2$** |
| `00_11 1011` | **`0x3B`** | **`PUSHPC`** | **PUSH Sequence** ($PC \rightarrow \text{Stack}$, $SP++$) | Idle Phase 2 | **4** | **$T_4$** | **$+2$** |
| `00_11 1111` | **`0x3F`** | **`SWI`** | **PUSH Sequence** ($PC \rightarrow \text{Stack}$, $SP++$) | **Drive SWI Vector** (fixed vector $\rightarrow PC$) | **6** | **$T_6$ (Natural)** | **$+2$** |

---

##### Discrete Pass-Gate & Sequencer Reset Control Equations



1. **Shared Phase 1 Stack POP Enable (`RET`, `RETK`, `RETI`):**


$$\text{POP\_SEQ\_ENABLE} = \text{ESCAPE\_EN} \cdot (d_1 \cdot \overline{d_0}) \cdot \overline{c_1 \cdot c_0} \cdot (T_3 \lor T_4)$$

2. **Shared Phase 1 Stack PUSH Enable (`CALL`, `PUSHPC`, `SWI`):**


$$\text{PUSH\_SEQ\_ENABLE} = \text{ESCAPE\_EN} \cdot (d_1 \cdot d_0) \cdot (c_1 \lor c_0) \cdot (T_3 \lor T_4)$$

3. **Shared Phase 2 Address Bus Drive (`JU`, `CALL`, `SWI`):**


$$\text{DRIVE\_AB\_ENABLE} = \text{ESCAPE\_EN} \cdot (d_1 \cdot d_0) \cdot \overline{c_1} \cdot (T_5 \lor T_6)$$

$$\text{DRIVE\_VEC\_ENABLE} = \text{ESCAPE\_EN} \cdot (d_1 \cdot d_0) \cdot (c_1 \cdot c_0) \cdot (T_5 \lor T_6)$$

4. **Shared Phase 2 Ascending Empty SP Restore (`RETK`):**


$$\text{SP\_RESTORE\_ENABLE} = \text{ESCAPE\_EN} \cdot (d_1 \cdot \overline{d_0}) \cdot (\overline{c_1} \cdot c_0) \cdot (T_5 \lor T_6)$$

5. **Sequencer Early Reset Logic ($T_2, T_4, T_6$):**

* **$T_2$ Reset Pulse:** Asserts **only** on non-matching conditional skips:



$$\text{RESET\_T2} = T_2 \cdot \underbrace{\overline{d_1} \cdot d_0}_{\text{Skip Row (01)}} \cdot \overline{\text{COND\_MATCH}}$$

* **$T_4$ Reset Pulse:** Asserts for single-phase instructions completing at $T_4$:

$$\text{RESET\_T4} = T_4 \cdot \text{SINGLE\_PHASE\_MASK}$$

* **$T_6$ Natural Reset:** Natural connection from 6th shift register stage directly to `SEQ_RESET` ($T_6 \rightarrow \text{SEQ\_RESET}$), recycling `NOP`, `RETK`, `CALL`, and `SWI`.

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
| **`00`** | `[0, 0]` | **`ADD dst, src`** | $dst \leftarrow A + B + C_{in}$ | $ZF, CF$<br> |
| **`01`** | `[0, 1]` | **`SUB dst, src`** | $dst \leftarrow A + \overline{B} + \overline{C_{in}}$ | $ZF, CF$<br> |
| **`10`** | `[1, 0]` | **`XOR dst, src`** | $dst \leftarrow A \oplus B$ *(Carry killed)* | $ZF$, $CF \leftarrow 0$<br> |
| **`11`** | `[1, 0]` *(Tap Mode)* | **`AND dst, src`** | $dst \leftarrow A \land B$ *(Tapped from adder AND gates)* | $ZF$, $CF \leftarrow 0$<br> |

---

### Quadrant 2: Load Immediate (`OPCODE = 10_dd`)



Loads a 4-bit literal value (`#imm[3:0]`, `#0..15`) directly into target register $dst[1:0]$.

* **`OPCODE[3:0]`:** `[1, 0, dst1, dst0]`

* **`OPERAND[3:0]`:** Literal 4-Bit Data (`#imm[3:0]`)



| Binary Pattern | Mnemonic | Hardware Action | Execution Cycle |
| --- | --- | --- | --- |
| `10_dd #imm` | **`LDI dst, #imm`** | $dst \leftarrow \text{OPERAND}[3:0]$ | Resets at $T_4$<br> |

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


* **Result:** Performs $dst \leftarrow dst + 0 + CF$ (`ADC`) or $dst \leftarrow dst + 0\text{xF} + CF$ (`SBB`), allowing clean multi-nibble chained arithmetic.




* **Fixed Immediate Mode (`opr[0] = 1` / Immediate `#1`):**

* **$B$-Bus Drive:** Sets `inv_b = 1` ($B = 0\text{x1}$ for ADD, $B = 0\text{xE}$ for SUB).


* **$C_{in}$ Source Gate:** $C_{in}$ is derived statically through `inv_b` inversion ($C_{in} \leftarrow \overline{C_{in}}$), executing direct increment (`ADDI #1`) or decrement (`SUBI #1`) without inheriting prior Carry Flag states.





#### 2. Unary & Clear Modes (`EXT = 1`)



* **Shift / Invert Mode (`opr[2:0] = 010`, `011`, `100`):** Bypasses the binary adder to engage dedicated pass-gate shift networks (`NOT`, `SHR`, `RCR`).


* **Output Disable Clear Mode (`CLR`, `opr[2:0] = 111`):** Disables all ALU output pass-transistors, disconnecting the ALU from the internal bus. Dynamic pull-down logic forces `0x0` onto target register inputs while asserting $ZF \leftarrow 1$ and $CF \leftarrow 0$.



---

#### Master Q3 Decoding Table



| `opr[3]` (`SYS`) | `opr[2]` | `opr[1]` (`EXT`) | `opr[0]` | Mnemonic | $C_{in}$ Source & $B$-Bus State | Hardware Logic | Flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **`0` / `1**` | `0` | **`0`** | `0` | **`ADC dst`** | **$C_{in} \leftarrow CF$**, $B = 0\text{x0}$ | $dst \leftarrow dst + 0 + CF$ | $ZF, CF$<br> |
| **`0` / `1**` | `0` | **`0`** | `1` | **`ADDI dst, #1`** | $C_{in}$ static (`inv_b = 1`), $B = 0\text{x1}$ | $dst \leftarrow dst + 1$ | $ZF, CF$<br> |
| **`0` / `1**` | `1` | **`0`** | `0` | **`SBB dst`** | **$C_{in} \leftarrow CF$**, $B = 0\text{xF}$ | $dst \leftarrow dst + 0\text{xF} + CF$ | $ZF, CF$<br> |
| **`0` / `1**` | `1` | **`0`** | `1` | **`SUBI dst, #1`** | $C_{in}$ static (`inv_b = 1`), $B = 0\text{xE}$ | $dst \leftarrow dst + 0\text{xE}$ | $ZF, CF$<br> |
| **`0` / `1**` | `0` | **`1`** | `0` | **`NOT dst`** | Unary Pass Gate | $dst \leftarrow \overline{dst}$ | $ZF$<br> |
| **`0` / `1**` | `0` | **`1`** | `1` | **`SHR dst`** | Shift Logic ($0 \rightarrow dst[3]$) | $dst[0] \rightarrow CF$ | $ZF, CF$<br> |
| **`0` / `1**` | `1` | **`1`** | `0` | **`RCR dst`** | Shift Logic ($CF \rightarrow dst[3]$) | $dst[0] \rightarrow CF$ | $ZF, CF$<br> |
| **`0` / `1**` | `1` | **`1`** | `1` | **`CLR dst`** | ALU Drivers Off | $dst \leftarrow 0\text{x0}$ | $ZF \leftarrow 1, CF \leftarrow 0$<br> |

---

## 6. Pipeline Timestep Matrix ($T_1 \dots T_6$)



| Instruction Class | $T_1$ (Addr Drive / Precharge) | $T_2$ (Fetch Opcode / PC+1) | $T_3$ (Phase 1 Step 1) | $T_4$ (Phase 1 Step 2) | $T_5$ (Phase 2 Step 1) | $T_6$ (Phase 2 Step 2 / Reset) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `opr[2]` $\rightarrow$ `SYS_SEL` | Assert `~OE1[src]` $\rightarrow$ `BUS` | Switch `SYS_SEL` $\rightarrow$ `opr[3]` | Assert `~WE[dst]` on `CLK` LOW

 |
| **Q0: Memory Read** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `RegC:RegD` $\rightarrow$ ADDR | Assert `~MEM_OE` $\rightarrow$ `BUS` | Switch `SYS_SEL` $\rightarrow$ `DST_SYS` | Assert `~WE[dst]` on `CLK` LOW

 |
| **Q0: Passive `NOP` (`0x00`)** | Assert `PC` $\rightarrow$ ADDR | Fetch `0x0` Payload | Passive Idle (Buses Off) | Passive Idle (Buses Off) | Passive Idle (Buses Off) | Passive Idle $\rightarrow$ Natural $T_6$ Reset |
| **Q0: Single-Phase Escapes** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Stack Pop / Target AB Drive | Stack Pop / Target AB Drive | — (Early Reset @ $T_4$) | —

 |
| **Q0: Multi-Phase Escapes** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Phase 1: Stack Push/Pop | Phase 1: Stack Push/Pop | Phase 2: Vector / AE Restore | Phase 2: Reset Pipeline @ $T_6$<br> |
| **Q1: Reg-Reg ALU** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `~OE1[src]` $\rightarrow$ `Latch_B` | Drive `~OE2[dst]` $\rightarrow$ `Latch_A` | Hold $C_g$ Compute State | Write `ALU_OUT` $\rightarrow$ `dst`, Sample Flags

 |
| **Q2: Load Immediate** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `OPERAND` $\rightarrow$ `BUS` | Assert `~WE[dst]` on `CLK` LOW | Reset Pipeline State | —

 |
| **Q3: Immediate ALU** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Sample `#imm1` / `EXT` $\rightarrow$ ALU Input B | Drive `~OE2[dst]` $\rightarrow$ `Latch_A` | Compute Result | Write `ALU_OUT` $\rightarrow$ `dst`, Sample Flags

 |
| **Hardware Interrupt** | Freeze `PC`, assert `IR_DISABLE`, inhibit `PC_INC` | Passive NOP / IRQ acceptance | Push $PCH_{\text{return}} \rightarrow$ STACK | Push $PCL_{\text{return}} \rightarrow$ STACK, Pulse `~IRQ_ACK` (Pin 06) | Clear $IE \leftarrow 0$ (Pin 09 LOW) | Load external `IRQ_VECTOR` $\rightarrow PCH:PCL$<br> |

---

## 7. Authoritative Timing and Semantic Clarifications

The following rules supersede any older per-instruction timing wording in
this document.

### Ordinary Instruction Templates

Most ordinary instructions complete early:

| Instruction class | Completion | Sequencer reset |
| --- | --- | --- |
| Q0 register and memory moves | `T2` | `T3` |
| Q2 `LDI` | `T2` | `T3` |
| Q1/Q3 ALU operations | `T4` writeback | `T5` |

This includes general-register moves, `MEM` reads and writes, system-register
moves, `MEM ↔ STACK` transfers, and `LDI`. The diagonal escape matrix below is
the only class that composes longer primitive sequences.

### Diagonal Escape Primitive Schedule

All escapes fetch the opcode in `T1` and the operand in `T2`. The existing
flags are already stable while the escape is fetched, so a conditional escape
may evaluate its condition immediately after `T2`:

| Escape | Phase 1 (`T3–T4`) | Phase 2 (`T5–T6`) | Reset |
| --- | --- | --- | --- |
| `NOP` | idle | idle | natural `T6` |
| `SRESET` | — | — | `T2` |
| `HALT` | — | — | `T2` / halt |
| failed `SZ/SNZ/SC/SNC` | condition evaluation | — | `T2` |
| `SKP` or successful conditional skip | `PC_INC` | — | `T4` |
| `GETPC` | `PC_TO_TARGET` | — | `T4` |
| `RET` | `STACK_TO_PC` | — | `T4` |
| `RETI` | `STACK_TO_PC` | `IE_SET` | `T4` |
| `RETK` | `STACK_TO_PC` | `SP_RESTORE` | natural `T6` |
| `JU` | `TARGET_TO_PC` | — | `T4` |
| `PUSHPC` | `PC_TO_STACK` | — | `T4` |
| `CALL` | `PC_TO_STACK` | `TARGET_TO_PC` | natural `T6` |
| `SWI` | `PC_TO_STACK` | vector-to-PC | natural `T6` |

`JU` is specifically `RegA:RegB → PCH:PCL`; `GETPC` is specifically the
reverse transfer. `RegC:RegD` is not implicitly involved in either operation.

Failed conditional escapes may assert the existing `CYCLE_RESET` line at `T2`
because `ZF` and `CF` belong to the preceding instruction and are already
stable. The condition decision must be held long enough for the reset pulse to
be recognized.

### IRQ Ownership and Vector Source

The IRQ card owns the request state, not the interrupt-call sequence. Its
interface to the central control logic is:

```text
IRQ_PENDING / IRQ_REQUEST
IR_DISABLE
PC_INC_DISABLE
IRQ_VECTOR[7:0]
```

When an enabled request is accepted at the instruction boundary, `IR_DISABLE`
disconnects the IR outputs. Because NOD-4 uses passive logical zero, the
opcode and operand rails then appear as `NOP`. `PC_INC_DISABLE` keeps the
already-correct next-instruction PC stable while the main decoder performs the
normal two-cycle `PC_TO_STACK` operation.

The main decoder then performs the complete IRQ sequence:

```text
PC_TO_STACK
IE_CLEAR
IRQ_VECTOR_TO_PC
```

The IRQ card supplies the vector value, selected by DIP switches or equivalent
vector hardware. The vector must remain stable throughout the vector-load
phase. The target may be ROM, RAM, or MMIO; a RAM target can contain a
software-configurable IRQ trampoline. The IRQ card does not need to own the
T-step sequencer or parallel the normal OE/WE controls.
