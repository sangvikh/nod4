# μ-Core Software & ABI Specification (v1.0.0)
**Status:** Frozen Reference Standard (Normative)

---

### 1. Purpose & Architectural Layering

This specification defines the standard **Application Binary Interface (ABI)** and programming conventions for software running on μ-Core processors conforming to **ISA Manifest v1.0.0**.

Software conventions are organized into three distinct, normative layers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 1: Application Binary Interface                                  │
│ • Register Roles (Scratch vs. Preserved)                               │
│ • Local Subroutine Calling Convention (CALL / RET)                      │
│ • FLAGS Preservation & Caller-Saved Contract                           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│ Layer 2: Domain Transfer Protocols                                     │
│ • Inter-Module Domain Switching (EXEC) & Page Entry Routers            │
│ • Shared Mailbox Ownership & Dispatcher Patterns                       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│ Layer 3: Canonical Assembly & Toolchain Conventions                    │
│ • Constant Materialization & Multi-Byte Arithmetic Mechanics           │
│ • Literal Data Page Invariant ($F0..$FE Allocation)                    │
└────────────────────────────────────────────────────────────────────────┘

```

---

### 2. Layer 1: Application Binary Interface (ABI)

#### Standard Register Roles

During a local subroutine invocation (`CALL` / `RET` within a Memory Page), registers are partitioned into **Scratch (Caller-Saved)** and **Preserved (Callee-Saved)**:

| Register | ABI Classification | Standard Purpose |
| --- | --- | --- |
| **`A`** | **Scratch (Caller-Saved)** | Primary argument passed in; primary return result out. |
| **`B`** | **Scratch (Caller-Saved)** | Secondary argument passed in; scratch register inside function. |
| **`C`** | **Preserved (Callee-Saved)** | Active Data Page Selector. A function that modifies `C` **must** restore `C` prior to `RET`. |
| **`D`** | **Scratch (Caller-Saved)** | Data Offset Pointer or Indirect Gateway target (`[D]`). |

#### FLAGS Register Contract

* **FLAGS ($ZF, CF$) are Caller-Saved.**
* Subroutines are not required to preserve ZF or CF across a `CALL` unless explicitly documented by a specialized function contract. Callers requiring ZF or CF to survive a subroutine call must save them explicitly using `PUSH FLAGS` prior to `CALL` and restore them using `POP FLAGS` afterward.

#### Local Subroutine Calling Convention

1. **Argument Passing:** The caller places the primary parameter in `A` and secondary parameter in `B`.
2. **Page Integrity:** The caller does not save `C`. If the callee alters `C` internally to access local data, the callee must execute `PUSH C` upon entry and `POP C` prior to `RET`.
3. **Return Values:** The callee places its primary scalar return value in `A`.
4. **Scratch Registers:** Registers `A`, `B`, `D`, and `FLAGS` are assumed destroyed across a `CALL`.

```assembly
; ===================================================================
; CALLER ROUTINE
; ===================================================================
    LOAD ADDR_PARAM     ; A <- Parameter
    CALL ADD_FIVE       ; Subroutine call (SP pushes return PC)
    STORE ADDR_RESULT   ; Save result waiting in A

; ===================================================================
; CALLEE ROUTINE (In same Memory Page)
; ===================================================================
ADD_FIVE:
    PUSH C              ; Preserved: Save caller's C register
    MOV B, A            ; B <- Parameter
    LOAD ADDR_CONST_5   ; A <- 5
    ALU ADD             ; A <- A + B (5 + Parameter)
    POP C               ; Preserved: Restore caller's C register
    RET                 ; Return to caller

```

---

### 3. Layer 2: Domain Transfer Protocols (`EXEC`)

Because `EXEC` is an explicit 1-way domain switch ($\text{PR} ← \text{Operand}, \text{PC} ← 0×00$) that does not push a hardware return address, cross-page interaction follows standardized software domain entry routers.

#### Page Entry Router Rule

**Normative Invariant:** Every memory page that receives `EXEC` transfers must place a **State-Machine Entry Router** starting at **Offset $0×00$**.

Because `EXEC` unconditionally forces $\text{PC} ← 0×00$:

1. **Memory Page $0×00$ (System Kernel):** The entry router at $0×00$ inspects Mailbox Command Offset `[00:$00]`.
* If Mailbox Command is `0`, execution branches to `BOOT_RESET`.
* If Mailbox Command is non-zero, execution branches to `SYSCALL_ROUTER`.


2. **User Pages ($0×01+$):** The entry router at $0×00$ inspects a Module Execution Stage variable stored in local Data RAM (`[C:$01]`).
* If Stage is `0`, execution runs initial setup.
* If Stage is non-zero, execution branches to the appropriate post-syscall continuation handler.



#### Shared Mailbox Protocol & Ownership Rules

For modules exchanging structured datasets, Data Page $C = \$00$ offsets `$00..$0F` are designated as the **Shared System Mailbox**:

```text
  Data Space (Page C = $00)
  +─────────────────────────────────────────+
  | Offset $00..$03 : Domain Control Block  | <── Return Page IDs & Status Codes
  | Offset $04..$0F : Parameter Payload     | <── Multi-byte Arguments
  | Offset $10..$FF : Module Private Space  | <── Scratch workspace for Page 0
  +─────────────────────────────────────────+

```

* **Transaction Ownership:** A mailbox region is strictly owned by the initiating domain for the duration of a synchronous domain-transfer transaction.
* **Consumption Contract:** A receiving service domain shall not overwrite control or parameter fields until it has consumed them.

---

### 4. Layer 3: Canonical Assembly & Toolchain Conventions

#### Toolchain Pseudo-Instruction Convention (`LI`)

A conforming assembler toolchain provides a **`LI A, #value`** (Load Immediate) pseudo-instruction.

* `LI` is a **toolchain/assembler abstraction**, not an ISA instruction or binary primitive.
* **Literal Data Page Invariant:** A conforming toolchain allocates literal values within the **Literal Data Pool** located at offsets **`$F0..$FE`** of the module's Data Page. Expansion of `LI A, #value` generates a `LOAD $literal_offset` instruction. Software must ensure Register $C$ addresses the module's active Data Page prior to executing `LI`.

#### Multi-Byte Arithmetic Mechanics ($W=8$)

Pursuant to **ISA v1.0.0 (Flag Preservation Law)**, `LOAD`, `STORE`, and `MOV` leave CF and ZF unchanged. Multi-byte addition and subtraction maintain CF across load/store boundaries without requiring flag-preservation workarounds:

```assembly
; ===================================================================
; 16-BIT ADDITION: Add [C:$00..$01] to [C:$02..$03] -> Result [C:$04..$05]
; ===================================================================
    ; 1. Low Byte Addition
    LOAD $00            ; Read Low Byte 1 (Flags UNCHANGED)
    MOV B, A            ; B <- Low Byte 1 (Flags UNCHANGED)
    LOAD $02            ; Read Low Byte 2 (Flags UNCHANGED)
    ALU ADD             ; A <- Low1 + Low2 (Sets ZF and CF)
    STORE $04           ; Store Low Result (CF PRESERVED)

    ; 2. High Byte Addition with Carry
    LOAD $01            ; Read High Byte 1 (CF PRESERVED!)
    MOV B, A            ; B <- High Byte 1 (CF PRESERVED!)
    LOAD $03            ; Read High Byte 2 (CF PRESERVED!)
    ALU ADC             ; A <- High1 + High2 + CF
    STORE $05           ; Store High Result

```


