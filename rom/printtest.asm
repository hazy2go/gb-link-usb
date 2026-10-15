; printtest.gb: the Game Boy acts as a printer game (clock MASTER) and shows
; what the printer answers. Row 2: replies to an INIT packet (10 bytes).
; Row 4: replies to a STATUS packet. Row 6: run counter. Repeats every second.
; A real printer answers 00 to every byte, then 81 and the status in the last two.

DEF rSB   EQU $FF01
DEF rSC   EQU $FF02
DEF rLCDC EQU $FF40
DEF rLY   EQU $FF44
DEF rBGP  EQU $FF47
DEF BLANK EQU 16

SECTION "vars", WRAM0
wReply: ds 10
wRuns:  ds 1

SECTION "entry", ROM0[$100]
    nop
    jp Main
    ds $150 - @, 0

SECTION "main", ROM0[$150]
Main:
    di
    ld sp, $DFFF
    call WaitVBlank
    xor a
    ldh [rLCDC], a
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
    xor a
    ld [wRuns], a
    ld a, %10010001
    ldh [rLCDC], a

Loop:
    ld hl, PktInit
    call SendPacket
    call WaitVBlank
    ld hl, $9800 + 2 * 32
    call ShowReplies
    ld hl, PktStatus
    call SendPacket
    call WaitVBlank
    ld hl, $9800 + 4 * 32
    call ShowReplies
    ld hl, wRuns
    inc [hl]
    ld a, [hl]
    ld hl, $9800 + 6 * 32
    call PrintHex
    ld b, 60                  ; about one second
.wait:
    call WaitVBlank
.leave:
    ldh a, [rLY]
    cp 144
    jr z, .leave
    dec b
    jr nz, .wait
    jr Loop

; hl = 10-byte packet. Sends each byte with the internal clock, stores replies.
SendPacket:
    ld de, wReply
    ld c, 10
.byte:
    ld a, [hl+]
    ldh [rSB], a
    ld a, $81                 ; start, internal clock (8192 Hz)
    ldh [rSC], a
.busy:
    ldh a, [rSC]
    bit 7, a
    jr nz, .busy
    ldh a, [rSB]
    ld [de], a
    inc de
    ld b, 40                  ; short pause between bytes, like games do
.pause:
    dec b
    jr nz, .pause
    dec c
    jr nz, .byte
    ret

; hl = map row; writes the 10 replies as 20 hex digits. Call in VBlank.
ShowReplies:
    ld de, wReply
    ld c, 10
.r:
    ld a, [de]
    inc de
    call PrintHex
    dec c
    jr nz, .r
    ret

PrintHex:
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

PktInit:   db $88,$33,$01,$00,$00,$00,$01,$00,$00,$00
PktStatus: db $88,$33,$0F,$00,$00,$00,$0F,$00,$00,$00

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
