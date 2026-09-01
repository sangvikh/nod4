# NOD-4 Reference Manual & Hardware Architecture (v8.7 Final)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Physical Hierarchy:** 48-Pin Passive Backplane Bus $\rightarrow$ Universal Base Cards $\rightarrow$ Counter Daughtercards

**Control Philosophy:** Pure Bitmapped Control (`OPCODE[3]` = Immediate, `OPCODE[2]` = ALU Enable), Orthogonal 2-Bit Quadrant Decoder, Hardwired Index Lines, Level-Active Execution, Zero-Decoder Glue Logic, Internal Decoder Self-Reset, 5-Transistor Steering Tree Branch Engine

---

## 1. Physical System Invariants & Electrical Specifications

* **Logic Family:** Discrete NMOS pass-transistor and depletion-load logic.
* **Signal Standard:** Active-LOW open-drain backplane rails with passive $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$. Active-LOW switching driven by 2N7000 NMOS transistors.
* **Hardwired Index Lines (v8.7 Invariant):**
* `OPCODE[1:0]` is hardwired directly to the Destination Write Enable (`DST_WE`) decoder CPU-wide.
* `OPERAND[1:0]` is hardwired directly to the Source Output Enable (`SRC_OE`) decoder CPU-wide. Zero pass-gate MUXes required on register index lines.


* **Level-Active Execution:** All control assertions are static logic levels active throughout $T_2$. Setup and latching occur on the trailing edge ($T_2 \rightarrow T_3$), where $T_3$ triggers an asynchronous $\overline{\text{CYCLE\_RESET}}$ for 3-cycle execution.
* **Stack Module (`STK`):** Self-contained daughtercard with an internal counter and LIFO register array. Interacts directly with `BUS[3:0]` without touching RAM or memory address buses.
* **Concurrency Bus Engine (5 Dedicated Parallel Buses):**
1. `BUS[3:0]`: Primary 4-bit bidirectional data and register transfer bus.
2. `ADDR_H[3:0]`: High 4-bit memory address rail (driven by `RegC` or `PCH` Base Cards via Header 3).
3. `ADDR_L[3:0]`: Low 4-bit memory address rail (driven by `RegD` or `PCL` Base Cards via Header 3).
4. `OPCODE[3:0]`: Latched instruction opcode nibble (`OP[3:0]`).
5. `OPERAND[3:0]`: Latched instruction operand nibble (`OPERAND[3:0]`).


* **Execution Flags:**
* **$ZF$ (Zero Flag):** Set if ALU output equals `0` (sampled on trailing edge of $T_3$).
* **$CF$ (Carry/Borrow Flag):** Set on arithmetic overflow or underflow (sampled on trailing edge of $T_3$).



---

## 2. System Hardware Card Manifest & Bus Slot Mapping

| Slot / Module | Board Type | Qty | Primary Function | Backplane Bus Connections |
| --- | --- | --- | --- | --- |
| **`RegA`** (Slot 0) | Universal Base Card (UBC) | 1 | 4-Bit Primary Accumulator | `BUS[3:0]`, `~WE[0]`, `~OE[0]` |
| **`RegB`** (Slot 1) | Universal Base Card (UBC) | 1 | 4-Bit Auxiliary Scratchpad | `BUS[3:0]`, `~WE[1]`, `~OE[1]` |
| **`RegC`** (Slot 2) | Universal Base Card (UBC) | 1 | High Pointer Byte (`PTR_H`) | `BUS[3:0]`, `ADDR_H[3:0]`, `~WE[2]`, `~OE[2]` |
| **`RegD`** (Slot 3) | Universal Base Card (UBC) | 1 | Low Pointer Byte (`PTR_L`) | `BUS[3:0]`, `ADDR_L[3:0]`, `~WE[3]`, `~OE[3]` |
| **`MEM`** (Slot 4) | Memory Transceiver Board | 1 | ROM/RAM Control & Bus Buffer | `ADDR_H/L`, `BUS[3:0]`, `~WE[4]`, `~OE[4]` |
| **`PCH`** (Slot 5) | UBC + Counter Daughtercard | 1 | Program Counter High Byte | `BUS[3:0]`, `ADDR_H[3:0]`, `~WE[5]`, `~OE[5]` |
| **`PCL`** (Slot 6) | UBC + Counter Daughtercard | 1 | Program Counter Low Byte | `BUS[3:0]`, `ADDR_L[3:0]`, `~WE[6]`, `~OE[6]` |
| **`STK`** (Slot 7) | UBC + Counter Daughtercard | 1 | Hardware Stack Pointer | `BUS[3:0]`, `~WE[7]`, `~OE[7]` |
| **`OPCODE`** | Universal Base Card (UBC) | 1 | Opcode Latch (`OP[3:0]`) | `BUS[3:0]`, `OPCODE[3:0]` |
| **`OPERAND`** | Universal Base Card (UBC) | 1 | Operand Latch (`OPERAND[3:0]`) | `BUS[3:0]`, `OPERAND[3:0]` |
| **`ALU`** | Custom Discrete Board | 1 | 4-Bit Adder, Carry Tap, Diode OR | `BUS[3:0]`, `OPCODE[3:0]`, `OPERAND[3:0]` |
| **`TIMING`** | Custom Discrete Board | 1 | State Counter, Decoder, Flags ($ZF, CF$), Steering Tree | `CLK`, `~T0`..`~T5`, Control Signals |

---

## 3. Universal Base Card Architecture & Physical Hierarchy

Every register node uses the standardized **Universal Base Card (UBC)** PCB layout, configured via three on-board headers:

```
+-----------------------------------------------------------------+
|                      BACKPLANE (48 Pins)                        |
+-----------------------------------------------------------------+
                                |
                                v (Plugs into Backplane Slot)
+-----------------------------------------------------------------+
|                    UNIVERSAL BASE CARD (UBC)                    |
| - 4x NMOS D-Latch Storage Core                                  |
| - Header 1: 2x14 Diode-OR Write Enable (INT_WE)                 |
| - Header 2: 2x14 Diode-OR Output Enable (OE_MAIN / SEC_OE)      |
| - Header 3: Secondary Destination Output Bridge (SEC_DEST)      |
| - Universal 13-Pin Daughtercard Interface Socket                |
+-----------------------------------------------------------------+
                                |
                                v (Plugs into Base Card Socket)
+-----------------------------------------------------------------+
|                   COUNTER DAUGHTERCARD                          |
| - Smart Auto-Increment / Decrement Adder Circuitry              |
| - On-board C_IN / C_OUT Pins for Inter-card Carry Routing       |
| - Base Card ~COUNT_LATCH Latching Logic                         |
+-----------------------------------------------------------------+

```

### Base Card Headers & Internal Logic

* **Latch Storage Core:** 4x Discrete NMOS D-Latch cells with clock-gated active-LOW write enable:

$$\text{WRITE\_ENABLE} = \overline{\text{INT\_WE}} \cdot \overline{\text{CLK}}$$


* **Header 1 (2x14 WE Header):** Active-LOW Diode-OR array linking backplane write enable signals ($\overline{\text{WE}}[0:7]$) or specific timestep lines ($\overline{T_0}$–$\overline{T_5}$) to internal write line ($\overline{\text{INT\_WE}}$).
* **Header 2 (2x14 OE Header):** Active-LOW Diode-OR array routing control step lines to primary bus buffer ($\overline{\text{OE\_MAIN}} \rightarrow \text{BUS}[3:0]$) or secondary output buffer ($\overline{\text{SEC\_OE}}$).
* **Header 3 (SEC_DEST Header):** 4-pin output bridge linking secondary outputs to target backplane rails (`ADDR_H[3:0]`, `ADDR_L[3:0]`, `OPCODE[3:0]`, or `OPERAND[3:0]`).

---

## 4. Master Universal Base Card Configuration Matrix

| Base Card | Architectural Role | Header 1 ($\text{WE}$) Trigger | Header 2 ($\text{OE}$) Control | Header 3 (`SEC_DEST`) Output | 13-Pin Socket |
| --- | --- | --- | --- | --- | --- |
| **`RegA`** | Accumulator | Backplane $\overline{\text{WE}}_0$ | Backplane $\overline{\text{OE}}_0$ | Unused | Unpopulated |
| **`RegB`** | Scratchpad | Backplane $\overline{\text{WE}}_1$ | Backplane $\overline{\text{OE}}_1$ | Unused | Unpopulated |
| **`RegC`** | High Pointer | Backplane $\overline{\text{WE}}_2$ | Backplane $\overline{\text{OE}}_2$ | `ADDR_H[3:0]` | Unpopulated |
| **`RegD`** | Low Pointer | Backplane $\overline{\text{WE}}_3$ | Backplane $\overline{\text{OE}}_3$ | `ADDR_L[3:0]` | Unpopulated |
| **`OPCODE`** | Instruction Opcode Latch | Timestep $\overline{T_0}$ | Tied LOW (Always Active) | `OPCODE[3:0]` | Unpopulated |
| **`OPERAND`** | Instruction Operand Latch | Timestep $\overline{T_1}$ | Tied LOW (Always Active) | `OPERAND[3:0]` | Unpopulated |
| **`PCH`** | Program Counter High | Backplane $\overline{\text{WE}}_5$ / Subops | $\overline{\text{OE}}_5$ / $\overline{T_0}$ / $\overline{T_1}$ | `ADDR_H[3:0]` | Counter Daughtercard |
| **`PCL`** | Program Counter Low | Backplane $\overline{\text{WE}}_6$ / Subops | $\overline{\text{OE}}_6$ / $\overline{T_0}$ / $\overline{T_1}$ | `ADDR_L[3:0]` | Counter Daughtercard |
| **`STK`** | Hardware Stack Pointer | Backplane $\overline{\text{WE}}_7$ / Subops | Backplane $\overline{\text{OE}}_7$ / Subops | Unused | Counter Daughtercard |

---

## 5. Universal 13-Pin Base-to-Daughtercard Interface

Base Cards requiring auto-increment/decrement (`PCL`, `PCH`, `STK`) interface with **Counter Daughtercards** via a 13-pin socket:

```
 Pin 1: VCC (+5V)          Pin 6:  D[0] (Data In 0)    Pin 10: Q[0] (Latch Out 0)
 Pin 2: GND                Pin 7:  D[1] (Data In 1)    Pin 11: Q[1] (Latch Out 1)
 Pin 3: ~T_STEP_A          Pin 8:  D[2] (Data In 2)    Pin 12: Q[2] (Latch Out 2)
 Pin 4: ~T_STEP_B          Pin 9:  D[3] (Data In 3)    Pin 13: Q[3] (Latch Out 3)
 Pin 5: ~COUNT_LATCH (Base Card Internal Latch Enable Pulse)

```

* **Surface Carry Pins (`C_IN` / `C_OUT`):** 2-pin header on the Counter Daughtercard PCB. Bridging `PCL` Daughtercard $C_{\text{out}} \rightarrow$ `PCH` Daughtercard $C_{\text{in}}$ enables 8-bit ripple-carry incrementing during fetches.

---

## 6. Timing Engine & Dual-Nibble Fetch Mechanics

* **State Engine:** 3-bit ripple counter ($Q_2 Q_1 Q_0$) driving a 3-to-8 decoder on the **TIMING** card.
* **Local Decoder Self-Reset Loop:** Decoder output step 6 ($\overline{T_6}$) connects directly on the TIMING board to the counter's active-LOW clear input ($\overline{\text{CLR}}$).
* Counter ticks `101` ($T_5$) $\rightarrow$ `110` ($T_6$).
* Internal $\overline{T_6}$ immediately pulls $\overline{\text{CLR}}$ LOW, resetting state to `000` ($T_0$) in $\approx 15\text{ ns}$.
* Only active steps $\overline{T_0}$ through $\overline{T_5}$ route to backplane pins 5–10.



```
  +---------------+        3-Bit         +-------------------+
  |               |===== Q[2:0] Bus =====|  3-to-8 DECODER   |
  | 3-Bit Counter |                      |  (NOR Matrix)     |
  |               |                      +----+---------+----+
  |  ~CLR Input   |<--- Internal ~T6 ---------|         |
  +---------------+     Decoder Output        v         v
                                          ~T0..~T5    Internal ~T6
                                        (Backplane)   (Self-Reset)

```

* **Fetch Mechanics:**
* **Phase $T_0$:** `PCH:PCL` drive `ADDR_H:ADDR_L`. $\text{RAM}[PC] \rightarrow \text{BUS}[3:0] \rightarrow \text{OPCODE}$ Base Card (latched via $\overline{T_0}$). $PCL \leftarrow PCL + 1$.
* **Phase $T_1$:** `PCH:PCL` drive `ADDR_H:ADDR_L`. $\text{RAM}[PC+1] \rightarrow \text{BUS}[3:0] \rightarrow \text{OPERAND}$ Base Card (latched via $\overline{T_1}$). $PCL \leftarrow PCL + 1$.
* **State at $T_2$ Entry:** Pipeline latched; $PC$ points to $PC_{\text{entry}} + 2$.



---

## 7. Hardware Control Boolean Equations & Steering Engine

### Control Class Decode

Control Quadrant decode is updated for `OPCODE[3:2] == 00` ($\text{IMM}=0, \text{ALU\_EN}=0$):


$$\text{IS\_CTRL} = \overline{\text{OPCODE}[3]} \cdot \overline{\text{OPCODE}[2]}$$

### Control Inhibit & Enable Gating Equations

Because register selection relies strictly on default bus wiring (`OPCODE[1:0]` for `DST_WE` and `OPERAND[1:0]` for `SRC_OE`), Control Quadrant (`00rr`) signals gate the global decoder enable lines during $T_2$:

* **`PUSH reg` (`0000` / `10rr`):**

$$\text{SRC\_OE\_ENABLE} = \text{IS\_CTRL} \cdot \text{OPERAND}[3] \cdot \overline{\text{OPERAND}[2]}$$


$$\text{DST\_WE\_ENABLE} = 0 \quad (\text{Inhibited})$$


$$\text{STK\_PUSH\_EN} = \text{IS\_CTRL} \cdot \text{OPERAND}[3] \cdot \overline{\text{OPERAND}[2]} \cdot T_2$$


* **`POP reg` (`00rr` / `0100`):**

$$\text{SRC\_OE\_ENABLE} = 0 \quad (\text{Inhibited})$$


$$\text{DST\_WE\_ENABLE} = \text{IS\_CTRL} \cdot \overline{\text{OPERAND}[3]} \cdot \text{OPERAND}[2]$$


$$\text{STK\_OE} = \text{IS\_CTRL} \cdot \overline{\text{OPERAND}[3]} \cdot \text{OPERAND}[2] \cdot T_2$$


* **`PUSHPC` (`0000` / `1110`):**
Executes standard `CALL` sequence ($PCL \rightarrow \text{STK}$, $PCH \rightarrow \text{STK}$), but asserts $\overline{\text{CYCLE\_RESET}}$ at entry to $T_3$ to perform an atomic PC read onto the stack without altering PC target registers.

### 5-Transistor Branch Steering Tree (`FAIL` Logic)

Let $P_1 = \text{OPERAND}[1]$ and $P_0 = \text{OPERAND}[0]$. The branch failure signal is derived via pass-transistor routing:

$$\text{FAIL} = \overline{P_0} \cdot (\overline{P_1} \cdot \overline{ZF} \lor P_1 \cdot \overline{CF}) \;\;\lor\;\; P_0 \cdot (\overline{P_1} \cdot ZF)$$

```
  Path A (P0 = 0: Test SET Flags)
  ~ZF -----[ Q1: Gate=~P1 ]----+
                               |----> (Node MUX) ----[ Q3: Gate=~P0 ]----+
  ~CF -----[ Q2: Gate= P1 ]----+                                         |
                                                                         +---> [ FAIL Rail ]
  Path B (P0 = 1: Test CLEAR Flags)                                      |
   ZF -----[ Q4: Gate= P0 ]----------> (Node B)   ----[ Q5: Gate=~P1 ]----+

```

### Active-LOW Cycle Reset Assertion

$$\overline{\text{CYCLE\_RESET}} = \overline{(T_2 \cdot \text{FAIL}) \lor (T_2 \cdot \text{3\_CYCLE\_OPS}) \lor (T_4 \cdot \text{JMP\_RET}) \lor (T_5 \cdot \text{CALL})}$$

---

## 8. Master Instruction Encoding & Quadrant Matrix

**8-Bit Explicit Instruction Format:**

$$\text{OPCODE}[3:0] = [\text{IMM} \mid \text{ALU\_EN} \mid \text{DST}_1 \mid \text{DST}_0]$$

$$\text{OPERAND}[3:0] = [\text{SUBOP}_1 \mid \text{SUBOP}_0 \mid \text{SRC}_1 / \text{IMM}_1 \mid \text{SRC}_0 / \text{IMM}_0]$$

```
  +-----+--------+------+------+----------+----------+---------+---------+
  | IMM | ALU_EN | DST1 | DST0 | SUB/OP_1 | SUB/OP_0 | SRC/IMM1| SRC/IMM0|
  +-----+--------+------+------+----------+----------+---------+---------+
  |        OPCODE (Bits 3:0)      |        OPERAND (Bits 3:0)             |
  +-------------------------------+---------------------------------------+

```

### Universal 4-Quadrant Major Class Matrix (`OPCODE[3:2]`)

| Quadrant (`OPCODE[3:2]`) | `OPCODE[1:0]` Target | `OPERAND[3:2]` Role | Operations | Hardware Behavior at $T_2$ |
| --- | --- | --- | --- | --- |
| **`00rr`** (`IMM=0, ALU=0`) | `dst = Reg[rr]` | Sub-Quadrant Select | **Control / System / Stack** | See sub-quadrant matrix below. |
| **`01rr`** (`IMM=0, ALU=1`) | `dst = Reg[rr]` | ALU Opcode (`00`–`11`) | **Reg-Reg ALU / `MOV**` | `Reg[OPERAND[1:0]]` drives `BUS`; `Reg[OPCODE[1:0]]` latches. |
| **`10rr`** (`IMM=1, ALU=0`) | `dst = Reg[rr]` | Mode / Address | **Immediate Load (`LDI`) / Memory Direct** | Memory address bus active or Immediate payload drives `BUS`; `Reg[rr]` latches. |
| **`11rr`** (`IMM=1, ALU=1`) | `dst = Reg[rr]` | ALU Opcode (`00`–`11`) | **Immediate ALU (`ALUI`)** | 2-Bit Immediate payload drives ALU input B; `Reg[rr]` latches result. |

---

### Control Quadrant (`00rr`) Sub-Class Encoding

| Instruction | Opcode (`OPCODE[3:0]`) | Operand (`OPERAND[3:0]`) | `SRC_OE` Decoder | `DST_WE` Decoder | $T_2$ Level Assertions |
| --- | --- | --- | --- | --- | --- |
| **`POP reg`** | **`00rr`** | `0100` | **Disabled** | **Active (`Reg[rr]`)** | `STK_OE` High $\rightarrow$ Stack card drives `BUS[3:0]` into `Reg[OPCODE[1:0]]`. |
| **`PUSH reg`** | `0000` | **`10rr`** | **Active (`Reg[rr]`)** | **Disabled** | `STK_PUSH_EN` High $\rightarrow$ Stack card latches `BUS[3:0]` from `Reg[OPERAND[1:0]]`. |
| **Branches** | `0000` | `00cc` | **Disabled** | **Disabled** | Steering tree evaluates condition `cc` (`00`: JZ, `01`: JNZ, `10`: JC, `11`: JMP). |
| **System Ops** | `0000` | `11xx` | **Disabled** | **Disabled** | Multi-cycle PC/STK control (`1100`: CALL, `1101`: RET, `1110`: PUSHPC, `1111`: NOP). |

### Register Encoding (`dst` or `src` in `OP[1:0]` / `OPERAND[1:0]`)

`00` = `RegA` | `01` = `RegB` | `10` = `RegC` (High Ptr) | `11` = `RegD` (Low Ptr)

---

## 9. Complete 0x0–0xF Execution Matrix

| Opcode | Binary | Mnemonic | Format | Timestep Execution & Micro-Operations | Total Steps |
| --- | --- | --- | --- | --- | --- |
| **`0x0`** | `0000` | *CTRL / System / PUSH / POP RegA* | `subop[3:2], arg[1:0]` | *See Section 10 for branches, PUSH, CALL, RET, PUSHPC* | 3 to 6 Steps |
| **`0x1`** | `0001` | `POP RegB` | `0100` | **$T_2$:** $\text{STK} \rightarrow \text{BUS} \rightarrow \text{RegB}$ ($SP \leftarrow SP + 1$) | 3 Steps ($T_3$ Reset) |
| **`0x2`** | `0010` | `POP RegC` | `0100` | **$T_2$:** $\text{STK} \rightarrow \text{BUS} \rightarrow \text{RegC}$ ($SP \leftarrow SP + 1$) | 3 Steps ($T_3$ Reset) |
| **`0x3`** | `0011` | `POP RegD` | `0100` | **$T_2$:** $\text{STK} \rightarrow \text{BUS} \rightarrow \text{RegD}$ ($SP \leftarrow SP + 1$) | 3 Steps ($T_3$ Reset) |
| **`0x4`** | `0100` | `MOV RegA, src` / Reg ALU | `alu_op[3:2], src[1:0]` | **$T_2$:** $\text{Reg}[src] \rightarrow \text{BUS} \rightarrow \text{RegA}$ (or ALU Reg-Reg) | 3 or 5 Steps |
| **`0x5`** | `0101` | `MOV RegB, src` / Reg ALU | `alu_op[3:2], src[1:0]` | **$T_2$:** $\text{Reg}[src] \rightarrow \text{BUS} \rightarrow \text{RegB}$ (or ALU Reg-Reg) | 3 or 5 Steps |
| **`0x6`** | `0110` | `MOV RegC, src` / Reg ALU | `alu_op[3:2], src[1:0]` | **$T_2$:** $\text{Reg}[src] \rightarrow \text{BUS} \rightarrow \text{RegC}$ (or ALU Reg-Reg) | 3 or 5 Steps |
| **`0x7`** | `0111` | `MOV RegD, src` / Reg ALU | `alu_op[3:2], src[1:0]` | **$T_2$:** $\text{Reg}[src] \rightarrow \text{BUS} \rightarrow \text{RegD}$ (or ALU Reg-Reg) | 3 or 5 Steps |
| **`0x8`** | `1000` | `LDI RegA, imm` / Memory | `imm[3:0]` | **$T_2$:** $\text{OPERAND}[3:0] \rightarrow \text{BUS} \rightarrow \text{RegA}$ | 3 Steps ($T_3$ Reset) |
| **`0x9`** | `1001` | `LDI RegB, imm` / Memory | `imm[3:0]` | **$T_2$:** $\text{OPERAND}[3:0] \rightarrow \text{BUS} \rightarrow \text{RegB}$ | 3 Steps ($T_3$ Reset) |
| **`0xA`** | `1010` | `LDI RegC, imm` / Memory | `imm[3:0]` | **$T_2$:** $\text{OPERAND}[3:0] \rightarrow \text{BUS} \rightarrow \text{RegC}$ | 3 Steps ($T_3$ Reset) |
| **`0xB`** | `1011` | `LDI RegD, imm` / Memory | `imm[3:0]` | **$T_2$:** $\text{OPERAND}[3:0] \rightarrow \text{BUS} \rightarrow \text{RegD}$ | 3 Steps ($T_3$ Reset) |
| **`0xC`** | `1100` | `ALUI RegA, imm` | `alu_op[3:2], imm[1:0]` | **$T_2$:** $\text{RegA} \rightarrow \text{ALU\_A}$, Imm $\rightarrow \text{ALU\_B}$, Compute, sample $ZF/CF$, write RegA | 5 Steps ($T_5$ Reset) |
| **`0xD`** | `1101` | `ALUI RegB, imm` | `alu_op[3:2], imm[1:0]` | **$T_2$:** $\text{RegB} \rightarrow \text{ALU\_A}$, Imm $\rightarrow \text{ALU\_B}$, Compute, sample $ZF/CF$, write RegB | 5 Steps ($T_5$ Reset) |
| **`0xE`** | `1110` | `ALUI RegC, imm` | `alu_op[3:2], imm[1:0]` | **$T_2$:** $\text{RegC} \rightarrow \text{ALU\_A}$, Imm $\rightarrow \text{ALU\_B}$, Compute, sample $ZF/CF$, write RegC | 5 Steps ($T_5$ Reset) |
| **`0xF`** | `1111` | `ALUI RegD, imm` | `alu_op[3:2], imm[1:0]` | **$T_2$:** $\text{RegD} \rightarrow \text{ALU\_A}$, Imm $\rightarrow \text{ALU\_B}$, Compute, sample $ZF/CF$, write RegD | 5 Steps ($T_5$ Reset) |

*Note: `POP RegA` is encoded as Opcode `0000` with Operand `0100`.*

---

## 10. Control Sub-Operations Matrix Breakdown

| Instruction | Encoding (`OPCODE / OPERAND`) | Serialized Hardware Micro-Operations | Total Steps |
| --- | --- | --- | --- |
| **`PUSH reg`** | `0000 / 10rr` | **$T_2$:** $\text{Reg}[rr] \rightarrow \text{BUS} \rightarrow \text{STK}$ ($SP \leftarrow SP - 1$). | 3 Steps ($T_3$ Reset) |
| **`POP reg`** | `00rr / 0100` | **$T_2$:** $\text{STK} \rightarrow \text{BUS} \rightarrow \text{Reg}[rr]$ ($SP \leftarrow SP + 1$). | 3 Steps ($T_3$ Reset) |
| **`Jcc` / `JMP**` | `0000 / 00cc` | **$T_2$:** Evaluate Steering Tree. If `FAIL=0`: $\text{RegD} \rightarrow \text{BUS} \rightarrow \text{PCL}$. If `FAIL=1`: Trigger $\overline{\text{CYCLE\_RESET}}$.<br>

<br>**$T_3$:** $\text{RegC} \rightarrow \text{BUS} \rightarrow \text{PCH}$. | 4 Steps ($T_4$ Reset taken, $T_2$ Reset untaken) |
| **`CALL`** | `0000 / 1100` | **$T_2$:** $\text{PCL} \rightarrow \text{BUS} \rightarrow \text{STK}$ ($SP \leftarrow SP - 1$)<br>

<br>**$T_3$:** $\text{PCH} \rightarrow \text{BUS} \rightarrow \text{STK}$ ($SP \leftarrow SP - 1$)<br>

<br>**$T_4$:** $\text{RegD} \rightarrow \text{BUS} \rightarrow \text{PCL}$<br>

<br>**$T_5$:** $\text{RegC} \rightarrow \text{BUS} \rightarrow \text{PCH}$ | 6