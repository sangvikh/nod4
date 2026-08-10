# μ-Core Software & ABI Specification (v1.1.0)

**Status:** Frozen Reference Standard (Normative)

---

### 1. Purpose & Architectural Layering

This specification defines the standard **Application Binary Interface (ABI)** and software conventions for programs running on μ-Core processors conforming to **ISA Specification v1.1.0**.

Software conventions are organized into three distinct, normative layers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 1: Application Binary Interface                                  │
│ • Register Roles (Scratch vs. Preserved)                               │
│ • Page-Local Subroutine Calling Convention (CALL / RET)                │
│ • FLAGS Preservation & Caller-Saved Contract                           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│ Layer 2: Cross-Page Transfer Protocols (JMP MAX)                       │
│ • Direct Coordinate Far Jumps (JMP MAX / JZ MAX / JC MAX)              │
│ • Stack-Based Far Call & Reentrant Return Protocol                     │
│ • Memory-Topology Agnostic Parameter Passing & Register Volatility     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│ Layer 3: Canonical Assembly & Toolchain Conventions                    │
│ • Constant Materialization (LI Pseudo-Instruction)                     │
│ • Literal Data Page Pool Allocation ($F0..$FE)                         │
│ • Multi-Byte Arithmetic Mechanics under Flag Preservation Law          │
└────────────────────────────────────────────────────────────────────────┘

```

---

### 2. Layer 1: Application Binary Interface (ABI)

#### Standard Register Roles

During a page-local subroutine invocation (`CALL` / `RET` within an active Memory Page PR), registers are partitioned into **Scratch (Caller-Saved)** and **Preserved (Callee-Saved)**:

| Register | ABI Classification | Standard Purpose |
| --- | --- | --- |
| **`A`** | **Scratch (Caller-Saved)** | Primary scalar argument passed in; primary scalar return value out. |
| **`B`** | **Scratch (Caller-Saved)** | Secondary argument passed in; general scratch register. |
| **`C`** | **Preserved (Callee-Saved)** | Data Address High Register / Active Data Page Selector. A local function modifying `C` **must** restore `C` prior to `RET`. For far jumps (`JMP MAX`), `C` serves as target Page ID (PR). |
| **`D`** | **Scratch (Caller-Saved)** | Data Address Low Register / Offset Pointer. For far jumps (`JMP MAX`), `D` serves as target instruction offset (PC). |

#### FLAGS Register Contract

* **FLAGS (ZF, CF) are Caller-Saved.**
* Subroutines are not required to preserve ZF or CF across a `CALL`. Callers requiring flags to survive a subroutine call must save them explicitly using `PUSH FLAGS` prior to `CALL` and restore them using `POP FLAGS` afterward.

#### Local Subroutine Calling Convention

1. **Argument Passing:** Primary parameter in `A`, secondary parameter in `B`.
2. **Page Integrity:** The caller assumes `C` is preserved across a local `CALL`. If the callee alters `C` internally to access alternate Data RAM pages, it must execute `PUSH C` upon entry and `POP C` prior to `RET`.
3. **Return Values:** Primary scalar return result placed in `A`.
4. **Scratch Volatility:** Registers `A`, `B`, `D`, and `FLAGS` are assumed destroyed across a `CALL`.

```assembly
; ===================================================================
; CALLER ROUTINE (Page PR = $01)
; ===================================================================
    LOAD ADDR_PARAM     ; A <- Parameter
    CALL ADD_FIVE       ; Local call (Pushes return PC to Hardware Stack)
    STORE ADDR_RESULT   ; Save result waiting in A

; ===================================================================
; CALLEE ROUTINE (In same Memory Page PR = $01)
; ===================================================================
ADD_FIVE:
    PUSH C              ; Preserved: Save caller's Data High Register C
    MOV B, A            ; B <- Parameter
    LI A, #5            ; A <- 5
    ALU ADD             ; A <- A + B (5 + Parameter)
    POP C               ; Preserved: Restore caller's Data High Register C
    RET                 ; Return to caller (Pops return PC)

```

---

### 3. Layer 2: Cross-Page Transfer Protocols (`JMP MAX`)

Under **ISA v1.1.0**, hardware `CALL` and `RET` instructions operate strictly page-locally (preserving Page Register PR). Cross-page execution transfers and far calls execute natively using the `MAX` escape sentinel (`$FF` on μ8):

JMP MAX => PR <- C_orig, PC <- D_orig

#### Hardware Reset Vector Invariant

Hardware `RESET` unconditionally forces PR <- $00 and PC <- $00. Instruction Page 0 Offset `$00` is strictly reserved as the **Hardware Reset & Boot Vector**. Software shall place system initialization logic starting at Offset `$00`.

Data Page C = $00 may reside in Read-Only Memory (ROM) alongside boot instruction code. Software shall not assume Data Page C = $00 is writable RAM.

#### Stack-Based Far Call Protocol

Because the Hardware Stack is a unified global namespace that persists across Page Register (PR) switches, cross-page subroutine calls use the Hardware Stack for reentrant return tracking.

##### 1. Stack Order & LIFO Layout

The caller pushes Return Page ID (PR_return) **first**, followed by Return Offset (PC_return) **second**. The callee pops PC_return into Register `D` **first**, and PR_return into Register `C` **second**:

```text
  Hardware Stack (LIFO Order)
  ┌──────────────────────────────────────────┐
  │ Top of Stack ->  PC_return  (Pushed 2nd) │ ──> Popped 1st into D
  │                  PR_return  (Pushed 1st) │ ──> Popped 2nd into C
  └──────────────────────────────────────────┘

```

##### 2. Step-by-Step Far Call Procedure

1. **Push Return Coordinates:** Caller executes `PUSH PR_return`, then `PUSH PC_return`.
2. **Setup Target Coordinates:** Caller sets Register `C` <- Target Page ID, Register `D` <- Target Offset.
3. **Execute Far Jump:** Caller executes `JMP MAX` (`JMP [D]`).
4. **Execute Far Return:** Target service executes `POP D` (restoring PC_return), `POP C` (restoring PR_return), and `JMP MAX` (`JMP [D]`), or uses the assembler pseudo-instruction `FRET`.

#### Register Volatility, FLAGS, & Pointer Parameters

* **C and D Volatility:** Registers `C` and `D` are **clobbered by the caller during far call setup**. Unlike local calls where `C` is callee-saved, far calls destroy caller values in `C` and `D`.
* **FLAGS Volatility:** FLAGS (ZF, CF) are caller-saved across far calls.
* **Stack Depth Limits:** Far calls push two entries onto the stack. For a stack depth of N entries, the maximum far call nesting depth is floor(N / 2). Software must ensure stack limits are respected.
* **Pointer & Buffer Ownership:** Multi-byte datasets or struct arguments are passed as pointer coordinates in RAM. Pointer memory is caller-owned; callees may read or modify buffer contents, but callers retain memory lifetime management.
* **Passing Pointers across Far Calls:** Because Register `C` is required for the target Page ID during `JMP MAX`, pointer high-page addresses must be passed in Register `B` (e.g., Buffer Page in `B`, Buffer Offset in `D`, Target Page loaded into `C` last).

```assembly
; ===================================================================
; CALLER DOMAIN (Page PR = $01)
; Invoking MATH_ADD on Page $02 at Offset $10
; ===================================================================
    ; 1. Push Far Return Coordinates onto Hardware Stack (PR first, PC second)
    LI A, #$01          ; PR_return = $01
    PUSH A              ; Stack[0] <- PR_return
    LI A, #RESUME       ; PC_return = RESUME offset
    PUSH A              ; Stack[1] <- PC_return

    ; 2. Pass scalar arguments in A and B
    LI A, #15           ; Argument 1
    LI B, #27           ; Argument 2

    ; 3. Setup Far Jump target (PR = $02, PC = $10)
    LI C, #$02          ; C <- Target Page ID ($02)
    LI D, #$10          ; D <- Target Entry Offset ($10)
    JMP MAX             ; Far Jump! PR <- $02, PC <- $10

RESUME:
    ; Execution resumes here; result is waiting in Accumulator A
    STORE $20
    HLT

; ===================================================================
; TARGET SERVICE (Page PR = $02, Entry Offset $10)
; ===================================================================
MATH_ADD:
    ALU ADD             ; A <- A + B (15 + 27 = 42)

    ; --- REENTRANT FAR RETURN (via FRET pseudo-instruction or explicit pops) ---
    FRET                ; Expands to: POP D -> POP C -> JMP MAX

```

---

### 4. Layer 3: Canonical Assembly & Toolchain Conventions

#### Toolchain Pseudo-Instructions (`LI`, `FRET`)

A conforming assembler provides standard toolchain abstractions:

* **`LI reg, #value` (Load Immediate):** Generates a `LOAD $literal_offset` primitive into Accumulator A, followed by a `MOV reg, A` if target is not `A`.
* **`FRET` (Far Return):** Generates the 3-instruction return sequence: `POP D` -> `POP C` -> `JMP MAX`.
* **Literal Data Pool Invariant:** Literal values are allocated sequentially within offsets **`$F0..$FE`** of the module's Data Page.

#### Multi-Byte Arithmetic Mechanics (W=8)

Pursuant to **ISA v1.1.0 (Flag Preservation Law)**, non-ALU instructions (`LOAD`, `STORE`, `MOV`, `PUSH`, `POP`) leave CF and ZF strictly untouched. Multi-byte addition and subtraction propagate CF cleanly across memory operations without requiring temporary flag storage:

```assembly
; ===================================================================
; 16-BIT ADDITION: [C:$00..$01] + [C:$02..$03] -> Result [C:$04..$05]
; ===================================================================
    ; 1. Low Byte Addition
    LOAD $00            ; Read Low Byte 1 (Flags UNCHANGED)
    MOV B, A            ; B <- Low Byte 1 (Flags UNCHANGED)
    LOAD $02            ; Read Low Byte 2 (Flags UNCHANGED)
    ALU ADD             ; A <- Low1 + Low2 (Updates ZF and CF)
    STORE $04           ; Store Low Result (CF PRESERVED)

    ; 2. High Byte Addition with Carry
    LOAD $01            ; Read High Byte 1 (CF PRESERVED)
    MOV B, A            ; B <- High Byte 1 (CF PRESERVED)
    LOAD $03            ; Read High Byte 2 (CF PRESERVED)
    ALU ADC             ; A <- High1 + High2 + CF
    STORE $05           ; Store High Result

```

