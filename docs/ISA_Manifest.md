# Architectural Manifesto: Discrete 4-Bit NMOS Engine

## 1. Core Philosophy: Active-LOW Open-Drain & Centralized Exceptions

Designing a high-capability computer out of discrete NMOS logic requires ruthless transistor economy. Traditional processor architectures place complex instruction-decoding logic on every circuit board, resulting in massive hardware duplication.

This engine operates on a radical alternative: **Active-LOW open-drain physics at the edges, minimal overrides at the center.**

By treating passive HIGH ($V_{CC}$ via pull-ups) as the default floating state and active LOW ($GND$ via open-drain N-FETs) as the asserted state, tri-stating becomes free, bus decoding vanishes into wired-AND nodes, and backplane timing simplifies into non-interfering invariants:

* **1. Floating is Inactive:** Every backplane trace defaults to $V_{CC}$ ($1$). Cards interact with the system strictly by pulling traces to $GND$ ($0$).
* **2. Implicit Tri-State:** Disabling a card requires zero active driver logic; the card simply turns off its pull-down N-FETs, letting backplane pull-ups hold $V_{CC}$ safely.
* **3. Temporal Phase Ownership:** $T_0\text{--}T_1$ exclusively belong to Fetch ($PC \to \text{Memory} \to IR$). $T_2\text{--}T_3$ exclusively belong to Execution ($Reg/ALU \to \text{Bus} \to Reg/\text{RAM}$).
* **4. Destructive Write Prevention (`111` NULL):** Addressing `DEST = 111` leaves all internal register enable FETs OFF. The data on `BUS[3:0]` dissipates harmlessly without latching anywhere.
* **5. Non-Destructive Override:** Central Control modifies execution paths solely by grounding specific control lines. It never needs to drive a line HIGH against another active output.

---

## 2. The 4 ISA Quadrants & $ALU\_ENABLE$

The 16-opcode instruction set is divided into four distinct 4-opcode quadrants dictated by `OPCODE[3:2]`. This structural layout makes instruction decoding virtually free in hardware:

```text
       OP[3] = 0 : ALU Disabled (Flags Frozen)   │   OP[3] = 1 : ALU Enabled (Flags Update)
                                                 │
 00xx  [0x0 - 0x3] Data & Control Movement       │ 10xx  [0x8 - 0xB] Binary ALU Ops
       • MOV, LD, ST, BRANCH                     │       • ADD, SUB, AND, OR
       • Drives register & memory transfers.     │       • OP[1:0] directly drives ALU F1, F0.
                                                 │
 01xx  [0x4 - 0x7] Immediate Loads               │ 11xx  [0xC - 0xF] Extended ALU & Pointer Ops
       • LDI A, B, C, D                          │       • XOR, UNARY, NOT, CMP
       • OP[1:0] is bitmapped to DEST_ADDR[1:0]. │       • Opcode 0xD swizzles to subop control.

```

* **The $OP[3]$ `ALU_ENABLE` Signal:** $OPCODE[3]$ serves as the hardware $ALU\_ENABLE$ control bit. When $OP[3] = 0$ (Quadrants `00xx` and `01xx`), the ALU output drivers tri-state and flag latches freeze—guaranteeing that data moves and branches never alter $\overline{ZF}$ or $CF$. When $OP[3] = 1$ (Quadrants `10xx` and `11xx`), the ALU drives `BUS[3:0]` and updates flags on $\overline{CLK}$.
* **Direct Function Mapping (`10xx`):** For primary binary operations (`ADD`, `SUB`, `AND`, `OR`), $OP[1:0]$ connects directly to the ALU function select lines ($F_1, F_0$) without passing through decoding logic.

---

## 3. Complete 16-Opcode ISA Matrix

| Opcode | Mnemonic | Format | Operational Logic & Execution Flow |
| --- | --- | --- | --- |
| **`0x0`** | `MOV dst, src` | `dst, src` | $\text{dst} \leftarrow \text{src}$ *(Note: `0x00` = `MOV A, A` / `NOP`)* |
| **`0x1`** | `LD dst, [C:D]` | `dst, 00` | $\text{dst} \leftarrow \text{RAM}[C:D]$ |
| **`0x2`** | `ST [C:D], src` | `00, src` | $\text{RAM}[C:D] \leftarrow \text{src}$ *(Sinks writeback to `111` NULL)* |
| **`0x3`** | `BRANCH c, [C:D]` | `00, cc` | If Condition $c$ true: $PC_H \leftarrow C, PC_L \leftarrow D$. <br>

<br>Conditions ($cc$): `00`=`JMP`, `01`=`JZ`, `10`=`JC`, `11`=`JNZ` |
| **`0x4`** | `LDI A, imm4` | `00, imm4` | $A \leftarrow \text{imm}_4$ *(Central card overrides `DEST_ADDR` to `000`)* |
| **`0x5`** | `LDI B, imm4` | `00, imm4` | $B \leftarrow \text{imm}_4$ *(Central card overrides `DEST_ADDR` to `001`)* |
| **`0x6`** | `LDI C, imm4` | `00, imm4` | $C \leftarrow \text{imm}_4$ *(Central card overrides `DEST_ADDR` to `010`)* |
| **`0x7`** | `LDI D, imm4` | `00, imm4` | $D \leftarrow \text{imm}_4$ *(Central card overrides `DEST_ADDR` to `011`)* |
| **`0x8`** | `ADD dst, src` | `dst, src` | $\text{dst} \leftarrow \text{dst} + \text{src}$ |
| **`0x9`** | `SUB dst, src` | `dst, src` | $\text{dst} \leftarrow \text{dst} - \text{src}$ |
| **`0xA`** | `AND dst, src` | `dst, src` | $\text{dst} \leftarrow \text{dst} \land \text{src}$ |
| **`0xB`** | `OR dst, src` | `dst, src` | $\text{dst} \leftarrow \text{dst} \lor \text{src}$ |
| **`0xC`** | `XOR dst, src` | `dst, src` | $\text{dst} \leftarrow \text{dst} \oplus \text{src}$ |
| **`0xD`** | `UNARY dst, sub` | `dst, sub` | **Subop (`OPERAND[1:0]`):** `00`=`INC`, `01`=`DEC`, `10`=`INCC`, `11`=`DECC` |
| **`0xE`** | `NOT dst` | `dst, 00` | $\text{dst} \leftarrow \sim\text{dst}$ |
| **`0xF`** | `CMP dst, src` | `dst, src` | Evaluates $\text{dst} - \text{src}$, updates $\overline{ZF}/CF$, suppresses write to `111` |

---

## 4. Smart Architectural Breakthroughs

### A. Direct Bitmapped `LDI` Destination Encoding

Instead of spending active logic gates to decode load targets during an immediate load (`0x4`–`0x7`), the opcode bits $OP[1:0]$ **are** the 2-bit register address:

* `0x4` (`0100`) $\to$ Reg A (`000`)
* `0x5` (`0101`) $\to$ Reg B (`001`)
* `0x6` (`0110`) $\to$ Reg C (`010`)
* `0x7` (`0111`) $\to$ Reg D (`011`)

When $OP[3:2] = 01$, Central Control routes $OP[1:0]$ directly to $DEST\_ADDR[1:0]$ with zero active gates.

### B. Memory-Safe `0x00 = NOP`

Opcode `0x00` decodes to `MOV A, A`. In discrete systems, unprogrammed or erased RAM/ROM cells default to `0x00`. Defining `0x00` as a non-destructive identity move allows the CPU to slide safely through uninitialized memory blocks without corrupting state or firing spurious memory writes.

### C. Zero-Transistor Timestep Address Bus Ownership

Instead of complex multiplexer circuits or instruction decoders to route $PC$ vs $C:D$ onto the address buses, ownership is hardwired to physical backplane slot pinout and timestep signals ($T_0\text{--}T_3$):

* **Fetch Phase ($T_0 \lor T_1$):** $PC_H$ and $PC_L$ auto-enable their address drivers onto `ADDR_H` and `ADDR_L`.
* **Execution Phase ($T_2 \lor T_3$):** $PC$ address drivers turn OFF. Slots $C$ and $D$ unconditionally drive `ADDR_H` and `ADDR_L` during $T_2 \lor T_3$. Memory operations (`LD`/`ST`) simply pull $\overline{MEM\_OE}$ or $\overline{MEM\_WE}$ LOW; non-memory operations leave memory enables floating HIGH ($+5\text{V}$), rendering the address bus drive completely harmless.

### D. Subopcode Swizzling (`0xD UNARY`)

To provide single-register increment and decrement without consuming four main opcodes, Opcode `0xD` acts as a subopcode switch. Four pass-FETs disconnect $OP[1:0]$ from the ALU function select lines and route $OPERAND[1:0]$ in their place, unlocking `INC`, `DEC`, `INCC`, and `DECC`.

### E. Clean Internal Carry Logic & Active-LOW Flags

* $\overline{ZF}$ (Active-LOW Zero Flag) is pulled to $GND$ when a result is zero, simplifying wired condition checks.
* The $CF$ backplane trace is a **1-way line** (ALU $\to$ Central Control) used exclusively for conditional branch (`JC`) evaluation. For `INCC` and `DECC` operations, the ALU multiplexer samples its internal $CF$ Master-Slave latch for $C_{in}$, eliminating backplane bus contention.

---

## 5. Silicon ROI & Trade-Off Analysis

Every transistor added to Central Control is weighed directly against code density and memory footprint:

| Feature | Hardware Cost | Rationale & Memory Savings |
| --- | --- | --- |
| **Tier-3 Branch MUX (`JMP`, `JZ`, `JC`, `JNZ`)** | **6 Pass-FETs** | In a 256-nibble address space, omitting `JNZ` or `JC` forces assembly "trampolines" (jumping over jumps), wasting up to 25% of ROM space. Spending 6 FETs buys back ~40 bytes of code space. |
| **Multi-Precision `INCC`/`DECC**` | **2 Pass-FETs** | Incrementing an 8-bit pointer ($C:D$) using a 4-bit ALU normally requires a 5-instruction branch check. `INCC` collapses 8-bit pointer arithmetic to **2 cycles** (`INC D` then `INCC C`). |
| **Single-Direction $CF$ Backplane Trace** | **1 Pin** | Delivers $CF$ directly to Central Control for `JC` checking without requiring bidirectional bus-driver logic. |
| **Flag Protection Gate ($OP[3] \land \overline{CLK}$)** | **2 Gates** | Gates flag latching so that binary/extended ALU ops (`0x8`–`0xF`) update flags, while data moves (`MOV`, `LDI`, `LD`/`ST`) leave $\overline{ZF}$ and $CF$ untouched—preserving flags across register transfers. |

---

## 6. Program Counter Daughtercard Architecture

To keep baseboards completely identical, Program Counter increment logic is isolated onto a 10-pin daughtercard.

```text
                        TOP-SIDE SINGLE CARRY WIRE
                        ┌─────────────────────────┐
                        ▼                         │
            ┌───────────────────────┐ ┌───────────────────────┐
            │   PC_H Daughtercard   │ │   PC_L Daughtercard   │
            │   (Ripple Adder +1)   │ │   (Ripple Adder +1)   │
            └───────────┬───────────┘ └───────────┬───────────┘
                        │ 10-Pin Header           │ 10-Pin Header
            ┌───────────┴───────────┐ ┌───────────┴───────────┐
            │  Universal PC_H Base  │ │  Universal PC_L Base  │
            └───────────────────────┘ └───────────────────────┘

```

* **10-Pin Header Signals:** $Q[3:0]$ (Current State Inputs), $D_{IN}[3:0]$ (Incremented Outputs), $C_{IN}$ (Carry In), $C_{OUT}$ (Carry Out).
* **Asynchronous Calculation:** The daughtercard contains a 4-bit passive ripple-incrementer. During $T_0$ / $T_1$, it continuously computes $Q + C_{IN}$ and presents the value to $D_{IN}$.
* **Latch Timing:** On the falling clock edge ($\overline{CLK}$) of $T_0$ / $T_1$, the baseboard latches $D_{IN}$ into its internal storage cells. Clocking to the $PC$ master-slave latches is gated OFF during $T_2 \lor T_3$, completely isolating the incrementer during execution.
* **Top-Side Inter-$PC$ Carry Link ($PC_L \to PC_H$):** $PC_L$'s $C_{IN}$ is tied to $V_{CC}$ ($+5\text{V}$), incrementing unconditionally on $T_0$ and $T_1$. A **single top-side jumper wire** connects $PC_L$'s $C_{OUT}$ directly to $PC_H$'s $C_{IN}$, ensuring $PC_H$ increments only when $PC_L$ overflows from `0xF` $\to$ `0x0`.

---

## 7. Clocking, Timesteps & Bus Ownership Matrix

System clock $CLK$ drives a 4-step 1-hot ring counter ($T_0\text{--}T_3$). **$CLK_{HIGH}$ serves as the settling phase**, while **$CLK_{LOW}$ ($\overline{CLK}$) serves as the write/latching phase**.

| Timestep | $CLK$ Phase | `ADDR_H:ADDR_L` Owner | `BUS[3:0]` Owner | Active Control Lines (Asserted LOW) | State Latch Event ($\overline{CLK}$ Falling Edge) |
| --- | --- | --- | --- | --- | --- |
| **$T_0$** | **HIGH** | $PC_H : PC_L$ | Program Memory | $\overline{MEM\_OE}$ | *Bus lines discharge and settle* |
| **$T_0$** | **LOW** | $PC_H : PC_L$ | Program Memory | $\overline{MEM\_OE}$, $\overline{IR_{OP}\_WE}$ | $IR_{OP} \leftarrow OPCODE$, $PC \leftarrow PC + 1$ |
| **$T_1$** | **HIGH** | $PC_H : PC_L$ | Program Memory | $\overline{MEM\_OE}$ | *Bus lines discharge and settle* |
| **$T_1$** | **LOW** | $PC_H : PC_L$ | Program Memory | $\overline{MEM\_OE}$, $\overline{IR_{OPER}\_WE}$ | $IR_{OPER} \leftarrow OPERAND$, $PC \leftarrow PC + 1$ |
| **$T_2$** | **HIGH** | Reg $C : D$ | Reg `SRC` *(or ALU if $OP[3]=1$)* | $\overline{REG\_OE}_{src}$ OR $\overline{ALU\_OE}$ | *Execution setup phase* |
| **$T_2$** | **LOW** | Reg $C : D$ | Reg `SRC` *(or ALU if $OP[3]=1$)* | $\overline{REG\_WE}_{dst}$, $\overline{MEM\_WE}$ *(if `ST`)*, $\overline{LOAD\_PC_H}$ *(if `BRANCH`)* | Reg $DEST \leftarrow BUS$, $\text{RAM}[C:D] \leftarrow BUS$, $PC_H \leftarrow C$ *(if `BRANCH`)* |
| **$T_3$** | **HIGH** | Reg $C : D$ | Reg $D$ *(if `BRANCH`)* / High-Z | $\overline{REG\_OE}_D$ *(if `BRANCH`)* | *Secondary execution setup phase* |
| **$T_3$** | **LOW** | Reg $C : D$ | Reg $D$ *(if `BRANCH`)* / High-Z | $\overline{LOAD\_PC_L}$ *(if `BRANCH`)* | $PC_L \leftarrow D$ *(if `BRANCH`)*, Ring Counter $\to T_0$ |

---

## 8. Central Control Network (~27 Pass-FETs)

```text
                               CENTRAL CONTROL ARCHITECTURE

   ┌────────────────────────────────────────────────────────────────────────┐
   │ 6-FET Tier 3 Branch MUX                                                │
   │  OP[1:0] Selects (VCC [JMP], ~ZF_n [JZ], CF [JC], ZF_n [JNZ])          │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Address Override Network                                                 │
 │  • If LDI (0x4-0x7):  Forces DEST_ADDR = OP[1:0]                        │
 │  • If Branch Taken:   Forces SRC_ADDR = Reg C (T2) / Reg D (T3),         │
 │                       Forces DEST_ADDR = 100 (PC)                        │
 │  • If CMP / ST:       Forces DEST_ADDR = 111 (NULL Sink)                 │
 └───────────────────────────────────┬──────────────────────────────────────┘
                                     │
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ 10-FET Unary Swizzler (Opcode 0xD)                                       │
 │  • Swaps ALU Function lines F1, F0 from OP[1:0] to OPERAND[1:0]           │
 │  • Forces ALU Input B = 0000; Connects Internal CF Latch to Cin          │
 └───────────────────────────────────┴──────────────────────────────────────┘

```

### Active-LOW Logic Equations

$$\overline{MEM\_OE} = \overline{(T_0 \lor T_1) \lor \left((OPCODE == \text{0x1}) \land (T_2 \lor T_3)\right)}$$

$$\overline{MEM\_WE} = \overline{(OPCODE == \text{0x2}) \land (T_2 \lor T_3) \land \overline{CLK}}$$

---

## 9. 37-Pin Master Backplane Map

```text
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        37-PIN SYSTEM BACKPLANE                          │
  ├──────────────┬───────┬──────────────────────────────────────────────────┤
  │ Group        │ Pins  │ Signals                                          │
  ├──────────────┼───────┼──────────────────────────────────────────────────┤
  │ Power & Clk  │   4   │ GND, VCC, RESET, CLK                             │
  │ Timesteps    │   4   │ T0, T1, T2, T3 (1-Hot Sequencer Traces)           │
  │ Datapath     │  12   │ BUS[3:0], ADDR_H[3:0], ADDR_L[3:0] (Open-Drain)  │
  │ Instruction  │   8   │ OPCODE[3:0], OPERAND[3:0]                        │
  │ Controls     │   6   │ SRC[2:0], DST[2:0] (111 = NULL Sink)              │
  │ System Flags │   2   │ MEM_OE_n, MEM_WE_n (Active-LOW Memory Control)   │
  │ ALU Flags    │   1   │ ZF_n (Active-LOW Zero Flag Trace)                │
  │ Carry Link   │   1   │ CF (Unidirectional ALU Output -> Central Input)   │
  └──────────────┴───────┴──────────────────────────────────────────────────┘

```

---

## 10. Physical Hardware & Electrical Rules

1. **Threshold Voltage ($V_{th}$) Compensation:** Passive $10\text{k}\Omega$ pull-up resistors are required on pass-FET outputs (such as `BRANCH_ACTIVE` and address override nodes) to restore signal voltages to the full $+5\text{V}$ supply rail.
2. **Backplane Bus Pull-Ups:** `BUS[3:0]`, `ADDR_H/L`, `OPCODE`, `OPERAND`, $\overline{ZF}$, and $CF$ require **$2.2\text{k}\Omega \text{--} 4.7\text{k}\Omega$** resistor networks to balance fast rise times against open-drain N-FET current-sinking limits.
3. **Power Decoupling:** Every card must include one $100\text{nF}$ ceramic capacitor per IC/module plus one $10\mu\text{F}\text{--}47\mu\text{F}$ bulk capacitor at the backplane edge connector.
4. **Clock Debouncing:** The manual single-step button must pass through an SR latch or 555-timer debouncer to prevent multi-triggering.
