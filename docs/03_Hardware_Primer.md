# The μ-Core Architecture Manifesto & Hardware Primer
*"A simple computer architecture designed to outlive its implementation."*

---

## Welcome to μ-Core!

If you’ve ever opened a modern x86 or ARM manual, you know the feeling: thousands of pages, hundreds of execution modes, complex microcode pipelines, and proprietary black boxes. 

μ-Core was born out of a simple question: **Can we design an Instruction Set Architecture (ISA) so clear, minimal, and orthogonal that a single person could wire it on breadboards over a weekend, write a full C-like compiler for it, and still run the exact same binary on a relay computer, an FPGA, or a Python emulator decades from now?**

The answer is **yes**. 

This primer is the "front door" to μ-Core. While the formal **ISA Specification (v1.0.0)** and **ABI Specification (v1.0.0)** provide the rigid contracts for compiler authors and hardware engineers, this guide explains the *why*, the *how*, and the *hardware tricks* that make μ-Core tick.

---

## 1. The Core Philosophy

### 1. Modules Before Gates
In classic CPU construction, people often start by placing individual NAND gates or flip-flops. μ-Core starts at a higher abstraction level: **Functional Modules**. 

Your CPU is just a collection of self-contained blocks connected by standard buses:
* An **Accumulator & ALU Block**
* A **Program Counter (PC) & Page Register ($PR$) Block**
* A **Data RAM Page Controller ($C:D$)**
* A **Hardware Stack Counter (SP)**

Because the interfaces between these modules are strictly defined, you can build your ALU out of 74HC TTL chips today, replace it with a discrete transistor card tomorrow, and wire a relay module next month—**without changing a single wire on the rest of the machine or altering a single byte of compiled code**.

### 2. Predictability Over Maximum Efficiency
Modern CPUs push clock speeds by using variable-length instructions, deep branch predictors, and non-uniform instruction timing. On a breadboard or logic analyzer, this makes debugging an absolute nightmare.

μ-Core chooses absolute determinism:
* **Fixed 2-byte instructions** (for μ8) across every execution cycle.
* **Uniform 4-phase execution cycles ($T_0, T_1, T_2, T_3$)** for every single instruction.
* **No hidden modal state.** There are no implicit "16-bit mode vs 8-bit mode" states or undocumented addressing modes. Every instruction has a single, explicitly defined architectural meaning.

### 3. The 2-Byte Orthogonal Grammar
Every instruction in μ8 fits cleanly into two 8-bit bytes:

$$\text{[ Opcode Nibble (4 bits) \vert{} Reserved Bits ]} \quad \text{[ Operand Byte (8 bits) ]}$$

By keeping the primary opcode to four bits, the instruction decoder can be implemented directly with a single 4-to-16 decoder such as a 74HC154. It eliminates complex multi-stage instruction decoding entirely while providing a clean, extensible architectural footprint.

---

## 2. Hardware Design Highlights & TTL Tricks

### Trick #1: The $C:D$ Paging Magic (64 KiB Space, 8-Bit ALU)
How do you address 64 KiB of Data RAM on an 8-bit computer without building a massive 16-bit adder circuit?

μ-Core splits address generation into two ordinary 8-bit registers:
* **Register `C` (High Byte):** Acts as the static "Data Page" selector.
* **Register `D` (Low Byte):** Acts as the fast offset or array index.

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

On a breadboard, you wire the output of Register `C` directly to the upper 8 address pins ($\text{A}_{15}..\text{A}_8$) of your RAM chip. The lower 8 address pins ($\text{A}_7..\text{A}_0$) are fed by a simple 2-to-1 Multiplexer ($74\text{HC}157$) that switches between the instruction operand byte (for direct access like `LOAD $05`) and Register `D` (for indirect access like `LOAD [D]`).

**Zero extra ALU cycle timing required!**

---

### Trick #2: The `$FF` Indirect Escape (Free Pointer Addressing)

In most architectures, adding register-indirect addressing (`LOAD [D]`) requires a dedicated opcode or a complex addressing-mode byte. μ-Core gets this capability for free using a single logical sentinel: **`$FF` (or `MAX`)**.

* When `LOAD` sees any operand from `$00` to `$FE`, it fetches directly from $C:\text{Operand}$.
* When `LOAD` sees operand **`$FF`**, a single 8-input NAND gate ($74\text{HC}30$) on the operand bus detects all 1s and flips the address Multiplexer to select Register `D` instead!

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

*(Need to access direct memory offset `$FF`? Just set $D = \$FF$ and use indirect mode!)*

---

### Trick #3: 2-Bit Opcode Class Decoding

Because opcodes are grouped logically by their top two bits (bits `[3:2]` of the 4-bit opcode), gating subsystem enables on your breadboard requires almost no logic chips:

| Opcode Class (`[3:2]`) | Category | Subsystem Activated | Hardware Benefit |
| --- | --- | --- | --- |
| **`00xx`** | **Data & Memory** | RAM Bus / Register File | `001x` (`0x2`/`0x3`) directly triggers RAM Read/Write lines. |
| **`01xx`** | **ALU & Branches** | ALU / PC Branch Load | Bit 2 high enables ALU or Branch Evaluator. |
| **`10xx`** | **Hardware Stack** | Stack Counter (SP) | **Bits [3:2] = 10** is a direct active-high enable for the Hardware Stack! |
| **`11xx`** | **System & Control** | I/O & Page Switch | Triggers Peripheral Bus or $PR$ domain updates. |

---

## 3. Annotated Bus Walkthroughs (Native Primitives)

To aid hardware debugging on logic analyzers or oscilloscope probes, these examples list exact byte offsets, 2-byte instruction pairs (`[Opcode | Operand]`), and native primitives without assembler pseudo-instruction abstractions.

### Example 1: Summing Numbers in a Loop (1 to 5)

Data Page initialization: Literal constant `$05` is pre-stored at offset `$F0` in Data RAM.

```assembly
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; 0x00    0x1     0x01      MOV B, A       ; Copy A into B (Flags unchanged)
; 0x02    0x4     0x06      ALU XOR        ; A <- A XOR B (Clears Accumulator A = 0)
; 0x04    0x3     0x10      STORE $10      ; RAM[C:$10] <- 0 (Initialize sum in RAM) 
; 0x06    0x2     0xF0      LOAD $F0       ; A <- 5 (Fetch pre-stored literal $05)
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

### Example 2: Subroutine Call (`CALL` / `RET` - Same Page)

Pursuant to **ABI v1.0.0**, Register `A` passes primary arguments, Register `B` holds secondary arguments, and Register `C` is strictly callee-saved. Literal `$07` is pre-stored at offset `$F0`.

```assembly
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; --- MAIN ROUTINE ---
; 0x00    0x2     0xF0      LOAD $F0       ; A <- 7 (Fetch parameter from$F0)
; 0x02    0x8     0x08      CALL $08       ; Hardware Stack[SP] <- 0x04; PC <- 0x08
; 0x04    0x3     0x20      STORE $20      ; Store returned result (14 / $0E) to RAM
; 0x06    0xF     0x00      HLT            ; Freeze execution
;
; --- SUBROUTINE: MULT_BY_TWO (Offset 0x08) ---
; 0x08    0xA     0x02      PUSH C         ; Save caller's Page Register C on Stack
; 0x0A    0x1     0x01      MOV B, A       ; B <- 7 (Copy input parameter)
; 0x0C    0x4     0x00      ALU ADD        ; A <- A + B (7 + 7 = 14)
; 0x0E    0xB     0x02      POP C          ; Restore caller's Page Register C from Stack
; 0x10    0x9     0x00      RET            ; PC <- Popped Stack return address (0x04)

```

---

### Example 3: Domain Switch across Instruction Pages (`EXEC`)

Demonstrates a 2-stage state continuation router using `EXEC`. Literals: `$42` is pre-stored at `$F0`, `$01` is pre-stored at `$F1`.

```assembly
; ===================================================================
; INSTRUCTION PAGE 0x01 (APPLICATION DOMAIN)
; Literals: $42 pre-stored at RAM offset $F0, $01 pre-stored at RAM offset $F1
; ===================================================================
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; --- PAGE 1 ENTRY ROUTER (Offset 0x00) ---
; 0x00    0x2     0x01      LOAD $01       ; Read Stage variable from RAM[C:$01]
; 0x02    0x6     0x0A      JZ $0A         ; Stage == 0 -> Branch to FIRST_PASS (0x0A)
; 0x04    0x5     0x14      JMP $14        ; Stage != 0 -> Branch to POST_RETURN (0x14)
;
; --- FIRST_PASS (Offset 0x0A) ---
; 0x0A    0x2     0xF1      LOAD $F1       ; A <- 1
; 0x0C    0x3     0x01      STORE $01      ; RAM[C:$01] <- 1 (Set Stage = 1 for return)
; 0x0E    0x2     0xF0      LOAD $F0       ; A <- 42 (Fetch argument)
; 0x10    0x1     0x01      MOV B, A       ; Pass argument in Register B (B <- 42)
; 0x12    0xD     0x02      EXEC $02       ; PR <- 0x02; PC <- 0x00 (Jump to Page 2)
;
; --- POST_RETURN (Offset 0x14) ---
; 0x14    0x2     0x05      LOAD $05       ; Fetch result (43 / $2B) stored by Page 2
; 0x16    0xF     0x00      HLT            ; Freeze execution clock phases (SUCCESS!)

; ===================================================================
; INSTRUCTION PAGE 0x02 (MATH WORKER DOMAIN)
; ===================================================================
; Offset  Opcode  Operand   Mnemonic       Bus Behavior & Hardware State
; -------------------------------------------------------------------
; 0x00    0x1     0x04      MOV A, B       ; Copy incoming argument from B into A
; 0x02    0x4     0x08      ALU INC        ; A <- A + 1 (Compute 43 / $2B)
; 0x04    0x3     0x05      STORE $05      ; Store result in RAM[C:$05]
; 0x06    0xD     0x01      EXEC $01       ; PR <- 0x01; PC <- 0x00 (Return to Page 1)

```

---

## 4. Where to Go From Here?

Now that you have the conceptual mental model and explicit bus semantics, you are ready to dive into the exact engineering standards or build software toolchains:

1. **Read the Formal ISA Specification (v1.0.0):** Complete bit-level definitions of all 16 opcodes, 16 ALU operations, flag semantics, and stack underflow/overflow rules.
2. **Read the Application Binary Interface (v1.0.0):** Register preservation rules, caller/callee contracts, shared mailbox structures, and assembly idioms.
3. **Run the Assembler Toolchain:** Use `ucore_asm.py` to translate assembly source files directly into binary instruction images and literal pool initializers.

**Welcome to μ-Core! Have fun building software and wiring chips!**

