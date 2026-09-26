# NOD-4 Microprocessor Architecture & System Specification (v14.4 Master Core)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Fetch Mechanics:** Sequential Dual-Nibble Fetch (`OPCODE[3:0]`, `OPERAND[3:0]`)

**Physical Hierarchy:** 31-Pin Passive Backplane Bus $\rightarrow$ Universal Base Cards (UBC) $\rightarrow$ Point-to-Point Control Harnesses $\rightarrow$ Central Control Board (CCB) & Daughtercards

**Logic Standard:** Active-LOW discrete 2N7000 NMOS pass-transistors and depletion loads with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.

---

## 1. Electrical Standard, Clocking & Latch Mechanics

The NOD-4 operates on a two-phase micro-step sequence ($T_1 \dots T_6$) driven by the falling edge of the master clock (`CLK`).

```text
                PHASE 1: SETUP & DRIVE               PHASE 2: LATCH WINDOW
CLK          ────────┐                             ┌───────────────────────┐
                     └─────────────────────────────┘                       └───────
~T[n]        ────────────────┐ (Timestep)
                             └─────────────────────────────────────────────────────
BUS[3:0]     ═══════════<     STABLE DATA WINDOW     >═════════════════════════════
~WE[n]       ────────┐ (Driven full T-step)
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

## 2. Register Architecture & Q0 Dual-Bank Router

The processing element contains two 4-slot register banks: **General Bank (`SYS = 0`)** and **System Bank (`SYS = 1`)**.

```text
                        Q0 Operand Nibble (opr[3:0])
                    ┌───────────┬───────────┬───────────────┐
                    │  opr[3]   │  opr[2]   │  opr[1:0]     │
                    └───────────┴───────────┴───────────────┘
                          │           │             │
                          ▼           ▼             ▼
                       DST SYS     SRC SYS    Register Index
                       Select      Select        [1:0]

```

### Bank 0: General Register Bank (`SYS = 0`)

Constructed using discrete 4-bit level-sensitive transparent latches.

| Index (`[1:0]`) | Mnemonic | Name | Primary Function |
| --- | --- | --- | --- |
| **`00`** | **`RegA`** | Accumulator A | Primary ALU Input / Target |
| **`01`** | **`RegB`** | Working Reg B | Secondary Operand Storage |
| **`10`** | **`RegC`** | Working Reg C | High Pointer Byte (`PCH` / `ADDR_H`) |
| **`11`** | **`RegD`** | Working Reg D | Low Pointer Byte (`PCL` / `ADDR_L`) |

### Bank 1: System Control Bank (`SYS = 1`)

Constructed using Master-Slave Universal Bit Cells (UBC) to prevent race conditions during updates.

| Index (`[1:0]`) | Mnemonic | Name | Primary Function | Special Hardware Action |
| --- | --- | --- | --- | --- |
| **`00`** | **`MEM`** | RAM Indirect Port | Indirect Data Access | Accesses external `RAM[RegC:RegD]` |
| **`01`** | **`STACK`** | Hardware Stack Port | Stack Push / Pop | Auto `DEC SP` on read, `INC SP` on write |
| **`10`** | **`SP`** | Stack Pointer | 4-Bit Stack Address Counter | Master-Slave Up/Down Counter |
| **`11`** | **`RegFLAGS`** | Status Register | Machine Flags | Master-Slave Latch (`[CF, ZF, IE, UF]`) |

### Q0 Dual High-Bit Bank Matrix (`opr[3:2]`)

In Quadrant 0 (`00_2`), bit `opr[3]` sets destination bank (`DST_SYS`), and `opr[2]` sets source bank (`SRC_SYS`):

$$\text{Full Destination Register Address} = [\text{opr[3]}, \text{opr[1:0]}]$$

$$\text{Full Source Register Address} = [\text{opr[2]}, \text{opr[1:0]}]$$

* **Phase-Gated `SYS_SEL` Line:**
* During **$T_3$ (Source Read):** Central Control Board asserts `opr[2]` onto internal `SYS_SEL` logic.
* During **$T_5$ (Destination Write):** Central Control Board switches `SYS_SEL` to assert `opr[3]`.



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
                     Carry      Zero     Interrupt   User Flag
                      Flag      Flag      Enable    (LSB Eject)

```

* **Bit 0 ($UF$ - User Flag):** Positioned at LSB to support zero-overhead conditional branching.
* **2-Cycle Conditional Branch Mechanism:**
1. Executing `SHR RegFLAGS` or `RCR RegFLAGS` ejects $UF$ directly out of Bit 0 into the Carry Flag ($CF$) in **1 cycle**.
2. The following instruction executes **`SC`** (Skip on Carry) or **`SNC`** (Skip on No Carry) in Q3 to branch conditionally in **2 cycles** total, eliminating dedicated branch-steering logic.



---

## 4. 31-Pin Master Backplane Pinout Mapping

The NOD-4 active backplane uses a 31-pin connector layout. All four machine flags (`CF`, `ZF`, `IE`, `UF`) are brought out directly to dedicated backplane pins.

```text
 POWER, CLK & CTRL (01-05)         4-BIT FLAG RAIL (06-09)          MEMORY & PARALLEL BUSES (10-31)
[ 01-03 ] +5V, GND, CLK           [ 06 ] Carry Flag (CF)           [ 10-11 ] Memory OE / WE
[ 04 ] HALT_STAT Execution        [ 07 ] Zero Flag (ZF)            [ 12-15 ] Data Bus (BUS[3:0])
[ 05 ] ~IRQ Hardware Request      [ 08 ] Interrupt Enable (IE)     [ 16-19 ] Address High (ADDR_H[3:0])
                                  [ 09 ] User Flag (UF)            [ 20-23 ] Address Low (ADDR_L[3:0])
                                                                   [ 24-27 ] Opcode Rail (OPCODE[3:0])
                                                                   [ 28-31 ] Operand Rail (OPERAND[3:0])

```

| Pin # | Signal Name | Bus/Rail Group | Direction | Description |
| --- | --- | --- | --- | --- |
| **01** | `+5V` | Power Rail | System | Main Logic VCC Supply (+5V DC) |
| **02** | `GND` | Power Rail | System | Common System Circuit Ground |
| **03** | `CLK` | Master Clock | Input | Single-Phase Master Clock Drive |
| **04** | `HALT_STAT` | Status | Output | CPU Run/Halt & Trap State Line |
| **05** | `~IRQ` | Interrupt | Input | Active-LOW Hardware Interrupt Request Line |
| **06** | `CF` | Flag Rail | Output | **Carry Flag** status output |
| **07** | `ZF` | Flag Rail | Output | **Zero Flag** status output |
| **08** | `IE` | Flag Rail | Output | **Interrupt Enable** status output (Implicit ACK) |
| **09** | `UF` | Flag Rail | Output | **User Flag** status output (Direct LSB Branching) |
| **10** | `~MEM_OE` | Memory Control | Output | Active-LOW Memory Read Output Enable |
| **11** | `~MEM_WE` | Memory Control | Output | Active-LOW Memory Write Enable |
| **12–15** | `BUS[3:0]` | Data Bus | Bidirectional | Parallel 4-Bit Bidirectional Data Bus |
| **16–19** | `ADDR_H[3:0]` | High Address | Output | Upper 4-Bit Address Bus (`RegC` / `PCH`) |
| **20–23** | `ADDR_L[3:0]` | Low Address | Output | Lower 4-Bit Address Bus (`RegD` / `PCL`) |
| **24–27** | `OPCODE[3:0]` | Opcode Rail | Output | Pre-fetched Instruction Opcode Rail |
| **28–31** | `OPERAND[3:0]` | Operand Rail | Output | Pre-fetched Instruction Operand Control Rail (`OPERAND[3]` = Pin 28) |

### Hardware Interrupt Handshake (`IE` Implicit ACK Strobe)

The standalone `~IRQ_ACK` pin is eliminated. Peripherals use the real-time state of the `IE` flag on **Pin 08** as an implicit hardware acknowledge strobe:

1. **Request Assertion:** An external peripheral pulls `~IRQ` (Pin 05) LOW.
2. **Evaluation ($T_6$):** Central Control evaluates $\text{TRIGGER\_IRQ} = \overline{\text{\textasciitilde IRQ}} \cdot \text{IE}$.
3. **Implicit ACK:** Central Control clears `IE` in `RegFLAGS` ($IE \leftarrow 0$), driving Pin 08 (`IE`) LOW. This HIGH-to-LOW transition signals the peripheral that its request is being serviced, prompting it to release `~IRQ` (Pin 05).
4. **Vector Hijack & Return:** `PCH:PCL` is saved to `STACK`, execution jumps to vector `0xF2`, and executing `RET` later restores $IE \leftarrow 1$ (Pin 08 returns HIGH).

---

## 5. Quadrant Decoder Architecture & Master ISA Specification

Instruction execution utilizes two sequentially fetched 4-bit nibbles: `OPCODE[3:0]` and `OPERAND[3:0]`. In all ALU and Immediate modes, the destination register `dst[1:0]` is **strictly locked** inside `OPCODE[1:0]`.

```text
         OPCODE NIBBLE (Fetched First)               OPERAND NIBBLE (Fetched Second)
     ┌───────┬─────────┬─────────┬─────────┐     ┌───────────┬───────────┬───────────────┐
     │  IMM  │ ALU_EN  │  dst1   │  dst0   │     │ OPERAND[3]│ OPERAND[2]│ OPERAND[1:0]  │
     └───────┴─────────┴─────────┴─────────┘     └───────────┴───────────┴───────────────┘
     ◄────── OP[3:2] ─► ◄── dst[1:0] ─────►        SYS Select   OP / MODE    #imm Payload /
        (Quadrant Select)   (ALWAYS HERE)          (0: General   (0: ADD/ADC   Unary Sub-Opcode
                                                    1: System)    1: SUB/Unary)

```

### Master Quadrant Summary

| Quadrant | Binary (`OP[3:2]`) | Class | Operational Description |
| --- | --- | --- | --- |
| **Q0** | `00` | Data Moves & Control Escapes | Dual-bank register/memory moves (`opr[3:2]`). Diagonal opcodes ($dd == ss$) decode control escapes (`CALL`, `RET`, `NOP`, `SWI`). |
| **Q1** | `01` | Reg-to-Reg Binary ALU | 4-function binary ALU (`ADD`, `SUB`, `XOR`, `AND`) targeting General Bank registers (`RegA`–`RegD`). |
| **Q2** | `10` | Load Immediate (`LDI`) | Drives 4-bit literal `#imm` payload directly from `OPERAND[3:0]` onto `BUS[3:0]` to target `dst[1:0]`. |
| **Q3** | `11` | Immediate ALU, Unary & Shifts | System/General 2-bit immediate math (`ADDI`/`SUBI`), multi-nibble carry propagation (`ADC`/`SBB`), and unary matrix (`NOT`/`SHR`/`RCR`/`CLR`). |

---

### Quadrant 0: Data Moves & Diagonal Control Escapes (`OPCODE = 00_dd`)

#### 1. Standard Register & Memory Moves ($dd \neq ss$)

* **`OPCODE[3:0]`:** `[0, 0, dst1, dst0]`
* **`OPERAND[3:0]`:** `[DST_SYS, SRC_SYS, src1, src0]`

| Binary Pattern | Mnemonic | Operation | Description |
| --- | --- | --- | --- |
| `OP=00_dd, OPR=00_ss` | **`MOV dst, src`** | $dst_{\text{Gen}} \leftarrow src_{\text{Gen}}$ | General register to General register transfer |
| `OP=00_dd, OPR=01_ss` | **`LD dst, src`** | $dst_{\text{Gen}} \leftarrow \text{RAM}[src_{\text{Sys}}]$ | Memory / System read to General register |
| `OP=00_dd, OPR=10_ss` | **`ST dst, src`** | $\text{RAM}[dst_{\text{Sys}}] \leftarrow src_{\text{Gen}}$ | General register write to Memory / System |
| `OP=00_dd, OPR=11_ss` | **`MOV dst_sys, src_sys`** | $dst_{\text{Sys}} \leftarrow src_{\text{Sys}}$ | System register to System register transfer |

#### 2. Q0 Diagonal Control Escapes ($dd == ss$)

When destination bits match source bits ($dst[1:0] == src[1:0]$) under specific high-bit configurations, the hardware triggers control escapes:

| Binary Pattern | Mnemonic | Hardware Action | Execution Cycle |
| --- | --- | --- | --- |
| `00_00 0000` | **`NOP`** | No operation; advances pipeline | Resets at $T_6$ |
| `00_01 0101` | **`RET`** | Pops `PCH:PCL` from hardware `STACK` | Resets at $T_4$ |
| `00_10 1010` | **`CALL addr`** | Pushes `PCH:PCL` to `STACK`, loads branch target | Resets at $T_6$ |
| `00_11 1111` | **`SWI`** | Forces software trap; jumps to vector `0xF2` | Resets at $T_6$ |

---

### Quadrant 1: Register-to-Register Binary ALU (`OPCODE = 01_dd`)

Both operands reside in registers. Target destination (`dd`) is locked to Bank 0 (General Bank: `RegA`–`RegD`).

* **`OPCODE[3:0]`:** `[0, 1, dst1, dst0]`
* **`OPERAND[3:0]`:** `[alu_op1, alu_op0, src1, src0]`

| `alu_op[1:0]` | Mnemonic | Logic / Arithmetic Equation | Flags Affected |
| --- | --- | --- | --- |
| **`00`** | **`ADD dst, src`** | $dst \leftarrow dst + src + CF$ | $ZF, CF$ |
| **`01`** | **`SUB dst, src`** | $dst \leftarrow dst + \overline{src} + CF$ | $ZF, CF$ |
| **`10`** | **`XOR dst, src`** | $dst \leftarrow dst \oplus src$ | $ZF$ ($CF \leftarrow 0$) |
| **`11`** | **`AND dst, src`** | $dst \leftarrow dst \land src$ | $ZF$ ($CF \leftarrow 0$) |

---

### Quadrant 2: Load Immediate (`OPCODE = 10_dd`)

Loads a 4-bit literal value directly into target register $dst[1:0]$.

* **`OPCODE[3:0]`:** `[1, 0, dst1, dst0]`
* **`OPERAND[3:0]`:** Literal 4-Bit Data (`#imm[3:0]`)

| Binary Pattern | Mnemonic | Hardware Action | Execution Cycle |
| --- | --- | --- | --- |
| `10_dd #imm` | **`LDI dst, #imm`** | $dst \leftarrow \text{OPERAND}[3:0]$ | Resets at $T_3$ |

---

### Quadrant 3: Immediate ALU, Carry Propagate & Unary/Shift Matrix (`OPCODE = 11_dd`)

Bit `OPERAND[3]` selects target bank (`SYS`). Bit `OPERAND[2]` switches between Immediate Addition / Carry Propagation (`MODE = 0`) and Subtraction / Unary / Shift Matrix (`MODE = 1`). `OPCODE[1:0]` strictly specifies the target register ($dst$).

```text
                      OPERAND[3:0] DECODE TREE (Q3)
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         │                                                   │
  OPERAND[3] = 0 (General Bank)                       OPERAND[3] = 1 (System Bank)
         │                                                   │
   ┌─────┴─────┐                                       ┌─────┴─────┐
   │           │                                       │           │
OPR[2]=0    OPR[2]=1                                OPR[2]=0    OPR[2]=1
(ADD/ADC)   (SUB/SBB)                               (ADD/ADC)   (Unary Matrix)

```

#### Master Q3 Decoding Table

| `opr[3]` (`SYS`) | `opr[2]` (`MODE`) | `opr[1:0]` | Mnemonic | Hardware Action | Flags |
| --- | --- | --- | --- | --- | --- |
| **`0`** | **`0`** | **`00_2`** | **`ADC Gen`** | $dst_{\text{Gen}} \leftarrow dst + 0 + CF$ | $ZF, CF$ |
| **`0`** | **`0`** | `#imm[1:0]` | **`ADDI Gen, #imm`** | $dst_{\text{Gen}} \leftarrow dst + \#imm$ | $ZF, CF$ |
| **`0`** | **`1`** | **`00_2`** | **`SBB Gen`** | $dst_{\text{Gen}} \leftarrow dst + 0x0F + CF$ | $ZF, CF$ |
| **`0`** | **`1`** | `#imm[1:0]` | **`SUBI Gen, #imm`** | $dst_{\text{Gen}} \leftarrow dst + \overline{\#imm} + 1$ | $ZF, CF$ |
| **`1`** | **`0`** | **`00_2`** | **`ADC Sys`** | $dst_{\text{Sys}} \leftarrow dst + 0 + CF$ | $ZF, CF$ |
| **`1`** | **`0`** | `#imm[1:0]` | **`ADDI Sys, #imm`** | $dst_{\text{Sys}} \leftarrow dst + \#imm$ *(e.g., `ADDI SP, #1`)* | $ZF, CF$ |
| **`1`** | **`1`** | **`00_2`** | **`NOT dst`** | $dst \leftarrow \overline{dst}$ | $ZF$ |
| **`1`** | **`1`** | **`01_2`** | **`SHR dst`** | $dst[3] \leftarrow 0, dst[i] \leftarrow dst[i+1], dst[0] \rightarrow CF$ | $ZF, CF$ |
| **`1`** | **`1`** | **`10_2`** | **`RCR dst`** | $dst[3] \leftarrow CF, dst[i] \leftarrow dst[i+1], dst[0] \rightarrow CF$ | $ZF, CF$ |
| **`1`** | **`1`** | **`11_2`** | **`CLR dst`** | $dst \leftarrow 0\text{x0}$ | $ZF \leftarrow 1, CF \leftarrow 0$ |

#### Q3 Skip Control Escapes

When $dst = \text{RegFLAGS}$ (`11_2`) in Q3, specialized skip hardware evaluates state without writeback:

| Binary Pattern | Mnemonic | Hardware Condition | Hardware Action |
| --- | --- | --- | --- |
| `11_11 1101` | **`SC`** | Skip on Carry Set ($CF = 1$) | Auto-increments `PC` by extra +2 to skip next instruction |
| `11_11 1110` | **`SNC`** | Skip on Carry Clear ($CF = 0$) | Auto-increments `PC` by extra +2 to skip next instruction |

---

## 6. Pipeline Timestep Matrix ($T_1 \dots T_6$)

| Instruction Class | $T_1$ (Addr Drive / Precharge) | $T_2$ (Fetch Opcode / PC+1) | $T_3$ (Decode / Read SRC) | $T_4$ (SRC Drive / Latch B) | $T_5$ (Compute / Switch SYS) | $T_6$ (Writeback / Commit) |
| --- | --- | --- | --- | --- | --- | --- |
| **Q0: Register Move** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `opr[2]` $\rightarrow$ `SYS_SEL` | Assert `~OE1[src]` $\rightarrow$ `BUS` | Switch `SYS_SEL` $\rightarrow$ `opr[3]` | Assert `~WE[dst]` on `CLK` LOW |
| **Q0: Memory Read** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `RegC:RegD` $\rightarrow$ ADDR | Assert `~MEM_OE` $\rightarrow$ `BUS` | Switch `SYS_SEL` $\rightarrow$ `DST_SYS` | Assert `~WE[dst]` on `CLK` LOW |
| **Q1: Reg-Reg ALU** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `~OE1[src]` $\rightarrow$ `Latch_B` | Drive `~OE2[dst]` $\rightarrow$ `Latch_A` | Hold $C_g$ Compute State | Write `ALU_OUT` $\rightarrow$ `dst`, Sample Flags |
| **Q2: Load Immediate** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Drive `OPERAND` $\rightarrow$ `BUS` | Assert `~WE[dst]` on `CLK` LOW | Reset Pipeline State | — |
| **Q3: Immediate ALU** | Assert `PC` $\rightarrow$ ADDR | Fetch Opcode $\rightarrow$ `IR` | Sample `#imm` $\rightarrow$ ALU Input B | Drive `~OE2[dst]` $\rightarrow$ `Latch_A` | Compute Result | Write `ALU_OUT` $\rightarrow$ `dst`, Sample Flags |
| **Hardware Interrupt** | Freeze `PC`, Force `NOP` | Fetch `NOP` Payload | Push $PCL_{\text{return}} \rightarrow$ STACK | Push $PCH_{\text{return}} \rightarrow$ STACK | Clear $IE \leftarrow 0$ (Pin 08 ACK) | Load Vector `0xF2` $\rightarrow PCH:PCL$ |