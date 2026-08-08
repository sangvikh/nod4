; ===================================================================
; Example 2: Subroutine Call & Local Stack Behavior
; Demonstrates CALL / RET and the ABI Callee-Saved Register C Contract
; ===================================================================

MAIN:
    LI A, #7            ; Load primary argument = 7
    CALL MULT_BY_TWO    ; Call subroutine (Pushes return PC to Hardware Stack)
    
    ; Result (14 / $0E) is waiting in Accumulator A!
    STORE $20           ; Save result to RAM[C:$20]
    HLT

; ===================================================================
; Subroutine: MULT_BY_TWO
; Input: A (number)
; Output: A (number * 2)
; ===================================================================
MULT_BY_TWO:
    PUSH C              ; ABI Contract: Preserve caller's Page Register C
    MOV B, A            ; B <- input number (7)
    ALU ADD             ; A <- A + B (7 + 7 = 14)
    POP C               ; ABI Contract: Restore caller's Page Register C
    RET                 ; Return to caller (Pops return PC from Hardware Stack)
