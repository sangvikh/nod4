# NOD-4 Microprocessor Architecture & System Specification (v12.3)

**Architecture Type:** 4-Bit Cumulative Discrete NMOS Microprocessor

**Addressing & Pointers:** 8-Bit Unified Address Space (`[RegC:RegD]` / `[PCH:PCL]`)

**Physical Hierarchy:** 50-Pin Passive Backplane Bus $\rightarrow$ Universal Base Cards $\rightarrow$ Counter / Extended ALU / Interrupt Daughtercards

**Control Philosophy:** Bitmapped Control, Direct-Drive Unary/Shift Matrix, Zero-Decoder Destination Routing, Internal Decoder Self-Reset, Diagonal Override Control Escape ($\text{dd} == \text{ss}$), Bus-Hijack Interrupt Engine.

---

## 1. Electrical Standard, Timing & Control Invariants

* **Logic Family:** Discrete NMOS pass-transistor and depletion-load logic using 2N7000 NMOS switches with active-LOW signal paths.
* **Signal Standard:** Active-LOW open-drain backplane rails with $2.2\text{ k}\Omega$ pull-up resistors to $+5\text{V}$.
* **Execution Micro-Steps ($T_0 \dots T_5$):**
* **$T_0$ (Opcode Fetch):** Program Counter outputs `PCH:PCL` to `ADDR_H/L`. ROM drives opcode onto `BUS[3:0]`, latched into `OPCODE[3:0]`.
* **$T_1$ (Operand Fetch):** $PC$ increments, outputs `PCH:PCL` to `ADDR_H/L`. ROM drives operand onto `BUS[3:0]`, latched into `OPERAND[3:0]`.
* **$T_2$ (Drive / Execute):** Source register or immediate data is driven onto `BUS[3:0]`. Destination card readies latching.
* **$T_3$ (ALU / Writeback):** ALU processes computation and outputs result onto `BUS[3:0]`. Target module latches input. Execution flags ($ZF, CF$) sample on the trailing edge of $T_3$.
* **$T_4$ (PC Auto-Increment):** $PC$ auto-increments to prepare for the next instruction fetch ($PC \leftarrow PC + 1$).
* **$T_5$ (Bus Release / Settle):** All card output buffers release backplane lines, state machine settles, and `~CYCLE_RESET` resets step counter to $T_0$.


* **PC Increment Gating:** Program counter auto-increment strobe is gated directly by the interrupt disable rail:

$$\text{PC\_INC\_ENABLE} = \text{INC\_STROBE} \cdot \overline{\text{IR\_DISABLE}}$$


* **Execution Flags:**
* $ZF$ (Zero Flag): Set if the 4-bit output of an operation equals $0\text{x0}$ (sampled at $T_3$).
* $CF$ (Carry/Borrow Flag): Set on arithmetic carry-out or cleared on borrow using inverted-borrow logic (sampled at $T_3$).
* $IE$ (Interrupt Enable Flag): Hardware latch on Interrupt Card (Set via `STI`/`RETI`, cleared via `CLI`/IRQ entry).



---

## 2. Master 50-Pin Backplane Pinout Specification

```
   SYSTEM & CONTROL (01-06)         CONTROL RAILS (~WE / ~OE)          PARALLEL NIBBLE BUSES
[ 01-03 ] Power & Clock           [ 15-22 ] Write Enables (~WE)   --->   [ 31-34 ] Data Bus (BUS)
[ 04-06 ] Reset, Disable, IRQ     [ 23-30 ] Output Enables (~OE)         [ 35-38 ] Address High (ADDR_H)
[ 07-12 ] Timesteps (T0-T5)                                              [ 39-42 ] Address Low (ADDR_L)
[ 13-14 ] Flags (ZF / CF)                                                [ 43-46 ] Opcode Rail (OPCODE)
                                                                         [ 47-50 ] Operand Rail (OPERAND)

```

| Pin # | Signal | Domain | Description & Interconnect Target |
| --- | --- | --- | --- |
| **01** | `GND` | Power | System Ground Reference Return |
| **02** | `VCC` | Power | $+5\text{V}$ Power Rail |
| **03** | `CLK` | Timing | Main Clock Input |
| **04** | `~CYCLE_RESET` | Control | Active-LOW Synchronous State Counter Reset |
| **05** | `~IR_DISABLE` | System | Active-LOW Interrupt Hijack / Halt NOP-Force Rail |
| **06** | `~IRQ` | System | Active-LOW Open-Drain Hardware Interrupt Request Rail |
| **07–12** | `~T0`–`~T5` | Timing | Execution Timesteps $0$ through $5$ |
| **13** | `~ZF` | Flag | Active-LOW Zero Flag Bus Rail |
| **14** | `~CF` | Flag | Active-LOW Carry / Borrow Flag Bus Rail |
| **15–22** | `~WE[0:7]` | Control | Write Enable Rails for Cards 0 through 7 |
| **23–30** | `~OE[0:7]` | Control | Output Enable Rails for Cards 0 through 7 |
| **31–34** | `BUS[0:3]` | Data | Bidirectional 4-Bit Data Bus |
| **35–38** | `ADDR_H[0:3]` | Address | Memory Address High Nibble |
| **39–42** | `ADDR_L[0:3]` | Address | Memory Address Low Nibble |
| **43–46** | `OPCODE[0:3]` | Control | Latched Instruction Opcode Nibble |
| **47–50** | `OPERAND[0:3]` | Control | Latched Instruction Operand Nibble |

---

## 3. System Hardware Card Manifest & Bus Slot Mapping

| Slot / Module | Board Type | Qty | Target Vector | Function & Backplane Connections |
| --- | --- | --- | --- | --- |
| **RegA** | Universal Base Card (UBC) | 1 | `000` (`0x0`) | General Purpose Register A (`BUS[3:0]`, `~WE[0]`, `~OE[0]`) |
| **RegB** | Universal Base Card (UBC) | 1 | `001` (`0x1`) | General Purpose Register B (`BUS[3:0]`, `~WE[1]`, `~OE[1]`) |
| **RegC** | Universal Base Card (UBC) | 1 | `010` (`0x2`) | High Pointer Nibble `PTR_H` (`BUS[3:0]`, `ADDR_H[3:0]`, `~WE[2]`, `~OE[2]`) |
| **RegD** | Universal Base Card (UBC) | 1 | `011` (`0x3`) | Low Pointer Nibble `PTR_L` (`BUS[3:0]`, `ADDR_L[3:0]`, `~WE[3]`, `~OE[3]`) |
| **MEM** | Memory Transceiver Board | 1 | `100` (`0x4`) | System RAM/ROM Interface (`ADDR_H/L`, `BUS[3:0]`, `~WE[4]`, `~OE[4]`) |
| **PCH** | UBC + Counter Daughtercard | 1 | `101` (`0x5`) | Program Counter High (`BUS[3:0]`, `ADDR_H[3:0]`, `~WE[5]`, `~OE[5]`) |
| **PCL** | UBC + Counter Daughtercard | 1 | `110` (`0x6`) | Program Counter Low (`BUS[3:0]`, `ADDR_L[3:0]`, `~WE[6]`, `~OE[6]`) |
| **STK** | UBC + Hardware Stack Core | 1 | `111` (`0x7`) | Hardware Stack Core & Pointer (`BUS[3:0]`, `~WE[7]`, `~OE[7]`) |
| **OPCODE** | Universal Base Card (UBC) | 1 | — | Opcode Latch (`BUS[3:0]`, `OPCODE[3:0]`, `~IR_DISABLE`) |
| **OPERAND** | Universal Base Card (UBC) | 1 | — | Operand Latch (`BUS[3:0]`, `OPERAND[3:0]`, `~IR_DISABLE`) |
| **ALU** | Custom Discrete Board | 1 | — | 4-Bit Binary Adder, Carry Tap (`BUS[3:0]`, `OPCODE[3:0]`, `OPERAND[3:0]`) |
| **EXT_ALU** | ALU Daughtercard | 1 | — | Shift Matrix & Unary Operations (Piggybacks on ALU Board) |
| **TIMING** | Custom Discrete Board | 1 | — | State Counter, Decoder, Flags (`CLK`, `~T0..~T5`, `~CYCLE_RESET`) |
| **INT** | Custom Discrete Board | 1 | — | Handshake, Vector Hijack, Halt (`~IRQ`, `~IR_DISABLE`, `BUS[3:0]`) |

---

## 4. Universal Base Card (UBC) Architecture

```
+-----------------------------------------------------------------------------------+
|                            BACKPLANE (50 Pins)                                    |
+-----------------------------------------------------------------------------------+
       |                  |                        |                  |
       v                  v                        v                  v
  ~WE[0:7]            ~OE[0:7]                  ~T0..~T5           BUS[3:0]
       |                  |                        |                  |
+------|------------------|------------------------|------------------|-------------+
|      v                  v                        v                  |             |
|  +-------+          +-------+                                       |             |
|  | HDR 1 |          | HDR 2 |                                       |             |
|  | 2x14  |          | 2x14  |                                       |             |
|  +-------+          +-------+                                       v             |
|      |                  |                              +-----------------------+  |
|   ~INT_WE            ~OE_MAIN / ~SEC_OE                | 4x Discrete NMOS      |  |
|      |                  |                              | D-Latch Core          |  |
|      +----------> [ GATE LOGIC ] <-------------------->| (4x 2N7000 + Depletion|  |
|                         |                              | Load Inverters)       |  |
|                         v                              +-----------------------+  |
|               +-------------------+                             |                 |
|               | 2N7000 Output     |=============================+                 |
|               | Bus Buffers       |                             |                 |
|               +-------------------+                             v                 |
|                         |                              +-----------------------+  |
|                         +=============================>| HDR 3 (SEC_DEST)      |  |
|                         |                              | Bridge Output         |  |
|                         v                              +-----------------------+  |
|                     BUS[3:0]                                    |                 |
|                         |                                       v                 |
|                         |                             ADDR_H / ADDR_L / OP / OPER |
|                         |                                                         |
|                         +==================================+                      |
|                                                            v                      |
|                                              [ 13-Pin Daughtercard Socket ]       |
+-----------------------------------------------------------------------------------+

```

---

## 5. Instruction Word Format & Opcode Decoding Matrix

The NOD-4 instruction word is defined by **`OP[3] = IMM`** (Immediate Flag) and **`OP[2] = ALU_EN`** (ALU Enable):

```
         OPCODE [3:0] (T0)                       OPERAND [3:0] (T1)
+------------+------------+------------+------------+------------+------------+------------+------------+
|  OP[3]     |  OP[2]     |  OP[1]     |  OP[0]     |  OPERAND3  |  OPERAND2  |  OPERAND1  |  OPERAND0  |
+------------+------------+------------+------------+------------+------------+------------+------------+
|    IMM     |   ALU_EN   |   SUB-OP / |   SUB-OP / |   TARGET / SOURCE / IMMEDIATE / EXTENDED     |
|   FLAG     |   ENABLE   |  TARGET 1  |  TARGET 0  |   CONTROL BITS                                |
+------------+------------+------------+------------+------------+------------+------------+------------+

```

### Quadrant Taxonomy (`OP[3:2]`)

| Quadrant | `OP[3:2]` (`IMM`, `ALU_EN`) | Functional Class | Micro-Control Logic & Signals |
| --- | --- | --- | --- |
| **Q0** | `00` | **Register Moves & System Escapes** | `IMM=0, ALU_EN=0`. Direct 3-bit routing (`00 dd cc ss`). Uses Diagonal Escape ($\text{dd} == \text{ss}$, $cc = 00$) for Control/Branching. |
| **Q1** | `01` | **Reg-to-Reg Binary ALU** | `IMM=0, ALU_EN=1`. `RegA` serves as primary accumulator; `OPERAND[3:0]` selects source register and ALU operation. |
| **Q2** | `10` | **Load Immediate (`LDI`)** | `IMM=1, ALU_EN=0`. Drives raw `OPERAND[3:0]` literal to `BUS[3:0]` and writes to target slot specified by `OP[1:0]`. |
| **Q3** | `11` | **Immediate ALU & Extended Shift Matrix** | `IMM=1, ALU_EN=1`. `OPERAND[3:0]` decodes immediate arithmetic, carry-chain operations (`ADC`/`SBB`), and shift matrix ops. |

---

## 6. Quadrant 0 (`OP[3:2] = 00`): Register Moves & System Escapes

* **Standard Moves (`00 dd cc ss` where $\text{dd} \neq \text{ss}$ or $cc \neq 00$):**
$\text{DST} = \{cc[1], \text{dd}\}$, $\text{SRC} = \{cc[0], \text{ss}\}$.
* $cc = 00$: `MOV reg, reg` (Core Register to Core Register)
* $cc = 01$: `ST sys, reg` (Core Register to System Node)
* $cc = 10$: `LD reg, sys` (System Node to Core Register)
* $cc = 11$: `MOV sys, sys` (System Node to System Node Direct Transfer)


* **Diagonal Control Escapes ($cc = 00$ and $\text{dd} == \text{ss}$):**

| Opcode Pattern | Binary | Hex | Mnemonic | Operational Logic & Micro-Steps |
| --- | --- | --- | --- | --- |
| **`00 00 00 00`** | `00000000` | `0x00` | **NOP** | System Idle; default state forced during `~IR_DISABLE` assertion. |
| **`00 00 01 00`** | `00000100` | `0x04` | *Reserved* | Unassigned control slot (formerly `BRK`). |
| **`00 00 10 00`** | `00001000` | `0x08` | *Reserved* | Unassigned control slot. |
| **`00 00 11 00`** | `00001100` | `0x0C` | *Reserved* | Unassigned control slot. |
| **`00 01 00 01`** | `00010001` | `0x11` | **CLI** | Clear Interrupt Enable Flag ($IE \leftarrow 0$). |
| **`00 01 01 01`** | `00010101` | `0x15` | **STI** | Set Interrupt Enable Flag ($IE \leftarrow 1$). |
| **`00 01 10 01`** | `00011001` | `0x19` | **RETI** | Return from Interrupt: Pop $PCH:PCL$ from hardware stack, set $IE \leftarrow 1$. |
| **`00 01 11 01`** | `00011101` | `0x1D` | **HALT** | Asserts Halt Latch and drives `~IR_DISABLE` LOW until hardware reset or IRQ. |
| **`00 10 00 10`** | `00100010` | `0x22` | **JZ / JE** | Branch to address in `RegC:RegD` if $ZF = 1$. |
| **`00 10 01 10`** | `00100110` | `0x26` | **JC / JAE** | Branch to address in `RegC:RegD` if $CF = 1$. |
| **`00 10 10 10`** | `00101010` | `0x2A` | **JNZ / JNE** | Branch to address in `RegC:RegD` if $ZF = 0$. |
| **`00 10 11 10`** | `00101110` | `0x2E` | **JMP** | Unconditional Branch to address in `RegC:RegD`. |
| **`00 11 00 11`** | `00110011` | `0x33` | **CALL** | Push $PCL$, Push $PCH$, load `RegC:RegD` into `PCH:PCL`. |
| **`00 11 01 11`** | `00110111` | `0x37` | **RET** | Pop $PCH$, Pop $PCL$ from stack into `PCH:PCL`. |
| **`00 11 10 11`** | `00111011` | `0x3B` | **PUSHPC** | Push current $PCL$ then $PCH$ to hardware stack. |
| **`00 11 11 11`** | `00111111` | `0x3F` | *Reserved* | Unassigned control slot. |

---

## 7. Quadrant 1 (`OP[3:2] = 01`): Reg-to-Reg Binary ALU

In Quadrant 1, `ALU_EN` is active (`OP[2]=1`), while `IMM` is inactive (`OP[3]=0`). `RegA` acts as the implicit accumulator, and `OPERAND[1:0]` specifies the source register.

```
Opcode Format: 01 op1 op0 ss  (where op[1:0] = ALU Function Select)

```

| Opcode Pattern | Mnemonic | ALU Function | Operational Logic | Flag Updates |
| --- | --- | --- | --- | --- |
| **`01 00 00 ss`** | `ADD RegA, src` | Binary Addition | $\text{RegA} \leftarrow \text{RegA} + \text{SRC}$ | $ZF, CF$ |
| **`01 01 00 ss`** | `SUB RegA, src` | Binary Subtraction | $\text{RegA} \leftarrow \text{RegA} - \text{SRC}$ | $ZF, CF$ |
| **`01 10 00 ss`** | `AND RegA, src` | Bitwise AND | $\text{RegA} \leftarrow \text{RegA} \cdot \text{SRC}$ | $ZF$ ($CF \leftarrow 0$) |
| **`01 11 00 ss`** | `OR  RegA, src` | Bitwise OR | $\text{RegA} \leftarrow \text{RegA} \lor \text{SRC}$ | $ZF$ ($CF \leftarrow 0$) |
| **`01 00 01 ss`** | `XOR RegA, src` | Bitwise XOR | $\text{RegA} \leftarrow \text{RegA} \oplus \text{SRC}$ | $ZF$ ($CF \leftarrow 0$) |
| **`01 01 01 ss`** | `CMP RegA, src` | Compare (No Write) | Evaluate $\text{RegA} - \text{SRC}$ | $ZF, CF$ |

---

## 8. Quadrant 2 (`OP[3:2] = 10`): Load Immediate (`LDI`)

In Quadrant 2, `IMM` is active (`OP[3]=1`), while `ALU_EN` is inactive (`OP[2]=0`). During $T_2$, the OPERAND Base Card outputs its stored nibble to `BUS[3:0]`, while `~WE[DST]` is driven LOW on the target card specified by `OP[1:0]`.

```
Opcode Format: 10 dd cc 00  (OPERAND[3:0] = 4-Bit Immediate Data)

```

| Opcode (`OPCODE[3:0]`) | Mnemonic | Destination Target | Execution Sequence ($T_2$) |
| --- | --- | --- | --- |
| **`10 00 00 00` (`0x80`)** | `LDI RegA, #imm` | `RegA` (Slot 0) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[0]` |
| **`10 01 00 00` (`0x90`)** | `LDI RegB, #imm` | `RegB` (Slot 1) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[1]` |
| **`10 10 00 00` (`0xA0`)** | `LDI RegC, #imm` | `RegC` (Slot 2) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[2]` |
| **`10 11 00 00` (`0xB0`)** | `LDI RegD, #imm` | `RegD` (Slot 3) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[3]` |
| **`10 00 01 00` (`0x84`)** | `LDI MEM, #imm` | `RAM[RegC:RegD]` | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[4]` |
| **`10 01 01 00` (`0x94`)** | `LDI PCH, #imm` | `PCH` (Slot 5) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[5]` |
| **`10 10 01 00` (`0xA4`)** | `LDI PCL, #imm` | `PCL` (Slot 6) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[6]` |
| **`10 11 01 00` (`0xB4`)** | `LDI STK, #imm` | Stack Core (Slot 7) | `OPERAND[3:0]` $\rightarrow$ `BUS[3:0]`, assert `~WE[7]` |

---

## 9. Quadrant 3 (`OP[3:2] = 11`): Immediate ALU & Shift Matrix

Both `IMM` (`OP[3]=1`) and `ALU_EN` (`OP[2]=1`) are asserted. Operation decoding is handled directly by the **Operand Nibble**:

$$\text{OPERAND}[3:0] = [\text{EXT} \mid \text{ALU\_OP1} \mid \text{ALU\_OP0} \mid \text{IMM0}]$$

> **Immediate Carry Handling Logic:**
> * When **`IMM0 = 0`**, arithmetic operations route the Carry Flag into the carry chain:
> * `ADC`: Computes $\text{dst} + 0 + CF$ ($C_{in} = CF$).
> * `SBB`: Computes $\text{dst} - 0 - (1 - CF)$ ($C_{in} = \overline{CF}$).
> 
> 
> * When **`IMM0 = 1`**, single-step arithmetic executes without active carry propagation:
> * `INC`: Computes $\text{dst} + 1$ ($C_{in} = 0$).
> * `DEC`: Computes $\text{dst} - 1$ ($C_{in} = 1$).
> 
> 
> 
> 

| EXT | ALU_OP[1:0] | IMM0 | Mnemonic | Hardware Operational Logic & Carry Handling |
| --- | --- | --- | --- | --- |
| `0` | `00` | **`0`** | **`ADC dst`** | **Add with Carry:** $\text{dst} \leftarrow \text{dst} + 0 + CF$ ($C_{in} = CF$) |
| `0` | `00` | **`1`** | **`INC dst`** | **Increment:** $\text{dst} \leftarrow \text{dst} + 1$ ($C_{in} = 0$) |
| `0` | `01` | **`0`** | **`SBB dst`** | **Subtract with Borrow:** $\text{dst} \leftarrow \text{dst} - 0 - (1 - CF)$ |
| `0` | `01` | **`1`** | **`DEC dst`** | **Decrement:** $\text{dst} \leftarrow \text{dst} - 1$ ($C_{in} = 1$) |
| `0` | `10` | `0` | `XORI dst, 0` | Bitwise XOR with 0 (Preserves value, updates $ZF$) |
| `0` | `10` | `1` | `XORI dst, 1` | Bitwise XOR with 1 (Flips Bit 0) |
| `0` | `11` | `0` | `ANDI dst, 0` | Bitwise AND with 0 (Clears register to $0\text{x0}$, sets $ZF$) |
| `0` | `11` | `1` | `ANDI dst, 1` | Bitwise AND with 1 (Isolates Bit 0) |
| `1` | `00` | `x` | `NOT dst` | Bitwise Invert via NMOS pull-down array |
| `1` | `01` | `x` | `SHR dst` | Logical Shift Right: $D_3 \leftarrow 0, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |
| `1` | `10` | `x` | `RCR dst` | Rotate Right thru Carry: $D_3 \leftarrow CF, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |
| `1` | `11` | `x` | `ASR dst` | Arithmetic Shift Right: $D_3 \leftarrow D_3, D_2 \leftarrow D_3, D_1 \leftarrow D_2, D_0 \leftarrow D_1$ ($CF \leftarrow D_0$) |

---

## 10. Hardware Vector Hijack Subsystem (Interrupt Engine)

```
  External I/O Cards
  assert ~IRQ (Pin 06) ──► [ Latch 1: IRQ_REQ ] ──┐
                                  ▲               │   T0 Strobe
                                  │               ├───────AND───────► Set HIJACK_RUN
                            Clear at T0 ──────────┴──────┐   (IE = 1)        Clear IRQ_REQ
                                                         ▼                   Clear IE
                           ┌─────────────────┐
                           │Latch 2: HIJACK  │ ─────────► Drives ~IR_DISABLE (Pin 05) LOW
                           └─────────────────┘
                                    ▲
                              Clear at T5

```

When `~IRQ` fires while $IE = 1$, the Interrupt Card forces `~IR_DISABLE` LOW at $T_0$, freezing program counter incrementing and executing a 6-step hardware vector hijack:

* **$T_0$ — Hijack Entry & Lock:** `~IR_DISABLE` asserts LOW, $PC$ auto-increment is disabled ($PC$ locked at $PC_{\text{orig}}$), $IE \leftarrow 0$, `IRQ_REQ` is cleared, and `HIJACK_RUN` is set.
* **$T_1$ — Push $PCL$:** Card drives $PCL_{\text{orig}}$ onto `BUS[3:0]` and asserts `~WE[7]` (`STK_PUSH`, $SP \leftarrow SP - 1$).
* **$T_2$ — Push $PCH$:** Card drives $PCH_{\text{orig}}$ onto `BUS[3:0]` and asserts `~WE[7]` (`STK_PUSH`, $SP \leftarrow SP - 1$).
* **$T_3$ — Load Vector Low:** Card drives the Hardware Vector Low nibble onto `BUS[3:0]` and asserts `~WE[6]` (`PCL_WRITE`).
* **$T_4$ — Load Vector High:** Card drives the Hardware Vector High nibble onto `BUS[3:0]` and asserts `~WE[5]` (`PCH_WRITE`).
* **$T_5$ — Release & Settle:** Card un-drives bus, clears `HIJACK_RUN`, and releases `~IR_DISABLE`. Fetch resumes at the ISR vector address at the next $T_0$.

---

## 11. Architectural Power-On Reset State Vector

Upon assertion of `~CYCLE_RESET` (Pin 04) LOW:

```
PCH:PCL      <- 0x00 (PCH = 0x0, PCL = 0x0)
SP           <- 0xF  (Top of internal hardware stack matrix)
ZF, CF       <- 0    (Flags cleared)
IE           <- 1    (Interrupts enabled by default)
HIJACK_RUN   <- 0    (Interrupt hijack inactive)
HALT_LATCH   <- 0    (Halt state cleared)
TIMING       <- T0   (State counter initialized to step 0)
RegA..RegD   <- Unspecified (Preserves power-up bistable state)

```
