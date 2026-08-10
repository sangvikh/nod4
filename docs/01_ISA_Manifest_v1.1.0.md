### μ-Core at a Glance

```text
================================================================================
                       μ-CORE ISA AT A GLANCE (v1.1.0)
================================================================================
Parameters:          W >= 4 (Datapath width in bits; typical W in {4, 8, 16, 32, 64})
Storage Unit (SU):   W bits (Instruction size = 2 SU = 2W bits)
Registers:           A (00), B (01), C (10), D (11) -- all W bits wide
Special Registers:   PR (Page), PC (Program Counter), SP (Stack Pointer), FLAGS (ZF, CF)

Instruction Word:    [ Opcode Field: W bits ] [ Operand Field: W bits ]
Primary Opcode:      Opcode Field bits [3:0] (bits [W-1:4] reserved, written as 0)

Memory Namespaces:   1. Instruction Space : Addressed by PR:PC (2W bits, continuous)
                     2. Data Space        : Addressed by C:Offset or C:D (2W bits)
                     3. Hardware Stack    : Addressed by SP (Hidden LIFO array)

Addressing Modes:    DIRECT   (operand != MAX) => Address = C : operand
                     EXTENDED (operand == MAX) => Address = C : D  [Escape Sentinel]

Execution Timing:    4 Architectural Phases: T0 (Opcode Fetch), T1 (Operand Fetch),
                                            T2 (Snapshot & Exec), T3 (Commit)

Primary Opcodes:     0: NOP      4: ALU      8: CALL     C: IO
                     1: MOV      5: JMP      9: RET      D: RSVD1 (NOP)
                     2: LOAD     6: JZ       A: PUSH     E: RSVD2 (NOP)
                     3: STORE    7: JC       B: POP      F: HLT

ALU Sub-Opcodes:     0: ADD  1: SUB  2: ADC  3: SBB  4: AND  5: OR   6: XOR  7: NOT
                     8: INC  9: DEC  A: SHL  B: SHR  C: ROL  D: ROR  E: CMP  F: TST

Flag Laws:           CF = 1 for SUB/SBB/CMP denotes NO BORROW (A >= Subtrahend).
                     INC/DEC modify ZF but PRESERVE CF.
                     Non-ALU ops (LOAD, STORE, MOV, IO, Branches) PRESERVE FLAGS.

Stack Laws:          N-entry circular LIFO (N <= 2^W). Full stack PUSH overwrites oldest.
                     Empty stack POP/RET returns 0. CALL/RET are strictly page-local.
================================================================================

```

---

# μ-Core ISA Specification (v1.1.0)

> **Status:** Frozen Reference Standard (Normative)
> **Target Widths:** μ4, μ8, μ16, μ32, μ64
> **Author:** Harald Sangvik
> **License:** MIT

---

### 1. Purpose & Canonical Machine State Tuple

μ-Core is a parameterized, technology-independent Instruction Set Architecture (ISA).

**The ISA defines the computer. The implementation is replaceable.**

#### Canonical Machine State Tuple ($\text{STATE}$)

A conforming μ-Core execution unit is formally defined by its architectural state tuple:

$$\text{STATE} = \langle A, B, C, D, \text{PC}, \text{PR}, \text{FLAGS}, SP, D_{stack}, \text{Stack}[], \text{CPU\_State} \rangle$$

Where $\text{FLAGS} \equiv \langle ZF, CF \rangle$ and $\text{CPU\_State} \in \{\text{NORMAL}, \text{HALTED}\}$.

Operating on three isolated architectural namespaces:

$$\text{NAMESPACES} = \langle \text{InstructionSpace}[], \text{DataSpace}[], \text{Ports}[] \rangle$$

---

### 2. Design Philosophy, Conformance Taxonomy & Normative Precedence

#### Core Design Principles

* **Modules before gates:** Reusable functional modules allow hardware builders to swap individual boards without altering software semantics.
* **Datapath simplicity over defensive hardware:** Hardware implements direct, deterministic state changes without parity checkers, target validation stages, or exception machinery.
* **Concept Isolation Principle:** Architectural state variables remain strictly independent when the concepts they represent are independent ($PR:\text{PC}$ for execution position, $C:D$ for data access, $SP$ for stack indexing).
* **Software Invariant Principle:** Hardware does not validate architectural software invariants. Encoding semantics are mandatory hardware obligations; program-state invariants are software responsibilities.
* **Minimalist Orthogonality & Deliberate Trade-offs:** The ISA omits immediate-mode arithmetic and multi-register indirect addressing to keep instruction decoders trivial. Constants are loaded from Data Space or synthesized via register ops. `CALL`/`RET` are intentionally page-local to avoid widening the hardware stack; cross-page control transfers use `JMP MAX`.

#### Conformance Specification Taxonomy

1. **Architecturally Defined:** Mandatory, deterministic behavior that shall be identically produced by every conforming implementation.
2. **Implementation-Defined:** Behavior that physical hardware chooses and shall explicitly declare and document in its technical specification.
3. **Unspecified:** Behavior where multiple physical outcomes are permitted and the implementation is not required to document which occurs.
4. **Architecturally Invalid:** Execution sequences forbidden by software invariants. Conforming software shall not generate these sequences. Physical hardware is not required to trap these operations; its physical behavior upon encountering them is *Implementation-Defined*.

#### Normative Precedence Rule

In the event of discrepancy between sections of this standard, the order of precedence is:

1. **Normative Prose & Formal Equations (§1 through §10, §13)**
2. **Normative Executable Reference Model (§11)**
3. **Canonical Conformance Litmus Tests (§12)**

---

### 3. Parameterized Scaling Model ($W$) & Storage Units

A μ-Core implementation is defined by a fundamental **datapath width parameter $W$**, where $W \ge 4$ ($W=4$ is the minimum bound required to accommodate all 16 primary opcodes; $W$ need not be a power of two, though power-of-two widths are recommended).

#### Storage Unit ($\text{SU}$) & Instruction Structure

* **Storage Unit ($\text{SU}$):** The fundamental unit of memory storage and addressing, defined as exactly $W$ bits. The term "Word" shall not be used as an architectural unit.
* **Instruction Layout:** Every instruction occupies exactly $2\text{ SU}$ ($2W$ bits), split into two physical $W$-bit fields:
1. **Opcode Field ($W$ bits):** The first $W$-bit storage unit of the instruction.
2. **Operand Field ($W$ bits):** The second $W$-bit storage unit of the instruction.



| Architectural Property | Parameterized Definition | μ4 ($W=4$) | μ8 ($W=8$) | μ16 ($W=16$) |
| --- | --- | --- | --- | --- |
| **Datapath & Register Width** | $W$ bits | 4 bits | 8 bits | 16 bits |
| **Instruction Size** | $2\text{ SU} = 2W$ bits | 8 bits (2 nibbles) | 16 bits (2 bytes) | 32 bits ($2 \times 16$-bit $\text{SU}$) |
| **Program Counter Unit** | Indexes $W$-bit storage units | Nibbles | Bytes | 16-bit Storage Units |
| **Low Address Pointer ($D$)** | $W$ bits ($2^W$ locations) | 16 nibbles | 256 bytes | 64 KiB |
| **Extended Address Space ($C:D$)** | $2W$ bits ($2^{2W}$ locations) | 256 nibbles | 64 KiB | 4 GiB |
| **Memory Page Size** | $2^W$ storage units | 16 nibbles | 256 bytes | 64 KiB |
| **Memory Page Count** | $2^W$ pages ($PR$) | 16 pages | 256 pages | 65,536 pages |
| **Override Sentinel (`MAX`)** | $2^W - 1$ (All 1s / Odd) | `0xF` | `$FF` | `$FFFF` |

#### Global Reserved-Bit & Noncanonical Encoding Rule

Execution hardware shall strictly decode **`bits [3:0]` of the Opcode Field** as the primary opcode. Conforming software shall write `bits [W-1:4]` of the Opcode Field and all unused upper bits `[W-1:k]` of the Operand Field as zero. Non-zero values in reserved bit fields constitute a noncanonical encoding; execution hardware shall ignore reserved bits during decoding and execution.

---

### 4. Registers & Processor States

#### Programmer-Visible Registers

Every μ-Core implementation defines four programmer-visible registers of width $W$:

| Register | ID (`[1:0]`) | Purpose |
| --- | --- | --- |
| **A** | `00` | Accumulator (Primary ALU destination & memory gateway) |
| **B** | `01` | Secondary Register (Implicit ALU source operand) |
| **C** | `10` | High Address Register / Page Selector |
| **D** | `11` | Low Address Register / Offset Pointer |

#### Extended Address Pair ($C:D$)

`C` and `D` form the primary $2W$-bit Extended Address Pair ($C:D$):


$$\text{Extended Address} = (C \times 2^W) + D$$

#### Special Control Registers

* **Program Counter ($\text{PC}$):** $W$-bit register tracking execution location within active Page $PR$. $\text{PC}$ addresses $W$-bit storage units; every 2-unit instruction advances $\text{PC}$ by 2.
* **Page Register ($\text{PR}$):** $W$-bit register holding the active Memory Page ID for instruction execution.
* **Auto Page-Increment Cascade ($PR:\text{PC}$):** $PR$ and $\text{PC}$ form a combined $2W$-bit synchronous instruction counter pair $PR:\text{PC}$. Sequential execution automatically ripples the overflow carry from $\text{PC}$ into $PR$.
* **Stack Pointer ($\text{SP}$):** Hidden logical integer index $SP \in [0, N-1]$ tracking the next physical write slot in the Hardware Stack. Physical register width is implementation-defined ($\lceil \log_2 N \rceil$ bits up to $W$ bits).
* **Logical Stack Depth Counter ($D_{stack}$):** Hidden logical integer counter $D_{stack} \in [0, N]$ tracking active pushed frames.
* **FLAGS Register:** Contains condition flags: **Zero (ZF)** and **Carry (CF)** ($\text{FLAGS} \equiv \langle ZF, CF \rangle$).

#### Processor Execution States & Hardware Reset Behavior

Physical execution states are **`NORMAL`** and **`HALTED`** (entered via `HLT` (`0xF`)). During `HALTED` state, architectural clock phases freeze; no instruction fetches, reads, writes, or register updates occur. External peripheral I/O behavior during `HALTED` state is implementation-defined.

A hardware `RESET` signal is an external architectural event. Electrical timing, active levels, and synchronization machinery of `RESET` are implementation-defined. `RESET` transitions processor state from either **`NORMAL`** or **`HALTED`** to **`NORMAL`**, establishing control state:

$$PR \leftarrow 0 \quad \mid \quad \text{PC} \leftarrow 0 \quad \mid \quad SP \leftarrow 0 \quad \mid \quad D_{stack} \leftarrow 0 \quad \mid \quad \text{CPU\_State} \leftarrow \text{NORMAL}$$

After `RESET` establishes control state, the next instruction execution cycle begins at Phase $T_0$ from address $PR:\text{PC} = 0:0$. `RESET` does not modify Instruction Space, Data Space, or Hardware Stack storage contents, nor does it guarantee clearing registers $A, B, C, D,$ or $FLAGS$ (their post-reset values are implementation-defined).

---

### 5. Memory Model & Three Independent Namespaces

μ-Core defines three strictly independent, non-overlapping memory namespaces:

```text
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│    INSTRUCTION SPACE    │ │       DATA SPACE        │ │     HARDWARE STACK      │
│      Addressed by       │ │      Addressed by       │ │      Addressed by       │
│   PR : PC (Continuous)  │ │      C : Offset / D     │ │        Hidden SP        │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘

```

1. **Instruction Space:** Addressed strictly using $PR : \text{PC}$. Contains executable instructions. Instruction Space mutability is an implementation property; the base ISA provides no architectural operation for modifying Instruction Space.
2. **Data Space:** Addressed strictly using $C : \text{Offset}$ or $C : D$. Accessed exclusively by `LOAD` and `STORE`.
3. **Hardware Stack:** Addressed internally by $\text{SP}$. Changing $PR$ or $C$ never affects stack contents.

*Architectural Isolation Rule:* Instruction Space, Data Space, and Hardware Stack are logically distinct. An implementation shall not expose one namespace through another even if physical storage media is shared.

---

### 6. Four-Phase Execution Model ($T_0..T_3$), Snapshots & Side-Effect Timing

#### The Architectural Four-Phase Model ($T_0..T_3$)

Every instruction executes across four ordered architectural phases in the reference execution model. An implementation may realize these phases using different physical timing (e.g., pipelining), provided the externally observable architectural behavior is identical:

* **Phase $T_0$ (Instruction Fetch):** Fetch Opcode Field from Instruction Space at address $PR:\text{PC}$.
* **Phase $T_1$ (Operand Fetch):** Fetch Operand Field from Instruction Space at address $PR:(\text{PC} + 1)$.
* **Phase $T_2$ (Execution & Snapshot):** Atomically sample execution register snapshot variables and external I/O values:

$$\text{SNAPSHOT} = \langle A_{orig}, B_{orig}, C_{orig}, D_{orig}, ZF_{orig}, CF_{orig}, PR_{orig}, \text{PC}_{orig}, SP_{orig}, D_{stack\_orig}, \text{PORT}_{orig} \rangle$$



Evaluate ALU operations, branch conditions, or perform reads (`LOAD`, `POP`, `IO IN`).
* **Phase $T_3$ (Architectural Commit):** Commit updated register variables and write side-effects simultaneously to architectural state. No instruction may observe its own $T_3$ commit results during $T_0/T_1$ of the same instruction.

#### Phase Execution & Side-Effect Timing Table

| Operation | Phase $T_0..T_1$ | Phase $T_2$ (Execution & Read) | Phase $T_3$ (Commit & Write) |
| --- | --- | --- | --- |
| **`LOAD`** | Fetch instruction | Read Data Space at $C_{orig}:\text{target}$ | Commit value to Accumulator $A$, advance $PR:\text{PC}$ |
| **`STORE`** | Fetch instruction | Sample $A_{orig}$ and target address | Commit write of $A_{orig}$ to Data Space at $C_{orig}:\text{target}$, advance $PR:\text{PC}$ |
| **`PUSH`** | Fetch instruction | Sample target register value | Commit value to $\text{Stack}[SP_{orig}]$, commit $SP, D_{stack}$, advance $PR:\text{PC}$ |
| **`POP`** | Fetch instruction | Read value from $\text{Stack}[(SP_{orig}-1+N) \bmod N]$ | Commit value to target register, commit $SP, D_{stack}$, advance $PR:\text{PC}$ |
| **`IO IN`** | Fetch instruction | Sample external `PORT[ID]` into $\text{PORT}_{orig}$ | Commit input value $\text{PORT}_{orig}$ to Accumulator $A$, advance $PR:\text{PC}$ |
| **`IO OUT`** | Fetch instruction | Sample $A_{orig}$ | Drive output value $A_{orig}$ to external `PORT[ID]`, advance $PR:\text{PC}$ |

#### Canonical PC Advancement Equations

At Phase $T_2$, sequential candidate address pair $(PR_{seq}, \text{PC}_{seq})$ is evaluated according to the single authoritative equation:


$$(PR \times 2^W + \text{PC})_{seq} = (PR \times 2^W + \text{PC} + 2) \bmod 2^{2W}$$

Equivalently, split into register components where $\text{PC}_{raw} = \text{PC} + 2$:


$$\text{PC}_{seq} = \text{PC}_{raw} \bmod 2^W, \quad PR_{seq} = \begin{cases} (PR + 1) \bmod 2^W & \text{if } \text{PC}_{raw} \ge 2^W \\ PR & \text{if } \text{PC}_{raw} < 2^W \end{cases}$$

#### Alignment Invariants & Terminal Address Space Boundary

* **Alignment Invariant:** All valid instruction addresses are even ($\text{PC} \pmod 2 == 0$). Conforming software shall ensure all direct control-flow targets (`JMP`, `JZ`, `JC`, `CALL`) and return addresses loaded into $\text{PC}$ via `RET` are even.
* **Terminal Address Space Boundary Rule:** The final valid instruction address in the entire $PR:\text{PC}$ space is $PR = \text{MAX}, \text{PC} = \text{MAX} - 3$. Sequential execution from that address produces the odd address $PR = \text{MAX}, \text{PC} = \text{MAX} - 1$. Conforming software shall not execute sequentially through the end of the address space without explicitly transferring control elsewhere.

---

### 7. Primary Opcode Table, Extended Address Escape, & Address Functions

#### Primary Opcode Table (4-bit Opcode Decoder)

| Opcode | Mnemonic | Primary Responsibility | Operand Field Sub-Layout |
| --- | --- | --- | --- |
| `0x0` | **NOP** | No Operation (Burns 4 phases, advances $PR:\text{PC}$) | Reserved (`[W-1:0]` = 0) |
| `0x1` | **MOV** | Register-to-register move | `[1:0]` = dst, `[3:2]` = src, `[W-1:4]` = 0 |
| `0x2` | **LOAD** | Read Data Space into Accumulator A | Direct offset or `MAX` for `[C:D]` |
| `0x3` | **STORE** | Write Accumulator A to Data Space | Direct offset or `MAX` for `[C:D]` |
| `0x4` | **ALU** | Execute arithmetic/logic on A and B | `[3:0]` = sub-opcode, `[W-1:4]` = 0 |
| `0x5` | **JMP** | Branch unconditional (Local or Far Jump) | Target offset or `MAX` for `[C:D]` |
| `0x6` | **JZ** | Branch if Zero flag set ($ZF_{orig} = 1$) (Local or Far Jump) | Target offset or `MAX` for `[C:D]` |
| `0x7` | **JC** | Branch if Carry flag set ($CF_{orig} = 1$) (Local or Far Jump) | Target offset or `MAX` for `[C:D]` |
| `0x8` | **CALL** | Page-local subroutine call (Pushes $\text{PC}_{seq}$, $\text{PC} \leftarrow \text{Operand}$) | Page-local target offset |
| `0x9` | **RET** | Return from page-local subroutine ($\text{PC} \leftarrow \text{Popped Stack}$) | Reserved (`[W-1:0]` = 0) |
| `0xA` | **PUSH** | Push register or FLAGS onto Hardware Stack | `[2:0]` = Target ID, `[W-1:3]` = 0 |
| `0xB` | **POP** | Pop Hardware Stack into register or FLAGS | `[2:0]` = Target ID, `[W-1:3]` = 0 |
| `0xC` | **IO** | Peripheral I/O transfer ($W$-bit transfer) | `[2:0]` = Port ID, `[3]` = Dir, `[W-1:4]` = 0 |
| `0xD` | **RSVD1** | Reserved opcode (Treat strictly as NOP) | Reserved (`[W-1:0]` = 0) |
| `0xE` | **RSVD2** | Reserved opcode (Treat strictly as NOP) | Reserved (`[W-1:0]` = 0) |
| `0xF` | **HLT** | Halt processor execution | Reserved (`[W-1:0]` = 0) |

#### PUSH / POP Operand Layout (`0xA` / `0xB`) & Reserved Target IDs

* `Bits [2:0]` Target ID Mapping: `000`=A, `001`=B, `010`=C, `011`=D, `100`=FLAGS, `101`..`111`=Reserved.
* **Reserved Target ID Rule:** Conforming software shall not encode Target IDs `5`, `6`, or `7`. Hardware shall treat `PUSH` or `POP` with a Reserved Target ID as a NOP (advancing $PR:\text{PC}$ without modifying registers, `SP`, or $D_{stack}$).
* **FLAGS Format on Stack:** `Bit [0]` = $ZF$, `Bit [1]` = $CF$, `Bits [W-1:2]` = 0.
* **`POP FLAGS` Execution Rule:** `POP FLAGS` updates $ZF \leftarrow \text{popped}[0]$ and $CF \leftarrow \text{popped}[1]$. POP FLAGS does not require reserved bits `[W-1:2]` of the popped value to be zero; unused upper bits are ignored and not retained.

#### Peripheral IO Operand Layout (`0xC`) & Contract

* `Bits [2:0]` = Port ID (`0`..`7`); `Bit [3]` = Direction (`0`=INPUT, `1`=OUTPUT).
* The architectural port namespace contains exactly 8 IDs (`0`..`7`). `IO` operations leave $FLAGS$ ($ZF, CF$) strictly unchanged. Reading an unimplemented port returns `0` (all bits zero); writing to an unimplemented port is ignored.

#### Reserved Opcodes `RSVD1` (`0xD`) & `RSVD2` (`0xE`) Rule

`RSVD1` and `RSVD2` behave strictly as NOPs (advancing $PR:\text{PC}$ by 2) regardless of Operand Field contents.

#### Extended Address Escape Sentinel (`MAX`) & Address Functions

The sentinel value $\text{MAX} = 2^W - 1$ is an extended-address escape override for `LOAD`, `STORE`, `JMP`, `JZ`, and `JC`. The direct-offset encoding domain is $[0, \text{MAX}-1]$; $\text{MAX}$ is exclusively the escape encoding. To access Data Space address $C:\text{MAX}$, software shall set $D = \text{MAX}$ and invoke `LOAD MAX` or `STORE MAX`:

$$\text{DIRECT}(\text{operand}) \equiv C_{orig} : \text{operand} \quad (\text{for } \text{operand} \neq \text{MAX})$$

$$\text{EXTENDED}(C, D) \equiv C_{orig} : D_{orig} \quad (\text{for } \text{operand} == \text{MAX})$$

$$\text{Effective Address}(\text{operand}) = \begin{cases} \text{DIRECT}(\text{operand}) & \text{if } \text{operand} \neq \text{MAX} \\ \text{EXTENDED}(C, D) & \text{if } \text{operand} == \text{MAX} \end{cases}$$

#### Page-Local Subroutine Constraint (`CALL` / `RET`)

* **Page-Local Invariant:** `CALL` and `RET` are page-local. `CALL` pushes $W$-bit $\text{PC}_{seq}$ onto the Hardware Stack and sets $\text{PC} \leftarrow \text{Operand}$ ($PR$ unchanged). `RET` performs a specialized stack-pop operation directly into $\text{PC}$ ($\text{PC} \leftarrow \text{Popped Stack}$), preserving $PR$. Software shall not modify $PR$ between `CALL` and its corresponding `RET`. The Hardware Stack is untyped; software is solely responsible for preserving return-address entries across subroutine execution.
* **CALL Validity Rule:** A `CALL` instruction is architecturally valid iff $PR_{seq} == PR_{orig}$ ($\text{PC}_{orig} + 2 < 2^W$). Executing `CALL` when $PR_{seq} \neq PR_{orig}$ ($\text{PC}_{orig} = 2^W - 2$) is an *Architecturally Invalid Operation*.

---

### 8. Definitive Flag Semantics & Functional ALU Contract

#### Subtraction Carry Convention & Precision Rules

* **Mathematical Operations:** Unless otherwise stated, all register arithmetic, comparisons, shifts, and addresses are unsigned modulo-$2^W$ operations.
* **Subtraction Carry Convention:** For subtraction-class operations (`SUB`, `SBB`, `CMP`), $CF=1$ indicates no borrow ($A_{orig} \ge \text{Subtrahend}$); $CF=0$ indicates borrow required ($A_{orig} < \text{Subtrahend}$).
* **`SBB` Intermediate Precision Rule:** Subtrahend $S = B + (1 - CF_{orig})$ shall be evaluated as an unsigned mathematical value with at least $W+1$ bits of precision prior to subtraction and borrow evaluation.
* **Rotate Operations:** `ROL` and `ROR` perform a $(W+1)$-bit rotate through the carry flag:

$$\text{ROL}: \{CF', A'\} = \{A_{orig}[W-1], A_{orig}[W-2:0], CF_{orig}\}$$


$$\text{ROR}: \{A', CF'\} = \{CF_{orig}, A_{orig}[W-1:1], A_{orig}[0]\}$$



Procedural evaluation:

$$\text{ROL} \implies \text{old\_cf} = CF_{orig}, \quad CF \leftarrow A_{orig}[W-1], \quad A \leftarrow ((A_{orig} \ll 1) \lor \text{old\_cf}) \bmod 2^W$$


$$\text{ROR} \implies \text{old\_cf} = CF_{orig}, \quad CF \leftarrow A_{orig}[0], \quad A \leftarrow \lfloor A_{orig} / 2 \rfloor \lor (\text{old\_cf} \ll (W-1))$$


* **Flag Preservation Law:** Only ALU operations and `POP FLAGS` modify $FLAGS$. `INC` and `DEC` update $ZF$ but leave $CF$ unchanged. `CMP` modifies both $ZF$ and $CF$ leaving $A$ unchanged. `TST` modifies $ZF$ leaving $CF$ and $A$ unchanged. Non-ALU instructions (`MOV`, `LOAD`, `STORE`, `JMP`, `JZ`, `JC`, `CALL`, `RET`, `PUSH`, `IO`, `NOP`, `HLT`) leave $FLAGS$ strictly unchanged.

| Sub-Opcode | Mnemonic | Operational Pseudocode | Zero Flag (ZF) | Carry Flag (CF) |
| --- | --- | --- | --- | --- |
| `0x0` | **ADD** | $T \leftarrow A_{orig} + B;$ $A \leftarrow T \bmod 2^W$ | $A == 0$ | $T \ge 2^W$ |
| `0x1` | **SUB** | $S = B;$ $A \leftarrow (A_{orig} - S + 2^W) \bmod 2^W$ | $A == 0$ | $A_{orig} \ge S$ *(1=No Borrow)* |
| `0x2` | **ADC** | $T \leftarrow A_{orig} + B + CF_{orig};$ $A \leftarrow T \bmod 2^W$ | $A == 0$ | $T \ge 2^W$ |
| `0x3` | **SBB** | $S = B + (1 - CF_{orig});$ $A \leftarrow (A_{orig} - S + 2^{W+1}) \bmod 2^W$ | $A == 0$ | $A_{orig} \ge S$ *(1=No Borrow)* |
| `0x4` | **AND** | $A \leftarrow A_{orig} \land B$ | $A == 0$ | Unchanged |
| `0x5` | **OR** | $A \leftarrow A_{orig} \lor B$ | $A == 0$ | Unchanged |
| `0x6` | **XOR** | $A \leftarrow A_{orig} \oplus B$ | $A == 0$ | Unchanged |
| `0x7` | **NOT** | $A \leftarrow (\neg A_{orig}) \bmod 2^W$ | $A == 0$ | Unchanged |
| `0x8` | **INC** | $A \leftarrow (A_{orig} + 1) \bmod 2^W$ | $A == 0$ | Unchanged |
| `0x9` | **DEC** | $A \leftarrow (A_{orig} - 1 + 2^W) \bmod 2^W$ | $A == 0$ | Unchanged |
| `0xA` | **SHL** | $A \leftarrow (A_{orig} \ll 1) \bmod 2^W$ | $A == 0$ | $A_{orig}[W-1]$ |
| `0xB` | **SHR** | $A \leftarrow \lfloor A_{orig} / 2 \rfloor$ | $A == 0$ | $A_{orig}[0]$ |
| `0xC` | **ROL** | See formal $(W+1)$-bit bit vector equations above | $A == 0$ | $A_{orig}[W-1]$ |
| `0xD` | **ROR** | See formal $(W+1)$-bit bit vector equations above | $A == 0$ | $A_{orig}[0]$ |
| `0xE` | **CMP** | $S = B;$ *(A unchanged)* | $A_{orig} == S$ | $A_{orig} \ge S$ *(1=No Borrow)* |
| `0xF` | **TST** | Test $A_{orig}$ *(A unchanged)* | $A_{orig} == 0$ | Unchanged |

---

### 9. Control Flow & Program Counter Precedence Rules

At Phase $T_3$, committed address pairs are finalized by instruction type:

1. **Ordinary Instructions (`NOP`, `MOV`, `LOAD`, `STORE`, `ALU`, `PUSH`, `POP`, `IO`, `RSVD1`, `RSVD2`):**

$$PR \leftarrow PR_{seq}, \quad \text{PC} \leftarrow \text{PC}_{seq}$$


2. **Unconditional Branch (`JMP`):**
* $\text{Operand} \neq \text{MAX}$: $PR \leftarrow PR, \quad \text{PC} \leftarrow \text{Operand}$.
* $\text{Operand} == \text{MAX}$: $PR \leftarrow C_{orig}, \quad \text{PC} \leftarrow D_{orig}$.


3. **Conditional Branch (`JZ` / `JC`):**
* Condition Met ($ZF_{orig}=1$ for `JZ`, $CF_{orig}=1$ for `JC` sampled at $T_2$): Apply `JMP` branch target rules.
* Condition Not Met: $PR \leftarrow PR_{seq}, \quad \text{PC} \leftarrow \text{PC}_{seq}$.


4. **Subroutine Call (`CALL`):** Push $\text{PC}_{seq}$ onto Hardware Stack, then $PR \leftarrow PR, \quad \text{PC} \leftarrow \text{Operand}$. *(Requires $PR_{seq} == PR$).* Performing a `CALL` on a full stack overwrites the logically oldest entry according to ordinary circular `PUSH` semantics.
5. **Subroutine Return (`RET`):** Perform specialized stack-pop operation directly into $\text{PC}$ ($PR \leftarrow PR, \quad \text{PC} \leftarrow \text{Popped Stack}$).
6. **Processor Halt (`HLT`):** Set $\text{CPU\_State} \leftarrow \text{HALTED}$. Registers $A, B, C, D, \text{FLAGS}, PR, \text{PC}, SP, D_{stack}$ remain unchanged. Execution freezes until external `RESET`.

---

### 10. Bounded LIFO Stack & Concrete State Transitions

The Hardware Stack is a $W$-bit wide, $N$-entry LIFO buffer ($1 \le N \le 2^W$) managed by physical write index $SP \in [0, N-1]$ and depth counter $D_{stack} \in [0, N]$.

#### Mathematical Invariants & Full-Stack Concrete Example

* **Pointer Invariant:** $SP$ always identifies the next physical write slot ($0 \le SP < N$). When $D_{stack} > 0$, the most recently pushed element resides at physical index $(SP - 1 + N) \bmod N$.
* **Full-Stack Circular Overwrite:** Overflow is defined behavior and does not trap. When $D_{stack} == N$ (Full Stack), a `PUSH` overwrites the logically oldest entry in the circular buffer and sets $SP \leftarrow (SP + 1) \bmod N$ while $D_{stack}$ remains $N$.
* **Underflow Behavior:** If $D_{stack} == 0$ (Empty Stack), POP returns `0` ($SP$ and $D_{stack}$ remain `0`). Executing `RET` on an empty stack pops `0`, setting $\text{PC} \leftarrow 0$ within active page $PR$ ($SP$ and $D_{stack}$ remain `0`). `RET` itself is always a defined instruction; executing `RET` on an empty stack or popping an unaligned odd target is an *Architecturally Invalid Operation* resulting from nonconforming stack state.

#### Formal Stack Operation State-Transition Table

| Operation | Stack Condition | Stack Array Write | SP Transition | $D_{stack}$ Transition | Returned Value |
| --- | --- | --- | --- | --- | --- |
| **`PUSH(v)`** | $D_{stack} < N$ | $\text{Stack}[SP_{orig}] \leftarrow v$ | $(SP_{orig} + 1) \bmod N$ | $D_{stack\_orig} + 1$ | None |
| **`PUSH(v)`** | $D_{stack} == N$ | $\text{Stack}[SP_{orig}] \leftarrow v$ | $(SP_{orig} + 1) \bmod N$ | $N$ (Unchanged) | None (Oldest Overwritten) |
| **`POP`** | $D_{stack} > 0$ | None | $(SP_{orig} - 1 + N) \bmod N$ | $D_{stack\_orig} - 1$ | $\text{Stack}[(SP_{orig} - 1 + N) \bmod N]$ |
| **`POP`** | $D_{stack} == 0$ | None | $SP_{orig}$ (Unchanged) | $0$ (Unchanged) | $0$ (All bits zero) |
| **`POP` (Reserved ID)** | Any | None | $SP_{orig}$ (Unchanged) | $D_{stack\_orig}$ (Unchanged) | None (Acts as NOP) |

---

### 11. Normative Executable Reference Model (Python)

```python
"""
μ-Core ISA v1.1.0 Normative Executable Reference Model
"""

class CPUState:
    NORMAL = 0
    HALTED = 1

class SparseMemory:
    """Sparse backing store preventing memory allocation explosion for large W."""
    def __init__(self):
        self._data = {}

    def __getitem__(self, addr):
        return self._data.get(addr, 0)

    def __setitem__(self, addr, val):
        self._data[addr] = val

class MuCoreCPU:
    def __init__(self, W=8, N=16):
        self.W = W
        self.N = N
        self.MASK = (1 << W) - 1
        self.MAX = self.MASK
        
        # State Tuple
        self.A = 0
        self.B = 0
        self.C = 0
        self.D = 0
        self.PC = 0
        self.PR = 0
        self.ZF = 0
        self.CF = 0
        self.SP = 0
        self.D_stack = 0
        self.Stack = [0] * N
        self.CPU_State = CPUState.NORMAL

        # Namespaces
        self.InstructionSpace = SparseMemory()
        self.DataSpace = SparseMemory()
        self.Ports = [0] * 8

    def reset(self):
        """Hardware RESET Signal"""
        self.PR = 0
        self.PC = 0
        self.SP = 0
        self.D_stack = 0
        self.CPU_State = CPUState.NORMAL

    def execute_instruction(self):
        """Executes a single 4-phase instruction cycle."""
        if self.CPU_State == CPUState.HALTED:
            return  # Frozen state: no fetch, decode, or state change

        # Guard: Check for Architecturally Invalid Odd Target
        if self.PC % 2 != 0:
            raise RuntimeError(f"Architecturally Invalid Operation: Odd PC target ({self.PC})")

        # Phase T0 & T1: Fetch Opcode and Operand
        pc_addr = self.PR * (1 << self.W) + self.PC
        opcode_word = self.InstructionSpace[pc_addr]
        operand_word = self.InstructionSpace[pc_addr + 1]
        
        primary_opcode = opcode_word & 0x0F
        
        # Phase T2: Take Snapshot
        A0, B0, C0, D0 = self.A, self.B, self.C, self.D
        ZF0, CF0 = self.ZF, self.CF
        PR0, PC0 = self.PR, self.PC
        SP0, D_stack0 = self.SP, self.D_stack
        
        # Evaluate Canonical Sequential Address
        PC_raw = PC0 + 2
        PC_seq = PC_raw & self.MASK
        PR_seq = (PR0 + 1) & self.MASK if PC_raw >= (1 << self.W) else PR0

        # Phase T3: Commit Rules by Opcode
        if primary_opcode == 0x0: # NOP
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x1: # MOV
            dst, src = operand_word & 0x03, (operand_word >> 2) & 0x03
            regs = [A0, B0, C0, D0]
            val = regs[src]
            if dst == 0: self.A = val
            elif dst == 1: self.B = val
            elif dst == 2: self.C = val
            elif dst == 3: self.D = val
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x2: # LOAD
            addr = (C0 * (1 << self.W) + D0) if operand_word == self.MAX else (C0 * (1 << self.W) + operand_word)
            self.A = self.DataSpace[addr] & self.MASK
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x3: # STORE
            addr = (C0 * (1 << self.W) + D0) if operand_word == self.MAX else (C0 * (1 << self.W) + operand_word)
            self.DataSpace[addr] = A0 & self.MASK
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x4: # ALU
            sub_op = operand_word & 0x0F
            if sub_op == 0x0: # ADD
                T = A0 + B0
                self.A = T & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = 1 if T >= (1 << self.W) else 0
            elif sub_op == 0x1: # SUB
                S = B0
                self.A = (A0 - S) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = 1 if A0 >= S else 0
            elif sub_op == 0x2: # ADC
                T = A0 + B0 + CF0
                self.A = T & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = 1 if T >= (1 << self.W) else 0
            elif sub_op == 0x3: # SBB
                S = B0 + (1 - CF0)
                self.A = (A0 - S) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = 1 if A0 >= S else 0
            elif sub_op == 0x4: # AND
                self.A = A0 & B0
                self.ZF = 1 if self.A == 0 else 0
            elif sub_op == 0x5: # OR
                self.A = A0 | B0
                self.ZF = 1 if self.A == 0 else 0
            elif sub_op == 0x6: # XOR
                self.A = A0 ^ B0
                self.ZF = 1 if self.A == 0 else 0
            elif sub_op == 0x7: # NOT
                self.A = (~A0) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
            elif sub_op == 0x8: # INC
                self.A = (A0 + 1) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
            elif sub_op == 0x9: # DEC
                self.A = (A0 - 1) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
            elif sub_op == 0xA: # SHL
                self.A = (A0 << 1) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = (A0 >> (self.W - 1)) & 1
            elif sub_op == 0xB: # SHR
                self.A = (A0 >> 1) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = A0 & 1
            elif sub_op == 0xC: # ROL
                self.A = ((A0 << 1) | CF0) & self.MASK
                self.ZF = 1 if self.A == 0 else 0
                self.CF = (A0 >> (self.W - 1)) & 1
            elif sub_op == 0xD: # ROR
                self.A = (A0 >> 1) | (CF0 << (self.W - 1))
                self.ZF = 1 if self.A == 0 else 0
                self.CF = A0 & 1
            elif sub_op == 0xE: # CMP
                S = B0
                self.ZF = 1 if A0 == S else 0
                self.CF = 1 if A0 >= S else 0
            elif sub_op == 0xF: # TST
                self.ZF = 1 if A0 == 0 else 0
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x5: # JMP
            if operand_word == self.MAX:
                self.PR, self.PC = C0, D0
            else:
                self.PC, self.PR = operand_word, PR0

        elif primary_opcode == 0x6: # JZ
            if ZF0 == 1:
                if operand_word == self.MAX: self.PR, self.PC = C0, D0
                else: self.PC, self.PR = operand_word, PR0
            else: self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x7: # JC
            if CF0 == 1:
                if operand_word == self.MAX: self.PR, self.PC = C0, D0
                else: self.PC, self.PR = operand_word, PR0
            else: self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0x8: # CALL
            if PR_seq != PR0:
                raise RuntimeError("Architecturally Invalid Operation: CALL across page boundary")
            self.Stack[SP0] = PC_seq
            self.SP = (SP0 + 1) % self.N
            if D_stack0 < self.N:
                self.D_stack = D_stack0 + 1
            # If D_stack0 == N, D_stack remains N (Full-stack overwrite)
            self.PC, self.PR = operand_word, PR0

        elif primary_opcode == 0x9: # RET
            if D_stack0 > 0:
                new_sp = (SP0 - 1 + self.N) % self.N
                self.PC = self.Stack[new_sp]
                self.SP = new_sp
                self.D_stack = D_stack0 - 1
                self.PR = PR0
            else:
                self.PC, self.PR = 0, PR0

        elif primary_opcode == 0xA: # PUSH
            target_id = operand_word & 0x07
            if target_id < 5:
                val = [A0, B0, C0, D0, (ZF0 | (CF0 << 1))][target_id]
                self.Stack[SP0] = val
                self.SP = (SP0 + 1) % self.N
                if D_stack0 < self.N:
                    self.D_stack = D_stack0 + 1
                # If D_stack0 == N, D_stack remains N
            # Reserved Target IDs 5, 6, 7 act strictly as NOP (no state change)
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0xB: # POP
            target_id = operand_word & 0x07
            if target_id < 5:
                if D_stack0 > 0:
                    new_sp = (SP0 - 1 + self.N) % self.N
                    val = self.Stack[new_sp]
                    self.SP = new_sp
                    self.D_stack = D_stack0 - 1
                    if target_id == 0: self.A = val
                    elif target_id == 1: self.B = val
                    elif target_id == 2: self.C = val
                    elif target_id == 3: self.D = val
                    elif target_id == 4:
                        self.ZF = val & 0x01
                        self.CF = (val >> 1) & 0x01
            # Reserved Target IDs 5, 6, 7 act strictly as NOP (no stack read, no pointer change)
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0xC: # IO
            port_id = operand_word & 0x07
            direction = (operand_word >> 3) & 0x01
            if direction == 0: # INPUT
                self.A = self.Ports[port_id] & self.MASK
            else: # OUTPUT
                self.Ports[port_id] = A0 & self.MASK
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode in (0xD, 0xE): # RSVD1, RSVD2
            self.PC, self.PR = PC_seq, PR_seq

        elif primary_opcode == 0xF: # HLT
            self.CPU_State = CPUState.HALTED
            # PC and PR remain unchanged

```

---

### 12. Canonical Conformance Litmus Test Suite

Every conforming μ-Core implementation shall produce identical state outcomes for the following litmus test cases:

#### Test 1: Sequential Page Rollover (μ8)

* **Initial State:** $PR = 0\text{x12}, \text{PC} = 0\text{xFE}$. Instruction Space at $0\text{x12FE} = [0\text{x00}, 0\text{x00}]$ (`NOP`).
* **Expected State:** $PR = 0\text{x13}, \text{PC} = 0\text{x00}$.

#### Test 2: Full-Stack Overwrite ($N=4$)

* **Initial State:** $\text{Stack} = [A, B, C, D], SP = 0, D_{stack} = 4$. Execute `PUSH(E)`.
* **Expected State:** $\text{Stack} = [E, B, C, D], SP = 1, D_{stack} = 4$. Logical Stack (Newest to Oldest) $= [E, D, C, B]$.

#### Test 3: Reserved Target ID POP Handling

* **Initial State:** $A = 0\text{x42}, \text{Stack} = [0\text{x99}], SP = 1, D_{stack} = 1$. Execute `POP ID=5`.
* **Expected State:** $A = 0\text{x42}$ (Unchanged), $\text{Stack} = [0\text{x99}]$ (Unchanged), $SP = 1$ (Unchanged), $D_{stack} = 1$ (Unchanged).

#### Test 4: Carry-Preserving INC

* **Initial State:** $A = 0\text{xFF}, CF = 1, ZF = 0$. Execute `ALU INC`.
* **Expected State:** $A = 0\text{x00}, CF = 1$ (Preserved), $ZF = 1$.

#### Test 5: Extended Escape Jump (`JMP MAX`)

* **Initial State:** $C = 0\text{x12}, D = 0\text{x34}, PR = 0\text{x00}, \text{PC} = 0\text{x00}$. Execute `JMP MAX` (`0x05 0xFF`).
* **Expected State:** $PR = 0\text{x12}, \text{PC} = 0\text{x34}$.

---

### 13. Consolidated Normative Reference Sections

#### Architecturally Invalid Operations (§13.1)

An *Architecturally Invalid Operation* is an instruction execution that conforming software is forbidden to generate under the ISA's software invariants. The ISA imposes no required result for such execution; physical hardware is not required to trap it and produces implementation-defined behavior:

1. Executing control flow to an unaligned odd instruction target ($\text{PC} \pmod 2 \neq 0$).
2. Executing `CALL` from address $\text{PC} = 2^W - 2$ where $\text{PC}_{seq}$ overflows into a new page ($PR_{seq} \neq PR_{orig}$).

#### Implementation-Defined Behaviors (§13.2)

Conforming implementation documentation shall explicitly declare:

1. Post-reset contents of registers $A, B, C, D,$ and $FLAGS$.
2. Electrical timing, active level, and synchronization machinery of external hardware `RESET`.
3. Hardware behavior upon encountering an *Architecturally Invalid Operation*.
4. Physical realizations of the three isolated memory namespaces.
5. Physical register width and representation of logical indices $SP$ and $D_{stack}$.
6. External handshake, electrical signaling, side-effects, and timing of peripheral I/O ports.

#### Architectural Invariants Summary (§13.3)

A conforming μ-Core v1.1.0 implementation shall preserve:

1. Registers $A, B, C, D, \text{PC}, \text{PR}$ are strictly $W$ bits wide ($W \ge 4$).
2. $FLAGS$ consists strictly of Zero ($ZF$) and Carry ($CF$).
3. All valid instruction addresses are even ($\text{PC} \pmod 2 == 0$).
4. Sequential instruction execution advances $PR:\text{PC}$ via canonical $2W$-bit auto-incrementing carry propagation.
5. `CALL` and `RET` operate strictly page-locally, preserving $PR$.
6. Instruction Space, Data Space, and Hardware Stack remain logically isolated.
7. Hardware reset zeroes $PR, \text{PC}, SP,$ and $D_{stack}$, setting $\text{CPU\_State} \leftarrow \text{NORMAL}$ without altering memory or stack storage.

---

### 14. Reference Targets

* **Minimal Target (μ4 Target, $W=4$):** 4-bit datapath, $2^4 = 16$ nibbles per page, $N=4$ stack depth, $\text{MAX} = \text{0xF}$.
* **Canonical Reference Target (μ8 Target, $W=8$):** 8-bit datapath, $2^8 = 256$ bytes per page, $N=16$ stack depth, $\text{MAX} = \text{\$FF}$.

---

### 15. The μ-Core Principle

A computer architecture should survive changes in technology.

A program written for μ-Core should execute on an emulator, a TTL computer, a discrete transistor machine, or a relay computer without modification.

**Hardware evolves. Implementations change. The architecture endures.**
