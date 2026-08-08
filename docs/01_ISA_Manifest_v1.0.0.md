# μ-Core ISA Specification (v1.0.0)
**Status:** Frozen Reference Standard (Normative)

---

### 1. Purpose

μ-Core is a parameterized, technology-independent Instruction Set Architecture (ISA).

Its purpose is to be:
* **Understandable**
* **Modular**
* **Technology-independent**
* **Practical to build**
* **Scalable without sacrificing simplicity**

The architecture should be implementable using software emulation, microcontrollers, TTL/CMOS logic, discrete transistors, relay logic, or future technologies without changing the Instruction Set Architecture.

**The ISA defines the computer. The implementation is replaceable.**

---

### 2. Design Philosophy & Rationale

#### Architecture Before Implementation

The architecture exists independently of the hardware used to realize it.

```text
Applications
     │
Assembly / Software Toolchain
     │
Instruction Set Architecture (ISA v1.0.0)
     │
CPU Architecture (Execution Model)
     │
Functional Modules (Registers, ALU, Counters)
     │
Physical Implementation (TTL, Transistors, Emulation)

```

Each layer depends only upon the layer beneath it. Software should never need to change because the underlying hardware changes.

#### Core Principles

* **Modules before gates:** Built from reusable functional modules (Registers, Counters, Decoders, ALU) allowing hardware builders to swap individual boards without altering the rest of the machine.
* **Predictability before maximum efficiency:** Avoids variable-length instructions, complex multi-byte addressing modes, instruction-specific timing matrices, and deep decode logic. A completely uniform timing cycle ($T_0..T_3$) makes execution deterministic and simplifies debugging.
* **Explicit instruction semantics over hidden modal state:** Contains no hidden addressing-mode flags or persistent ALU mode registers. Each instruction explicitly determines its operation from its opcode and operand fields, combined with defined architectural state.

---

### 3. Parameterized Scaling Model (W)

A μ-Core implementation is defined by a fundamental **datapath width parameter W**, where $W ≥ 4$ and W is typically a power of 2:

| Architectural Property | Parameterized Definition | μ4 ($W=4$) | μ8 ($W=8$) | μ16 ($W=16$) |
| --- | --- | --- | --- | --- |
| **Register Width** | W bits | 4 bits | 8 bits | 16 bits |
| **Operand Width** | W bits | 4 bits | 8 bits | 16 bits |
| **Instruction Size** | $2W$ bits (Opcode + Operand) | 8 bits | 16 bits | 32 bits |
| **PC Addressing Unit** | W-bit storage units | Nibble | Byte | 16-bit Word |
| **Data Offset Pointer ($D$)** | W bits (2^W locations) | 16 nibbles | 256 bytes | 64 KiB |
| **Data Address Space ($C:D$)** | $2W$ bits (2^(2W) locations) | 256 nibbles | 64 KiB | 4 GiB |
| **Memory Page Size** | 2^W storage units | 16 nibbles | 256 bytes | 64 KiB |
| **Memory Page Count** | 2^W pages ($PR$) | 16 pages | 256 pages | 65,536 pages |
| **Indirect Sentinel (`MAX`)** | $2^W - 1$ (All 1s) | `0xF` | `$FF` | `$FFFF` |

The ISA rules, opcodes, and control semantics remain identical across all values of W.

---

### 4. Registers

#### Programmer-Visible Registers

Every μ-Core implementation defines four programmer-visible registers of width W:

| Register | ID (`[1:0]`) | Purpose |
| --- | --- | --- |
| **A** | `00` | Accumulator (Primary ALU destination & memory gateway) |
| **B** | `01` | Secondary Register (Implicit ALU source operand) |
| **C** | `10` | Data Page Selector (High Address / Data Page) |
| **D** | `11` | Data Offset Pointer (Low Address / Indirect Pointer) |

#### $C:D$ Logical Address Pair

Registers **`C`** and **`D`** form a $2W$-bit logical address pair ($C:D$):

$$\text{Logical Data Address} = (C × 2^W) + D$$

`C` selects the Data Page; `D` selects the offset within that page.

#### Special & Control Registers

* **Program Counter (PC):** W-bit register tracking execution location within the active Memory Page. PC addresses W-bit instruction-storage units; every 2-unit instruction advances PC by $2$.
* **Page Register (PR):** W-bit register holding the active Memory Page ID for execution domain switches.
* **Stack Pointer (SP):** Hidden W-bit register indexing the next physical array entry in the Hardware Stack ($0 ≤ SP < N$).
* **Logical Stack Depth Counter ($D_{stack}$):** Hidden counter tracking the active number of valid pushed frames ($0 ≤ D_{stack} ≤ N$).
* **FLAGS Register:** Contains condition flags: **Zero (ZF)** and **Carry (CF)**.

---

### 5. Memory Model & Three Independent Namespaces

μ-Core defines three strictly independent, non-overlapping memory namespaces:

```text
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│    INSTRUCTION SPACE    │ │       DATA SPACE        │ │     HARDWARE STACK      │
│      Addressed by       │ │      Addressed by       │ │      Addressed by       │
│       PR : PC           │ │      C : Offset / D     │ │        Hidden SP        │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘

```

1. **Instruction Space:** Addressed using $\text{PR} : \text{PC}$. Contains executable instructions.
2. **Data Space:** Addressed using $C : \text{Offset}$ or $C : D$. Accessed exclusively by `LOAD` and `STORE`.
3. **Hardware Stack:** Addressed internally by SP. Changing `PR` or `C` never affects stack contents.

---

### 6. Instruction Format & Opcode Encodings

Every instruction occupies $2W$ bits (Opcode W bits + Operand W bits):

```text
+────────────────────+────────────────────+
|  Opcode (W bits)   |  Operand (W bits)  |
+────────────────────+────────────────────+

```

#### Opcode Width Standard

The primary architectural opcode is strictly encoded in the **low 4 bits** (`bits [3:0]`) of the Opcode field. Bits `[W-1:4]` are reserved; software shall write them as zero, and execution logic shall ignore them.

#### Primary Opcode Table (4-bit Opcode Decoder)

| Opcode | Mnemonic | Primary Responsibility | Operand Layout |
| --- | --- | --- | --- |
| `0x0` | **NOP** | No Operation (Burns 4 phases, PC $←$ PC + 2) | Ignored |
| `0x1` | **MOV** | Register-to-register move | `[1:0]` = dst, `[3:2]` = src |
| `0x2` | **LOAD** | Read Data RAM into Accumulator $A$ | Direct offset or `MAX` for `[D]` |
| `0x3` | **STORE** | Write Accumulator $A$ to Data RAM | Direct offset or `MAX` for `[D]` |
| `0x4` | **ALU** | Execute arithmetic/logic on $A$ and $B$ | `[3:0]` = ALU sub-opcode |
| `0x5` | **JMP** | Unconditional local branch ($\text{PC} ← \text{Operand}$) | Target offset in current page |
| `0x6` | **JZ** | Branch if Zero flag set ($ZF = 1$) | Target offset in current page |
| `0x7` | **JC** | Branch if Carry flag set ($CF = 1$) | Target offset in current page |
| `0x8` | **CALL** | Local subroutine call (Pushes PC+2, $\text{PC} ← \text{Operand}$) | Target offset in current page |
| `0x9` | **RET** | Return from subroutine ($\text{PC} ← \text{Popped Stack}$) | Ignored |
| `0xA` | **PUSH** | Push register or FLAGS onto Hardware Stack | `[2:0]` = Target ID (`0`..`4`) |
| `0xB` | **POP** | Pop Hardware Stack into register or FLAGS | `[2:0]` = Target ID (`0`..`4`) |
| `0xC` | **IO** | Peripheral I/O transfer | `[2:0]` = Port ID, `[3]` = Dir ($0=\text{IN}, 1=\text{OUT}$) |
| `0xD` | **EXEC** | Transfer execution domain ($\text{PR} ← \text{Operand}, \text{PC} ← 0$) | Target Memory Page |
| `0xE` | **RSVD** | Reserved for extension | Reserved (Treat as NOP) |
| `0xF` | **HLT** | Halt processor execution | Ignored |

---

### 7. Explicit Operand Layout Encodings

#### MOV Operand Layout (`0x1`)

* `Bits [1:0]` = Source Register ID (`00`=A, `01`=B, `10`=C, `11`=D)
* `Bits [3:2]` = Destination Register ID (`00`=A, `01`=B, `10`=C, `11`=D)
* `Bits [W-1:4]` = Reserved (Ignored on read, software writes zero)

#### PUSH / POP Operand Layout (`0xA` / `0xB`)

* `Bits [2:0]` = Register / Special Target:
* `000` (`0`): Register A
* `001` (`1`): Register B
* `010` (`2`): Register C
* `011` (`3`): Register D
* `100` (`4`): FLAGS Register (ZF and CF)


* `Bits [W-1:3]` = Reserved (Ignored on read, software writes zero)

#### Peripheral IO Operand Layout (`0xC`)

* `Bits [2:0]` = Peripheral Port ID (`0` through `7`)
* `Bit [3]` = Transfer Direction:
* `0`: **INPUT** ($A ← \text{PORT}[ID]$) — Reads peripheral port into Accumulator $A$.
* `1`: **OUTPUT** ($\text{PORT}[ID] ← A$) — Writes Accumulator $A$ to peripheral port.


* `Bits [W-1:4]` = Reserved (Ignored on read, software writes zero)
* *I/O Transfers are synchronous and leave FLAGS ($ZF, CF$) unchanged. Unmapped ports return `0` on INPUT and ignore OUTPUT.*

#### Memory Addressing & The Indirect Sentinel (`MAX`)

For `LOAD` (`0x2`) and `STORE` (`0x3`):

* **Direct Mode ($\text{Operand} \neq \text{MAX}$):** Target Data Address = $C : \text{Operand}$.
* **Register-Indirect Mode ($\text{Operand} == \text{MAX}$):** Target Data Address = $C : D$.
*(Where $\text{MAX} = 2^W - 1$. To access direct offset $\text{MAX}$, set $D = \text{MAX}$ and use indirect mode).*

#### Reserved Opcodes & Bits Rule

* **Opcode `0xE` (RSVD):** Executing `0xE` acts as a NOP (advances PC by 2). Future ISA revisions may define non-NOP operations for `0xE`.
* **Reserved Bits:** Any unassigned operand bits are ignored by execution hardware. Software shall encode reserved bits as zero.

---

### 8. Definitive Flag Semantics & Pseudocode ALU Table

* **Zero Flag (ZF):** Set to `1` if the result of an operation is equal to `0`; otherwise cleared to `0`.
* **Carry Flag (CF):** Serves as **Carry Out** for addition/shifts and **No-Borrow** for subtraction ($CF = 1 \implies A_{orig} ≥ B$).
* **Flag Preservation Law:** Only instructions explicitly documented in the ALU Sub-Opcode Table (`0x4`) or `POP FLAGS` (`0xB 4`) may modify ZF or CF. All other instructions (`NOP`, `MOV`, `LOAD`, `STORE`, `JMP`, `JZ`, `JC`, `CALL`, `RET`, `PUSH`, `IO`, `EXEC`, `RSVD`, `HLT`) leave both ZF and CF strictly unchanged.

$$\text{Borrow} = \text{NOT}(CF) \quad \implies \quad \text{SBB Subtracts Borrow} = (1 - CF)$$

Let $A_{orig}$ denote the initial value of Accumulator $A$ prior to instruction execution:

| Sub-Opcode | Mnemonic | Operational Pseudocode | ZF | CF |
| --- | --- | --- | --- | --- |
| `0x0` | **ADD** | $\text{Temp} ← A_{orig} + B; \ A ← \text{Temp}[W-1:0]$ | $\text{Temp} == 0$ | $\text{Temp} ≥ 2^W$ |
| `0x1` | **SUB** | $\text{Temp} ← A_{orig} - B; \ A ← \text{Temp}[W-1:0]$ | $\text{Temp} == 0$ | $A_{orig} ≥ B$ (No-Borrow) |
| `0x2` | **ADC** | $\text{Temp} ← A_{orig} + B + CF; \ A ← \text{Temp}[W-1:0]$ | $\text{Temp} == 0$ | $\text{Temp} ≥ 2^W$ |
| `0x3` | **SBB** | $\text{Temp} ← A_{orig} - B - (1 - CF); \ A ← \text{Temp}[W-1:0]$ | $\text{Temp} == 0$ | $A_{orig} ≥ (B + (1 - CF))$ |
| `0x4` | **AND** | $A ← A_{orig} ∧ B$ | $A == 0$ | Unchanged |
| `0x5` | **OR** | $A ← A_{orig} ∨ B$ | $A == 0$ | Unchanged |
| `0x6` | **XOR** | $A ← A_{orig} ⊕ B$ | $A == 0$ | Unchanged |
| `0x7` | **NOT** | $A ← ¬ A_{orig}$ | $A == 0$ | Unchanged |
| `0x8` | **INC** | $A ← A_{orig} + 1$ | $A == 0$ | **Unchanged** |
| `0x9` | **DEC** | $A ← A_{orig} - 1$ | $A == 0$ | **Unchanged** |
| `0xA` | **SHL** | $\text{oldCF} ← A_{orig}[W-1]; \ A ← (A_{orig} \ll 1); \ CF ← \text{oldCF}$ | $A == 0$ | Shifted-out MSB |
| `0xB` | **SHR** | $\text{oldCF} ← A_{orig}[0]; \ A ← (A_{orig} \gg 1); \ CF ← \text{oldCF}$ | $A == 0$ | Shifted-out LSB |
| `0xC` | **ROL** | $\text{oldCF} ← CF; \ CF ← A_{orig}[W-1]; \ A ← (A_{orig} \ll 1) \mid \text{oldCF}$ | $A == 0$ | Shifted-out MSB |
| `0xD` | **ROR** | $\text{oldCF} ← CF; \ CF ← A_{orig}[0]; \ A ← (A_{orig} \gg 1) \mid (\text{oldCF} \ll (W-1))$ | $A == 0$ | Shifted-out LSB |
| `0xE` | **CMP** | $\text{Temp} ← A_{orig} - B$ (Flags updated, $A$ unchanged) | $A_{orig} == B$ | $A_{orig} ≥ B$ (No-Borrow) |
| `0xF` | **TST** | Test $A_{orig}$ ($ZF ← (A_{orig} == 0)$, $A$ unchanged) | $A_{orig} == 0$ | Unchanged |

*Note: `INC` and `DEC` modify ZF but leave CF untouched, preserving carry chains in multi-precision arithmetic loops.*

---

### 9. Control Flow & Program Counter Precedence Rules

#### Conceptual Execution Phases

Every instruction consists of four architectural sequencing phases:

* **T0 (Fetch Opcode):** Fetch opcode at current $\text{PC}$.
* **T1 (Fetch Operand):** Fetch operand at $\text{PC} + 1$.
* **T2 (Execute & Evaluate Next PC):** Execute operation and calculate potential next $\text{PC}$.
* **T3 (Write-Back & Commit PC):** Commit results and finalize committed $\text{PC}$.

#### Program Counter (PC) Update Precedence

At $T_2$, the sequential next address is calculated as:

$$\text{PC}_{seq} = (\text{PC} + 2) \bmod 2^W$$

At $T_3$, the committed $\text{PC}$ value is determined strictly by instruction classification:

1. **Ordinary Instructions (`NOP`, `MOV`, `LOAD`, `STORE`, `ALU`, `PUSH`, `POP`, `IO`, `RSVD`):** $\text{PC} ← \text{PC}_{seq}$.
2. **Unconditional Branch (`JMP $target`):** $\text{PC} ← \text{Operand}$.
3. **Conditional Branch (`JZ $target` / `JC $target`):**
* If condition met ($ZF=1$ for `JZ`, $CF=1$ for `JC`): $\text{PC} ← \text{Operand}$.
* If condition not met: $\text{PC} ← \text{PC}_{seq}$.


4. **Subroutine Call (`CALL $target`):** Pushes $\text{PC}_{seq}$ onto Hardware Stack, then $\text{PC} ← \text{Operand}$.
5. **Subroutine Return (`RET`):** Pops address from Hardware Stack into $\text{PC}$.
6. **Domain Switch (`EXEC $page`):** $\text{PR} ← \text{Operand}$, then $\text{PC} ← 0×00$. *(Leaves SP, $D_{stack}$, $FLAGS$, and programmer registers $A, B, C, D$ unchanged).*
7. **Processor Halt (`HLT`):** $\text{PC}$ remains unchanged at the current instruction address; execution enters the **HALTED** state. While in the HALTED state, execution clock phases $T_0..T_3$ freeze, and no instruction fetching or state modification occurs until an external hardware `RESET` is received.

#### Hardware Reset

A hardware `RESET` signal forces:

$$\text{PR} ← 0 \quad \mid \quad \text{PC} ← 0 \quad \mid \quad \text{SP} ← 0 \quad \mid \quad D_{stack} ← 0$$

Execution begins immediately at address $0×00$ of Memory Page 0 (**Reset Page**).

---

### 10. Hardware Stack Specification & Circular Overwrite Rules

The Hardware Stack is defined as a W-bit wide, $N$-entry LIFO buffer ($1 ≤ N ≤ 2^W$) managed by physical index SP ($0 ≤ SP < N$) and logical depth counter $D_{stack}$ ($0 ≤ D_{stack} ≤ N$):

* **Stack Pointer Reset:** Hardware `RESET` initializes $D_{stack} ← 0$ and $SP ← 0$.
* **PUSH Operation:**
* Write value to physical entry $\text{Stack}[SP]$.
* Increment index $SP ← (SP + 1) \bmod N$.
* If $D_{stack} < N$: Increment $D_{stack} ← D_{stack} + 1$.
* If $D_{stack} == N$ (Stack Full): $D_{stack}$ remains $N$ (the write overwrites the oldest historical entry in the circular buffer).


* **POP Operation:**
* If $D_{stack} > 0$: Set index $SP ← (SP - 1 + N) \bmod N$, decrement $D_{stack} ← D_{stack} - 1$, and return value at $\text{Stack}[SP]$.
* If $D_{stack} == 0$ (Stack Empty / Underflow): Return `0` (all bits zero); SP and $D_{stack}$ remain $0$.



---

### 11. Reference Targets

#### Minimal Target (μ4 Target, $W=4$)

* 4-bit datapath, registers, operands, and memory paging.
* $2^4 = 16$ nibbles per Memory Page; $C:D$ gives 256 nibble data space.
* Indirect sentinel = `0xF`. 4-entry Hardware Stack ($N=4$).

#### Canonical Reference Target (μ8 Target, $W=8$)

* 8-bit datapath, registers, operands, and memory paging.
* $2^8 = 256$ bytes per Memory Page; $C:D$ gives 64 KiB data space.
* Indirect sentinel = `$FF`. 16-entry Hardware Stack ($N=16$).

---

### 12. The μ-Core Principle

A computer architecture should survive changes in technology.

A program written for μ-Core should execute on an emulator, a TTL computer, a discrete transistor machine, or a relay computer without modification.

**Hardware evolves. Implementations change. The architecture endures.**

```
