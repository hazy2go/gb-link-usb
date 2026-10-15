; sodax.gb: live SODAX market data on an original Game Boy.
; The Game Boy is the link clock master: it polls the Pico (bridge mode) byte by
; byte, sends button commands, and receives screen frames prepared on the PC by
; tools/sodax-bridge.mjs (prices: SODAX oracle candles, quote: SODAX solver).
;
; Frame from the PC: $7E, type $01, length (LE16) = 278, payload, sum (LE16).
; Payload: title 20, big price 10, row4 20, row11 20, row13 20, row14 20,
;          row15 20, row16 20, chart 128 (y 0 = top .. 47 = bottom).
; Text bytes are ASCII $20-$5F; bit 7 set = drawn inverted (white on black).
; Commands to the PC: 'H' hello, 'L'/'R' previous/next coin, 'B' range, 'A' refresh.
;
; Tiles: 0-63 font, 64-127 inverted font, 128-223 chart (logo on the splash),
;        224-251 big digits (two tiles each). Screen layout in docs/SODAX.md.

DEF rP1   EQU $FF00
DEF rSB   EQU $FF01
DEF rSC   EQU $FF02
DEF rLCDC EQU $FF40
DEF rLY   EQU $FF44
DEF rBGP  EQU $FF47

DEF MAP          EQU $9800
DEF TILE_INV     EQU 64
DEF TILE_CHART   EQU 128
DEF TILE_BIG     EQU 224
DEF CHART_ROW    EQU 5          ; chart occupies map rows 5-10, columns 2-17
DEF CHART_COL    EQU 2
DEF CHART_H      EQU 48

DEF P_TITLE  EQU 0
DEF P_PRICE  EQU 20
DEF P_ROW4   EQU 30
DEF P_ROW11  EQU 50
DEF P_ROW13  EQU 70
DEF P_ROW14  EQU 90
DEF P_ROW15  EQU 110
DEF P_ROW16  EQU 130
DEF P_CHART  EQU 150
DEF P_LEN    EQU 278

MACRO TEXT20                    ; a 20-column text row, padded with spaces
    db \1
    ds 20 - STRLEN(\1), ' '
ENDM

SECTION "vars", WRAM0[$C000]
wCmd:        ds 1
wJoyPrev:    ds 1
wRxState:    ds 1
wRxType:     ds 1
wRxLenL:     ds 1
wRxLenH:     ds 1
wRxPosL:     ds 1
wRxPosH:     ds 1
wRxSumL:     ds 1
wRxSumH:     ds 1
wRxGotL:     ds 1
wFrameReady: ds 1
wX:          ds 1
wY:          ds 1
wPrev:       ds 1
wBigTop:     ds 20
wBigBot:     ds 20

SECTION "chart", WRAM0[$C200]   ; page aligned: Plot builds addresses from x and y
wChart:      ds 16 * 6 * 16     ; 96 tiles, 2 bpp

SECTION "buf", WRAM0[$C800]
wBuf:        ds 512

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
    ldh [rLCDC], a              ; LCD off while loading graphics

    ld hl, $C000
    ld bc, $100
    call Clear
    ld hl, wBuf
    ld bc, 512
    call Clear

    ld hl, $8000                ; font, tiles 0-63
    ld de, Font
    ld bc, FontEnd - Font
    call CopyExpand
    ld hl, $8000 + TILE_INV * 16 ; inverted font, tiles 64-127
    ld de, Font
    ld bc, FontEnd - Font
    call CopyExpandInv
    ld hl, $8000 + TILE_CHART * 16 ; SODAX logo in the chart tiles
    ld de, Logo
    ld bc, LogoEnd - Logo
    call Copy
    ld hl, $8000 + TILE_BIG * 16 ; big digits
    ld de, BigFont
    ld bc, BigFontEnd - BigFont
    call CopyExpand

    ld hl, MAP                  ; whole map blank (tile 0 = space)
    ld bc, 32 * 32
    call Clear
    call SetupChartMap

    ld hl, SplashTitle
    ld de, MAP + 0 * 32
    call TextRowInv
    ld hl, SplashLine1
    ld de, MAP + 13 * 32
    call TextRow
    ld hl, SplashLine2
    ld de, MAP + 14 * 32
    call TextRow
    ld hl, SplashLine3
    ld de, MAP + 16 * 32
    call TextRow
    ld hl, Footer
    ld de, MAP + 17 * 32
    call TextRowInv

    ld a, %11100100             ; shades: 0 white .. 3 black
    ldh [rBGP], a
    ld a, %10010001             ; LCD on, BG tiles at $8000, BG on
    ldh [rLCDC], a

    ld a, 'H'                   ; say hello: the PC answers with a screen
    ld [wCmd], a

IF DEF(TESTFRAME)                ; test build: feed a recorded frame through the parser
    ld hl, TestFrame
    ld bc, TestFrameEnd - TestFrame
.feed:
    push bc
    ld a, [hl+]
    push hl
    call ParseByte
    pop hl
    pop bc
    dec bc
    ld a, b
    or c
    jr nz, .feed
ENDC

MainLoop:
    call ReadJoy
    ld b, 8                     ; poll the Pico: 8 bytes (~8 ms) per pass
.poll:
    push bc
    ld a, [wCmd]
    ldh [rSB], a
    xor a
    ld [wCmd], a                ; a command is sent once
    ld a, $81                   ; start, internal clock (8192 Hz)
    ldh [rSC], a
.busy:
    ldh a, [rSC]
    bit 7, a
    jr nz, .busy
    ldh a, [rSB]
    call ParseByte
    pop bc
    dec b
    jr nz, .poll
    ld a, [wFrameReady]
    and a
    call nz, Render
    jr MainLoop

; ---------------------------------------------------------------- input
ReadJoy:
    ld a, $20                   ; d-pad
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    cpl
    and $0F
    swap a
    ld b, a                     ; bit 4 Right, 5 Left, 6 Up, 7 Down
    ld a, $10                   ; buttons
    ldh [rP1], a
    REPT 6
    ldh a, [rP1]
    ENDR
    cpl
    and $0F
    or b
    ld b, a                     ; bit 0 A, 1 B, 2 Select, 3 Start
    ld a, $30
    ldh [rP1], a
    ld a, [wJoyPrev]
    cpl
    and b
    ld c, a                     ; newly pressed
    ld a, b
    ld [wJoyPrev], a
    ld a, 'R'
    bit 4, c
    jr nz, .send
    bit 7, c
    jr nz, .send
    ld a, 'L'
    bit 5, c
    jr nz, .send
    bit 6, c
    jr nz, .send
    ld a, 'B'
    bit 1, c
    jr nz, .send
    ld a, 'A'
    bit 0, c
    jr nz, .send
    bit 3, c
    ret z
.send:
    ld [wCmd], a
    call WaitVBlankStart        ; feedback until the new screen arrives
    ld hl, Loading
    ld de, MAP + 13 * 32
    jp TextRowInv

; ---------------------------------------------------------------- frame parser
; a = byte from the PC. Sets wFrameReady when a valid screen frame is in wBuf.
ParseByte:
    ld c, a
    ld a, [wRxState]
    and a
    jr z, .s0
    dec a
    jr z, .s1
    dec a
    jr z, .s2
    dec a
    jr z, .s3
    dec a
    jr z, .s4
    dec a
    jp z, .s5
    ; state 6: checksum high byte, then check everything
    ld a, [wRxSumH]
    cp c
    jr nz, .reset
    ld a, [wRxGotL]
    ld b, a
    ld a, [wRxSumL]
    cp b
    jr nz, .reset
    ld a, [wRxType]
    cp 1
    jr nz, .reset
    ld a, [wRxLenL]
    cp LOW(P_LEN)
    jr nz, .reset
    ld a, [wRxLenH]
    cp HIGH(P_LEN)
    jr nz, .reset
    ld a, 1
    ld [wFrameReady], a
.reset:
    xor a
    ld [wRxState], a
    ret
.s0:
    ld a, c
    cp $7E
    ret nz
    ld a, 1
    ld [wRxState], a
    ret
.s1:
    ld a, c
    ld [wRxType], a
    ld a, 2
    ld [wRxState], a
    ret
.s2:
    ld a, c
    ld [wRxLenL], a
    ld a, 3
    ld [wRxState], a
    ret
.s3:
    ld a, c
    ld [wRxLenH], a
    cp 2                        ; length < 512 (wBuf holds 512)
    jr nc, .reset
    ld a, [wRxLenL]
    or c
    jr z, .reset                ; empty frames are not used
    xor a
    ld [wRxPosL], a
    ld [wRxPosH], a
    ld [wRxSumL], a
    ld [wRxSumH], a
    ld a, 4
    ld [wRxState], a
    ret
.s4:
    ld a, [wRxPosL]
    ld e, a
    ld a, [wRxPosH]
    ld d, a
    ld hl, wBuf
    add hl, de
    ld [hl], c
    inc de
    ld a, e
    ld [wRxPosL], a
    ld a, d
    ld [wRxPosH], a
    ld a, [wRxSumL]
    add c
    ld [wRxSumL], a
    ld a, [wRxSumH]
    adc 0
    ld [wRxSumH], a
    ld a, [wRxLenL]
    cp e
    ret nz
    ld a, [wRxLenH]
    cp d
    ret nz
    ld a, 5
    ld [wRxState], a
    ret
.s5:
    ld a, c
    ld [wRxGotL], a
    ld a, 6
    ld [wRxState], a
    ret

; ---------------------------------------------------------------- render
; Draw the chart off screen, then update VRAM a slice per VBlank (no blank flash).
Render:
    xor a
    ld [wFrameReady], a
    call BuildChart
    call PrepBigPrice

    ld hl, wChart               ; 1536 bytes, 96 per VBlank
    ld de, $8000 + TILE_CHART * 16
    ld b, 16
.chunk:
    push bc
    call WaitVBlankStart
    ld c, 96
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .copy
    pop bc
    dec b
    jr nz, .chunk

    call WaitVBlankStart
    ld hl, wBuf + P_TITLE
    ld de, MAP + 0 * 32
    call TextRow
    call WaitVBlankStart
    ld hl, MAP + 2 * 32         ; Copy: hl = dest, de = src
    ld de, wBigTop
    ld bc, 20
    call Copy
    ld hl, MAP + 3 * 32
    ld de, wBigBot
    ld bc, 20
    call Copy
    call WaitVBlankStart
    ld hl, wBuf + P_ROW4
    ld de, MAP + 4 * 32
    call TextRow
    call WaitVBlankStart
    ld hl, wBuf + P_ROW11
    ld de, MAP + 11 * 32
    call TextRow
    call WaitVBlankStart
    ld hl, wBuf + P_ROW13
    ld de, MAP + 13 * 32
    call TextRow
    call WaitVBlankStart
    ld hl, wBuf + P_ROW14
    ld de, MAP + 14 * 32
    call TextRow
    call WaitVBlankStart
    ld hl, wBuf + P_ROW15
    ld de, MAP + 15 * 32
    call TextRow
    call WaitVBlankStart
    ld hl, wBuf + P_ROW16
    ld de, MAP + 16 * 32
    jp TextRow

; Big price: 10 chars at columns 1-10 of rows 2-3 -> wBigTop/wBigBot (20 tiles each).
PrepBigPrice:
    ld hl, wBigTop
    ld bc, 40
    call Clear
    ld hl, wBuf + P_PRICE
    ld de, wBigTop + 1
    ld b, 10
.ch:
    ld a, [hl+]
    push hl
    push bc
    ld c, a
    ld hl, BigChars
    ld b, 0                     ; index into BigChars
.find:
    ld a, [hl+]
    and a
    jr z, .blank                ; not a big character (e.g. space)
    cp c
    jr z, .found
    inc b
    jr .find
.found:
    ld a, b
    add a
    add TILE_BIG
    ld [de], a                  ; top half
    ld hl, 20
    add hl, de
    inc a
    ld [hl], a                  ; bottom half
.blank:
    inc de
    pop bc
    pop hl
    dec b
    jr nz, .ch
    ret

; Chart into wChart: shaded area under the line, dotted grid above it, a 2 px
; line, and a marker on the latest price.
BuildChart:
    ld hl, wChart
    ld bc, 16 * 6 * 16
    call Clear
    ld a, [wBuf + P_CHART]
    ld [wPrev], a
    xor a
    ld [wX], a
.col:
    ld a, [wX]
    ld d, a
    ld hl, wBuf + P_CHART
    add l
    ld l, a
    adc h
    sub l
    ld h, a
    ld a, [hl]
    cp CHART_H
    jr c, .inrange
    ld a, CHART_H - 1
.inrange:
    ld [wY], a
    ld c, 1                     ; area: light grey below the line
    inc a
    ld e, a
.area:
    ld a, e
    cp CHART_H
    jr nc, .grid
    call Plot
    inc e
    jr .area
.grid:
    ld a, d                     ; dotted grid at 1/4, 1/2, 3/4 height, above the line
    and 1
    jr nz, .line
    ld c, 2
    ld e, 12
    ld a, [wY]
    cp 13
    jr c, .g2
    call Plot
.g2:
    ld e, 24
    ld a, [wY]
    cp 25
    jr c, .g3
    call Plot
.g3:
    ld e, 36
    ld a, [wY]
    cp 37
    jr c, .line
    call Plot
.line:
    ld c, 3                     ; black line from the previous point, 2 px thick
    ld a, [wPrev]
    ld b, a
    ld a, [wY]
    cp b
    jr c, .ylow
    ld e, b                     ; prev <= y: draw prev .. y
    ld b, a
    jr .draw
.ylow:
    ld e, a                     ; y < prev: draw y .. prev
.draw:
    inc b
.dl:
    ld a, e
    cp CHART_H
    jr nc, .next
    call Plot
    ld a, e
    cp b
    jr z, .next
    inc e
    jr .dl
.next:
    ld a, [wY]
    ld [wPrev], a
    ld a, [wX]
    inc a
    ld [wX], a
    cp 128
    jp nz, .col

    ld a, [wPrev]               ; marker: 4x4 block on the latest point
    and a
    jr z, .m0
    dec a
.m0:
    ld e, a
    add 4
    ld [wY], a                  ; last row (exclusive)
    ld c, 3
.mrow:
    ld d, 124
.mcol:
    ld a, e
    cp CHART_H
    ret nc
    call Plot
    inc d
    ld a, d
    cp 128
    jr nz, .mcol
    inc e
    ld a, [wY]
    cp e
    jr nz, .mrow
    ret

; Set pixel (d = x 0-127, e = y 0-47) in wChart to OR colour c (1, 2 or 3).
; Address = wChart + (y/8)*256 + (x/8)*16 + (y%8)*2. Keeps bc, de.
Plot:
    push bc
    ld a, d
    and 7
    ld hl, Masks
    or l
    ld l, a
    ld b, [hl]
    ld a, e
    and $F8
    rrca
    rrca
    rrca
    add HIGH(wChart)
    ld h, a
    ld a, d
    and $F8
    add a
    ld l, a
    ld a, e
    and 7
    add a
    or l
    ld l, a
    bit 0, c
    jr z, .hi
    ld a, [hl]
    or b
    ld [hl], a
.hi:
    inc l
    bit 1, c
    jr z, .done
    ld a, [hl]
    or b
    ld [hl], a
.done:
    pop bc
    ret

; ---------------------------------------------------------------- helpers
SetupChartMap:                  ; rows 5-10, cols 2-17 -> tiles 128..223
    ld hl, MAP + CHART_ROW * 32 + CHART_COL
    ld a, TILE_CHART
    ld c, 6
.row:
    ld b, 16
.t:
    ld [hl+], a
    inc a
    dec b
    jr nz, .t
    ld de, 32 - 16
    add hl, de
    dec c
    jr nz, .row
    ret

TextRow:                        ; hl = 20 chars, de = map address; bit 7 = inverted
    ld b, 20
.c:
    ld a, [hl+]
    bit 7, a
    jr nz, .inv
    sub $20
    jr .put
.inv:
    and $7F
    sub $20 - TILE_INV
.put:
    ld [de], a
    inc de
    dec b
    jr nz, .c
    ret

TextRowInv:                     ; hl = 20 chars, de = map address; all inverted
    ld b, 20
.c:
    ld a, [hl+]
    sub $20 - TILE_INV
    ld [de], a
    inc de
    dec b
    jr nz, .c
    ret

Clear:                          ; hl = dest, bc = count
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, Clear
    ret

Copy:                           ; hl = dest, de = src, bc = count
    ld a, [de]
    inc de
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, Copy
    ret

CopyExpand:                     ; 1 bpp -> 2 bpp colour 3
    ld a, [de]
    inc de
    ld [hl+], a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, CopyExpand
    ret

CopyExpandInv:                  ; 1 bpp -> 2 bpp, inverted (white on black)
    ld a, [de]
    inc de
    cpl
    ld [hl+], a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, CopyExpandInv
    ret

WaitVBlank:                     ; any time in VBlank
    ldh a, [rLY]
    cp 144
    jr c, WaitVBlank
    ret

WaitVBlankStart:                ; the start of the next VBlank (full VBlank ahead)
    ldh a, [rLY]
    cp 144
    jr nc, WaitVBlankStart
.w:
    ldh a, [rLY]
    cp 144
    jr nz, .w
    ret

; ---------------------------------------------------------------- data
SECTION "masks", ROM0, ALIGN[3]
Masks: db $80, $40, $20, $10, $08, $04, $02, $01

SECTION "data", ROM0
BigChars:    db "0123456789,.$-", 0
SplashTitle: TEXT20 "  SODAX ON GAME BOY"
SplashLine1: TEXT20 "LIVE PRICES + QUOTES"
SplashLine2: TEXT20 "  FROM THE SODAX API"
SplashLine3: TEXT20 "WAITING FOR BRIDGE.."
Loading:     TEXT20 "    LOADING...      "
Footer:      TEXT20 "<>COIN B:RANGE A:NEW"

INCLUDE "font.inc"

IF DEF(TESTFRAME)
TestFrame:
    INCBIN TESTFRAME
TestFrameEnd:
ENDC
