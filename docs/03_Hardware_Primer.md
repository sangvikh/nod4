# The μ-Core Architecture Manifesto & Hardware Primer

*"A simple computer architecture designed to outlive its implementation."*

---

## Welcome to μ-Core!

μ-Core is a minimalist, parameterized Instruction Set Architecture (ISA) engineered for long-term stability, hardware economy, and complete binary determinism.

While the formal **ISA Specification (v1.1.0)** and **ABI Specification (v1.1.0)** define the rigid normative standards for hardware builders and toolchain authors, this primer provides the pedagogical narrative, architectural rationale, and hardware tricks that make μ-Core tick.

---

## 1. The Core Philosophy

### 1. Modules Before Gates

Rather than designing around individual logic gates, μ-Core specifies self-contained functional modules connected by standardized buses:

* **Accumulator & ALU Block** (A, B, FLAGS)
* **Instruction Counter Block** (PR:PC)
* **Data RAM Addressing Block** (C:D)
* **Hardware Stack Controller** (SP, D_stack)

You can build your ALU out of 74HC TTL chips today, replace it with discrete transistors tomorrow, and run an FPGA implementation next week—**without changing a single byte of compiled software**.

### 2. Predictability Over Maximum Efficiency

Modern CPUs introduce complex pipeline stalls, out-of-order execution, and non-uniform instruction timings. μ-Core prioritizes absolute determinism:

* **Fixed 2-Storage-Unit Instructions** (2W bits: Opcode + Operand) across all datapath widths W.
* **Uniform 4-Phase Architectural Cycles (T0, T1, T2, T3)** for every instruction.
* **Explicit Snapshot Mechanics:** State transitions sample snapshot variables at T2 and commit atomically at T3.

---

## 2. Hardware Design Highlights & TTL Tricks

### Trick #1: C:D Addressing (64 KiB Space, 8-Bit Datapath)

Addressing 64 KiB of Data RAM on an 8-bit datapath without a 16-bit adder is accomplished by splitting address generation across two ordinary 8-bit registers:

* **Register `C` (High Byte):** Serves as the static Data Page selector.
* **Register `D` (Low Byte):** Serves as the fast offset pointer.

```text
        16-bit Physical RAM Address Bus (A15 .. A0)
     ┌──────────────────────────┬──────────────────────────┐
     │ High Address (A15 .. A8) │  Low Address (A7 .. A0)  │
     └────────────▲─────────────┴────────────▲─────────────┘
                  │                          │
         ┌────────┴─────────┐       ┌────────┴─────────┐
         │  Register C Page │       │ Register D / Inst│
         │     (74HC574)    │       │   MUX (74HC157)  │
         └──────────────────┘       └──────────────────┘

```

The output of Register `C` wires directly to address pins A15..A8 of the Data RAM chip. Address pins A7..A0 are fed by a 2-to-1 Multiplexer (74HC157) switching between the instruction operand byte (for direct access `LOAD $05`) and Register `D` (for indirect access `LOAD [D]`).

---

### Trick #2: The `$FF` Dual Escape Sentinel

In μ-Core, the sentinel value **`$FF` (or `MAX`)** provides two fundamental escape capabilities with zero extra opcode bloat:

1. **Indirect Memory Gateway (`LOAD MAX` / `STORE MAX`):** Switches the Data RAM address MUX to select Register `D`, accessing location C:D.
2. **Cross-Page Far Jump (`JMP MAX` / `JZ MAX` / `JC MAX`):** Sets Page Register PR <- C and Program Counter PC <- D.

```text
 Operand Bus (D7 .. D0)
 ───┬───┬───┬───┬───┬───┬───┬───
    │   │   │   │   │   │   │   │
 ┌──┴───┴───┴───┴───┴───┴───┴───┴─┐
 │    74HC30 8-Input NAND Gate    │
 └───────────────┬────────────────
                 │ (Low when Operand == $FF)
                 ▼
        Addr MUX Select Line ──────► [ 0 = Instruction Operand | 1 = Register D ]

```

---

### Trick #3: 2-Bit Opcode Class Decoding (ISA v1.1.0)

Primary opcodes are logically grouped by their top two bits (`bits [3:2]`), simplifying instruction decoding:

| Opcode Class (`[3:2]`) | Primary Opcodes | Functional Category | Hardware Subsystem Triggered |
| --- | --- | --- | --- |
| **`00xx`** | `0x0`..`0x3` (`NOP`, `MOV`, `LOAD`, `STORE`) | **Memory & Register Data** | Triggers Register File bus / Data RAM Read/Write lines. |
| **`01xx`** | `0x4`..`0x7` (`ALU`, `JMP`, `JZ`, `JC`) | **ALU & Control Branches** | Enables ALU function generator or PC branch target load. |
| **`10xx`** | `0x8`..`0xB` (`CALL`, `RET`, `PUSH`, `POP`) | **Stack & Call Control** | Direct active-high enable for Hardware Stack Pointer (SP). |
| **`11xx`** | `0xC`..`0xF` (`IO`, `RSVD1`, `RSVD2`, `HLT`) | **System Control & I/O** | Activates Peripheral I/O bus or halts timing clock generator. |

---

## 3. Annotated Bus Walkthroughs

### Example 1: Summing Numbers in a Loop (1 to 5)

Data RAM initialization: Literal constant `$05` is pre-stored at offset `$F0` in Data RAM page C.

```assembly
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; 0x00    0x1     0x01      MOV B, A       ; Copy A into B (Flags unchanged)
; 0x02    0x4     0x06      ALU XOR        ; A <- A XOR B (Clears Accumulator A = 0)
; 0x04    0x3     0x10      STORE $10      ; RAM[C:$10] <- 0 (Initialize sum in RAM)  ; 0x06    0x2     0xF0      LOAD $F0       ; A <- 5 (Fetch pre-stored literal $05)
; 0x08    0x1     0x01      MOV B, A       ; B <- 5 (Set B as loop index counter)
;
; --- LOOP HEAD (Offset 0x0A) ---
; 0x0A    0x2     0x10      LOAD $10       ; Fetch running sum into Accumulator A
; 0x0C    0x4     0x00      ALU ADD        ; A <- A + B (Add current loop index)
; 0x0E    0x3     0x10      STORE $10      ; Write updated sum back to RAM[C:$10]
; 0x10    0x1     0x04      MOV A, B       ; Copy index counter B into Accumulator A
; 0x12    0x4     0x09      ALU DEC        ; A <- A - 1 (Decrements index; updates ZF)
; 0x14    0x1     0x01      MOV B, A       ; Store decremented index back in B
; 0x16    0x6     0x1A      JZ $1A         ; If ZF == 1, jump to DONE (Offset 0x1A)
; 0x18    0x5     0x0A      JMP $0A        ; Otherwise, jump back to LOOP HEAD
;
; --- DONE (Offset 0x1A) ---
; 0x1A    0x2     0x10      LOAD $10       ; Load final sum (15 / $0F) into Accumulator A
; 0x1C    0xF     0x00      HLT            ; Freeze execution clock phases

```

---

### Example 2: Page-Local Subroutine Call (`CALL` / `RET`)

Pursuant to **ABI v1.1.0**, Register `A` passes arguments, Register `B` holds secondary arguments, and Register `C` is strictly callee-saved. Pre-stored literal `$07` resides at `$F0`.

```assembly
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; --- MAIN ROUTINE ---
; 0x00    0x2     0xF0      LOAD $F0       ; A <- 7 (Fetch parameter from $F0)
; 0x02    0x8     0x08      CALL $08       ; Hardware Stack[SP] <- 0x04; PC <- 0x08
; 0x04    0x3     0x20      STORE $20      ; Store returned result (14 / $0E) to RAM
; 0x06    0xF     0x00      HLT            ; Freeze execution clock
;
; --- SUBROUTINE: MULT_BY_TWO (Offset 0x08) ---
; 0x08    0xA     0x02      PUSH C         ; Save caller's Data High Register C on Stack
; 0x0A    0x1     0x01      MOV B, A       ; B <- 7 (Copy input parameter)
; 0x0C    0x4     0x00      ALU ADD        ; A <- A + B (7 + 7 = 14)
; 0x0E    0xB     0x02      POP C          ; Restore caller's Data High Register C
; 0x10    0x9     0x00      RET            ; PC <- Popped return address (0x04)

```

---

### Example 3: Cross-Page Domain Transfer (`JMP MAX`)

Demonstrates a cross-page domain switch between Application Domain (Page 1) and Math Domain (Page 2) using `JMP MAX` (`0x05 0xFF`). Pre-stored literal `$42` resides at `$F0`.

```assembly
; ===================================================================
; INSTRUCTION PAGE 0x01 (APPLICATION DOMAIN)
; ===================================================================
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; 0x00    0x2     0xF0      LOAD $F0       ; A <- 42 (Fetch parameter)
; 0x02    0x1     0x01      MOV B, A       ; Pass argument in Register B (B <- 42)
; 0x04    0x2     0xF1      LOAD $F1       ; Load Page 2 target ID (2) 
; 0x06    0x1     0x08      MOV C, A       ; C <- 2 (Set target Page ID) 
; 0x08    0x2     0xF2      LOAD $F2       ; Load Page 2 entry offset (0x00)
; 0x0A    0x1     0x0C      MOV D, A       ; D <- 0x00 (Set target offset)
; 0x0C    0x5     0xFF      JMP [D]        ; Far Jump! PR <- C (2), PC <- D (0x00)
;
; --- RESUME ENTRY POINT (Offset 0x0E) ---
; 0x0E    0x2     0x05      LOAD $05       ; Fetch result (43 / $2B) stored by Page 2
; 0x10    0xF     0x00      HLT            ; Freeze execution clock (SUCCESS!)

; ===================================================================
; INSTRUCTION PAGE 0x02 (MATH WORKER DOMAIN)
; ===================================================================
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; 0x00    0x1     0x04      MOV A, B       ; Copy incoming argument from B into A
; 0x02    0x4     0x08      ALU INC        ; A <- A + 1 (Compute 43 / $2B)
; 0x04    0x3     0x05      STORE $05      ; Store result in RAM[C:$05]
; 0x06    0x2     0xF3      LOAD $F3       ; Load Page 1 return ID (1) 
; 0x08    0x1     0x08      MOV C, A       ; C <- 1 (Set return Page ID) 
; 0x0A    0x2     0xF4      LOAD $F4       ; Load Page 1 return offset (0x0E)
; 0x0C    0x1     0x0C      MOV D, A       ; D <- 0x0E (Set return offset)
; 0x0E    0x5     0xFF      JMP [D]        ; Far Return! PR <- C (1), PC <- D (0x0E)

```

---

## 4. Where to Go From Here?

Now that you have the conceptual mental model and explicit bus semantics, you are ready to dive into the exact engineering standards or build software toolchains:

1. **Read the Formal ISA Specification (v1.1.0):** Complete bit-level definitions of all 16 opcodes, 16 ALU operations, flag semantics, and stack underflow/overflow rules.
2. **Read the Application Binary Interface (v1.1.0):** Register preservation rules, caller/callee contracts, shared mailbox structures, and assembly idioms.
3. **Run the Assembler Toolchain:** Use `ucore_asm.py` to translate assembly source files directly into binary instruction images and literal pool initializers.

**Welcome to μ-Core! Have fun building software and wiring chips!**
