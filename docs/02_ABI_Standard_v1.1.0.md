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
│ Layer 2: Cross-Page & Domain Transfer Protocols (JMP MAX)              │
│ • Cross-Page Far Jumps (JMP MAX / JZ MAX / JC MAX)                     │
│ • Far Call/Return Control Block Conventions                            │
│ • Shared Mailbox Protocol (C = $00)                                    │
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

During a page-local subroutine invocation (`CALL` / `RET` within an active Memory Page $PR$), registers are partitioned into **Scratch (Caller-Saved)** and **Preserved (Callee-Saved)**:

| Register | ABI Classification | Standard Purpose |
| --- | --- | --- |
| **`A`** | **Scratch (Caller-Saved)** | Primary scalar argument passed in; primary scalar return value out. |
| **`B`** | **Scratch (Caller-Saved)** | Secondary argument passed in; general scratch register. |
| **`C`** | **Preserved (Callee-Saved)** | Data Address High Register / Active Data Page Selector. A local function modifying `C` **must** restore `C` prior to `RET`. For far jumps (`JMP MAX`), `C` serves as target Page ID ($PR$). |
| **`D`** | **Scratch (Caller-Saved)** | Data Address Low Register / Offset Pointer. For far jumps (`JMP MAX`), `D` serves as target instruction offset ($\text{PC}$). |

#### FLAGS Register Contract

* **FLAGS ($ZF, CF$) are Caller-Saved.**
* Subroutines are not required to preserve $ZF$ or $CF$ across a `CALL`. Callers requiring flags to survive a subroutine call must save them explicitly using `PUSH FLAGS` prior to `CALL` and restore them using `POP FLAGS` afterward.

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

Under **ISA v1.1.0**, hardware `CALL` and `RET` operations are strictly page-local (preserving Page Register $PR$). Cross-page domain transfers and far jumps are executed natively using the `MAX` escape sentinel (`$FF` on μ8):

$$\text{JMP MAX} \implies PR \leftarrow C_{orig}, \quad \text{PC} \leftarrow D_{orig}$$

#### Cross-Page Subroutine / Far Return Convention

Because `JMP MAX` is an unconditional control transfer that does not push a return address, cross-page function calls rely on software cooperation via the **Shared Mailbox**:

1. **Setup Far Return Address:** Prior to executing a far jump, the calling domain writes its Return Page ID ($PR_{caller}$) and Return Offset ($\text{PC}_{return}$) into the designated Mailbox Control Block.
2. **Execute Far Jump:** The caller sets $C \leftarrow C_{target}$ and $D \leftarrow D_{target}$, then executes `JMP [D]` (`JMP MAX`).
3. **Execute Far Return:** Upon completion, the target domain reads the caller's return destination into $C$ and $D$, then executes `JMP [D]` (`JMP MAX`) to resume caller execution.

#### Shared Mailbox Protocol & Layout

Data Page $C = \$00$ offsets `$00..$0F` are designated as the **Shared System Mailbox**:

```text
  Data Space (Page C = $00)
  +─────────────────────────────────────────+
  | Offset $00      : Syscall / Command ID  | <── Command Identifier
  | Offset $01      : Return Page ID (PR)   | <── Far Return Destination Page
  | Offset $02      : Return Offset (PC)    | <── Far Return Destination Offset
  | Offset $03      : Status / Response Code| <── Execution Result Status
  | Offset $04..$0F : Parameter Payload     | <── Multi-byte Parameters
  | Offset $10..$FF : Module Private RAM    | <── Workspace for Kernel / Page 0
  +─────────────────────────────────────────+

```

---

### 4. Layer 3: Canonical Assembly & Toolchain Conventions

#### Toolchain Pseudo-Instruction (`LI`)

A conforming assembler provides a **`LI A, #value`** (Load Immediate) pseudo-instruction.

* `LI` is a toolchain abstraction, generating a `LOAD $literal_offset` primitive.
* **Literal Data Pool Invariant:** Literal values are allocated sequentially within offsets **`$F0..$FE`** of the module's Data Page.

#### Multi-Byte Arithmetic Mechanics ($W=8$)

Pursuant to **ISA v1.1.0 (Flag Preservation Law)**, non-ALU instructions (`LOAD`, `STORE`, `MOV`, `PUSH`, `POP`) leave $CF$ and $ZF$ strictly untouched. Multi-byte addition and subtraction propagate $CF$ cleanly across memory operations without requiring temporary flag storage:

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

