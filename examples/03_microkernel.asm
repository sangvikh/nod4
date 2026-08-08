; ===================================================================
; Example 3: Page 0 Microkernel & Page 1 State-Machine Router
; Demonstrates how EXEC domain switches use Offset 0x00 Entry Routers
; ===================================================================

; ===================================================================
; INSTRUCTION PAGE 0x00: SYSTEM KERNEL DOMAIN
; ===================================================================

; -------------------------------------------------------------------
; Offset 0x00: KERNEL ENTRY ROUTER (EXEC $00 target)
; -------------------------------------------------------------------
KERNEL_ENTRY:
    LOAD $00            ; Read Command ID from Shared Mailbox [00:$00]
    JZ BOOT_RESET       ; If Command == 0 -> Perform Cold Boot Reset!
    JMP SYSCALL_ROUTER  ; If Command != 0 -> Service System Call!

BOOT_RESET:
    MOV B, A
    ALU XOR             ; Clear Accumulator A
    STORE $00           ; Clear Mailbox Command
    EXEC $01            ; Launch User Application on Page 1!

SYSCALL_ROUTER:
    LOAD $01            ; Read System Call Parameter from Mailbox [00:$01]
    IO 0, OUT           ; Service I/O Request: Write payload to Port 0
    
    MOV B, A
    ALU XOR
    STORE $00           ; Clear Mailbox Command (A = 0)
    EXEC $01            ; Return domain execution back to User Page 1!


; ===================================================================
; INSTRUCTION PAGE 0x01: USER APPLICATION DOMAIN
; ===================================================================

; -------------------------------------------------------------------
; Offset 0x00: USER ENTRY ROUTER (EXEC $01 target)
; -------------------------------------------------------------------
USER_ENTRY:
    LOAD $01            ; Read User Continuation Stage variable [C:$01]
    JZ USER_STAGE_0     ; Stage 0 -> First time initialization
    JMP USER_STAGE_1    ; Stage 1 -> Resuming post-syscall!

USER_STAGE_0:
    LI A, #1
    STORE $01           ; Set Local Stage Variable = 1 (Post-syscall resume point)
    
    LI A, #42
    STORE $05           ; Store payload (42) into Mailbox parameter [00:$05]
    LI A, #1
    STORE $00           ; Store Syscall Command ID = 1 into Mailbox [00:$00]
    
    EXEC $00            ; Trigger Kernel Trap! (EXEC Page 0)

USER_STAGE_1:
    ; --- CONTROL RESUMES HERE AFTER KERNEL SERVICES REQUEST ---
    HLT                 ; Application Complete

```
