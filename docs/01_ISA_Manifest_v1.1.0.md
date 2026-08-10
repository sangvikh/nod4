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

#### Canonical Machine State Tuple (`STATE`)

A conforming μ-Core execution unit is formally defined by its architectural state tuple:

`STATE` = ⟨A, B, C, D, PC, PR, FLAGS, SP, D_stack, Stack[], CPU_State⟩

Where `FLAGS` ≡ ⟨ZF, CF⟩ and `CPU_State` ∈ {NORMAL, HALTED}.

Operating on three isolated architectural namespaces:

`NAMESPACES` = ⟨InstructionSpace[], DataSpace[], Ports[]⟩

---

### 2. Design Philosophy, Conformance Taxonomy & Normative Precedence

#### Core Design Principles

* **Modules before gates:** Reusable functional modules allow hardware builders to swap individual boards without altering software semantics.
* **Datapath simplicity over defensive hardware:** Hardware implements direct, deterministic state changes without parity checkers, target validation stages, or exception machinery.
* **Concept Isolation Principle:** Architectural state variables remain strictly independent when the concepts they represent are independent (PR:PC for execution position, C:D for data access, SP for stack indexing).
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

### 3. Parameterized Scaling Model (W) & Storage Units

A μ-Core implementation is defined by a fundamental **datapath width parameter W**, where W >= 4 (W=4 is the minimum bound required to accommodate all 16 primary opcodes; W need not be a power of two, though power-of-two widths are recommended).

#### Storage Unit (SU) & Instruction Structure

* **Storage Unit (SU):** The fundamental unit of memory storage and addressing, defined as exactly W bits. The term "Word" shall not be used as an architectural unit.
* **Instruction Layout:** Every instruction occupies exactly 2 SU (2W bits), split into two physical W-bit fields:

1. **Opcode Field (W bits):** The first W-bit storage unit of the instruction.
2. **Operand Field (W bits):** The second W-bit storage unit of the instruction.

| Architectural Property | Parameterized Definition | μ4 (W=4) | μ8 (W=8) | μ16 (W=16) |
| --- | --- | --- | --- | --- |
| **Datapath & Register Width** | W bits | 4 bits | 8 bits | 16 bits |
| **Instruction Size** | 2 SU = 2W bits | 8 bits (2 nibbles) | 16 bits (2 bytes) | 32 bits (2 x 16-bit SU) |
| **Program Counter Unit** | Indexes W-bit storage units | Nibbles | Bytes | 16-bit Storage Units |
| **Low Address Pointer (D)** | W bits (2^W locations) | 16 nibbles | 256 bytes | 64 KiB |
| **Extended Address Space (C:D)** | 2W bits (2^(2W) locations) | 256 nibbles | 64 KiB | 4 GiB |
| **Memory Page Size** | 2^W storage units | 16 nibbles | 256 bytes | 64 KiB |
| **Memory Page Count** | 2^W pages (PR) | 16 pages | 256 pages | 65,536 pages |
| **Override Sentinel (`MAX`)** | 2^W - 1 (All 1s / Odd) | `0xF` | `$FF` | `$FFFF` |

#### Global Reserved-Bit & Noncanonical Encoding Rule

Execution hardware shall strictly decode **bits [3:0] of the Opcode Field** as the primary opcode. Conforming software shall write `bits [W-1:4]` of the Opcode Field and all unused upper bits `[W-1:k]` of the Operand Field as zero. Non-zero values in reserved bit fields constitute a noncanonical encoding; execution hardware shall ignore reserved bits during decoding and execution.

---

### 4. Registers & Processor States

#### Programmer-Visible Registers

Every μ-Core implementation defines four programmer-visible registers of width W:

| Register | ID (`[1:0]`) | Purpose |
| --- | --- | --- |
| **A** | `00` | Accumulator (Primary ALU destination & memory gateway) |
| **B** | `01` | Secondary Register (Implicit ALU source operand) |
| **C** | `10` | High Address Register / Page Selector |
| **D** | `11` | Low Address Register / Offset Pointer |

#### Extended Address Pair (C:D)

`C` and `D` form the primary 2W-bit Extended Address Pair (C:D):

Extended Address = (C * 2^W) + D

#### Special Control Registers

* **Program Counter (PC):** W-bit register tracking execution location within active Page PR. PC addresses W-bit storage units; every 2-unit instruction advances PC by 2.
* **Page Register (PR):** W-bit register holding the active Memory Page ID for instruction execution.
* **Auto Page-Increment Cascade (PR:PC):** PR and PC form a combined 2W-bit synchronous instruction counter pair PR:PC. Sequential execution automatically ripples the overflow carry from PC into PR.
* **Stack Pointer (SP):** Hidden logical integer index SP in [0, N-1] tracking the next physical write slot in the Hardware Stack. Physical register width is implementation-defined (ceil(log2(N)) bits up to W bits).
* **Logical Stack Depth Counter (D_stack):** Hidden logical integer counter D_stack in [0, N] tracking active pushed frames.
* **FLAGS Register:** Contains condition flags: **Zero (ZF)** and **Carry (CF)** (FLAGS = <ZF, CF>).

#### Processor Execution States & Hardware Reset Behavior

Physical execution states are **`NORMAL`** and **`HALTED`** (entered via `HLT` (`0xF`)). During `HALTED` state, architectural clock phases freeze; no instruction fetches, reads, writes, or register updates occur. External peripheral I/O behavior during `HALTED` state is implementation-defined.

A hardware `RESET` signal is an external architectural event. Electrical timing, active levels, and synchronization machinery of `RESET` are implementation-defined. `RESET` transitions processor state from either **`NORMAL`** or **`HALTED`** to **`NORMAL`**, establishing control state:

PR <- 0 | PC <- 0 | SP <- 0 | D_stack <- 0 | CPU_State <- NORMAL

After `RESET` establishes control state, the next instruction execution cycle begins at Phase T0 from address PR:PC = 0:0. `RESET` does not modify Instruction Space, Data Space, or Hardware Stack storage contents, nor does it guarantee clearing registers A, B, C, D, or FLAGS (their post-reset values are implementation-defined).

---

### 5. Memory Model & Three Independent Namespaces

μ-Core defines three strictly independent, non-overlapping memory namespaces:

```text
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│    INSTRUCTION SPACE    │ │        DATA SPACE       │ │      HARDWARE STACK     │
│      Addressed by       │ │       Addressed by      │ │       Addressed by      │
│   PR : PC (Continuous)  │ │      C : Offset / D     │ │        Hidden SP        │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘

```

1. **Instruction Space:** Addressed strictly using PR:PC. Contains executable instructions. Instruction Space mutability is an implementation property; the base ISA provides no architectural operation for modifying Instruction Space.
2. **Data Space:** Addressed strictly using C:Offset or C:D. Accessed exclusively by `LOAD` and `STORE`.
3. **Hardware Stack:** Addressed internally by SP. Changing PR or C never affects stack contents.

*Architectural Isolation Rule:* Instruction Space, Data Space, and Hardware Stack are logically distinct. An implementation shall not expose one namespace through another even if physical storage media is shared.

---

### 6. Four-Phase Execution Model (T0..T3), Snapshots & Side-Effect Timing

#### The Architectural Four-Phase Model (T0..T3)

Every instruction executes across four ordered architectural phases in the reference execution model. An implementation may realize these phases using different physical timing (e.g., pipelining), provided the externally observable architectural behavior is identical:

* **Phase T0 (Instruction Fetch):** Fetch Opcode Field from Instruction Space at address PR:PC.
* **Phase T1 (Operand Fetch):** Fetch Operand Field from Instruction Space at address PR:(PC + 1).
* **Phase T2 (Execution & Snapshot):** Atomically sample execution register snapshot variables and external I/O values:

SNAPSHOT = <A_orig, B_orig, CF_orig, C_orig, D_orig, D_stack_orig, PC_orig, PORT_orig PR_orig, SP_orig, ZF_orig,>

Evaluate ALU operations, branch conditions, or perform reads (`LOAD`, `POP`, `IO IN`).

* **Phase T3 (Architectural Commit):** Commit updated register variables and write side-effects simultaneously to architectural state. No instruction may observe its own T3 commit results during T0/T1 of the same instruction.

#### Phase Execution & Side-Effect Timing Table

| Operation | Phase T0..T1 | Phase T2 (Execution & Read) | Phase T3 (Commit & Write) |
| --- | --- | --- | --- |
| **`LOAD`** | Fetch instruction | Read Data Space at C_orig:target | Commit value to Accumulator A, advance PR:PC |
| **`STORE`** | Fetch instruction | Sample A_orig and target address | Commit write of A_orig to Data Space at C_orig:target, advance PR:PC |
| **`PUSH`** | Fetch instruction | Sample target register value | Commit value to Stack[SP_orig], commit SP, D_stack, advance PR:PC |
| **`POP`** | Fetch instruction | Read value from Stack[(SP_orig - 1 + N) mod N] | Commit value to target register, commit SP, D_stack, advance PR:PC |
| **`IO IN`** | Fetch instruction | Sample external `PORT[ID]` into PORT_orig | Commit input value PORT_orig to Accumulator A, advance PR:PC |
| **`IO OUT`** | Fetch instruction | Sample A_orig | Drive output value A_orig to external `PORT[ID]`, advance PR:PC |

#### Canonical PC Advancement Equations

At Phase T2, sequential candidate address pair (PR_seq, PC_seq) is evaluated according to the single authoritative equation:

(PR * 2^W + PC)_seq = (PR * 2^W + PC + 2) mod 2^(2W)

Equivalently, split into register components where PC_raw = PC + 2:

PC_seq = PC_raw mod 2^W
PR_seq = (PR + 1) mod 2^W if PC_raw >= 2^W else PR

#### Alignment Invariants & Terminal Address Space Boundary

* **Alignment Invariant:** All valid instruction addresses are even (PC % 2 == 0). Conforming software shall ensure all direct control-flow targets (`JMP`, `JZ`, `JC`, `CALL`) and return addresses loaded into PC via `RET` are even.
* **Terminal Address Space Boundary Rule:** The final valid instruction address in the entire PR:PC space is PR = MAX, PC = MAX - 3. Sequential execution from that address produces the odd address PR = MAX, PC = MAX - 1. Conforming software shall not execute sequentially through the end of the address space without explicitly transferring control elsewhere.

---

### 7. Primary Opcode Table, Extended Address Escape, & Address Functions

#### Primary Opcode Table (4-bit Opcode Decoder)

| Opcode | Mnemonic | Primary Responsibility | Operand Field Sub-Layout |
| --- | --- | --- | --- |
| `0x0` | **NOP** | No Operation (Burns 4 phases, advances PR:PC) | Reserved (`[W-1:0]` = 0) |
| `0x1` | **MOV** | Register-to-register move | `[1:0]` = dst, `[3:2]` = src, `[W-1:4]` = 0 |
| `0x2` | **LOAD** | Read Data Space into Accumulator A | Direct offset or `MAX` for `[C:D]` |
| `0x3` | **STORE** | Write Accumulator A to Data Space | Direct offset or `MAX` for `[C:D]` |
| `0x4` | **ALU** | Execute arithmetic/logic on A and B | `[3:0]` = sub-opcode, `[W-1:4]` = 0 |
| `0x5` | **JMP** | Branch unconditional (Local or Far Jump) | Target offset or `MAX` for `[C:D]` |
| `0x6` | **JZ** | Branch if Zero flag set (ZF_orig = 1) (Local or Far Jump) | Target offset or `MAX` for `[C:D]` |
| `0x7` | **JC** | Branch if Carry flag set (CF_orig = 1) (Local or Far Jump) | Target offset or `MAX` for `[C:D]` |
| `0x8` | **CALL** | Page-local subroutine call (Pushes PC_seq, PC <- Operand) | Page-local target offset |
| `0x9` | **RET** | Return from page-local subroutine (PC <- Popped Stack) | Reserved (`[W-1:0]` = 0) |
| `0xA` | **PUSH** | Push register or FLAGS onto Hardware Stack | `[2:0]` = Target ID, `[W-1:3]` = 0 |
| `0xB` | **POP** | Pop Hardware Stack into register or FLAGS | `[2:0]` = Target ID, `[W-1:3]` = 0 |
| `0xC` | **IO** | Peripheral I/O transfer (W-bit transfer) | `[2:0]` = Port ID, `[3]` = Dir, `[W-1:4]` = 0 |
| `0xD` | **RSVD1** | Reserved opcode (Treat strictly as NOP) | Reserved (`[W-1:0]` = 0) |
| `0xE` | **RSVD2** | Reserved opcode (Treat strictly as NOP) | Reserved (`[W-1:0]` = 0) |
| `0xF` | **HLT** | Halt processor execution | Reserved (`[W-1:0]` = 0) |

#### PUSH / POP Operand Layout (`0xA` / `0xB`) & Reserved Target IDs

* `Bits [2:0]` Target ID Mapping: `000`=A, `001`=B, `010`=C, `011`=D, `100`=FLAGS, `101`..`111`=Reserved.
* **Reserved Target ID Rule:** Conforming software shall not encode Target IDs `5`, `6`, or `7`. Hardware shall treat `PUSH` or `POP` with a Reserved Target ID as a NOP (advancing PR:PC without modifying registers, SP, or D_stack).
* **FLAGS Format on Stack:** `Bit [0]` = ZF, `Bit [1]` = CF, `Bits [W-1:2]` = 0.
* **`POP FLAGS` Execution Rule:** `POP FLAGS` updates ZF <- popped[0] and CF <- popped[1]. POP FLAGS does not require reserved bits `[W-1:2]` of the popped value to be zero; unused upper bits are ignored and not retained.

#### Peripheral IO Operand Layout (`0xC`) & Contract

* `Bits [2:0]` = Port ID (`0`..`7`); `Bit [3]` = Direction (`0`=INPUT, `1`=OUTPUT).
* The architectural port namespace contains exactly 8 IDs (`0`..`7`). `IO` operations leave FLAGS (ZF, CF) strictly unchanged. Reading an unimplemented port returns `0` (all bits zero); writing to an unimplemented port is ignored.

#### Reserved Opcodes `RSVD1` (`0xD`) & `RSVD2` (`0xE`) Rule

`RSVD1` and `RSVD2` behave strictly as NOPs (advancing PR:PC by 2) regardless of Operand Field contents.

#### Extended Address Escape Sentinel (`MAX`) & Address Functions

The sentinel value MAX = 2^W - 1 is an extended-address escape override for `LOAD`, `STORE`, `JMP`, `JZ`, and `JC`. The direct-offset encoding domain is [0, MAX-1]; MAX is exclusively the escape encoding. To access Data Space address C:MAX, software shall set D = MAX and invoke `LOAD MAX` or `STORE MAX`:

DIRECT(operand) = C_orig : operand (for operand != MAX)
EXTENDED(C, D) = C_orig : D_orig (for operand == MAX)

Effective Address(operand) = DIRECT(operand) if operand != MAX else EXTENDED(C, D)

#### Page-Local Subroutine Constraint (`CALL` / `RET`)

* **Page-Local Invariant:** `CALL` and `RET` are page-local. `CALL` pushes W-bit PC_seq onto the Hardware Stack and sets PC <- Operand (PR unchanged). `RET` performs a specialized stack-pop operation directly into PC (PC <- Popped Stack), preserving PR. Software shall not modify PR between `CALL` and its corresponding `RET`. The Hardware Stack is untyped; software is solely responsible for preserving return-address entries across subroutine execution.
* **CALL Validity Rule:** A `CALL` instruction is architecturally valid iff PR_seq == PR_orig (PC_orig + 2 < 2^W). Executing `CALL` when PR_seq != PR_orig (PC_orig = 2^W - 2) is an *Architecturally Invalid Operation*.

---

### 8. Definitive Flag Semantics & Functional ALU Contract

#### Subtraction Carry Convention & Precision Rules

* **Mathematical Operations:** Unless otherwise stated, all register arithmetic, comparisons, shifts, and addresses are unsigned modulo-2^W operations.
* **Subtraction Carry Convention:** For subtraction-class operations (`SUB`, `SBB`, `CMP`), CF=1 indicates no borrow (A_orig >= Subtrahend); CF=0 indicates borrow required (A_orig < Subtrahend).
* **`SBB` Intermediate Precision Rule:** Subtrahend S = B + (1 - CF_orig) shall be evaluated as an unsigned mathematical value with at least W+1 bits of precision prior to subtraction and borrow evaluation.
* **Rotate Operations:** `ROL` and `ROR` perform a (W+1)-bit rotate through the carry flag:

ROL: {CF', A'} = {A_orig[W-1], A_orig[W-2:0], CF_orig}
ROR: {A', CF'} = {CF_orig, A_orig[W-1:1], A_orig[0]}

Procedural evaluation:

ROL => old_cf = CF_orig, CF <- A_orig[W-1], A <- ((A_orig << 1) | old_cf) mod 2^W
ROR => old_cf = CF_orig, CF <- A_orig[0], A <- floor(A_orig / 2) | (old_cf << (W-1))

* **Flag Preservation Law:** Only ALU operations and `POP FLAGS` modify FLAGS. `INC` and `DEC` update ZF but leave CF unchanged. `CMP` modifies both ZF and CF leaving A unchanged. `TST` modifies ZF leaving CF and A unchanged. Non-ALU instructions (`MOV`, `LOAD`, `STORE`, `JMP`, `JZ`, `JC`, `CALL`, `RET`, `PUSH`, `IO`, `NOP`, `HLT`) leave FLAGS strictly unchanged.

| Sub-Opcode | Mnemonic | Operational Pseudocode | Zero Flag (ZF) | Carry Flag (CF) |
| --- | --- | --- | --- | --- |
| `0x0` | **ADD** | T <- A_orig + B; A <- T mod 2^W | A == 0 | T >= 2^W |
| `0x1` | **SUB** | S = B; A <- (A_orig - S + 2^W) mod 2^W | A == 0 | A_orig >= S (1=No Borrow) |
| `0x2` | **ADC** | T <- A_orig + B + CF_orig; A <- T mod 2^W | A == 0 | T >= 2^W |
| `0x3` | **SBB** | S = B + (1 - CF_orig); A <- (A_orig - S + 2^(W+1)) mod 2^W | A == 0 | A_orig >= S (1=No Borrow) |
| `0x4` | **AND** | A <- A_orig AND B | A == 0 | Unchanged |
| `0x5` | **OR** | A <- A_orig OR B | A == 0 | Unchanged |
| `0x6` | **XOR** | A <- A_orig XOR B | A == 0 | Unchanged |
| `0x7` | **NOT** | A <- (NOT A_orig) mod 2^W | A == 0 | Unchanged |
| `0x8` | **INC** | A <- (A_orig + 1) mod 2^W | A == 0 | Unchanged |
| `0x9` | **DEC** | A <- (A_orig - 1 + 2^W) mod 2^W | A == 0 | Unchanged |
| `0xA` | **SHL** | A <- (A_orig << 1) mod 2^W | A == 0 | A_orig[W-1] |
| `0xB` | **SHR** | A <- floor(A_orig / 2) | A == 0 | A_orig[0] |
| `0xC` | **ROL** | See formal (W+1)-bit bit vector equations above | A == 0 | A_orig[W-1] |
| `0xD` | **ROR** | See formal (W+1)-bit bit vector equations above | A == 0 | A_orig[0] |
| `0xE` | **CMP** | S = B; (A unchanged) | A_orig == S | A_orig >= S (1=No Borrow) |
| `0xF` | **TST** | Test A_orig; (A unchanged) | A_orig == 0 | Unchanged |

---

### 9. Control Flow & Program Counter Precedence Rules

At Phase T3, committed address pairs are finalized by instruction type:

1. **Ordinary Instructions (`NOP`, `MOV`, `LOAD`, `STORE`, `ALU`, `PUSH`, `POP`, `IO`, `RSVD1`, `RSVD2`):**

PR <- PR_seq, PC <- PC_seq

2. **Unconditional Branch (`JMP`):**

* Operand != MAX: PR <- PR, PC <- Operand
* Operand == MAX: PR <- C_orig, PC <- D_orig

3. **Conditional Branch (`JZ` / `JC`):**

* Condition Met (ZF_orig=1 for `JZ`, CF_orig=1 for `JC` sampled at T2): Apply `JMP` branch target rules.
* Condition Not Met: PR <- PR_seq, PC <- PC_seq

4. **Subroutine Call (`CALL`):** Push PC_seq onto Hardware Stack, then PR <- PR, PC <- Operand. *(Requires PR_seq == PR).* Performing a `CALL` on a full stack overwrites the logically oldest entry according to ordinary circular `PUSH` semantics.
5. **Subroutine Return (`RET`):** Perform specialized stack-pop operation directly into PC (PR <- PR, PC <- Popped Stack).
6. **Processor Halt (`HLT`):** Set CPU_State <- HALTED. Registers A, B, C, D, FLAGS, PR, PC, SP, D_stack remain unchanged. Execution freezes until external `RESET`.

---

### 10. Bounded LIFO Stack & Concrete State Transitions

The Hardware Stack is a W-bit wide, N-entry LIFO buffer (1 <= N <= 2^W) managed by physical write index SP in [0, N-1] and depth counter D_stack in [0, N].

#### Mathematical Invariants & Full-Stack Concrete Example

* **Pointer Invariant:** SP always identifies the next physical write slot (0 <= SP < N). When D_stack > 0, the most recently pushed element resides at physical index (SP - 1 + N) mod N.
* **Full-Stack Circular Overwrite:** Overflow is defined behavior and does not trap. When D_stack == N (Full Stack), a `PUSH` overwrites the logically oldest entry in the circular buffer and sets SP <- (SP + 1) mod N while D_stack remains N.
* **Underflow Behavior:** If D_stack == 0 (Empty Stack), POP returns `0` (SP and D_stack remain `0`). Executing `RET` on an empty stack pops `0`, setting PC <- 0 within active page PR (SP and D_stack remain `0`). `RET` itself is always a defined instruction; executing `RET` on an empty stack or popping an unaligned odd target is an *Architecturally Invalid Operation* resulting from nonconforming stack state.

#### Formal Stack Operation State-Transition Table

| Operation | Stack Condition | Stack Array Write | SP Transition | D_stack Transition | Returned Value |
| --- | --- | --- | --- | --- | --- |
| **`PUSH(v)`** | D_stack < N | Stack[SP_orig] <- v | (SP_orig + 1) mod N | D_stack_orig + 1 | None |
| **`PUSH(v)`** | D_stack == N | Stack[SP_orig] <- v | (SP_orig + 1) mod N | N (Unchanged) | None (Oldest Overwritten) |
| **`POP`** | D_stack > 0 | None | (SP_orig - 1 + N) mod N | D_stack_orig - 1 | Stack[(SP_orig - 1 + N) mod N] |
| **`POP`** | D_stack == 0 | None | SP_orig (Unchanged) | 0 (Unchanged) | 0 (All bits zero) |
| **`POP` (Reserved ID)** | Any | None | SP_orig (Unchanged) | D_stack_orig (Unchanged) | None (Acts as NOP) |
