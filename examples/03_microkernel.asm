; ===================================================================
; μ-CORE EXAMPLE 03: STACK-BASED CROSS-PAGE FAR CALLS (ABI v1.1.0)
; ===================================================================
; Demonstrates reentrant, stack-based domain switching between:
;   - Page 0x01: Application Domain (Caller)
;   - Page 0x02: Math Kernel Service Domain (Callee)
;
; Compile:
;   python3 toolchain/asm/ucore_asm.py examples/03_microkernel.asm -o build/
; Run Emulator:
;   python3 toolchain/asm/ucore_emu.py build/03_microkernel.bin
; ===================================================================

; -------------------------------------------------------------------
; INSTRUCTION PAGE 0x01: APPLICATION DOMAIN
; -------------------------------------------------------------------
APP_START:
    ; --- STEP 1: PREPARE FAR CALL RETURN LINKAGE ON STACK ---
    LI A, #$01          ; Return Page ID (PR = 0x01)
    PUSH A              ; Stack[0] <- PR_return (Pushed 1st)
    
    LI A, #APP_RESUME   ; Return Instruction Offset
    PUSH A              ; Stack[1] <- PC_return (Pushed 2nd)

    ; --- STEP 2: SET UP ARGUMENTS ---
    LI A, #18           ; Parameter 1 = 18
    LI B, #24           ; Parameter 2 = 24

    ; --- STEP 3: EXECUTE FAR JUMP TO KERNEL SERVICE (Page 0x02, Offset 0x00) ---
    LI C, #$02          ; C <- Kernel Service Page ID (0x02)
    LI D, #$00          ; D <- Kernel Service Entry Offset (0x00)
    JMP MAX             ; Far Jump! PR <- $02, PC <- $00

APP_RESUME:
    ; --- STEP 4: PROCESS KERNEL RETURN RESULT ---
    ; Execution resumes here after Kernel performs FRET.
    ; Result (18 + 24 = 42 / 0x2A) is waiting in Accumulator A.
    STORE $10           ; Save result into RAM[C:$10]
    HLT                 ; Execution Complete!

; -------------------------------------------------------------------
; INSTRUCTION PAGE 0x02: MATH KERNEL SERVICE DOMAIN
; (In a real system, assembled into a separate binary page image)
; -------------------------------------------------------------------
KERNEL_ADD_SERVICE:
    ; --- KERNEL COMPUTATION ---
    ALU ADD             ; A <- A + B (18 + 24 = 42)

    ; --- REENTRANT FAR RETURN TO CALLER ---
    FRET                ; Expands to: POP D -> POP C -> JMP MAX

