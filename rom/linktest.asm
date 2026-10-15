; linktest.gb: first-light test ROM for gb-link-usb.
; The Game Boy is the serial SLAVE (external clock): the Pico clocks every byte.
; Each transfer: the GB sends `next`, receives a byte, then sets next = received + 1.
; So if the PC sends A, B, C it gets back $42, A+1, B+1.
; Screen: row 2 = last received byte (hex), row 4 = transfer count (hex).
; Registers per Pan Docs: SB $FF01 data, SC $FF02 (bit 7 start, bit 0 = 0 external clock).

DEF rSB   EQU $FF01
DEF rSC   EQU $FF02
DEF rLCDC EQU $FF40
DEF rLY   EQU $FF44
DEF rBGP  EQU $FF47
DEF BLANK EQU 16              ; tile index of the empty tile

SECTION "vars", WRAM0
wNext:  ds 1
wLast:  ds 1
wCount: ds 2                  ; little-endian

SECTION "entry", ROM0[$100]
    nop
    jp Main
    ds $150 - @, 0            ; header, filled in by rgbfix

SECTION "main", ROM0[$150]
Main:
    di
    ld sp, $DFFF
    call WaitVBlank
    xor a
    ldh [rLCDC], a            ; LCD off: free VRAM access

    ; font: 16 hex digits + 1 blank tile, 1 bpp source -> 2 bpp (same byte twice = black)
    ld hl, $8000
    ld de, Font
    ld b, 17 * 8
.font:
    ld a, [de]
    inc de
    ld [hl+], a
    ld [hl+], a
    dec b
    jr nz, .font

    ; clear the background map with the blank tile
    ld hl, $9800
    ld bc, 32 * 32
.clear:
    ld a, BLANK
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .clear

    ld a, $E4
    ldh [rBGP], a
    ld a, $42
    ld [wNext], a
    xor a
    ld [wLast], a
    ld [wCount], a
    ld [wCount + 1], a
    call Draw
    ld a, %10010001           ; LCD on, BG tiles at $8000, BG on
    ldh [rLCDC], a

Loop:
    ld a, [wNext]
    ldh [rSB], a
    ld a, $80                 ; start, external clock
    ldh [rSC], a
.wait:
    ldh a, [rSC]
    bit 7, a
    jr nz, .wait              ; cleared by hardware after 8 clocks from the Pico
    ldh a, [rSB]
    ld [wLast], a
    inc a
    ld [wNext], a
    ld hl, wCount
    inc [hl]
    jr nz, .nocarry
    inc hl
    inc [hl]
.nocarry:
    call WaitVBlank
    call Draw
    jr Loop

; Write last byte at row 2, col 2 and count at row 4, col 2. Call in VBlank or LCD off.
Draw:
    ld hl, $9800 + 2 * 32 + 2
    ld a, [wLast]
    call PrintHex
    ld hl, $9800 + 4 * 32 + 2
    ld a, [wCount + 1]
    call PrintHex
    ld a, [wCount]
    ; fall through
PrintHex:                     ; a = byte, hl = map address; tile n = hex digit n
    ld b, a
    swap a
    and $0F
    ld [hl+], a
    ld a, b
    and $0F
    ld [hl+], a
    ret

WaitVBlank:
    ldh a, [rLY]
    cp 144
    jr nz, WaitVBlank
    ret

Font:
    db $3C,$66,$6E,$76,$66,$66,$3C,$00 ; 0
    db $18,$38,$18,$18,$18,$18,$7E,$00 ; 1
    db $3C,$66,$06,$0C,$30,$60,$7E,$00 ; 2
    db $3C,$66,$06,$1C,$06,$66,$3C,$00 ; 3
    db $0C,$1C,$3C,$6C,$7E,$0C,$0C,$00 ; 4
    db $7E,$60,$7C,$06,$06,$66,$3C,$00 ; 5
    db $3C,$60,$7C,$66,$66,$66,$3C,$00 ; 6
    db $7E,$06,$0C,$18,$30,$30,$30,$00 ; 7
    db $3C,$66,$66,$3C,$66,$66,$3C,$00 ; 8
    db $3C,$66,$66,$3E,$06,$0C,$38,$00 ; 9
    db $18,$3C,$66,$66,$7E,$66,$66,$00 ; A
    db $7C,$66,$66,$7C,$66,$66,$7C,$00 ; B
    db $3C,$66,$60,$60,$60,$66,$3C,$00 ; C
    db $78,$6C,$66,$66,$66,$6C,$78,$00 ; D
    db $7E,$60,$60,$7C,$60,$60,$7E,$00 ; E
    db $7E,$60,$60,$7C,$60,$60,$60,$00 ; F
    db $00,$00,$00,$00,$00,$00,$00,$00 ; blank
