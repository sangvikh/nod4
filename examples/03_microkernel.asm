; ===================================================================
; Example 3: Cross-Page Domain Switch & Microkernel System Call
; Conforms to μ-Core ISA v1.1.0 & ABI v1.1.0
; Demonstrates Far Control Transfers via JMP MAX (C:D)
; ===================================================================

; ===================================================================
; INSTRUCTION PAGE 0x01: USER APPLICATION DOMAIN
; ===================================================================
USER_START:
    ; 1. Prepare System Call arguments in Shared Mailbox [00:$04]
    LI A, #42           ; Payload = 42
    STORE $04           ; Mailbox[00:$04] = 42

    ; 2. Set Syscall Command ID in Mailbox [00:$00]
    LI A, #1            ; Command ID = 1 (Print Payload)
    STORE $00           ; Mailbox[00:$00] = 1

    ; 3. Setup Far Return Control Block in Shared Mailbox
    LI A, #1            ; Return Page ID = 1
    STORE $01           ; Mailbox[00:$01] = Return Page
    LI A, #USER_RESUME  ; Return PC Offset = USER_RESUME
    STORE $02           ; Mailbox[00:$02] = Return Offset

    ; 4. Execute Far Jump to Kernel Domain (Page 0, Offset KERNEL_SYSCALL)
    LI A, #0            ; Target Page ID = 0 (Kernel)
    MOV C, A            ; C <- 0
    LI A, #KERNEL_SYSCALL ; Target Offset = KERNEL_SYSCALL
    MOV D, A            ; D <- KERNEL_SYSCALL
    JMP [D]             ; JMP MAX (Far Jump -> Page 0, KERNEL_SYSCALL)

USER_RESUME:
    ; --- Execution resumes here after Kernel completes system call ---
    HLT                 ; Application complete


; ===================================================================
; INSTRUCTION PAGE 0x00: KERNEL DOMAIN
; ===================================================================
KERNEL_SYSCALL:
    ; 1. Read Syscall Payload from Shared Mailbox [00:$04]
    LOAD $04            ; A <- Mailbox Payload (42)

    ; 2. Output Payload to Peripheral Port 0
    IO 0, OUT           ; Send payload to Port 0

    ; 3. Clear Syscall Command in Mailbox
    LI A, #0
    STORE $00           ; Mailbox Command = 0 (Idle)

    ; 4. Read Return Destination from Mailbox Control Block
    LOAD $01            ; Read Return Page ID (1)
    MOV C, A            ; C <- Return Page ID (1)
    LOAD $02            ; Read Return Offset (USER_RESUME)
    MOV D, A            ; D <- Return Offset

    ; 5. Execute Far Return Jump back to User Application
    JMP [D]             ; JMP MAX (Far Return -> Page C, Offset D)

