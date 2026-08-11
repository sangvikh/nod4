# μ-Core ISA Specification v1.3.0

**Normative Architecture Reference**
**Version:** 1.3.0
**Classification:** Parameterized Minimalist Deterministic ISA
**Status:** Proposed Architectural Standard

---

## 1. Architectural Philosophy

μ-Core is a deliberately small, deterministic instruction set intended to permit straightforward implementations using a low part count and minimal control logic.

The architecture follows these principles:

1. **Small opcode space:** Every instruction has a fixed two-storage-unit encoding.
2. **Simple datapath:** The general-purpose datapath is centered on registers `A`, `B`, `C`, and `D`.
3. **Explicit addressing:** `C:D` forms the complete data-memory address.
4. **One sentinel:** `MAX = 2^W - 1` selects the exceptional/indirect form of instructions that use it.
5. **No hidden state:** Architectural state changes are explicit and deterministic.
6. **No unnecessary traps:** The circular stack deliberately has no overflow or underflow exceptions.
7. **Fixed timing:** Every instruction occupies exactly four clock phases.
8. **Unified memory:** Instructions and data inhabit the same logical address space.
9. **Minimal special hardware:** `SP` is a small auxiliary counter and does not enter the general ALU datapath.

The ISA is parameterized by datapath width `W` and stack-address width `K`.

---

# 2. Architectural Parameterization & State Model

## 2.1 Datapath Width

A μ-Core implementation has a datapath width:

$$W \ge 4$$

All general-purpose registers, system registers, storage units, and instruction fields are `W` bits wide.

A **Storage Unit (SU)** is exactly `W` bits.

Each instruction occupies exactly two SUs:

```text
┌──────────────────────────────┬──────────────────────────────┐
│          Opcode              │           Operand             │
│            W bits            │            W bits             │
└──────────────────────────────┴──────────────────────────────┘
```

The opcode is `IR_op`; the operand is `IR_opr`.

The architectural address is `2W` bits:

```text
┌──────────────────────────────┬──────────────────────────────┐
│          Page                │            Offset             │
│            W bits            │            W bits             │
└──────────────────────────────┴──────────────────────────────┘
```

Therefore the unified logical address space contains:

$$2^{2W}$$

addressable storage units.

For `W = 8`, the architecture has a 16-bit address space containing 65,536 byte-sized storage units.

---

## 2.2 Immediate Sentinel

The value

$$MAX = 2^W - 1$$

is reserved as the architectural sentinel.

Examples:

|  W |      MAX |
| -: | -------: |
|  4 |    `0xF` |
|  8 |   `0xFF` |
| 16 | `0xFFFF` |

`MAX` is not available as an ordinary immediate operand for instructions whose operand interpretation reserves it.

In particular:

* `LOAD MAX` means **load from memory through `C:D`**.
* `STORE MAX` means **store to memory through `C:D`**.
* `JMP MAX`, `JZ MAX`, and `JC MAX` mean **far transfer through `C:D`**.

This convention provides indirect addressing without adding an addressing-mode field or additional opcode.

---

# 3. Architectural Registers

The complete architectural state is:

$$
\mathcal{S} =
\langle
A,B,C,D,FLAGS,PC,PR,SP,Stack,Memory
\rangle
$$

The instruction register (`IR`) is implementation state and is not persistent architectural state.

| Register | Width | Function                                   | PUSH/POP ID |
| :------- | :---: | :----------------------------------------- | :---------: |
| `A`      |   W   | Accumulator and primary ALU operand/result |    `0x0`    |
| `B`      |   W   | Secondary ALU operand                      |    `0x1`    |
| `C`      |   W   | Data-page register                         |    `0x2`    |
| `D`      |   W   | Data-offset / indirect pointer             |    `0x3`    |
| `FLAGS`  |   W   | Carry and zero flags                       |    `0x4`    |
| `PC`     |   W   | Program offset                             |    `0x5`    |
| `PR`     |   W   | Program page                               |    `0x6`    |
| `RSVD`   |   W   | Reserved                                   |    `0x7`    |

The complete 2W-bit program address is:

$$
ADDR_{inst} = (PR \ll W) \mid PC
$$

The complete 2W-bit data address is:

$$
ADDR_{data} = (C \ll W) \mid D
$$

---

## 3.1 General Registers

### A — Accumulator

`A` is the primary ALU input and destination.

### B — Secondary Operand

`B` supplies the second ALU operand.

### C — Data Page

`C` supplies the upper `W` bits of a data-memory address.

### D — Data Offset

`D` supplies the lower `W` bits of a data-memory address.

Together:

```text
C:D = complete 2W-bit data address
```

---

## 3.2 Program Registers

### PC — Program Counter

`PC` contains the low `W` bits of the current instruction address.

### PR — Program Page Register

`PR` contains the high `W` bits of the current instruction address.

Sequential execution therefore operates on the pair:

```text
PR:PC
```

---

## 3.3 FLAGS

Only two flag bits are architecturally defined:

| Bit | Name | Meaning             |
| --: | :--: | :------------------ |
|   0 | `CF` | Carry / borrow flag |
|   1 | `ZF` | Zero flag           |

Bits `W-1..2` read as zero and are ignored when written.

`FLAGS` is modified only by:

1. an ALU instruction; or
2. an explicit `POP FLAGS`.

All other instructions preserve it.

---

# 4. Stack Architecture

## 4.1 Parameterization

The hardware stack contains:

$$N = 2^K$$

entries, each `W` bits wide.

`SP` is a `K`-bit counter.

The stack is therefore:

$$2^K \times W\text{-bit}$$

and operates modulo `2^K`.

`SP` always identifies the **next insertion slot**.

---

## 4.2 PUSH

For a value `v`:

$$
Stack[SP] \leftarrow v
$$

$$
SP \leftarrow (SP+1)\bmod 2^K
$$

If more than `2^K` values are pushed without corresponding pops, the oldest entries are overwritten.

No overflow exception exists.

---

## 4.3 POP

A pop first decrements `SP`:

$$
SP \leftarrow (SP-1)\bmod 2^K
$$

The resulting slot is then read:

$$
v \leftarrow Stack[SP]
$$

No underflow exception exists.

If the stack is logically empty, the operation simply returns whatever physical word is present in the selected slot.

The stack contains untyped `W`-bit words.

---

# 5. Unified Memory

A conforming implementation exposes one logical memory space of:

$$2^{2W}$$

storage units.

Instruction and data accesses address this same space.

Consequently:

* RAM may contain executable instructions.
* ROM may contain executable instructions.
* Code may be generated or copied using `STORE`.
* A program may execute directly from RAM.
* No architectural distinction exists between code memory and data memory.

The physical implementation MAY divide the logical address space among ROM, SRAM, DRAM, MMIO, or other storage technologies, provided architectural behavior remains deterministic.

---

# 6. Instruction Fetch and Sequential Execution

Every instruction occupies two SUs.

The current instruction begins at:

$$PR:PC$$

The sequential address is:

$$PC_{seq} = PC + 2$$

with normal `W`-bit wrapping.

If the sequential instruction crosses the page boundary, `PR` is incremented.

Thus:

```text
PR:PC = 00:FC
       ↓ +2
PR:PC = 01:00
```

For the final instruction-aligned position:

```text
PR:PC = XX:FE
       ↓ +2
PR:PC = (XX+1):00
```

The page increment is modulo `2^W`.

---

# 7. Four-Phase Instruction Cycle

Every instruction executes in exactly four clock phases.

```text
T0 ─ Opcode fetch
T1 ─ Operand fetch
T2 ─ Evaluation / bus settle
T3 ─ Atomic architectural commit
```

## T0 — Opcode Fetch

$$
IR_{op} \leftarrow Memory[PR:PC]
$$

## T1 — Operand Fetch

$$
IR_{opr} \leftarrow Memory[PR:PC+1]
$$

The operand is always fetched from the same program page as the opcode.

## T2 — Evaluation

The instruction decoder selects the required datapath, memory, ALU, or stack operation.

No architectural register is modified during `T2`.

## T3 — Commit

All architectural effects become visible at the `T3` commit edge.

A conforming implementation MUST NOT expose partially committed instruction state.

---

# 8. Instruction Set

The complete base opcode map is:

| Opcode | Mnemonic       | Format                    | Function                          |
| :----: | :------------- | :------------------------ | :-------------------------------- |
|  `0x0` | `NOP`          | `NOP`                     | No operation                      |
|  `0x1` | `MOV`          | `MOV dst,src`             | Register transfer                 |
|  `0x2` | `LOAD` / `LDI` | `LOAD imm` / `LOAD MAX`   | Immediate or indirect memory load |
|  `0x3` | `STORE`        | `STORE off` / `STORE MAX` | Memory store                      |
|  `0x4` | `ALU`          | `ALU op`                  | Arithmetic / logic                |
|  `0x5` | `JMP`          | `JMP off` / `JMP MAX`     | Unconditional branch              |
|  `0x6` | `JZ`           | `JZ off` / `JZ MAX`       | Branch if ZF                      |
|  `0x7` | `JC`           | `JC off` / `JC MAX`       | Branch if CF                      |
|  `0x8` | `CALL`         | `CALL off`                | Page-local subroutine call        |
|  `0x9` | `RET`          | `RET`                     | Page-local subroutine return      |
|  `0xA` | `PUSH`         | `PUSH target`             | Push register/control register    |
|  `0xB` | `POP`          | `POP target`              | Pop register/control register     |
|  `0xC` | `IO`           | `IO operand`              | Implementation-defined I/O        |
|  `0xD` | `RSVD1`        | —                         | Reserved                          |
|  `0xE` | `RSVD2`        | —                         | Reserved                          |
|  `0xF` | `HLT`          | `HLT`                     | Halt                              |

`LDI` is an assembler mnemonic alias for the immediate form of `LOAD`.

There is **no separate memory-LOAD opcode**.

---

# 9. LOAD / LDI

Opcode:

```text
0x2
```

`LOAD` has exactly two architectural forms.

## 9.1 Immediate Load

For any operand other than `MAX`:

$$
A \leftarrow IR_{opr}
$$

The assembler MAY spell this:

```asm
LOAD 0x42
```

or:

```asm
LDI 0x42
```

Both assemble to the same instruction:

```text
opcode = 0x2
operand = 0x42
```

No data-memory access occurs.

This is the preferred primitive for constructing constants.

---

## 9.2 Indirect Memory Load

When:

$$IR_{opr}=MAX$$

the instruction means:

$$
A \leftarrow Memory[C:D]
$$

The assembler form is:

```asm
LOAD 0xFF        ; W = 8
```

or, preferably for clarity:

```asm
LOAD [C:D]
```

The bracketed form is assembler syntax only; the encoded operand remains `MAX`.

This is the sole base-ISA memory-read form.

---

## 9.3 Rationale

The distinction is intentional:

```text
LOAD 0x42     → constant
LOAD MAX      → memory[C:D]
```

Thus one opcode supplies both constant loading and memory reading without requiring an additional addressing-mode bit.

Memory reads therefore occur only when explicitly requested.

---

# 10. STORE

Opcode:

```text
0x3
```

For an operand other than `MAX`:

$$
Memory[C:IR_{opr}] \leftarrow A
$$

For `MAX`:

$$
Memory[C:D] \leftarrow A
$$

Therefore:

```asm
STORE 0x20        ; Memory[C:0x20] ← A
STORE MAX         ; Memory[C:D]    ← A
```

or, using assembler notation:

```asm
STORE [C:D]
```

for the indirect form.

Unlike `LOAD`, `STORE` always performs a memory write.

---

# 11. MOV

Opcode:

```text
0x1
```

The operand contains two 2-bit register IDs:

$$
operand = (dst \ll 2) \mid src
$$

Valid IDs are:

```text
0x0 = A
0x1 = B
0x2 = C
0x3 = D
```

Execution:

$$
R[dst] \leftarrow R[src]
$$

`MOV` cannot directly access `FLAGS`, `PC`, or `PR`.

Those registers are accessed through `PUSH` and `POP`.

---

# 12. Branch Instructions

## 12.1 Local Branch

For `JMP`, `JZ`, and `JC`, an operand other than `MAX` is a page-local target.

For `JMP`:

$$
PC \leftarrow IR_{opr}
$$

For `JZ`:

$$
PC \leftarrow
\begin{cases}
IR_{opr}, & ZF=1\
PC_{seq}, & ZF=0
\end{cases}
$$

For `JC`:

$$
PC \leftarrow
\begin{cases}
IR_{opr}, & CF=1\
PC_{seq}, & CF=0
\end{cases}
$$

`PR` is unchanged by a local branch.

---

## 12.2 Far Branch

When:

$$IR_{opr}=MAX
$$

the target is `C:D`:

$$
PR \leftarrow C
$$

$$
PC \leftarrow D
$$

This update is atomic.

The assembler syntax MAY be:

```asm
JMP MAX
```

or:

```asm
JMP C:D
```

The latter is assembler notation for the sentinel encoding.

The same rule applies to `JZ MAX` and `JC MAX`.

---

# 13. CALL and RET

## 13.1 CALL

`CALL` is page-local.

Before changing `PC`, the sequential return offset is pushed:

$$
Stack[SP] \leftarrow PC_{seq}
$$

$$
SP \leftarrow (SP+1)\bmod 2^K
$$

$$
PC \leftarrow IR_{opr}
$$

`PR` is unchanged.

Because the return address is `PC_seq`, a `CALL` whose opcode begins at the final `W`-bit instruction position cannot be represented as a page-local call with a same-page return address.

Therefore a conforming assembler MUST reject:

```text
CALL at PC = 2^W - 2
```

unless a future ISA revision explicitly defines a different call convention.

---

## 13.2 RET

`RET` performs the inverse operation:

$$
SP \leftarrow (SP-1)\bmod 2^K
$$

$$
PC \leftarrow Stack[SP]
$$

`PR` is unchanged.

---

## 13.3 Far Calls

The base ISA does not add a separate far-call instruction.

A far call is constructed from existing primitives.

Software is responsible for preserving the caller's program page and establishing the target page. A conventional sequence is:

```asm
PUSH PR
LOAD target_page
MOV C,A
LOAD target_offset
MOV D,A
JMP MAX
```

The callee can return to the original page using a software-defined convention that restores `PR` and returns the saved offset.

This intentionally avoids adding a dedicated far-call opcode.

---

# 14. PUSH and POP

`PUSH` and `POP` use a 3-bit target identifier.

```text
Bit 2 = 0 → general register
Bit 2 = 1 → system register
```

|   ID  | Target   |
| :---: | :------- |
| `0x0` | `A`      |
| `0x1` | `B`      |
| `0x2` | `C`      |
| `0x3` | `D`      |
| `0x4` | `FLAGS`  |
| `0x5` | `PC`     |
| `0x6` | `PR`     |
| `0x7` | Reserved |

The remaining operand bits are ignored and SHOULD be encoded as zero.

---

## 14.1 PUSH

$$
Stack[SP] \leftarrow Target
$$

$$
SP \leftarrow (SP+1)\bmod 2^K
$$

`PUSH FLAGS` stores the architecturally visible flags value.

---

## 14.2 POP

$$
SP \leftarrow (SP-1)\bmod 2^K
$$

$$
Target \leftarrow Stack[SP]
$$

`POP FLAGS` is the only non-ALU instruction capable of modifying `FLAGS`.

`POP PC` changes only `PC`.

`POP PR` changes only `PR`.

No implicit interaction between `PC` and `PR` occurs for `POP`.

This permits explicit software control over far transfers.

---

# 15. ALU

Opcode:

```text
0x4
```

The operand directly selects the ALU operation.

The ALU operates on `A` and `B`.

Unless otherwise stated:

$$
A \leftarrow f(A,B)
$$

and `ZF` is set according to the resulting `A`.

---

## 15.1 ALU Encoding

| Operand | Mnemonic | Operation               | CF           |
| :-----: | :------- | :---------------------- | :----------- |
|  `0x00` | `ADD`    | `A ← A + B`             | Carry out    |
|  `0x01` | `SUB`    | `A ← A - B`             | Borrow out   |
|  `0x02` | `AND`    | `A ← A & B`             | `0`          |
|  `0x03` | `OR`     | `A ← A \| B`            | `0`          |
|  `0x06` | `XOR`    | `A ← A ^ B`             | `0`          |
|  `0x08` | `INC`    | `A ← A + 1`             | Unchanged    |
|  `0x09` | `DEC`    | `A ← A - 1`             | Unchanged    |
|  `0x0A` | `SHL`    | `A ← A << 1`            | Original MSB |
|  `0x0B` | `SHR`    | `A ← A >> 1`            | Original LSB |
|  `0x0C` | `ROL`    | Rotate left through CF  | Original MSB |
|  `0x0D` | `ROR`    | Rotate right through CF | Original LSB |
|  `0x0E` | `CMP`    | Compare `A` with `B`    | Borrow       |
|  `0x0F` | `TST`    | Test `A & B`            | `0`          |

Unassigned ALU sub-opcodes are reserved and MUST NOT be assigned architectural meaning by an implementation.

---

## 15.2 Zero Flag

For all ALU operations that produce a result:

$$
ZF' =
\begin{cases}
1,&A'=0\
0,&A'\ne0
\end{cases}
$$

For `CMP`:

$$
ZF=1 \iff A=B
$$

For `TST`:

$$
ZF=1 \iff (A\land B)=0
$$

---

## 15.3 Carry / Borrow Flag

For arithmetic operations, `CF` is defined as follows.

### ADD

`CF` is the carry out of bit `W-1`.

### SUB and CMP

`CF` is the borrow condition:

$$
CF=1 \iff A < B
$$

This definition is normative.

### INC / DEC

`CF` is preserved.

This allows software to perform loop counters without destroying a previously established carry condition.

---

## 15.4 Shifts

### SHL

$$
A'=(A\ll1)\bmod2^W
$$

$$
CF'=A[W-1]
$$

### SHR

$$
A'=A\gg1
$$

$$
CF'=A[0]
$$

---

## 15.5 Rotates Through Carry

### ROL

$$
A'=(A\ll1)\mid CF_{old}
$$

$$
CF'=A_{old}[W-1]
$$

### ROR

$$
A'=(A\gg1)\mid(CF_{old}\ll(W-1))
$$

$$
CF'=A_{old}[0]
$$

---

# 16. I/O

Opcode:

```text
0xC
```

`IO` is reserved for implementation-defined peripheral access.

The base ISA does not impose a specific port width, bus protocol, or peripheral map.

A conforming implementation MAY define `IO` semantics provided that implementation-defined behavior is documented.

`IO` does not modify `FLAGS` unless the implementation's documented extension explicitly specifies otherwise.

---

# 17. HLT

Opcode:

```text
0xF
```

`HLT` stops architectural execution.

The implementation MUST cease advancing the instruction phase sequence.

The precise mechanism used to stop the clock is microarchitectural and implementation-defined.

An external reset or implementation-defined wake mechanism MAY resume execution.

---

# 18. Reserved Opcodes

Opcodes:

```text
0xD
0xE
```

are reserved.

A base μ-Core implementation MUST NOT assign them additional architectural instructions.

Future revisions MAY define them.

For forward compatibility, software intended to run on multiple ISA revisions MUST NOT depend on their behavior.

---

# 19. Instruction Timing and Memory Access

Every instruction consumes exactly one four-phase instruction cycle:

```text
T0 → T1 → T2 → T3
```

Instruction fetch always requires the two mandatory memory reads at `T0` and `T1`.

Data-memory operations are additional only where required by the instruction.

| Instruction        |    Data-memory read    |    Data-memory write   |
| :----------------- | :--------------------: | :--------------------: |
| `NOP`              |           No           |           No           |
| `MOV`              |           No           |           No           |
| `LOAD imm` / `LDI` |         **No**         |           No           |
| `LOAD MAX`         |         **Yes**        |           No           |
| `STORE`            |           No           |         **Yes**        |
| `ALU`              |           No           |           No           |
| Branches           |           No           |           No           |
| `CALL`             |           No           |           No           |
| `RET`              |       Stack read       |           No           |
| `PUSH`             |           No           |       Stack write      |
| `POP`              |       Stack read       |           No           |
| `IO`               | Implementation-defined | Implementation-defined |
| `HLT`              |           No           |           No           |

This distinction is architecturally important.

`LDI` does **not** perform a data-memory read.

A memory read occurs only for:

```asm
LOAD MAX
```

which accesses:

```text
Memory[C:D]
```

---

# 20. Atomicity

All architectural state changes produced by one instruction become visible at the `T3` commit edge.

An implementation MUST behave as though the following sequence occurs:

```text
T0: fetch
T1: fetch
T2: evaluate
T3: commit
```

even if the physical implementation uses a different internal circuit arrangement.

In particular, an instruction MUST NOT expose an intermediate state in which:

* `PC` has changed but its associated branch state has not;
* `PR` has changed but `PC` has not for a far branch;
* `SP` has changed without the corresponding stack operation;
* a register has partially changed;
* `FLAGS` contains a mixture of old and new flag bits.

---

# 21. FLAGS Preservation

The following instructions preserve `FLAGS`:

```text
NOP
MOV
LOAD / LDI
STORE
JMP
JZ
JC
CALL
RET
PUSH
POP (except POP FLAGS)
IO
HLT
```

The following modify `FLAGS`:

```text
ALU
POP FLAGS
```

For `POP FLAGS`, only bits 0 and 1 are architecturally retained.

Thus:

$$
FLAGS[1:0] \leftarrow Stack[SP][1:0]
$$

and:

$$
FLAGS[W-1:2]=0
$$

---

# 22. Addressing Summary

The base ISA deliberately exposes only three useful data-addressing forms:

### Immediate

```asm
LOAD value
LDI value
```

Result:

$$
A \leftarrow value
$$

### Page-relative direct store

```asm
STORE offset
```

Result:

$$
Memory[C:offset]\leftarrow A
$$

### C:D indirect access

```asm
LOAD MAX
STORE MAX
```

Results:

$$
A\leftarrow Memory[C:D]
$$

$$
Memory[C:D]\leftarrow A
$$

The architecture therefore requires only:

```text
C register
D register
one offset mux
one MAX detector
one memory data path
```

No general-purpose addressing-mode decoder is required.

---

# 23. Example Memory Operations

For `W = 8`:

```asm
LDI 0x42
MOV D,A
LDI 0x80
MOV C,A
LOAD 0xFF
```

results in:

```text
A = Memory[0x8042]
```

More directly, if the desired address is already in `C:D`:

```asm
LOAD 0xFF
```

performs:

```text
A ← Memory[C:D]
```

To write:

```asm
STORE 0xFF
```

performs:

```text
Memory[C:D] ← A
```

---

# 24. Dynamic Program Loading

Because instruction and data memory are unified, software can construct executable code in RAM.

A loader can:

1. Set `C` to the destination page.
2. Set `D` to successive offsets.
3. Place instruction bytes/words into memory using `STORE`.
4. Set `C:D` to the program entry point.
5. Execute `JMP MAX`.

The far jump performs:

$$
PR\leftarrow C
$$

$$
PC\leftarrow D
$$

and execution subsequently continues from the newly selected RAM address.

No special loader, executable-memory instruction, or code/data distinction is required by the ISA.

---

# 25. Page Boundary Rules

Sequential execution is the only operation that implicitly changes `PR`.

For every ordinary sequential instruction:

$$
PC' = PC+2
$$

If the addition wraps:

$$
PR' = PR+1
$$

Otherwise:

$$
PR'=PR
$$

A local `JMP`, `JZ`, `JC`, `CALL`, or `RET` changes `PC` only.

A far branch using `MAX` changes both:

$$
PR'=C
$$

$$
PC'=D
$$

This distinction is intentional and prevents hidden page-register side effects.

---

# 26. CALL Boundary Rule

A page-local `CALL` stores the sequential `PC` value.

Because instructions are two SUs wide, the last valid `CALL` position is:

$$
PC \le 2^W-4
$$

The position:

$$
PC=2^W-2
$$

is not a valid location for `CALL`.

For `W=8`:

```text
0xFC  valid CALL
0xFE  CALL prohibited
```

The assembler/linker SHOULD diagnose this condition.

No runtime exception mechanism is required.

---

# 27. Architectural Invariants

A conforming implementation MUST satisfy all of the following.

### Invariant I — Fixed Instruction Size

Every instruction occupies exactly two SUs.

### Invariant II — Fixed Four-Phase Timing

Every instruction occupies exactly one `T0..T3` execution cycle.

### Invariant III — Sequential PC Advance

Normal sequential execution advances by exactly two SUs.

### Invariant IV — Explicit Page Changes

Only sequential page rollover and explicit far transfer modify `PR`.

### Invariant V — C:D Data Address

All indirect data accesses use exactly:

$$
C:D
$$

### Invariant VI — Unified Memory

Instruction and data accesses address the same logical memory space.

### Invariant VII — Single LOAD Opcode

Opcode `0x2` is the sole load opcode.

For `operand != MAX`:

$$
A\leftarrow operand
$$

For `operand = MAX`:

$$
A\leftarrow Memory[C:D]
$$

`LDI` is only an assembler alias for the former.

### Invariant VIII — Sentinel Reservation

`MAX` is reserved for indirect/far forms and MUST NOT represent an ordinary direct operand in an instruction that defines a `MAX` special case.

### Invariant IX — Circular Stack

Stack addressing is modulo `2^K`.

No stack overflow or underflow exception exists.

### Invariant X — Untyped Stack

Stack entries are raw `W`-bit values.

### Invariant XI — Flag Preservation

Only ALU operations and `POP FLAGS` modify `FLAGS`.

### Invariant XII — Atomic Commit

Architectural effects become visible atomically at `T3`.

### Invariant XIII — Determinism

Given identical initial architectural state and identical memory/peripheral inputs, conforming implementations produce identical architectural results.

### Invariant XIV — Parameter Independence

Changing `W` or `K` within their permitted ranges does not alter the instruction encoding structure or the abstract semantics of existing instructions.

---

# 28. Minimal Hardware Interpretation

The ISA is intentionally implementable using a small set of fundamental blocks:

```text
                 ┌───────────────┐
                 │ Instruction   │
                 │ Memory        │
                 └───────┬───────┘
                         │
                  ┌──────▼──────┐
                  │ IR / Decode │
                  └──────┬──────┘
                         │
       ┌─────────────────┼──────────────────┐
       │                 │                  │
 ┌─────▼─────┐     ┌─────▼─────┐      ┌────▼─────┐
 │ Registers │────►│    ALU    │◄─────│  FLAGS   │
 │ A B C D   │     └─────┬─────┘      └──────────┘
 └─────┬─────┘           │
       │                 A
       │
 ┌─────▼─────────────────────────┐
 │        Address MUX             │
 │                                │
 │ Instruction: PR : PC           │
 │ Data direct: C  : operand      │
 │ Data indirect: C  : D          │
 └──────────────┬─────────────────┘
                │
          ┌─────▼─────┐
          │ Unified   │
          │ Memory    │
          └───────────┘

          ┌───────────┐
          │ Stack RAM │
          │ 2^K × W   │
          └─────┬─────┘
                │
               SP
```

No general-purpose address register is required.

No separate instruction-memory interface is architecturally required.

No stack bounds logic is required.

No branch-condition instruction-specific flag hardware is required beyond the `ZF` and `CF` bits.

No dedicated immediate-load datapath is required beyond the existing operand-to-A path.

---

# 29. Design Rationale

The apparent dual meaning of `LOAD` is intentional.

The encoding space is scarce, while immediate constants are extremely common. Requiring an additional opcode merely to distinguish immediate loading from memory loading would increase decoder complexity without adding fundamental capability.

The `MAX` sentinel provides a simple discriminator:

```text
LOAD x       → A = x
LOAD MAX     → A = Memory[C:D]
```

The same mechanism already exists for `STORE` and far branches:

```text
STORE x      → Memory[C:x] = A
STORE MAX    → Memory[C:D] = A

JMP x        → PC = x
JMP MAX      → PR:PC = C:D
```

Thus `MAX` acts as a single, consistent escape value rather than introducing independent addressing-mode encodings.

The result is a small and regular machine:

```text
Immediate values  → operand field
Local addresses   → operand field
Indirect address  → C:D
Far address       → C:D
ALU second input  → B
Stack state       → SP + stack RAM
```

This is consistent with the μ-Core design objective:

> **Simple enough to understand completely; small enough to build without unnecessary machinery.**

---

# 30. Canonical Assembly Notation

For clarity, assemblers SHOULD accept the following canonical forms:

```asm
NOP

MOV A,B
MOV C,D

LDI 0x42
LOAD 0x42

LOAD [C:D]
LOAD MAX

STORE 0x20
STORE [C:D]
STORE MAX

ADD
SUB
AND
OR
XOR
INC
DEC
SHL
SHR
ROL
ROR
CMP
TST

JMP 0x40
JMP [C:D]
JMP MAX

JZ 0x40
JZ [C:D]
JZ MAX

JC 0x40
JC [C:D]
JC MAX

CALL 0x40
RET

PUSH A
PUSH B
PUSH C
PUSH D
PUSH FLAGS
PUSH PC
PUSH PR

POP A
POP B
POP C
POP D
POP FLAGS
POP PC
POP PR

IO 0x00

HLT
```

`LDI` and `LOAD` with a non-`MAX` operand are identical encodings.

`[C:D]` is assembler notation for the `MAX` sentinel encoding and does not consume additional instruction bits.

---

# 31. Compatibility with v1.2.6

Version 1.3.0 retains the architectural structure of v1.2.6:

* four general-purpose registers;
* `FLAGS`, `PC`, and `PR`;
* parameterized circular stack;
* unified `2W`-bit memory;
* fixed two-SU instructions;
* four-phase execution;
* `MAX` sentinel;
* local and far branches;
* page-local `CALL`/`RET`;
* `PUSH`/`POP` extended target selection;
* ALU and flag contracts;
* reserved `0xD` and `0xE` opcodes;
* `IO` and `HLT`.

The principal semantic clarification introduced by v1.3.0 is opcode `0x2`:

```text
v1.2.6:
    LOAD offset      → memory load
    LOAD [D]         → indirect memory load

v1.3.0:
    LOAD immediate   → immediate load (LDI)
    LOAD MAX         → indirect memory load through C:D
```

Consequently, v1.3.0 deliberately removes the separate direct-memory `LOAD offset` form.

This provides immediate loading while retaining exactly one memory-read mechanism and exactly one sentinel-based indirect addressing mechanism.

---

# 32. Conformance

A μ-Core implementation, emulator, assembler, linker, debugger, or compiler backend claiming conformance to v1.3.0 MUST implement the normative semantics defined herein.

Where this specification uses:

* **MUST / SHALL:** architectural requirement;
* **MUST NOT / SHALL NOT:** architectural prohibition;
* **SHOULD:** recommended behavior;
* **MAY:** permitted implementation or tooling choice.

Microarchitectural implementation is otherwise unrestricted.

Two conforming implementations MAY differ internally in:

* register technology;
* memory technology;
* clock generation;
* bus implementation;
* stack RAM implementation;
* combinational versus registered datapaths;
* physical memory decoding;
* I/O implementation;

provided that they expose identical architectural behavior.

---

# Appendix A — Opcode Map

```text
0x0  NOP
0x1  MOV
0x2  LOAD / LDI
0x3  STORE
0x4  ALU
0x5  JMP
0x6  JZ
0x7  JC
0x8  CALL
0x9  RET
0xA  PUSH
0xB  POP
0xC  IO
0xD  RESERVED
0xE  RESERVED
0xF  HLT
```

# Appendix B — Register Target Map

```text
0x0  A
0x1  B
0x2  C
0x3  D
0x4  FLAGS
0x5  PC
0x6  PR
0x7  RESERVED
```

# Appendix C — The μ-Core in One Page

```text
DATAPATH
    A B C D              W bits each
    FLAGS                W bits
    PC PR                W bits each
    SP                   K bits
    STACK                2^K × W

MEMORY
    2^W pages
    2^W SUs per page
    2^(2W) total SUs

INSTRUCTION
    [ W-bit OPCODE ][ W-bit OPERAND ]

ADDRESSING
    Program = PR:PC
    Data    = C:offset
    Indirect= C:D when operand == MAX

LOAD
    LOAD x       → A ← x
    LOAD MAX     → A ← Memory[C:D]
    LDI x        → alias for LOAD x

STORE
    STORE x      → Memory[C:x] ← A
    STORE MAX    → Memory[C:D] ← A

BRANCH
    JMP x        → PC ← x
    JMP MAX      → PR:PC ← C:D

STACK
    PUSH         → write at SP, SP++
    POP          → SP--, read at SP
    modulo 2^K

FLAGS
    ALU          → updates ZF/CF
    POP FLAGS    → restores ZF/CF
    everything else preserves them

TIMING
    T0 fetch opcode
    T1 fetch operand
    T2 evaluate
    T3 commit
```

**End of μ-Core ISA Specification v1.3.0**

