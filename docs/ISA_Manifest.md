# NOD-4 Reference Manual & Hardware Architecture (v8.6 Final)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Physical Hierarchy:** 48-Pin Passive Backplane Bus $\rightarrow$ Universal Base Cards $\rightarrow$ Counter/Stack Daughtercards

**Control Philosophy:** Pure Bitmapped Control, Direct-Hardwired Register Indexing, Zero-Decoder Glue Logic, Level-Active Execution, Internal Decoder Self-Reset, 5-Transistor Steering Tree Branch Engine

---

## 1. Physical System Invariants & Electrical Specifications

* **Strict Hardware Invariant:** `OPCODE[1:0]` is hardwired directly to the Destination Write Enable (`DST_WE`) decoder across all quadrants. `OPERAND[1:0]` is hardwired directly to the Source Output Enable (`SRC_OE`) decoder CPU-wide. Zero pass-gate MUXes are required on register index lines.
* **Stack Module (`STK`):** Self-contained daughtercard featuring an internal up/down counter and LIFO register array. Interacts directly with `BUS[3:0]` without touching RAM or external memory address buses.
* **Level-Active Execution:** All control assertions are static logic levels active throughout $T_2$. Setup and latching occur on the trailing edge ($T_2 \rightarrow T_3$), where $T_3$ triggers an asynchronous $\overline{\text{CYCLE\_RESET}}$ for standard 3-cycle execution.
* **Logic Family:** Discrete NMOS pass-transistor and depletion-load logic.
* **Signal Standard:** Active-LOW open-drain backplane rails with passive $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$. Active-LOW switching driven by 2N7000 NMOS transistors.
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
| **`STK`** (Slot 7) | UBC + Stack LIFO Daughtercard | 1 | Hardware Stack Pointer & Array | `BUS[3:0]`, `~WE[7]`, `~OE[7]`, `STK_PUSH_EN`, `STK_OE` |
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
|               COUNTER / STACK DAUGHTERCARD                      |
| - Counter: Smart Auto-Inc/Dec Adder Circuitry & Carry Routing   |
| - Stack: Internal Up/Down Pointer & Dedicated LIFO RAM Array   |
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
| **`STK`** | Hardware Stack Module | Backplane $\overline{\text{WE}}_7$ / Subops | Backplane $\overline{\text{OE}}_7$ / Subops | Unused | Stack LIFO Daughtercard |

---

## 5. Universal 13-Pin Base-to-Daughtercard Interface

Base Cards requiring auto-increment/decrement or hardware stack control (`PCL`, `PCH`, `STK`) interface with daughtercards via a standard 13-pin socket:

```
 Pin 1: VCC (+5V)          Pin 6:  D[0] (Data In 0)    Pin 10: Q[0] (Latch Out 0)
 Pin 2: GND                Pin 7:  D[1] (Data In 1)    Pin 11: Q[1] (Latch Out 1)
 Pin 3: ~T_STEP_A          Pin 8:  D[2] (Data In 2)    Pin 12: Q[2] (Latch Out 2)
 Pin 4: ~T_STEP_B          Pin 9:  D[3] (Data In 3)    Pin 13: Q[3] (Latch Out 3)
 Pin 5: ~COUNT_LATCH (Base Card Internal Latch Enable Pulse)

```

* **Surface Carry Pins (`C_IN` / `C_OUT`):** 2-pin header on Counter Daughtercards. Bridging `PCL` Daughtercard $C_{\text{out}} \rightarrow$ `PCH` Daughtercard $C_{\text{in}}$ enables 8-bit ripple-carry incrementing during instruction fetches.

---

## 6. Timing Engine & Dual-Nibble Fetch Mechanics

* **State Engine:** 3-bit ripple counter ($Q_2 Q_1 Q_0$) driving a 3-to-8 decoder on the **TIMING** card.
* **Local Decoder Self-Reset Loop:** Decoder output step 6 ($\overline{T_6}$) connects directly on the TIMING board to the counter's active-LOW clear input ($\overline{\text{CLR}}$).
* Counter ticks `101` ($T_5$) $\rightarrow$ `110` ($T_6$).
* Internal $\overline{T_6}$ immediately pulls $\overline{\text{CLR}}$ LOW, resetting state to `000` ($T_0$) in $\approx 15\text{ ns}$.
* Only active steps $\overline{T_0}$ through $\overline{T_5}$ route to backplane pins 05–10.



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
* **Phase $T_2$ Execution:** All level assertions execute during $T_2$. Standard single-cycle register/ALU/Stack operations trigger $\overline{\text{CYCLE\_RESET}}$ at entry to $T_3$, achieving optimal 3-cycle execution ($T_0, T_1, T_2$).



---

## 7. Hardware Control Boolean Equations & 5-Transistor Branch Engine

### Intermediate Quadrant Decodes

$$\text{IS\_CTRL} = \text{OP}[3] \cdot \text{OP}[2]$$

$$\text{DATA\_OP} = \overline{\text{OP}[3]} \cdot \overline{\text{OP}[2]}$$

$$\text{IMM\_OP} = \overline{\text{OP}[3]} \cdot \text{OP}[2]$$

$$\text{MEM\_OP} = \text{OP}[3] \cdot \overline{\text{OP}[2]}$$

### Control Inhibit & Direct Gating Equations

Because register selection relies strictly on default bus wiring (`OPCODE[1:0]` $\rightarrow$ `DST_WE`, `OPERAND[1:0]` $\rightarrow$ `SRC_OE`), Control Quadrant signals gate global decoder enable lines during $T_2$:

* **`PUSH reg` (`1100` / `10rr`):**

$$\text{SRC\_OE\_ENABLE} = \text{IS\_CTRL} \cdot \text{OPERAND}[3] \cdot \overline{\text{OPERAND}[2]}$$


$$\text{DST\_WE\_ENABLE} = 0 \quad (\text{Inhibited})$$


$$\text{STK\_PUSH\_EN} = \text{IS\_CTRL} \cdot \text{OPERAND}[3] \cdot \overline{\text{OPERAND}[2]} \cdot T_2$$


* **`POP reg` (`11rr` / `0100`):**

$$\text{SRC\_OE\_ENABLE} = 0 \quad (\text{Inhibited})$$


$$\text{DST\_WE\_ENABLE} = \text{IS\_CTRL} \cdot \overline{\text{OPERAND}[3]} \cdot \text{OPERAND}[2]$$


$$\text{STK\_OE} = \text{IS\_CTRL} \cdot \overline{\text{OPERAND}[3]} \cdot \text{OPERAND}[2]} \cdot T_2$$


* **`PUSHPC` (`1100` / `1110`):**
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

$$\overline{\text{CYCLE\_RESET}} = \overline{(T_2 \cdot \text{FAIL}) \lor (T_3 \cdot (\text{DATA\_OP} \lor \text{IMM\_OP} \lor \text{PUSH} \lor \text{POP})) \lor (T_4 \cdot \text{JMP\_RET}) \lor (T_5 \cdot \text{CALL})}$$

---

## 8. Master Instruction Encoding & Quadrant Architecture

**8-Bit Explicit Instruction Breakdown:**

$$\text{OPCODE}[3:0] = [\text{QUAD}_1 \mid \text{QUAD}_0 \mid \text{DST}_1 \mid \text{DST}_0]$$

$$\text{OPERAND}[3:0] = [\text{MODE}_1 / \text{OP}_1 \mid \text{MODE}_0 / \text{OP}_0 \mid \text{SRC}_1 / \text{PAYLOAD}_1 \mid \text{SRC}_0 / \text{PAYLOAD}_0]$$

```
  +-------+-------+------+------+----------+----------+---------+---------+
  | QUAD1 | QUAD0 | DST1 | DST0 | MODE/OP1 | MODE/OP0 | SRC/PL1 | SRC/PL0 |
  +-------+-------+------+------+----------+----------+---------+---------+
  |    OPCODE (Bits 3:0)        |        OPERAND (Bits 3:0)             |
  +-----------------------------+---------------------------------------+

```

### Universal 4-Quadrant Major Class Matrix (`OPCODE[3:2]`)

| Quadrant (`OPCODE[3:2]`) | `OPCODE[1:0]` Target | `OPERAND[3:2]` Role | Operations | Hardware Behavior at $T_2$ |
| --- | --- | --- | --- | --- |
| **`00rr`** | `dst = Reg[rr]` | `00` (Src) | **Reg-Reg ALU / `MOV**` | `Reg[OPERAND[1:0]]` drives `BUS`; `Reg[OPCODE[1:0]]` latches. |
| **`01rr`** | `dst = Reg[rr]` | Payload | **Immediate ALU** | Immediate payload drives `BUS`; `Reg[OPCODE[1:0]]` latches. |
| **`10rr`** | `dst = Reg[rr]` | Mode | **Memory `LD`/`ST**` | Memory address bus active; transfers between RAM and `Reg[rr]`. |
| **`11rr`** | `dst = Reg[rr]` | **Control Class** | **Control / System / Stack** | See sub-quadrant matrix below. |

### Control Quadrant (`11rr`) Sub-Class Encoding

| Instruction | Opcode (`OPCODE[3:0]`) | Operand (`OPERAND[3:0]`) | `SRC_OE` Decoder | `DST_WE` Decoder | $T_2$ Level Assertions |
| --- | --- | --- | --- | --- | --- |
| **`POP reg`** | **`11rr`** | `0100` | **Disabled** | **Active (`Reg[rr]`)** | `STK_OE` High $\rightarrow$ Stack card drives `BUS[3:0]` into `Reg[OPCODE[1:0]]`. |
| **`PUSH reg`** | `1100` | **`10rr`** | **Active (`Reg[rr]`)** | **Disabled** | `STK_PUSH_EN` High $\rightarrow$ Stack card latches `BUS[3:0]` from `Reg[OPERAND[1:0]]`. |
| **Branches** | `1100` | `00cc` | **Disabled** | **Disabled** | Steering tree evaluates condition `cc` (`00`: JZ, `01`: JNZ, `10`: JC, `11`: JMP). |
| **System Ops** | `1100` | `11xx` | **Disabled** | **Disabled** | Multi-cycle PC/STK control (`1100`: CALL, `1101`: RET, `1110`: PUSHPC, `1111`: NOP). |

### Register Encoding (`dst` or `src` in `OP[1:0]` / `OPERAND[1:0]`)

`00` = `RegA` | `01` = `RegB` | `10` = `RegC` (High Ptr) | `11` = `RegD` (Low Ptr)

---

## 9. Complete 0x0–0xF Execution Matrix

| Opcode | Binary | Mnemonic | Format | Timestep Execution & Micro-Operations | Total Steps |
| --- | --- | --- | --- | --- | --- |
| **`0x0`** | `0000` | `MOV/ALU RegA, src` | `00, src[1:0]` | **$T_2$:** `Reg[src]` drives `BUS[3:0]` $\rightarrow$ `RegA` latches. | 3 Steps ($T_3$ Reset) |
| **`0x1`** | `0001` | `MOV/ALU RegB, src` | `00, src[1:0]` | **$T_2$:** `Reg[src]` drives `BUS[3:0]` $\rightarrow$ `RegB` latches. | 3 Steps ($T_3$ Reset) |
| **`0x2`** | `0010` | `MOV/ALU RegC, src` | `00, src[1:0]` | **$T_2$:** `Reg[src]` drives `BUS[3:0]` $\rightarrow$ `RegC` latches. | 3 Steps ($T_3$ Reset) |
| **`0x3`** | `0011` | `MOV/ALU RegD, src` | `00, src[1:0]` | **$T_2$:** `Reg[src]` drives `BUS[3:0]` $\rightarrow$ `RegD` latches. | 3 Steps ($T_3$ Reset) |
| **`0x4`** | `0100` | `ALUI RegA, imm` | `op[3:2], imm[1:0]` | **$T_2$:** Immediate payload drives `BUS[3:0]` $\rightarrow$ ALU computes $\rightarrow$ `RegA` latches. | 3 Steps ($T_3$ Reset) |
| **`0x5`** | `0101` | `ALUI RegB, imm` | `op[3:2], imm[1:0]` | **$T_2$:** Immediate payload drives `BUS[3:0]` $\rightarrow$ ALU computes $\rightarrow$ `RegB` latches. | 3 Steps ($T_3$ Reset) |
| **`0x6`** | `0110` | `ALUI RegC, imm` | `op[3:2], imm[1:0]` | **$T_2$:** Immediate payload drives `BUS[3:0]` $\rightarrow$ ALU computes $\rightarrow$ `RegC` latches. | 3 Steps ($T_3$ Reset) |
| **`0x7`** | `0111` | `ALUI RegD, imm` | `op[3:2], imm[1:0]` | **$T_2$:** Immediate payload drives `BUS[3:0]` $\rightarrow$ ALU computes $\rightarrow$ `RegD` latches. | 3 Steps ($T_3$ Reset) |
| **`0x8`** | `1000` | `LD/ST RegA, mode` | `mode[3:2], src[1:0]` | **$T_2$:** `RegC:RegD` drives `ADDR_H:ADDR_L`, RAM $\leftrightarrow$ `RegA`. | 3 Steps ($T_3$ Reset) |
| **`0x9`** | `1001` | `LD/ST RegB, mode` | `mode[3:2], src[1:0]` | **$T_2$:** `RegC:RegD` drives `ADDR_H:ADDR_L`, RAM $\leftrightarrow$ `RegB`. | 3 Steps ($T_3$ Reset) |
| **`0xA`** | `1010` | `LD/ST RegC, mode` | `mode[3:2], src[1:0]` | **$T_2$:** `RegC:RegD` drives `ADDR_H:ADDR_L`, RAM $\leftrightarrow$ `RegC`. | 3 Steps ($T_3$ Reset) |
| **`0xB`** | `1011` | `LD/ST RegD, mode` | `mode[3:2], src[1:0]` | **$T_2$:** `RegC:RegD` drives `ADDR_H:ADDR_L`, RAM $\leftrightarrow$ `RegD`. | 3 Steps ($T_3$ Reset) |
| **`0xC`** | `1100` | `CTRL / POP RegA` | Subop / `0100` | **$T_2$:** If Operand=`0100`: `STK` drives `BUS[3:0]` $\rightarrow$ `RegA` latches. Else Branch/System. | 3 to 6 Steps |
| **`0xD`** | `1101` | `POP RegB` | `0100` | **$T_2$:** `STK` drives `BUS[3:0]` $\rightarrow$ `RegB` latches. | 3 Steps ($T_3$ Reset) |
| **`0xE`** | `1110` | `POP RegC` | `0100` | **$T_2$:** `STK` drives `BUS[3:0]` $\rightarrow$ `RegC` latches. | 3 Steps ($T_3$ Reset) |
| **`0xF`** | `1111` | `POP RegD` | `0100` | **$T_2$:** `STK` drives `BUS[3:0]` $\rightarrow$ `RegD` latches. | 3 Steps ($T_3$ Reset) |

---

## 10. Control & Stack Sub-Operations Breakdown

| Subop | Mnemonic | Format | Serialized Hardware Micro-Operations | Total Steps |
| --- | --- | --- | --- | --- |
| **Stack** | `PUSH reg` | `1100, 10rr` | **$T_2$:** `SRC_OE` active (`Reg[rr]`). `STK_PUSH_EN` active $\rightarrow$ Stack module latches `BUS[3:0]`. SP decrements. | 3 Steps ($T_3$ Reset) |
| **Stack** | `POP reg` | `11rr, 0100` | **$T_2$:** `STK_OE` active. `DST_WE` active (`Reg[rr]`). Stack module drives `BUS[3:0]` $\rightarrow$ `Reg[rr]` latches. SP increments. | 3 Steps ($T_3$ Reset) |
| **Branch** | `Jcc` / `JMP` | `1100, 00cc` | **$T_2$:** Evaluate Steering Tree. If `FAIL=0`: $\text{RegD} \rightarrow \text{BUS} \rightarrow \text{PCL}$. If `FAIL=1`: Trigger $\overline{\text{CYCLE\_RESET}}$.<br>

<br>**$T_3$:** $\text{RegC} \rightarrow \text{BUS} \rightarrow \text{PCH}$. | 4 Steps ($T_4$ Reset taken, $T_2$ Reset untaken) |
| **System** | `CALL` | `1100, 1100` | **$T_2$:** $\text{PCL} \rightarrow \text{BUS} \rightarrow \text{STK}$ ($SP \leftarrow SP - 1$)<br>

<br>**$T_3$:** $\text{PCH} \rightarrow \text{BUS} \rightarrow \text{STK}$ ($SP \leftarrow SP - 1$)<br>

<br>**$T_4$:** $\text{RegD} \rightarrow \text{BUS} \rightarrow \text{PCL}$<br>

<br>**$T_5$:** $\text{RegC} \rightarrow \text{BUS} \rightarrow \text{PCH}$ | 6 Steps ($T_0$–$T_5$, internal $T_6$ reset)