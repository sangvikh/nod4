Here is the updated `README.md` including `ucore_dis.py` across the repository structure, architecture overview, and toolchain workflows:

```markdown
# μ-Core Architecture Specification (v1.1.0)

> **A simple, modular computer architecture designed to outlive its physical implementation.**

[![Specification: Frozen v1.1.0](https://img.shields.io/badge/ISA%20%26%20ABI-v1.1.0%20Frozen-blue.svg)](docs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

μ-Core (uCore) is a minimalist, parameterized Instruction Set Architecture (ISA) engineered for maximum clarity, hardware economy, and long-term stability. Whether implemented on 74HC TTL logic breadboards, FPGA soft-cores, discrete transistor cards, or software emulators, μ-Core maintains strict, deterministic binary compatibility.

---

## 🌟 Key Architectural Features

* **Fixed 2-Unit Instruction Format:** Every instruction across all execution widths ($W$) occupies exactly two Storage Units ($2W$ bits: $\text{Opcode} + \text{Operand}$), driven by a uniform 4-phase architectural cycle ($T_0..T_3$).
* **Data Page $C:D$ Addressing:** Accesses up to $2^{2W}$ locations (64 KiB on μ8) without requiring multi-byte ALUs or multi-cycle address calculations.
* **The `MAX` Escape Sentinel:** Uses a single logical sentinel (`$FF` on μ8) to provide indirect data addressing (`LOAD [D]`) and cross-page far jumps (`JMP [D]`) with zero extra opcode bloat or modal bits.
* **Flag Preservation Law:** Non-ALU instructions (`LOAD`, `STORE`, `MOV`, `PUSH`, `POP`, `IO`) leave $ZF$ and $CF$ strictly untouched, enabling portable multi-precision arithmetic chains.
* **Page-Local Subroutine & Untyped Stack:** `CALL` and `RET` operate strictly page-locally within active Page Register $PR$. Reentrant cross-page domain switches execute far jumps via `JMP MAX` ($PR \leftarrow C, \text{PC} \leftarrow D$) using the global hardware stack for return linkage (`FRET`).

---

## 📁 Repository Structure

```text
ucore-architecture/
├── README.md                   # High-level overview & project guide
├── docs/
│   ├── 01_ISA_Manifest_v1.1.0.md  # Formal Hardware Specification (Normative)
│   ├── 02_ABI_Standard_v1.1.0.md  # Formal Software Cooperation Specification (Normative)
│   └── 03_Hardware_Primer.md      # Conceptual Guide, TTL Logic & Pedagogy
├── toolchain/
│   └── asm/
│       ├── ucore_asm.py           # Conforming Two-Pass Python Assembler
│       ├── ucore_dis.py           # Conforming Python Disassembler
│       └── ucore_emu.py           # Reference Interactive Python Emulator
└── examples/
    ├── 01_loop_sum.asm            # Basic arithmetic & branching loop
    ├── 02_subroutine.asm          # Page-local call conventions & callee-saved rules
    └── 03_microkernel.asm         # Cross-page domain switch & stack-based far calls

```

---

## 📖 Specifications Overview

The architecture is organized into three distinct, non-overlapping normative layers:

1. **[ISA Specification v1.1.0](docs/01_ISA_Manifest_v1.1.0.md):** The normative hardware contract. Defines opcodes, instruction timings, flag semantics, memory namespaces, and hardware stack behavior.
2. **[ABI Specification v1.1.0](docs/02_ABI_Standard_v1.1.0.md):** The normative software contract. Defines register volatility ($A, B, D$ scratch; $C$ preserved), `CALL`/`RET` local subroutine conventions, and `JMP MAX` / `FRET` far-jump protocols.
3. **[Hardware Primer & Manifesto](docs/03_Hardware_Primer.md):** The pedagogical narrative. Explains design decisions, $74\text{HC}$ TTL breadboard implementation tricks, and $C:D$ RAM paging.

---

## ⚡ Assembly Quickstart

Here is how multi-byte addition works under μ-Core assembly:

```assembly
; ===================================================================
; 16-BIT ADDITION: Add [C:$00..$01] to [C:$02..$03] -> Result [C:$04..$05]
; (Pursuant to Flag Preservation Law: LOAD/STORE preserve Carry Flag!)
; ===================================================================
    ; 1. Low Byte Addition
    LOAD $00            ; Read Low Byte 1 (Flags UNCHANGED)
    MOV B, A            ; B <- Low Byte 1 (Flags UNCHANGED)
    LOAD $02            ; Read Low Byte 2 (Flags UNCHANGED)
    ALU ADD             ; A <- Low1 + Low2 (Updates ZF and CF)
    STORE $04           ; Store Low Result (CF PRESERVED)

    ; 2. High Byte Addition with Carry
    LOAD $01            ; Read High Byte 1 (CF PRESERVED!)
    MOV B, A            ; B <- High Byte 1 (CF PRESERVED!)
    LOAD $03            ; Read High Byte 2 (CF PRESERVED!)
    ALU ADC             ; A <- High1 + High2 + CF
    STORE $05           ; Store High Result

```

---

## 🛠️ Toolchain Usage

The toolchain relies on standard Python 3.8+ with zero external dependencies.

```bash
# 1. Assemble source into binary instruction image (.bin)
python3 toolchain/asm/ucore_asm.py examples/01_loop_sum.asm -o build/ -v

# 2. Disassemble binary image into human-readable assembly instructions
python3 toolchain/asm/ucore_dis.py build/01_loop_sum.bin

# 3. Run simulation in interactive CLI emulator
python3 toolchain/asm/ucore_emu.py build/01_loop_sum.bin

```

### Disassembler Options (`ucore_dis.py`)

```bash
# Disassemble specifying a base PC offset
python3 toolchain/asm/ucore_dis.py build/01_loop_sum.bin --base 0x00

```

---

## 📜 License

This specification and reference software are open-source and released under the [MIT License](https://en.wikipedia.org/wiki/MIT_License).

