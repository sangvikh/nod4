; ===================================================================
; Example 1: Sum Numbers from 1 to 5
; Accumulator A holds running sum; Register B holds index counter
; ===================================================================

INIT:
    MOV B, A            ; B <- A
    ALU XOR             ; A <- A XOR B (Clear Accumulator A = 0)
    STORE $10           ; RAM[C:$10] = 0 (Initialize Sum in Data RAM)
    
    LI A, #5            ; Materialize Constant 5 into A via Literal Pool
    MOV B, A            ; B <- 5 (Loop Index Counter)

LOOP:
    ; Add current index B into accumulated sum at RAM[C:$10]
    LOAD $10            ; Load current running sum into A
    ALU ADD             ; A <- sum + B
    STORE $10           ; Save updated sum back to RAM[C:$10]
    
    ; Decrement Loop Index B
    MOV A, B            ; Move index into Accumulator A to work on it
    ALU DEC             ; A <- A - 1 (Decrements index; updates Zero Flag)
    MOV B, A            ; Move updated index back to B
    
    JZ DONE             ; If Index reaches 0, branch out of loop!
    JMP LOOP            ; Otherwise, loop again

DONE:
    LOAD $10            ; Bring final result (15 / $0F) into Accumulator A
    HLT                 ; Halt CPU execution
