"""Self-test: put each defect back and prove the Gate still bites.

A suite that has only ever been green says nothing about what it would catch.
Every mutation here is the ACTUAL defect as it shipped, reintroduced verbatim,
with the checks that must go red.  Run it after changing the suite, and after
any refactor that moves the code these cases reach into.
"""

import os
import shutil

MUTATIONS = [
    {
        'name': 'r1-dir-pass',
        'why': 'the compaction slides records but its directory pass updates no entry',
        'file': 'COMPACT.Z8A',
        'old': """                LD      A, (CMPSEG)
                CP      C
                JR      NZ, .P2NXT""",
        'new': """                LD      A, (CMPSEG)
                CP      C
                JR      .P2NXT          ; MUTATION: NO ENTRY FOLLOWS ITS RECORD""",
        'filter': 'R1',
        'expect_any': ['R1/content', 'R1/entered', 'R1-freelist-compact'],
    },
    {
        'name': 's2-menu-old-item',
        'target': 'S2ED',
        'why': 'a menu move repaints the item it reaches but not the one it leaves',
        'file': 'MENU.Z8A',
        'old': """                LD      A, C            ; THE TWO ITEMS IT TOUCHES, AND ONLY
                LD      B, 0            ; THEIR ROWS TO VRAM: IT REPAINTED THE
                CALL    .ITEM           ; WHOLE MENU (~70 MS PER ARROW)""",
        'new': """                LD      A, C            ; THE TWO ITEMS IT TOUCHES, AND ONLY
                LD      B, 0            ; THEIR ROWS TO VRAM: IT REPAINTED THE
                CALL    MNUPNT          ; MUTATION: THE OLD ROW NEVER DUMPED""",
        'filter': 'S2-44',
        'expect': ['S2-44/restored'],
    },
    {
        'name': 'v4-colon-wrap',
        'why': 'the :N parser wraps at 16 bits instead of saturating',
        'file': 'ACTION.Z8A',
        'old': """.DONUM          CALL    ATOI16          ; HL = TARGET LINE (1-BASED), SATURATED:""",
        'new': """.DONUM          LD      HL, 1           ; MUTATION: WHAT THE WRAP GAVE FOR 65537""",
        'filter': 'V4',
        'expect': ['V4/last'],
    },
    {
        'name': 'x1-seleol',
        'why': 'copy and cut leave out a line break the Vi selection covers',
        'file': 'ACTION.Z8A',
        'old': """.CPYINIT        CALL    SELEOL          ; A COVERED LINE BREAK IS COPIED TOO""",
        'new': """.CPYINIT        NOP                     ; MUTATION: THE BREAK STAYS OUT
                NOP
                NOP""",
        'filter': 'X1',
        'expect': ['X1/yank/clip', 'X1/cut/clip'],
    },
    {
        'name': 'w2-focus-old-strip',
        'why': 'a Settings focus move blits only the row it reaches, not the one it leaves',
        'file': 'WINDOW.Z8A',
        'old': """                CALL    WINVSY          ; ONE SYNC FOR BOTH BLITS
                POP     BC
                CALL    .UPDFOC""",
        'new': """                CALL    WINVSY          ; ONE SYNC FOR BOTH BLITS
                POP     BC
                NOP                     ; MUTATION: THE OLD STRIP STAYS
                NOP
                NOP""",
        'filter': 'W2',
        'expect': ['W2/restored'],
    },
    {
        'name': 'w1-tab-perchar',
        'why': 'ACTTAB inserts its spaces one EDINSCHR at a time',
        'file': 'ACTION.Z8A',
        'old': """                JR      C, .TABLP       ; DOES NOT FIT: THE WRAP MODE DECIDES""",
        'new': """                JR      .TABLP          ; MUTATION: ALWAYS PER CHARACTER""",
        'filter': 'W1',
        'expect': ['W1/time'],
    },
    {
        'name': 's2-clock-rg9sav',
        'target': 'S2ED',
        'why': 'S2ED takes the frequency from RG9SAV on an MSX1 as well',
        'file': 'S2ED.Z8A',
        'old': """                OR      A
                JR      NZ, .FRQV2""",
        'new': """                OR      A
                JR      .FRQV2          ; MUTATION: RG9SAV ON AN MSX1 TOO""",
        'filter': 'S2-43',
        'expect': ['S2-43/ntsc'],
    },
    {
        'name': 's2-scroll-band-first',
        'target': 'S2ED',
        'why': 'SHUPN pushes the moved band before composing the exposed row, which shows the row above twice',
        'file': 'SCROLL.Z8A',
        'old': """                LD      A, 1
                LD      (RNDNODMP), A
.EXPLP          CALL    COLRNDR""",
        'new': """                PUSH    BC
                CALL    TXTPUSH         ; MUTATION: THE BAND GOES OUT FIRST
                POP     BC
                LD      A, 1
                LD      (RNDNODMP), A
.EXPLP          CALL    COLRNDR""",
        'filter': 'S2-42',
        'expect': ['S2-42/no-dup'],
    },
    {
        'name': 'v1-leader-b',
        'why': 'the pending Vi leader is kept in B, over the modifiers the keymap scan matches',
        'file': 'DISP.Z8A',
        'old': """                LD      E, A            ; E = PENDING LEADER (B HOLDS THE MODIFIERS
                XOR     A               ; THE KEYMAP SCAN BELOW MATCHES AGAINST)
                LD      (VILEAD), A
                LD      A, E""",
        'new': """                LD      B, A            ; MUTATION: THE LEADER OVER THE MODIFIERS
                XOR     A
                LD      (VILEAD), A
                LD      A, B""",
        'filter': 'V1',
        'expect': ['V1/moved'],
    },
    {
        'name': 'v2-wrapsel-room',
        'why': 'WRAPSEL inserts its delimiters whether or not the line has room',
        'file': 'MARKUP.Z8A',
        'old': """                JP      C, .WRPMUL      ; NO ROOM: LEAVE THE LINE ALONE""",
        'new': """                NOP                     ; MUTATION: NO ROOM CHECK
                NOP
                NOP""",
        'filter': 'V2',
        'expect': ['V2/content'],
    },
    {
        'name': 'v3-insdelim-room',
        'why': 'INSDELIM inserts what fits and steps the cursor back regardless',
        'file': 'MARKUP.Z8A',
        'old': """.INSN           CALL    MKROOM
                JR      C, .NOROOM""",
        'new': """.INSN           CALL    MKROOM
                NOP                     ; MUTATION: NO ROOM CHECK
                NOP""",
        'filter': 'V3',
        # The cursor lands on 3 either way (two '*' in, two steps back):
        # the document is what shows the half-inserted delimiters.
        'expect': ['V3/content'],
    },
    {
        # The margin is blanked by POSITION.  Without the test the last cell's
        # right half is fetched like any other column, and on a line longer
        # than the viewport that is a real character -- painted into the
        # 4 px the margin exists to keep clear.
        'name': 's2-rmargin-pos',
        'target': 'S2ED',
        'why': 'COMROW blanks the right margin only past the end of the line, '
               'so a long line paints its column 61 on screen column 63',
        'file': 'RENDER.Z8A',
        'old': """.NPOS           CP      TEXTCOLS + 1
                JR      C, .NOK
                LD      A, TEXTCOLS""",
        'new': """.NPOS           CP      TEXTCOLS + 2    ; MUTATION: MARGIN BY LENGTH ONLY
                JR      C, .NOK
                LD      A, TEXTCOLS + 1""",
        'filter': 'S2-47',
        'expect': ['S2-47/boot-margin', 'S2-47/mid-margin'],
    },
    {
        # TEXTCOLS is odd, so a row holds an odd number of characters: the
        # lone last one has its own cell, and dropping it loses column 60.
        'name': 's2-txcells-half',
        'target': 'S2ED',
        'why': 'COMROW composes only the pairs, so text column 60 is never drawn',
        'file': 'RENDER.Z8A',
        'old': """.HALF           LD      A, (CRN)
                RRCA
                JR      NC, .PTAIL""",
        'new': """.HALF           LD      A, (CRN)
                RRCA
                JR      .PTAIL          ; MUTATION: NO LONE LAST CHARACTER""",
        'filter': 'S2-47',
        'expect': ['S2-47/boot'],
    },
    {
        'name': 's2-about-width',
        'target': 'S2ED',
        'why': 'the About states the width by hand, and it says 62',
        'file': 'WINDOW.Z8A',
        'old': """.STRHDR         DEFB    "S2ED - MSX1 ", '0' + TEXTCOLS / 10
                DEFB    '0' + TEXTCOLS - TEXTCOLS / 10 * 10, "-Col", 0""",
        'new': """.STRHDR         DEFM    "S2ED - MSX1 62-Col", 0 ; MUTATION""",
        'filter': 'S2-11',
        'expect': ['S2-11/body-text'],
    },
    {
        'name': 't0-manual-62',
        'why': 'a manual line one column wider than the narrowest editor, '
               'which then needs horizontal scrolling to read it',
        'file': '../DOC/SXED.TXT',
        'old': 'SXED is a family of full screen text editors for MSX\n'
               'computers running MSX-DOS 2 or Nextor.',
        'new': 'SXED is a family of full screen text editors for MSX computers\n'
               'running MSX-DOS 2 or Nextor.',
        'filter': 'T0',
        'expect_static': ['manual-width'],
    },
    {
        'name': 't0-changes-62',
        'why': 'a version history line one column wider than the narrowest '
               'editor',
        'file': '../DOC/CHANGES.TXT',
        'old': 'Newest first. The manual is SXED.TXT.',
        'new': 'Newest first. The manual is SXED.TXT, read with any editor ok.',
        'filter': 'T0',
        'expect_static': ['manual-width'],
    },
    {
        'name': 't0-changes-s2disk',
        'why': 'the S2ED disk goes out without the version history',
        'file': 'Makefile',
        'old': 'add DEV $(MANUAL)=SXED.TXT $(CHANGES)=CHANGES.TXT TEST_S2.TXT',
        'new': 'add DEV $(MANUAL)=SXED.TXT TEST_S2.TXT',
        'filter': 'T0',
        'expect_static': ['manual-charset'],
    },
    {
        'name': 's2-col-digits',
        'target': 'S2ED',
        'why': 'the S2ED status bar shows the column with two digits',
        'file': 'UI.Z8A',
        'old': """                INC     HL
                LD      B, 3
                JP      .CPYNUM""",
        'new': """                INC     HL
                LD      B, 2            ; MUTATION: TWO DIGITS
                JP      .CPYNUM""",
        'filter': 'S2-40',
        'expect': ['S2-40/col'],
    },
    {
        'name': 's2-caret-cell24',
        'target': 'S2ED',
        'why': 'the S2ED name field clears cells 5..23 only',
        'file': 'BROWSER.Z8A',
        'old': """                LD      B, 20 * 8       ; 160""",
        'new': """                LD      B, 19 * 8       ; MUTATION: NOT CELL 24""",
        'filter': 'S2-41',
        'expect': ['S2-41/cell24'],
    },
    {
        'name': 'q1-style-off',
        'why': 'with MARKUP=OFF the style keys still write delimiters',
        'file': 'ACTION.Z8A',
        'old': """                RET     Z               ; MKUP_OFF: NO DELIMITERS TO WRITE""",
        'new': """                NOP                     ; MUTATION: STYLE KEYS WITH MARKUP OFF""",
        'filter': 'Q1',
        'expect': ['Q1/undo-is-the-edit'],
    },
    {
        'name': 'q2-slmr-guard',
        'why': 'Shift+Right that wraps and scrolls does not keep the overlay through the scroll',
        'file': 'ACTION.Z8A',
        'old': """                POP     DE              ; GUESSING IT BEFORE THE MOVE LEFT THE
                CALL    SELSCRL         ; OVERLAY SCROLLED UN-XORED: MEASURE IT""",
        'new': """                POP     DE              ; GUESSING IT BEFORE THE MOVE LEFT THE
                NOP                     ; MUTATION: NO SELSCRL
                NOP
                NOP""",
        'filter': 'Q2',
        'expect': ['Q2/short/render-pure', 'Q2/full/render-pure'],
    },
    {
        'name': 'q2-slml-guard',
        'why': 'Shift+Left that rolls up and scrolls does not keep the overlay through the scroll',
        'file': 'ACTION.Z8A',
        'old': """                POP     DE              ; DE = TOPLINE BEFORE THE MOVE
                CALL    SELSCRL
                JP      SELPOST""",
        'new': """                POP     DE              ; DE = TOPLINE BEFORE THE MOVE
                NOP                     ; MUTATION: NO SELSCRL
                NOP
                NOP
                JP      SELPOST""",
        'filter': 'Q2',
        'expect': ['Q2/left/render-pure'],
    },
    {
        'name': 's2-lineread-attrs',
        'target': 'S2ED',
        'why': 'LINEREAD zeroes only TEXTCOLS attributes, so a long line keeps '
               'the last MD scan past them once markup is off',
        'file': 'BUFFER.Z8A',
        'old': """                JR      NC, .ATRLEN     ; L > TEXTCOLS: ALL L""",
        'new': """                NOP                     ; MUTATION: TEXTCOLS ONLY
                NOP""",
        'filter': 'S2-58',
        'expect': ['S2-58/plain'],
    },
    {
        'name': 's2-coldiff-same',
        'target': 'S2ED',
        'why': 'COLDIFF calls every moved row unchanged, so a scroll never sends the colours that moved',
        'file': 'SCROLL.Z8A',
        'old': """.DIFF           LD      A, 1
.SET            POP     DE""",
        'new': """.DIFF           XOR     A               ; MUTATION: ALWAYS THE SAME
.SET            POP     DE""",
        'filter': 'S2-59',
        'expect': ['S2-59/scroll/colour-mirror', 'S2-59/enter/colour-mirror', 'S2-59/dev-bs/colour-mirror'],
    },
    {
        'name': 's2-colrndr-flag',
        'target': 'S2ED',
        'why': "a scroll's exposed row is composed but never flagged, so its colours never reach VRAM",
        'file': 'SCROLL.Z8A',
        'old': """                CALL    RENDEROW        ; BC PRESERVED
                LD      A, (COLDIRT)""",
        'new': """                CALL    RENDEROW        ; BC PRESERVED
                XOR     A               ; MUTATION: NEVER FLAGGED""",
        'filter': 'S2-59',
        'expect': ['S2-59/scroll/colour-mirror'],
    },
    {
        'name': 's2-nwpaint-head',
        'target': 'S2ED',
        'why': 'NWPAINT composes the new line but not the shortened head above it',
        'file': 'SCROLL.Z8A',
        'old': """                DEC     B
                CALL    COLRNDR         ; THE SHORTENED HEAD""",
        'new': """                DEC     B
                NOP                     ; MUTATION: NO HEAD
                NOP
                NOP""",
        'filter': 'S2-59',
        'expect': ['S2-59/enter/patterns'],
    },
    {
        'name': 's2-nwscrl-head',
        'target': 'S2ED',
        'why': 'NWSCRL scrolls and composes the new last row but not the head above it',
        'file': 'SCROLL.Z8A',
        'old': """                LD      B, TXRLAST - 1
                CALL    COLRNDR
                JP      TXTPUSH""",
        'new': """                LD      B, TXRLAST - 1
                NOP                     ; MUTATION: NO HEAD
                NOP
                NOP
                JP      TXTPUSH""",
        'filter': 'S2-59',
        'expect': ['S2-59/enter-bottom/patterns'],
    },
    {
        'name': 's2-jnshift-noshift',
        'target': 'S2ED',
        'why': 'JNSHIFT repaints the joined row but leaves the rows below where they were',
        'file': 'SCROLL.Z8A',
        'old': """JNSHIFT         PUSH    BC
                INC     B
                LD      C, 1
                CALL    SHUPN""",
        'new': """JNSHIFT         PUSH    BC
                INC     B
                LD      C, 1
                LD      A, 1            ; MUTATION: NO SHIFT
                LD      (RNDNODMP), A""",
        'filter': 'S2-59',
        'expect': ['S2-59/dev-bs/patterns', 'S2-59/dev-del/patterns'],
    },
    {
        'name': 's2-jnpaint-two',
        'target': 'S2ED',
        'why': 'a join that removed no line repaints the first row only, not the second',
        'file': 'EDIT.Z8A',
        'old': """.JNTWO          CALL    RENDEROW        ; BC PRESERVED
                LD      A, B
                CP      TXRLAST
                RET     NC""",
        'new': """.JNTWO          CALL    RENDEROW        ; BC PRESERVED
                RET                     ; MUTATION: ONE ROW ONLY""",
        'filter': 'S2-59',
        'expect': ['S2-59/txt-partial/patterns'],
    },
    {
        'name': 's2-txtpshb-head',
        'target': 'S2ED',
        'why': 'NWPAINT pushes from the new line, so the shortened head is composed but never sent',
        'file': 'SCROLL.Z8A',
        'old': """                CALL    COLRNDR         ; THE NEW LINE
                DEC     B
                JP      TXTPSHB""",
        'new': """                CALL    COLRNDR         ; THE NEW LINE
                NOP                     ; MUTATION: PUSH FROM THE NEW LINE
                JP      TXTPSHB""",
        'filter': 'S2-59',
        'expect': ['S2-59/enter/patterns'],
    },
    {
        'name': 's2-fastdn-short',
        'target': 'S2ED',
        'why': 'FASTDN moves one 16-byte pass and stops, so a shift leaves most rows behind',
        'file': 'SCROLL.Z8A',
        'old': """                JP      PE, FASTDN
                RET""",
        'new': """                RET                     ; MUTATION: ONE PASS
                RET""",
        'filter': 'S2-59',
        'expect': ['S2-59/enter/patterns'],
    },
    {
        'name': 'mk-quick-reject',
        'target': 'S2ED',
        'why': 'SCANMKUP returns as soon as the line has no asterisk, so an underscore span is never styled',
        'file': 'MARKUP.Z8A',
        'old': """                LD      A, '_'
                CPIR
                RET     NZ              ; NEITHER: A PLAIN LINE""",
        'new': """                RET                     ; MUTATION: '*' ONLY
                CPIR
                RET     NZ              ; NEITHER: A PLAIN LINE""",
        'filter': 'S2-14',
        'expect': ['S2-14/line2'],
    },
    {
        'name': 'perf-join-redraw',
        'target': 'S2ED',
        'why': 'every join redraws the page again, as before JNPAINT',
        'file': 'EDIT.Z8A',
        'old': """JNPAINT         LD      A, (SELACT)
                OR      A
                JP      NZ, REDRAW""",
        'new': """JNPAINT         JP      REDRAW          ; MUTATION: THE OLD FULL REDRAW
                OR      A
                JP      NZ, REDRAW""",
        'filter': 'S2-60',
        'expect': ['S2-60/join'],
    },
    {
        'name': 'perf-colband-all',
        'target': 'S2ED',
        'why': 'COLBCHG dumps every row whether its colours changed or not',
        'file': 'SCROLL.Z8A',
        'old': """                LD      A, (HL)
                OR      A
                CALL    NZ, COLDUMP     ; BC PRESERVED""",
        'new': """                LD      A, (HL)
                OR      A
                CALL    COLDUMP         ; MUTATION: EVERY ROW""",
        'filter': 'S2-60',
        'expect': ['S2-60/enter', 'S2-60/scroll'],
    },
    {
        'name': 'perf-no-reject',
        'target': 'S2ED',
        'why': 'SCANMKUP runs its full passes over a line with no delimiter',
        'file': 'MARKUP.Z8A',
        'old': """                LD      A, '*'
                CPIR
                JR      Z, .DELIM""",
        'new': """                LD      A, '*'
                CPIR
                JR      .DELIM          ; MUTATION: NO QUICK REJECT""",
        'filter': 'S2-60',
        'expect': ['S2-60/page'],
    },
    {
        'name': 'u15-reflow-drop',
        'why': 'the key join in WRAP_TXT drops the undo history again',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, 1
                LD      (RWKEEP), A     ; REWRAP DROPS NOTHING: THE RECORDS BELOW""",
        'new': """                XOR     A               ; MUTATION: REWRAP DROPS THE HISTORY
                LD      (RWKEEP), A     ; REWRAP DROPS NOTHING: THE RECORDS BELOW""",
        # the join itself is still recorded: only what came before is lost
        'filter': 'U15',
        'expect': ['U15/u2', 'U15/u3'],
    },
    {
        'name': 'u15-reflow-delop',
        'why': 'a join that took all of L + 1 records it as changed, not deleted',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, UNDOT_DEL | UNDOF_CHN
.REC2           CALL    UNDOLNR         ; L + 1 AS IT WAS""",
        'new': """                LD      A, UNDOT_MOD | UNDOF_CHN ; MUTATION: NEVER DELETED
.REC2           CALL    UNDOLNR         ; L + 1 AS IT WAS""",
        # a MOD replayed on a line the join deleted is undefined behaviour:
        # some sessions hang, so the case name counts as well
        'filter': 'U15',
        'expect_any': ['U15/full-u1', 'U15/u2', 'U15-txt-join-undo'],
    },
    {
        'name': 'u15-reflow-empty',
        'why': 'deleting the empty line the key joins is not recorded',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, UNDOT_DEL
                CALL    UNDOLNR         ; ITS DELETION, A GROUP OF ONE""",
        'new': """                LD      A, UNDOT_DEL
                NOP                     ; MUTATION: NOT RECORDED
                NOP
                NOP""",
        'filter': 'U15',
        'expect': ['U15/empty-u1'],
    },
    {
        'name': 'u15-dup-chain',
        'why': 'Ctrl+D records only the split, so its undo joins the copy back on',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, UNDOT_MOD | UNDOF_CHN
                CALL    UNDOLNR

                ; READ ORIGINAL LINE FROM (DOCLINE - 1) INTO WORKBUF""",
        'new': """                LD      A, UNDOT_MOD | UNDOF_CHN
                NOP                     ; MUTATION: THE COPY NOT RECORDED
                NOP
                NOP

                ; READ ORIGINAL LINE FROM (DOCLINE - 1) INTO WORKBUF""",
        'filter': 'U15',
        'expect': ['U15/dev-dup-u1', 'U15/u2'],
    },
    {
        'name': 's2-u15-dup-chain',
        'target': 'S2ED',
        'why': 'Ctrl+D records only the split, so its undo joins the copy back on',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, UNDOT_MOD | UNDOF_CHN
                CALL    UNDOLNR

                ; READ ORIGINAL LINE FROM (DOCLINE - 1) INTO WORKBUF""",
        'new': """                LD      A, UNDOT_MOD | UNDOF_CHN
                NOP                     ; MUTATION: THE COPY NOT RECORDED
                NOP
                NOP

                ; READ ORIGINAL LINE FROM (DOCLINE - 1) INTO WORKBUF""",
        'filter': 'S2-61',
        'expect': ['S2-61/dev-dup-u1'],
    },
    {
        'name': 'u8-reflow-split',
        'why': 'a key join that split a line records its two lines anyway, naming lines the split moved',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, (RWSPL)
                OR      A
                JR      NZ, .DROP       ; A LINE WAS SPLIT: MORE THAN TWO MOVED""",
        'new': """                LD      A, (RWSPL)
                OR      A
                NOP                     ; MUTATION: RECORDED ANYWAY
                NOP""",
        'filter': 'U8',
        'expect': ['U8/reflow/dropped'],
    },
    {
        'name': 'x5-rollover-clamp',
        'why': 'LEFT rollover on the top row does not clamp CURX where the queued UPs land',
        'file': 'EDIT.Z8A',
        'old': """                CALL    EDMOVROW        ; ON THE TOP ROW IT TAKES QUEUED UPS TOO,
                JP      EDCLMPX         ; SO THE COLUMN IS CLAMPED WHERE IT LANDS""",
        'new': """                JP      EDMOVROW        ; MUTATION: NO CLAMP""",
        'filter': 'X5',
        'expect': ['X5/landed', 'X5/content'],
    },
    {
        'name': 'q3-find-cursor',
        'why': 'Find Next always restarts one past the cursor, the end of the previous match',
        'file': 'SEARCH.Z8A',
        'old': """                OR      A
                JR      Z, .CUR
                PUSH    HL""",
        'new': """                OR      A
                JR      .CUR            ; MUTATION: NEVER THE SELECTION
                PUSH    HL""",
        'filter': 'Q3',
        'expect': ['Q3/adjacent'],
    },
    {
        'name': 'q4-settings-winsid',
        'why': 'Settings clears its body with a band as wide as the window and leaves the sides erased',
        'file': 'WINDOW.Z8A',
        'old': """                CALL    WINSID          ; THE BAND SPANS WINW: PUT THE SIDES BACK""",
        'new': """                NOP                     ; MUTATION: NO SIDES
                NOP
                NOP""",
        'filter': 'Q4',
        'expect': ['Q4/borders'],
    },
    {
        'name': 'q5-shadow-ui',
        'why': 'Settings OK turns any shadow that stays on into UI',
        'file': 'WINDOW.Z8A',
        'old': """                CP      CLR_BG          ; SET IT. IT WAS ALWAYS REWRITTEN AS UI
                JR      NZ, .SHDDON""",
        'new': """                CP      CLR_BG          ; SET IT. IT WAS ALWAYS REWRITTEN AS UI
                NOP                     ; MUTATION: ALWAYS UI
                NOP""",
        'filter': 'Q5',
        'expect': ['Q5/kept'],
    },
    {
        'name': 'q6-vdpwait-di',
        'why': 'VDPWAIT polls the command engine with interrupts off for the whole command',
        'file': 'VDP.Z8A',
        'old': """                EI                      ; ONE POLL PER DI: THE VBLANK IS SERVED
                JR      C, .WAIT        ; BETWEEN POLLS, NOT HELD OFF FOR THE
                POP     BC
                POP     AF              ; WHOLE COMMAND (A 128 MS YMMM LOST ~6)""",
        'new': """                NOP                     ; MUTATION: NO EI BETWEEN POLLS
                JR      C, .WAIT        ; BETWEEN POLLS, NOT HELD OFF FOR THE
                EI
                POP     BC
                POP     AF              ; WHOLE COMMAND (A 128 MS YMMM LOST ~6)""",
        'filter': 'Q6',
        'expect': ['Q6/rate'],
    },
    {
        'name': 's2-reflow-attr-off',
        'target': 'S2ED',
        'why': 'the reflow copies the remainder text from the start of the line, not from where the remainder starts',
        'file': 'EDIT.Z8A',
        'old': """                LD      HL, WORKBUF2 + 1
                ADD     HL, DE
                LD      DE, WORKBUF + 1""",
        'new': """                LD      HL, WORKBUF2 + 1 ; MUTATION: TEXT FROM COLUMN 0
                NOP
                LD      DE, WORKBUF + 1""",
        'filter': 'S2-38',
        'expect': ['S2-38/bold'],
    },
    {
        'name': 's2-browse-title',
        'target': 'S2ED',
        'why': 'the S2ED browser repaint starts below the title row a rescan rebuilt',
        'file': 'BROWSER.Z8A',
        'old': """                ;    TO THIS ONE -- IT USED TO SEND THE ROWS TWICE (~85 MS)
                JP      WDUMP""",
        'new': """                ;    TO THIS ONE -- IT USED TO SEND THE ROWS TWICE (~85 MS)
                RET                     ; MUTATION: THE REPAINT NEVER REACHES VRAM""",
        'filter': 'S2-39',
        'expect': ['S2-39/title'],
    },
    {
        'name': 's61-name-label',
        'target': 'S61ED',
        'why': 'the S61ED name field box starts at 40 and paints over the label colon',
        'file': 'BROWSER.Z8A',
        'old': """                LD      A, 60           ; THE BOX STARTS AT 56, CLEAR OF "Name:" (8..47)""",
        'new': """                LD      A, 44           ; MUTATION: S6 GEOMETRY""",
        'filter': 'S62-6',
        'expect': ['S62-6/name-label'],
    },
    # p1-reflow-pass (REWRAP's 'RET Z ; REFLOW: THE PARAGRAPH ENDS HERE'
    # NOPed) was retired 2026-10-16: the key join now rewraps only L..L + 1
    # and REFLOW deletes an empty L + 1 itself, so that branch cannot be
    # reached from a key any more and no case can catch it.  P1 still pins
    # the behaviour; W5 / S2-57 and their cascade mutations guard the range.
    {
        'name': 'p2-dlok-setcury',
        'why': 'ACTDELLN derives CURY without bringing DOCLINE back into the viewport',
        'file': 'ACTION.Z8A',
        'old': """.DLOK           LD      HL, (DOCLINE)   ; DELETING THE LAST LINE FROM ROW 0
                CALL    SHOWLN          ; LEFT DOCLINE ABOVE TOPLINE: CURY #FF""",
        'new': """.DLOK           CALL    SETCURY         ; MUTATION: NO SHOWLN
                NOP
                NOP
                NOP""",
        'filter': 'P2',
        'expect_any': ['P2/on-screen', 'P2-delete-last-row0'],
    },
    {
        'name': 'p3-rpl-nocap',
        'why': 'Replace All records a group larger than the ring holds whole: '
               'UNDOREC keeps no byte budget for the group',
        'file': 'UNDO.Z8A',
        'old': """                JR      NC, .KEEP
                LD      A, 1
                LD      (UNDODRP), A""",
        'new': """                JR      .KEEP           ; MUTATION: NO GROUP BUDGET
                LD      A, 1
                LD      (UNDODRP), A""",
        'filter': 'P3',
        'expect': ['P3/many/dropped', 'P3/many/content'],
    },
    {
        'name': 'p3-rpl-peroccur',
        'why': 'Replace All records every occurrence instead of every line',
        'file': 'SEARCH.Z8A',
        'old': """                JR      NZ, .RECD       ; THIS LINE IS ALREADY RECORDED""",
        'new': """                NOP                     ; MUTATION: ONE RECORD PER HIT
                NOP""",
        'filter': 'P3',
        'expect': ['P3/few/content'],
    },
    {
        'name': 'k1-wq-term',
        'why': ':wq jumps to TERM whether or not FILESAVE managed to save',
        'file': 'ACTION.Z8A',
        'old': """                RET     C               ; NOT SAVED: STAY, THE STATUS BAR SAYS WHY""",
        'new': """                NOP                     ; MUTATION: QUIT ANYWAY""",
        'filter': 'K1',
        # TERM leaves the editor, so the snapshot after :wq never comes.
        'expect_any': ['K1/wq/stayed', 'K1/x/stayed', 'K1-wq-save-failed'],
    },
    {
        'name': 'k2-read-count',
        'why': 'LOADDOC takes HL as a byte count even when DSKREAD failed',
        'file': 'FILEIO.Z8A',
        'old': """                JR      NC, .GOT
                CP      EEOF            ; THE BDOS WRAPPER SETS CY ON .EOF TOO
                JP      NZ, .RDERR      ; A REAL ERROR: HL IS NOT A COUNT
                LD      HL, 0
.GOT            LD      A, H""",
        'new': """                JR      .GOT            ; MUTATION: NO CARRY TEST
                CP      EEOF            ; THE BDOS WRAPPER SETS CY ON .EOF TOO
                JP      NZ, .RDERR      ; A REAL ERROR: HL IS NOT A COUNT
                LD      HL, 0
.GOT            LD      A, H""",
        'filter': 'K2',
        'expect_any': ['K2/rolled-back', 'K2-load-disk-error'],
    },
    {
        'name': 'k3-close-ignored',
        'why': 'FILESAVE reports [SAVED] when the close fails',
        'file': 'FILEIO.Z8A',
        'old': """                JR      C, .SVERR       ; THE CLOSE FAILED: NOT SAVED""",
        'new': """                NOP                     ; MUTATION: THE CLOSE IS TRUSTED
                NOP""",
        'filter': 'K3',
        'expect': ['K3/reported'],
    },
    {
        'name': 'r1-freelist-header',
        'why': 'FREEPSH writes its link over the record header (RECCAP and RECLEN low) instead of the payload',
        'file': 'BUFFER.Z8A',
        'old': """                LD      HL, TXPAGE + RECHDR_SZ
                ADD     HL, DE          ; HL = THE FREED RECORD'S PAYLOAD""",
        'new': """                LD      HL, TXPAGE      ; MUTATION: THE LINK OVER THE HEADER
                ADD     HL, DE          ; HL = THE FREED RECORD'S PAYLOAD""",
        'filter': 'R1',
        # The compactor then walks a garbage size: a dead session or a wrong
        # document, depending on where the slide lands.
        'expect_any': ['R1/compacted', 'R1/content', 'R1-freelist-compact'],
    },
    {
        'name': 'r1-freelist-stale',
        'why': 'SEGCOMP keeps the free list, whose entries point at records it has just slid',
        'file': 'COMPACT.Z8A',
        'old': """                LD      A, FREENIL
                LD      (FREEHD), A

                ; CLEAR STATUS MESSAGE AND REDRAW""",
        'new': """                NOP                     ; MUTATION: THE LIST SURVIVES
                NOP
                NOP
                NOP
                NOP

                ; CLEAR STATUS MESSAGE AND REDRAW""",
        'filter': 'R1',
        'expect_any': ['R1/entered', 'R1/content', 'R1-freelist-compact'],
    },
    {
        'name': 'r2-tomb-first',
        'why': 'LINEWRT retires the old record before NEWREC, so an OOM leaves the line on a dead record',
        'file': 'BUFFER.Z8A',
        'old': """                LD      A, (WORKBUF)
                LD      C, A            ; C = REQUIRED CAPACITY
                CALL    NEWREC
                JR      C, .OOM         ; CY = 1: OUT OF MEMORY, NOTHING CHANGED""",
        'new': """                POP     HL              ; MUTATION: KILL THE OLD RECORD FIRST
                PUSH    HL
                CALL    DIRREAD
                CALL    RECKILL
                LD      A, (WORKBUF)
                LD      C, A            ; C = REQUIRED CAPACITY
                CALL    NEWREC
                JR      C, .OOM         ; CY = 1: OUT OF MEMORY, NOTHING CHANGED""",
        'filter': 'R2',
        'expect_any': ['R2/content', 'R2/alive', 'R2-linewrt-oom'],
    },
    {
        'name': 'r3-segcomp-ix',
        'why': 'SEGCOMP does not give IX back, so the undo record UNDORST holds in it is lost to DRWSTAT',
        'file': 'COMPACT.Z8A',
        'old': """                POP     IY
                POP     IX
                OR      A               ; CY = 0: SUCCESS""",
        'new': """                POP     IY
                POP     HL              ; MUTATION: IX STAYS AS DRWSTAT LEFT IT
                OR      A               ; CY = 0: SUCCESS""",
        'filter': 'R3',
        'expect_any': ['R3/undone', 'R3/content', 'R3-undo-compact-ix'],
    },
    {
        'name': 'r4-undo-long',
        'why': 'a line longer than TEXTCOLS is packed into a normal record: '
               'the restore keeps a stale tail and the redo is lost',
        'file': 'UNDO.Z8A',
        'old': """                SET     6, C            ; UNDOF_BIG: LONGER THAN TEXTCOLS""",
        'new': """                NOP                     ; MUTATION: NOT FLAGGED BIG
                NOP""",
        'filter': 'R4',
        'expect': ['R4/long/recorded'],
    },
    {
        'name': 'undo-long-skip',
        'why': 'the first fix as it shipped on fix/undo-join-split: an edit '
               'on a long line is skipped and the history kept, so the undo '
               'splits a join with the space inside, replays records over '
               'lines the skipped edit moved, and reports a clean document',
        'file': 'UNDO.Z8A',
        'old': """                JR      C, .SIZED
                SET     6, C            ; UNDOF_BIG: LONGER THAN TEXTCOLS""",
        'new': """                JR      C, .SIZED
                RET                     ; MUTATION: SKIPPED, HISTORY KEPT
                NOP""",
        'filter': 'U1',
        'expect': ['U11/undo/content', 'U12/del/content',
                   'U12/modified/still-modified'],
    },
    {
        'name': 's2-undo-long-skip',
        'why': 'the first fix on S2ED: an edit on a line past 61 columns is '
               'skipped and the history kept',
        'target': 'S2ED',
        'file': 'UNDO.Z8A',
        'old': """                JR      C, .SIZED
                SET     6, C            ; UNDOF_BIG: LONGER THAN TEXTCOLS""",
        'new': """                JR      C, .SIZED
                RET                     ; MUTATION: SKIPPED, HISTORY KEPT
                NOP""",
        'filter': 'S2-53',
        'expect': ['S2-53/undo/content'],
    },
    {
        'name': 's61-undo-long-skip',
        'why': 'the first fix on S61ED: an edit on a line past 61 columns is '
               'skipped and the history kept',
        'target': 'S61ED',
        'file': 'UNDO.Z8A',
        'old': """                JR      C, .SIZED
                SET     6, C            ; UNDOF_BIG: LONGER THAN TEXTCOLS""",
        'new': """                JR      C, .SIZED
                RET                     ; MUTATION: SKIPPED, HISTORY KEPT
                NOP""",
        'filter': 'S62-13',
        'expect': ['S62-13/undo/content'],
    },
    {
        'name': 'rewrap-split',
        'why': 'REWRAP never finds a break inside the margin and splits a long '
               'line at the first space past it, leaving it longer than the margin',
        'file': 'EDIT.Z8A',
        'old': """                CP      ' '
                JR      Z, .BREAK
                DJNZ    .BKBACK""",
        'new': """                CP      ' '
                NOP                     ; MUTATION: NO BREAK INSIDE THE MARGIN
                NOP
                DJNZ    .BKBACK""",
        'filter': 'W4',
        'expect': ['W4/para/content'],
    },
    {
        'name': 'rewrap-fill',
        'why': 'REWRAP only splits: a short line never pulls the next one up, '
               'and the reflow the keys do in WRAP_TXT stops working',
        'file': 'EDIT.Z8A',
        'old': """.FILL           LD      HL, (RWLINE)""",
        'new': """.FILL           JP      .NEXT           ; MUTATION: NO PULL
                LD      HL, (RWLINE)""",
        'filter': 'W5',
        'expect': ['W5/content'],
    },
    {
        'name': 'reflow-first-empty',
        'why': 'reflow mode treats its own first line, when empty, as the end '
               'of the paragraph: Backspace below an empty line does nothing',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, 2
                LD      (RWSTOP), A""",
        'new': """                LD      A, 1            ; MUTATION: FIRST LINE NOT SPECIAL
                LD      (RWSTOP), A""",
        'filter': 'W5',
        'expect': ['W5/content'],
    },
    {
        'name': 'rewrap-ask',
        'why': 'switching WRAP from DEV to TXT in Settings no longer offers to '
               'rewrap the document',
        'file': 'ACTION.Z8A',
        'old': """                LD      HL, WRAPMODE
                AND     (HL)
                JR      Z, .NOWRP""",
        'new': """                LD      HL, WRAPMODE
                XOR     A               ; MUTATION: NEVER ASKED
                JR      Z, .NOWRP""",
        'filter': 'W3',
        # no question: the capture gated on WINPOLL never fires and the
        # session does not finish, so the case itself is what goes red
        'expect_any': ['W3/yes/asked', 'W3-rewrap-settings'],
    },
    {
        'name': 'rewrap-dev',
        'why': 'Edit > Rewrap acts in WRAP_DEV, which has no margin, and refills '
               'the paragraph to TEXTCOLS',
        'file': 'ACTION.Z8A',
        'old': """ACTRWRP         LD      A, (WRAPMODE)
                CP      WRAP_TXT
                RET     NZ""",
        'new': """ACTRWRP         LD      A, (WRAPMODE)
                CP      WRAP_TXT
                NOP                     ; MUTATION: DEV REWRAPS TOO""",
        'filter': 'W4',
        'expect': ['W4/dev/content'],
    },
    {
        'name': 'rewrap-sel-col0',
        'why': 'a selection ending at column 0 of a line rewraps that line too',
        'file': 'ACTION.Z8A',
        'old': """                DEC     HL              ; ENDS AT COLUMN 0: NOT THAT LINE""",
        'new': """                NOP                     ; MUTATION: THAT LINE TOO""",
        'filter': 'W4',
        'expect': ['W4/sel/content'],
    },
    {
        'name': 'quit-save-none',
        'why': 'the Save button of the quit question acts as No: it cancels',
        'file': 'WINDOW.Z8A',
        'old': """.SECOND         LD      A, (ASKSAV)     ; NO (1) CANCELS: 0; SAVE: 2
                ADD     A, A""",
        'new': """.SECOND         LD      A, (ASKSAV)     ; NO (1) CANCELS: 0; SAVE: 2
                XOR     A               ; MUTATION: SAVE CANCELS""",
        'filter': 'Q7',
        # the session waits on TERM that never comes: the case goes red
        'expect_any': ['Q7/save/exits', 'Q7-quit-save'],
    },
    {
        'name': 's2-quit-save-none',
        'why': 'S2ED: the Save button of the quit question acts as No',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """.SECOND         LD      A, (ASKSAV)     ; NO (1) CANCELS: 0; SAVE: 2
                ADD     A, A""",
        'new': """.SECOND         LD      A, (ASKSAV)     ; NO (1) CANCELS: 0; SAVE: 2
                XOR     A               ; MUTATION: SAVE CANCELS""",
        'filter': 'S2-55',
        'expect_any': ['S2-55/save/exits', 'S2-55-quit-save'],
    },
    {
        'name': 's61-quit-save-none',
        'why': 'S61ED: the Save button of the quit question acts as No',
        'target': 'S61ED',
        'file': 'WINDOW.Z8A',
        'old': """.SECOND         LD      A, (ASKSAV)     ; NO (1) CANCELS: 0; SAVE: 2
                ADD     A, A""",
        'new': """.SECOND         LD      A, (ASKSAV)     ; NO (1) CANCELS: 0; SAVE: 2
                XOR     A               ; MUTATION: SAVE CANCELS""",
        'filter': 'S62-15',
        'expect_any': ['S62-15/save/exits', 'S62-15-quit-save'],
    },
    {
        'name': 'quit-askflag',
        'why': 'a modified document is asked Yes / No, as if clean: no way to save',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, 1
.SETASK         LD      (ASKSAV), A""",
        'new': """                XOR     A               ; MUTATION: NEVER THE SAVE BUTTON
                NOP
.SETASK         LD      (ASKSAV), A""",
        'filter': 'Q7',
        # the save variant then waits on a TERM that never comes: the whole
        # case goes red and its checks are not evaluated
        'expect_any': ['Q7/yes/dialog', 'Q7-quit-save'],
    },
    {
        'name': 'quit-askclr',
        'why': 'the Save flag outlives the quit question and turns the next '
               'Yes / No dialog into Yes / Save',
        'file': 'ACTION.Z8A',
        'old': """                XOR     A
                LD      (ASKSAV), A     ; FOR THIS DIALOG ONLY""",
        'new': """                XOR     A               ; MUTATION: FLAG KEPT
                NOP
                NOP
                NOP""",
        'filter': 'Q7',
        'expect': ['Q7/esc/stays'],
    },
    {
        'name': 'quit-skey',
        'why': 'S does not answer Save in the quit question',
        'file': 'WINDOW.Z8A',
        'old': """                CP      'S'             ; SAVE (ASKSAV); WITHOUT IT, A CANCEL
                JR      Z, .SECOND
                CP      's'
                JR      Z, .SECOND""",
        'new': """                NOP                     ; MUTATION: NO S KEY
                NOP
                NOP
                NOP
                NOP
                NOP
                NOP
                NOP""",
        'filter': 'Q7',
        'expect_any': ['Q7/save/exits', 'Q7-quit-save'],
    },
    {
        'name': 'rollover-dev',
        'why': 'the cursor stops at the line ends in WRAP_DEV, as before v0.7',
        'file': 'EDIT.Z8A',
        'old': """ROLLOK          LD      A, (WRAPMODE)
                CP      WRAP_TXT
                RET     Z""",
        'new': """ROLLOK          LD      A, (WRAPMODE)
                CP      WRAP_TXT
                RET     Z
                OR      #FF             ; MUTATION: NO ROLLOVER IN DEV
                RET""",
        'filter': 'X3',
        'expect': ['X3/std/right', 'X3/ted/left'],
    },
    {
        'name': 'rollover-vi-normal',
        'why': 'Vi normal mode rolls over too: l at the end of a line leaves it',
        'file': 'EDIT.Z8A',
        'old': """                CP      KMVI
                JR      NZ, .YES
                LD      A, (VIMODE)""",
        'new': """                CP      KMVI
                JR      .YES            ; MUTATION: VI ROLLS IN EVERY MODE
                LD      A, (VIMODE)""",
        'filter': 'X3',
        'expect': ['X3/vi/normal-stays'],
    },
    {
        'name': 'undo-long-drop',
        'why': 'dev as it was reported: an edit on a long line drops the '
               'whole history, so Ctrl+Z does nothing',
        'file': 'UNDO.Z8A',
        'old': """                JR      C, .SIZED
                SET     6, C            ; UNDOF_BIG: LONGER THAN TEXTCOLS""",
        'new': """                JR      C, .SIZED
                JP      UNDOINIT        ; MUTATION: HISTORY DROPPED""",
        'filter': 'U1',
        'expect': ['U11/undo/undone', 'U11/undo/content', 'U12/sel/content'],
    },
    {
        'name': 'r4-redo-long',
        'why': 'an undo that displaces a line too long for its record keeps the redo, replayed truncated',
        'file': 'UNDO.Z8A',
        'old': """                LD      (UNDONRD), A    ; NON-ZERO: NO REDO FOR THIS ACTION""",
        'new': """                NOP                     ; MUTATION: THE REDO IS KEPT
                NOP
                NOP""",
        'filter': 'R4',
        'expect': ['R4/redo/withdrawn', 'R4/redo/content'],
    },
    {
        'name': 'f2-winpoll-flags',
        'why': 'the defect as it shipped: WINPOLL returns CHGET\'s flags, which '
               'are Z when the keyboard buffer pointer wraps, so every dialog '
               'dropped one key in forty',
        'file': 'UI.Z8A',
        'old': """                LD      IX, CHGET
                CALL    BIOSCALL
                ; CHGET RETURNS THE KEY IN A AND NO FLAG AT ALL: WHEN ITS""",
        'new': """                LD      IX, CHGET
                JP      BIOSCALL        ; MUTATION: CHGET'S FLAGS AS THE ANSWER
                ; CHGET RETURNS THE KEY IN A AND NO FLAG AT ALL: WHEN ITS""",
        'filter': 'H35',
        'expect': ['H35/every-key'],
    },
    {
        'name': 's2-f2-winpoll-flags',
        'why': 'the same WINPOLL defect on S2ED',
        'target': 'S2ED',
        'file': 'UI.Z8A',
        'old': """                LD      IX, CHGET
                CALL    BIOSCALL
                ; CHGET RETURNS THE KEY IN A AND NO FLAG AT ALL: WHEN ITS""",
        'new': """                LD      IX, CHGET
                JP      BIOSCALL        ; MUTATION: CHGET'S FLAGS AS THE ANSWER
                ; CHGET RETURNS THE KEY IN A AND NO FLAG AT ALL: WHEN ITS""",
        'filter': 'S2-27',
        'expect': ['S2-27/every-key'],
    },
    {
        'name': 'f2-mask-ignored',
        'why': 'the scan keeps every file whatever the mask says',
        'file': 'BROWSE.Z8A',
        'old': """                CALL    BRWMATCH        ; A FILE: IF THE MASK LETS IT THROUGH
                JR      NZ, .NEXT       ; (THE SLOT IS SIMPLY REUSED)""",
        'new': """                CALL    BRWMATCH        ; MUTATION: RESULT IGNORED""",
        'filter': 'H34',
        'expect': ['H34/mask/masked'],
    },
    {
        'name': 'f2-mask-dirs',
        'why': 'directories go through the mask too, so *.TXT hides the way '
               'into every subdirectory',
        'file': 'BROWSE.Z8A',
        'old': """                AND     #10             ; A DIRECTORY: ALWAYS
                JR      NZ, .TAKE""",
        'new': """                AND     #10             ; MUTATION: MASKED LIKE A FILE""",
        'filter': 'H34',
        'expect': ['H34/mask/masked'],
    },
    {
        'name': 'f2-no-parent',
        'why': 'no parent entry below the root, so there is no way back up',
        'file': 'BROWSE.Z8A',
        'old': """                CALL    BRWROOT
                JR      Z, .NOUP
                CALL    BRWFREE""",
        'new': """                CALL    BRWROOT
                JR      .NOUP           ; MUTATION: NEVER A PARENT
                CALL    BRWFREE""",
        'filter': 'H34',
        # Without the parent every later key lands one entry off, a file
        # opens early and the next WINPOLL snapshot never fires.
        'expect_any': ['H34/nav/into', 'H34-browse-open'],
    },
    {
        'name': 'f2-no-reselect',
        'why': 'going up lands on the first entry, not on the directory left',
        'file': 'BROWSE.Z8A',
        'old': """.SELPRV         ; COMING BACK UP: SELECT THE DIRECTORY JUST LEFT
                LD      A, (BRWPREV)""",
        'new': """.SELPRV         ; COMING BACK UP: SELECT THE DIRECTORY JUST LEFT
                JR      .CLRPRV         ; MUTATION: FORGET IT
                LD      A, (BRWPREV)""",
        'filter': 'H34',
        'expect': ['H34/nav/back-up'],
    },
    {
        'name': 'f2-no-hidden',
        'why': 'the search attributes leave out hidden and system files',
        'file': 'CONST_CORE.Z8A',
        'old': "ATR_ALL         EQU     #16",
        'new': "ATR_ALL         EQU     #10             ; MUTATION: NO H, NO S",
        'filter': 'H34',
        'expect': ['H34/nav/listing'],
    },
    {
        'name': 'f2-no-italic',
        'why': 'hidden and system entries are drawn like any other',
        'file': 'BROWSER.Z8A',
        'old': """                AND     %00000110       ; HIDDEN OR SYSTEM: ITALIC""",
        'new': """                AND     0               ; MUTATION: ALWAYS UPRIGHT""",
        'filter': 'H34',
        'expect': ['H34/nav/drawn'],
    },
    {
        'name': 's2-f3-sel-color',
        'why': 'the selected slot is not highlighted with VCOLBSEL on S2ED',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': "                LD      A, (VCOLBSEL)   ; SELECTED, THE GRID FOCUSED: VCOLBSEL",
        'new': "                LD      A, (VCOLWIN)    ; MUTATION: NORMAL COLOR",
        'filter': 'S2-28',
        'expect': ['S2-28/nav/drawn'],
    },
    {
        'name': 's2-f3-hid-color',
        'why': 'hidden and system entries are drawn in normal color instead of VCOLHI on S2ED',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': "                LD      A, (VCOLHI)     ; HIDDEN/SYSTEM: VCOLHI",
        'new': "                LD      A, (VCOLWIN)    ; MUTATION: NORMAL COLOR",
        'filter': 'S2-28',
        'expect': ['S2-28/nav/drawn'],
    },
    {
        'name': 's2-f3-btn-color',
        'why': 'unfocused buttons in the file browser are drawn with color 0 instead of VCOLWIN on S2ED',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': """                LD      A, (VCOLWIN)
                JR      NZ, .B1COL""",
        'new': """                XOR     A               ; MUTATION: COLOR 0 (BLACK ON BLACK)
                JR      NZ, .B1COL""",
        'filter': 'S2-28',
        'expect': ['S2-28/nav/drawn'],
    },
    {
        'name': 'f2-btn-arrows',
        'why': 'left and right arrow keys do not switch focus between browser buttons',
        'file': 'BROWSER.Z8A',
        'old': """                CP      CRIGHT
                JR      Z, .BTNRGT""",
        'new': """                CP      CRIGHT
                NOP
                NOP""",
        'filter': 'H34',
        'expect': ['H34/cursor/btn-arrows'],
    },
    {
        'name': 'f2-fld-down',
        'why': 'down arrow in name field does not move focus to the buttons',
        'file': 'BROWSER.Z8A',
        'old': """                CP      CDOWN
                JR      Z, .FLDDN""",
        'new': """                CP      CDOWN
                NOP
                NOP""",
        'filter': 'H34',
        'expect': ['H34/cursor/fld-down'],
    },
    {
        'name': 's2-f3-btn-arrows',
        'why': 'left and right arrow keys do not switch focus between browser buttons on S2ED',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': """                CP      CRIGHT
                JR      Z, .BTNRGT""",
        'new': """                CP      CRIGHT
                NOP
                NOP""",
        'filter': 'S2-28',
        'expect': ['S2-28/cursor/btn-arrows'],
    },
    {
        'name': 's2-f3-fld-down',
        'why': 'down arrow in name field does not move focus to the buttons on S2ED',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': """                CP      CDOWN
                JR      Z, .FLDDN""",
        'new': """                CP      CDOWN
                NOP
                NOP""",
        'filter': 'S2-28',
        'expect': ['S2-28/cursor/fld-down'],
    },
    {
        'name': 'f2-date-env',
        'why': 'the date format ignores the DATE environment item',
        'file': 'BROWSE.Z8A',
        'old': """.DATE           LD      HL, .DATENM""",
        'new': """.DATE           RET                     ; MUTATION: ALWAYS YMD
                LD      HL, .DATENM""",
        'filter': 'H34',
        'expect': ['H34/nav/info'],
    },
    {
        'name': 'f2-rowmv-wrong',
        'why': 'a one-row scroll moves the grid the wrong way',
        'file': 'BROWSER.Z8A',
        'old': """                CP      1
                JR      NZ, .RMDOWN""",
        'new': """                CP      1
                JR      Z, .RMDOWN      ; MUTATION: BACKWARDS""",
        'filter': 'H35',
        'expect': ['H35/scroll-paint'],
    },
    {
        'name': 'f2-no-more',
        'why': 'a full listing does not say so',
        'file': 'BROWSE.Z8A',
        'old': """                JR      C, .ROOM
                LD      A, 1
                LD      (BRWMORE), A""",
        'new': """                JR      C, .ROOM
                XOR     A               ; MUTATION: SILENT
                LD      (BRWMORE), A""",
        'filter': 'H35',
        'expect': ['H35/capacity'],
    },
    {
        'name': 's2-f3-capacity',
        'why': 'BRWMAX lowered to 32 on S2ED: capacity ceiling drops',
        'target': 'S2ED',
        'file': 'CONST_S2.Z8A',
        'old': "BRWMAX          EQU     64              ; FILE BROWSER ENTRY CAPACITY",
        'new': "BRWMAX          EQU     32              ; MUTATION",
        'filter': 'S2-29',
        'expect': ['S2-29/capacity'],
    },
    {
        'name': 's2-f3-scroll-down',
        'why': 'scroll computation off by one row on S2ED',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': "                SUB     BRWROWS - 1",
        'new': "                SUB     BRWROWS         ; MUTATION: OFF BY ONE",
        'filter': 'S2-29',
        'expect': ['S2-29/scroll-down'],
    },
    {
        'name': 'f2-start-cwd',
        'why': 'the browser always starts in the current directory, not in '
               'the one the document came from',
        'file': 'BROWSER.Z8A',
        'old': """                JR      Z, .CWD         ; NO DOCUMENT NAME
                LD      A, (FILENAME + 1)
                CP      ':'
                JR      NZ, .CWD""",
        'new': """                JR      Z, .CWD         ; NO DOCUMENT NAME
                LD      A, (FILENAME + 1)
                CP      ':'
                JR      .CWD            ; MUTATION""",
        'filter': 'H35',
        'expect': ['H35/start-dir'],
    },
    {
        'name': 'f2-open-noask',
        'why': 'Open throws a modified document away without asking',
        'file': 'ACTION.Z8A',
        'old': """ACTOPEN         LD      A, (MODIFIED)
                OR      A
                JR      Z, .BROWSE""",
        'new': """ACTOPEN         LD      A, (MODIFIED)
                OR      A
                JR      .BROWSE         ; MUTATION: NEVER ASK""",
        'filter': 'H34',
        'expect_any': ['H34/dirty/kept', 'H34-browse-open'],
    },
    {
        'name': 'f2-ctrl-o',
        'why': 'Ctrl+O is bound in no keymap again',
        'file': 'KEYMAP.Z8A',
        'old': """                DEFB    CTRL_O,  MODCTRL, ACOPEN
""",
        'new': "",
        'filter': 'H34',
        'expect_any': ['H34/nav/listing', 'H34-browse-open'],
    },
    {
        'name': 'f2-vi-e',
        'why': 'Vi :e with no name says "Argument required" instead of '
               'opening the browser',
        'file': 'ACTION.Z8A',
        'old': """                JP      Z, ACTOPEN      ; :e ALONE: THE FILE BROWSER""",
        'new': """                JP      Z, .ERARG       ; MUTATION""",
        'filter': 'H34',
        'expect_any': ['H34/vi/listing', 'H34-browse-open'],
    },
    {
        'name': 'f2-typed-absolute',
        'why': 'a name typed in the field is taken as a whole path instead '
               'of relative to the directory being browsed',
        'file': 'BROWSER.Z8A',
        'old': """                CP      ':'
                JR      NZ, .RELAT""",
        'new': """                CP      ':'
                JR      Z, .RELAT       ; MUTATION: INVERTED""",
        'filter': 'H34',
        'expect': ['H34/typed/opened'],
    },
    {
        'name': 'f1-fnamlen40',
        'why': 'FILENAME back to 40 bytes: a 48-character path is cut on the '
               'command line and the file it names cannot be found',
        'file': 'CONST_CORE.Z8A',
        'old': "FNAMLEN         EQU     64",
        'new': "FNAMLEN         EQU     40              ; MUTATION",
        'filter': 'H33',
        'expect': ['H33/loaded', 'H33/filename'],
    },
    {
        'name': 's2-f1-fnamlen40',
        'why': 'FILENAME back to 40 bytes on S2ED',
        'target': 'S2ED',
        'file': 'CONST_CORE.Z8A',
        'old': "FNAMLEN         EQU     64",
        'new': "FNAMLEN         EQU     40              ; MUTATION",
        'filter': 'S2-26',
        'expect': ['S2-26/loaded', 'S2-26/filename'],
    },
    {
        'name': 'f1-fnbase',
        'why': 'the menu bar prints the whole FILENAME, path included, over '
               'the menu titles',
        'file': 'UI.Z8A',
        'old': """                CALL    FNBASE          ; HL = BASENAME, CLOBBERS AF, DE
                LD      DE, FNAMBUF""",
        'new': """                LD      HL, FILENAME    ; MUTATION: THE WHOLE PATH
                LD      DE, FNAMBUF""",
        'filter': 'H33',
        'expect': ['H33/menu-name'],
    },
    {
        'name': 's2-f1-fnbase',
        'why': 'S2ED\'s menu bar copies the whole FILENAME, path included',
        'target': 'S2ED',
        'file': 'UI.Z8A',
        'old': """                CALL    FNBASE          ; HL = BASENAME, CLOBBERS AF, DE
                LD      DE, FNAMBUF""",
        'new': """                LD      HL, FILENAME    ; MUTATION: THE WHOLE PATH
                LD      DE, FNAMBUF""",
        'filter': 'S2-26',
        'expect': ['S2-26/menu-name'],
    },
    {
        'name': 'f0-new-noask',
        'why': 'the defect as it shipped: New resets a modified document '
               'without asking',
        'file': 'ACTION.Z8A',
        'old': """ACTNEW          LD      A, (MODIFIED)
                OR      A
                JR      Z, .FRESH""",
        'new': """ACTNEW          LD      A, (MODIFIED)
                OR      A
                JR      .FRESH          ; MUTATION: NEVER ASK""",
        'filter': 'H30',
        # No dialog ever opens, so the snapshot armed on WINPOLL never fires
        # and the dirty sessions die waiting for it.
        'expect_any': ['H30/dirty-no/asked', 'H30-new-document'],
    },
    {
        'name': 'f0-new-ignores-no',
        'why': 'New asks but discards the document whatever the answer',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, (WINRES)
                OR      A
                RET     Z               ; NO: KEEP THE DOCUMENT""",
        'new': """                LD      A, (WINRES)
                OR      A               ; MUTATION: THE ANSWER IS IGNORED""",
        'filter': 'H30',
        'expect': ['H30/dirty-no/kept'],
    },
    {
        'name': 'f0-ctrl-n',
        'why': 'Ctrl+N is bound in no keymap again',
        'file': 'KEYMAP.Z8A',
        'old': """                DEFB    CTRL_N,  MODCTRL, ACNEW
""",
        'new': "",
        'filter': 'H30',
        # Ctrl+N does nothing: the clean check goes red, and the dirty
        # sessions die waiting for a dialog that never opens.
        'expect_any': ['H30/clean/fresh', 'H30-new-document'],
    },
    {
        'name': 'f0-load-order',
        'why': 'the defect as it shipped: FILELOAD resets the document before '
               'opening the file, so a refused :e has already thrown it away',
        'file': 'FILEIO.Z8A',
        'old': """LOADDOC         XOR     A
                LD      (LOADERR), A
                PUSH    HL              ; [SP] = NAME""",
        'new': """LOADDOC         PUSH    HL
                CALL    FILENEW         ; MUTATION: RESET BEFORE OPENING
                POP     HL
                XOR     A
                LD      (LOADERR), A
                PUSH    HL              ; [SP] = NAME""",
        'filter': 'H31',
        'expect': ['H31/toolarge/state'],
    },
    {
        'name': 'f0-e-name-first',
        'why': 'the defect as it shipped: :e copies the new name into FILENAME '
               'before loading, so a refused load leaves the old document '
               'under the name of the file it refused',
        'file': 'ACTION.Z8A',
        'old': """                LD      DE, LINBUF
                CALL    .CPYFN
                LD      HL, LINBUF""",
        'new': """                CALL    .CPYFNAM        ; MUTATION: STRAIGHT INTO FILENAME
                LD      HL, FILENAME""",
        'filter': 'H31',
        'expect': ['H31/toolarge/state'],
    },
    {
        'name': 'f0-noexist-refused',
        'why': ':e on a missing file reports an error instead of opening an '
               'empty document under that name, as vi does',
        'file': 'ACTION.Z8A',
        'old': """                CP      ENOFIL
                JR      NZ, .ECANT""",
        'new': """                CP      ENOFIL
                JR      .ECANT          ; MUTATION: NOT FOUND IS AN ERROR""",
        'filter': 'H31',
        'expect': ['H31/noexist/state', 'H31/noexist/message'],
    },
    {
        'name': 'f0-load-modified',
        'why': 'FILELOAD leaves MODIFIED as it was, so the document :e! has '
               'just read back from disk still counts as unsaved',
        'file': 'FILEIO.Z8A',
        'old': """                CALL    FNAMSET         ; THE NAME BECOMES THE DOCUMENT'S
                XOR     A
                LD      (MODIFIED), A""",
        'new': """                CALL    FNAMSET         ; THE NAME BECOMES THE DOCUMENT'S
                XOR     A               ; MUTATION: MODIFIED LEFT ALONE""",
        'filter': 'H31',
        'expect': ['H31/force/state'],
    },
    {
        'name': 'f0-save-silent',
        'why': 'the defect as it shipped: Ctrl+S with no file name returns '
               'without a word',
        'file': 'FILEIO.Z8A',
        'old': """                LD      HL, .STRNONM
                CALL    SETMSG
                CALL    DRWSTAT
                SCF
                RET""",
        'new': """                SCF                     ; MUTATION: SILENT
                RET""",
        'filter': 'H32',
        'expect': ['H32/message'],
    },
    {
        'name': 's2-f0-donew',
        'why': 'S2ED\'s DONEW confirms without showing the dialog',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """DONEW           LD      HL, DOASK.TITNEW
                LD      DE, DOASK.STRNEW""",
        # Same size as the two LDs it replaces (6 bytes): S2ED's feature
        # container has 2 bytes above its 128-byte floor, so a mutation that
        # grows it no longer assembles (measured 2026-10-06).
        'new': """DONEW           LD      A, 1            ; MUTATION: YES WITHOUT ASKING
                LD      (WINRES), A
                RET""",
        'filter': 'S2-25',
        'expect_any': ['S2-25/dirty-no/asked', 'S2-25-new-document'],
    },
    {
        'name': 'b5-dsk-root',
        'why': 'the disk goes back to carrying the programs in the root, where '
               'the PATH that AUTOEXEC.BAT sets does not look, so booting it '
               'never reaches the editor',
        'file': 'Makefile',
        'old': '\t@$(DSKFAT) $(DSKFILE) add TOOLS $(DSKTOOLS)',
        'new': '\t@$(DSKFAT) $(DSKFILE) add . $(DSKTOOLS)',
        'filter': 'B5',
        'expect_any': ['B5/booted', 'B5-shipped-disk'],
    },
    {
        'name': 's2-b5-dsk-root',
        'why': 'the S2 disk carries S2ED in the root again, off the PATH',
        'target': 'S2ED',
        'file': 'Makefile',
        'old': '\t@$(DSKFAT) $(DSKFILE_S2) add TOOLS $(DSKCONT_S2)',
        'new': '\t@$(DSKFAT) $(DSKFILE_S2) add . $(DSKCONT_S2)',
        'filter': 'S2-24',
        'expect_any': ['S2-24/booted', 'S2-24-shipped-disk'],
    },
    {
        'name': 's2-h29-bare-open',
        'why': 'S2ED opens S2ED.DAT and S2ED.FNT by bare name again, so run '
               'through PATH it aborts at boot',
        'target': 'S2ED',
        'file': 'BDOS.Z8A',
        'old': """HOMEOPN         PUSH    HL
                CALL    HOMEFN""",
        'new': """HOMEOPN         JP      DSKOPEN         ; MUTATION: BARE NAME ONLY
                PUSH    HL
                CALL    HOMEFN""",
        'filter': 'S2-23',
        'expect_any': ['S2-23/path/booted', 'S2-23-home-path'],
    },
    {
        'name': 'h29-bare-open',
        'why': 'the defect as it shipped: S6ED.DAT and S6ED.FNT are opened by '
               'bare name, i.e. in the current directory, so a program found '
               'through PATH aborts at boot with "S6ED.DAT not found"',
        'file': 'BDOS.Z8A',
        'old': """HOMEOPN         PUSH    HL
                CALL    HOMEFN""",
        'new': """HOMEOPN         JP      DSKOPEN         ; MUTATION: BARE NAME ONLY
                PUSH    HL
                CALL    HOMEFN""",
        'filter': 'H29',
        # CHKDAT aborts to DOS: MAINLOOP is never reached.
        'expect_any': ['H29/path/booted', 'H29-home-path'],
    },
    {
        'name': 'h29-no-fallback',
        'why': 'HOMEOPN tries only the home directory, so a setup that worked '
               'before -- the .COM on the PATH, DAT and FNT in the current '
               'directory -- stops booting',
        'file': 'BDOS.Z8A',
        'old': """                POP     BC              ; BC = THE BARE NAME
                RET     NC""",
        'new': """                POP     BC              ; BC = THE BARE NAME
                RET                     ; MUTATION: NO RETRY IN THE CURRENT DIR""",
        'filter': 'H29',
        'expect_any': ['H29/fallback/booted', 'H29-home-path'],
    },
    {
        'name': 'h29-loadflag',
        'why': 'LOAD_FLAG is read after DOSVER, which zeroes it, so PROGRAM is '
               'never trusted and every name stays bare',
        'file': 'S6ED.Z8A',
        'old': """                LD      A, (LOADFLAG)
                LD      (LOADFLG), A""",
        'new': """                XOR     A               ; MUTATION: FLAG ALREADY ZEROED
                LD      (LOADFLG), A""",
        'filter': 'H29',
        'expect_any': ['H29/path/booted', 'H29-home-path'],
    },
    {
        'name': 'h29-no-local',
        'why': 'CFGRUN reads only the general CFG next to the program, so the '
               'CFG of the directory the editor is run from is ignored',
        'file': 'XSEG.Z8A',
        'old': """                LD      A, (CFGLOC)
                OR      A
                RET     Z
                LD      HL, CFGNAME     ; LOCAL""",
        'new': """                RET                     ; MUTATION: GENERAL CFG ONLY
                LD      A, (CFGLOC)
                OR      A
                RET     Z
                LD      HL, CFGNAME     ; LOCAL""",
        'filter': 'H29',
        'expect': ['H29/path/tabwidth', 'H29/path/profile'],
    },
    {
        'name': 'h29-samedir',
        'why': 'the directory comparison always reports a difference, so the '
               'root disk reads its one CFG twice',
        'file': 'BDOS.Z8A',
        'old': """                LD      A, (DE)
                OR      A
                RET     Z               ; SAME DIRECTORY: ONE CFG, READ ONCE""",
        'new': """                LD      A, (DE)
                OR      A
                JR      .LOCAL          ; MUTATION: NEVER THE SAME""",
        'filter': 'H29',
        'expect': ['H29/root/cfgloc'],
    },
    {
        'name': 'g8-alntbl',
        'why': 'PARSALN dispatches on the first letter of the value again, so '
               'OFF and ON collide on O and AUTOALIGN=OFF turns auto-align ON',
        'file': 'CFG.Z8A',
        'old': """                CP      'O'
                RET     NZ              ; UNKNOWN VALUE: KEEP THE DEFAULT
                INC     HL
                LD      A, (HL)
                CALL    UPCASE
                CP      'N'
                JR      Z, .ALNON
                CP      'F'
                RET     NZ
                LD      A, ALGN_OFF
                JR      .ALNSET""",
        'new': """                CP      'O'                 ; MUTATION: ONE LETTER ONLY
                RET     NZ
                JR      .ALNON""",
        'filter': 'G8',
        'expect': ['G8/compact/autoalign'],
    },
    {
        'name': 'd11-splitl',
        'why': 'SPLITL splits at the raw CURX, so a space at the right margin '
               'of a full line carries its last character down instead of '
               'breaking after it',
        'file': 'EDIT.Z8A',
        'old': 'SPLITL          CALL    EFFCURX',
        'new': 'SPLITL          LD      A, (CURX)   ; MUTATION: RAW COLUMN',
        'filter': 'D11',
        'expect': ['D11/space/content'],
    },
    {
        'name': 'd11-pushwrap',
        'why': 'EDPSHWR measures the cursor with the raw CURX, so the '
               'character that forces the wrap lands one place too early '
               'inside the word that moved down',
        'file': 'EDIT.Z8A',
        'old': """                CALL    EFFCURX
                CP      B""",
        'new': """                LD      A, (CURX)       ; MUTATION: RAW COLUMN
                CP      B""",
        'filter': 'D11',
        'expect': ['D11/push/content'],
    },
    {
        'name': 's2-pushwrap',
        'why': 'the same raw-column push-wrap seen on the 64-column record, '
               'with the screen checked as well as the document',
        'target': 'S2ED',
        'file': 'EDIT.Z8A',
        'old': """                CALL    EFFCURX
                CP      B""",
        'new': """                LD      A, (CURX)       ; MUTATION: RAW COLUMN
                CP      B""",
        'filter': 'S2-9',
        'expect': ['S2-9/push/content', 'S2-9/push/screen'],
    },
    # --- SUITE S2 (MSX1 / SCREEN 2) -----------------------------------
    #
    # These run on the S2 target: a different binary, a different gate and a
    # different machine, from the same CORE sources.  `target` says which.
    {
        'name': 's2-render-brow',
        'why': 'RENDEROW calls COMROW with B destroyed, so every text row '
               'composes on top of row 0',
        'target': 'S2ED',
        'file': 'RENDER.Z8A',
        'old': """                ; RESTORE B = SCREEN ROW. LINEREAD ENDS IN AN LDIR AND
                ; SCANMKUP CLOBBERS BC, SO COMROW WOULD OTHERWISE COMPOSE
                ; EVERY ROW ON TOP OF ROW 0.
                POP     BC
                PUSH    BC""",
        'new': """                ; MUTATION: B IS NOT RESTORED BEFORE COMROW""",
        'filter': 'S2-1',
        'expect': ['S2-1/rows'],
    },
    {
        # 2026-09-25: under variable-length records, WORKBUF is zeroed at boot
        # by INIT so an offset of 81 instead of 1 + TEXTCOLS leaves bytes 65..80
        # as zero when loading from command line, and no yellow bands appear.
        # What guards against target literal geometry in shared CORE code is
        # the static target-params check.
        'name': 's2-attr-clear',
        'why': 'FILELOAD clears the attribute half from the S6 offset (81 '
               'instead of 1 + TEXTCOLS): an S6 literal in shared CORE code',
        'file': 'FILEIO.Z8A',
        'old': """                LD      HL, WORKBUF + 1 + WORKATTR
                LD      (HL), 0
                LD      D, H
                LD      E, L
                INC     DE
                LD      BC, MAXCOLS - 1""",
        'new': """                LD      HL, WORKBUF + 81  ; MUTATION: THE S6 LITERAL
                LD      (HL), 0
                LD      D, H
                LD      E, L
                INC     DE
                LD      BC, MAXCOLS - 1""",
        'filter': 'T0',
        'expect_static': ['target-params'],
    },
    {
        'name': 's2-cursor-cell',
        'why': 'the inversion covers the WHOLE cell instead of one text '
               'column -- a two-character cursor, and consecutive selection '
               'deltas that cancel each other out',
        'target': 'S2ED',
        'file': 'RENDER.Z8A',
        'old': """                LD      A, #F0          ; EVEN COLUMN: HIGH NIBBLE
                JR      Z, .HALF
                LD      A, #0F          ; ODD COLUMN: LOW NIBBLE""",
        'new': """                LD      A, #FF          ; MUTATION: WHOLE CELL
                JR      Z, .HALF
                LD      A, #FF""",
        'filter': 'S2-3',
        'expect': ['S2-3/one-column'],
    },
    {
        'name': 's2-sel-cell',
        'why': 'the same whole-cell inversion seen through the selection: '
               'SELDIFF extends one column at a time, so two deltas land on '
               'one cell and their XORs cancel, leaving residue behind',
        'target': 'S2ED',
        'file': 'RENDER.Z8A',
        'old': """                LD      E, #F0
                JR      Z, .PXHAVE
                LD      E, #0F""",
        'new': """                LD      E, #FF          ; MUTATION: WHOLE CELL
                JR      Z, .PXHAVE
                LD      E, #FF""",
        'filter': 'S2-4',
        'expect': ['S2-4/range'],
    },
    {
        'name': 's2-band-rows',
        'why': 'the cursor is bounded by SCRROWS (the physical screen) where '
               'it means ROWSVIS (the text band), so it walks two rows below '
               'the painted band before the viewport scrolls',
        'target': 'S2ED',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, (CURY)
                CP      ROWSVIS - 1
                JR      Z, .SCRLDN""",
        'new': """                LD      A, (CURY)
                CP      SCRROWS - 1     ; MUTATION: PHYSICAL, NOT VISIBLE
                JR      Z, .SCRLDN""",
        'filter': 'S2-5',
        'expect': ['S2-5/cury'],
    },
    {
        # 2026-09-25: under variable-length records the historical poison (an
        # attribute byte dragged into the last text column, after which
        # EDINSCHR saw a full record) is no longer observable -- line I/O is
        # length-bounded, so the garbage sits past the length and nothing
        # reads it.  What still guards the class is the static target-params
        # check: CORE may not spell record geometry as numbers.  The mutation
        # therefore runs on the S6ED context, where the static checks live.
        'name': 's2-delbk-79',
        'why': 'EDDELBK walks its shift loop to a literal 79 and blanks '
               'WORKBUF + 80: an S6 literal in shared CORE code',
        'file': 'EDIT.Z8A',
        # Re-anchored 2026-09-27: since Phase B, EDDELBK shifts by the line
        # length and addresses the attribute half through WORKATTR.  The
        # defect is the same one: an S6 geometry literal (the 81-byte
        # attribute offset, the 80-column blank) in EDDELBK's shift and blank.
        'old': """                LD      HL, WORKATTR
                ADD     HL, DE          ; HL = DEST ATTR (DEST TEXT + WORKATTR)""",
        'new': """                LD      HL, 81          ; MUTATION: THE S6 LITERAL
                ADD     HL, DE          ; HL = DEST ATTR (DEST TEXT + WORKATTR)""",
        'also': [('EDIT.Z8A',
                  """                LD      BC, WORKATTR
                ADD     HL, BC          ; HL = WORKBUF + L + WORKATTR""",
                  """                LD      BC, 80          ; MUTATION: THE S6 LITERAL
                ADD     HL, BC          ; HL = WORKBUF + L + WORKATTR""")],
        'filter': 'S2-6',
        'expect_static': ['target-params'],
    },
    {
        'name': 's2-enterbot-23',
        'why': 'EDNWLIN repaints the shortened head at a literal row 23, '
               'which on S2 is the status bar',
        'target': 'S2ED',
        'file': 'SCROLL.Z8A',
        'old': """                LD      B, TXRLAST - 1
                CALL    COLRNDR
                JP      TXTPUSH""",
        'new': """                LD      B, 23           ; MUTATION: THE S6 LITERAL
                CALL    COLRNDR
                JP      TXTPUSH""",
        'filter': 'S2-7',
        'expect': ['S2-7/head-repainted'],
    },
    {
        'name': 's2-scroll-nodump',
        'why': 'TXTPSHB composes the scrolled band and never pushes the pattern '
               'band to VRAM -- the round-1 defect: the shadows are right and '
               'the screen is a scroll behind',
        'target': 'S2ED',
        'file': 'SCROLL.Z8A',
        'old': """                LD      C, 0            ; BC = ROWS * ROWLEN
                CALL    VDPDUMP
                POP     BC
                LD      C, TXRLAST""",
        'new': """                LD      C, 0            ; BC = ROWS * ROWLEN
                                        ; MUTATION: BAND NEVER PUSHED TO VRAM
                POP     BC
                LD      C, TXRLAST""",
        'filter': 'S2-5',
        'expect': ['S2-5/scrolled-rows'],
    },
    {
        'name': 's2-theme-default',
        'why': 'THMAMBR carries the DARK data, so THEME=AMBER loads the '
               'default theme: the vars say white-on-black and the VRAM '
               'colour table agrees, while the config claims amber',
        'target': 'S2ED',
        'file': 'VDP.Z8A',
        'old': "THMAMBR         DEFB    #A1, #A6, #B1, #71, #31, #E1, 1, #A6  ; AMBER",
        'new': "THMAMBR         DEFB    #F1, #F4, #B1, #71, #31, #E1, 1, #F4  ; MUTATION: DARK DATA",
        'filter': 'S2-10',
        'expect': ['S2-10/amber/vars', 'S2-10/amber/text',
                   'S2-10/amber/menu', 'S2-10/amber/status'],
    },
    {
        'name': 's2-coldirt',
        'target': 'S2ED',
        'why': 'COMROW changes COLMAP without flagging the row, so RENDEROW skips its COLDUMP and the new colours never reach VRAM',
        'file': 'RENDER.Z8A',
        'old': """                LD      (IY + 0), A
                LD      A, #FF
                LD      (COLDIRT), A
.SAMEC          INC     IY""",
        'new': """                LD      (IY + 0), A
                LD      A, #FF
                NOP                     ; MUTATION: THE ROW STAYS CLEAN
                NOP
                NOP
.SAMEC          INC     IY""",
        'filter': 'S2-14',
        'expect': ['S2-14/line0', 'S2-14/line1'],
    },
    {
        # The TPA chain (VARS.Z8A) exists so no buffer ever names an address.
        # One literal here and the allocation stops following whatever the
        # target actually declared above it.
        'name': 't0-tpa-fixed',
        'why': 'the S2 font buffer is pinned to a literal address '
               'instead of chaining off the top of the undo ring',
        'file': 'VARS.Z8A',
        'old': 'FONT4H          EQU     ((UNDOTOP + 255) / 256) * 256',
        'new': 'FONT4H          EQU     #6A00',
        'filter': 'T0',
        'expect_static': ['tpa-chain'],
    },
    {
        'name': 's2-wsvbuf-undo',
        'why': 'the window save buffer is allocated on top of the undo ring: '
               'the dialog opens and restores perfectly, and eats the undo '
               'transaction while it is open',
        'target': 'S2ED',
        'file': 'S2/CONST_S2.Z8A',
        # Re-anchored 2026-09-27: WSVBUF moved to page 3 (#C600).  Symbolic,
        # so the mutation follows the undo ring wherever the layout puts it.
        'old': 'WSVBUF          EQU     #C600',
        'new': 'WSVBUF          EQU     UNDOBAS         ; MUTATION: ON THE UNDO RING',
        'filter': 'S2-12',
        'expect': ['S2-12/content'],
    },
    {
        # The chrome split of 2026-09-22.  Before it the menu bar, the status
        # bar, the dialog body and the dialog button all came out of two role
        # bytes, so "theming the status bar" was not a thing you could do.
        'name': 's2-role-stat',
        'why': 'DRWSTAT paints the status bar in the document text role, so '
               'the bar stops being chrome and no theme can move it',
        'target': 'S2ED',
        'file': 'VDP.Z8A',
        'old': """                ; ROW 23: STATUS BAR COLOR
                LD      HL, COLMAP + (STBROW * CELLROW)
                LD      B, CELLROW
                LD      A, (VCOLSTAT)""",
        'new': """                ; ROW 23: STATUS BAR COLOR
                LD      HL, COLMAP + (STBROW * CELLROW)
                LD      B, CELLROW
                LD      A, (VCOLTXT)    ; MUTATION: THE BAR IS NOT CHROME ANY MORE""",
        'filter': 'S2-10',
        'expect': ['S2-10/amber/status'],
    },
    {
        'name': 's2-role-win',
        'why': 'WBOX fills the dialog body with the document text role, so a '
               'dialog is a patch of document and cannot be themed apart',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """.CBODY          LD      A, (VCOLWIN)    ; ...UNLESS A DROPDOWN""",
        'new': """.CBODY          LD      A, (VCOLTXT)    ; MUTATION: BODY = DOCUMENT""",
        'filter': 'S2-11',
        'expect': ['S2-11/window-colour'],
    },
    {
        'name': 's2-role-wtit',
        'why': 'WBOX paints the top row as body, so there is no title bar '
               'band and the accent never reaches the screen',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (VCOLHI)     ; TOP ROW: TITLE BAR...
                JR      NZ, .CFILS""",
        'new': """                LD      A, (VCOLWIN)    ; MUTATION: NO TITLE BAR
                JR      NZ, .CFILS""",
        'filter': 'S2-11',
        'expect': ['S2-11/window-colour'],
    },
    {
        'name': 's2-role-btn',
        'why': 'the OK button loses its focus role and wears the plain '
               'accent, so nothing on the dialog shows where the focus is',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': '                LD      A, (VCOLBSEL)   ; THE FOCUSED BUTTON: INVERSE ACCENT',
        'new': '                LD      A, (VCOLHI)     ; MUTATION: NO FOCUS',
        'filter': 'S2-11',
        'expect': ['S2-11/window-colour'],
    },
    {
        # S6ED closes its title band with a COL_HI separator.  On S2 the line
        # has to go in AFTER the title, because WINPUTC overwrites all eight
        # scanlines of a cell -- drawn first it survives everywhere except
        # under the title, which is the half anyone would notice.
        'name': 's2-wbox-sep',
        'why': 'the title bar has no separator closing it, so the dialog '
               'header runs into the body',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (WINNC)
                LD      B, A
                LD      A, #FF
.SEPLP          LD      (HL), A""",
        'new': """                LD      A, (WINNC)
                LD      B, A
                LD      A, #00          ; MUTATION: NO SEPARATOR
.SEPLP          LD      (HL), A""",
        'filter': 'S2-11',
        'expect': ['S2-11/title-separator'],
    },
    {
        # PARSTHM dispatches on the FIRST LETTER, which is how AUTOALIGN=OFF
        # once turned auto-align on.  MSX is index 12: with the old A-H table
        # the value is rejected and the editor silently stays on DARK.
        'name': 's2-theme-idx',
        'why': 'the theme index table stops at H again, so THEME=MSX is '
               'rejected in silence and the default theme stays',
        'target': 'S2ED',
        'file': 'CFG.Z8A',
        'old': '                CP      #0D             ; 13 ENTRIES (A-M): M IS INDEX 12',
        'new': '                CP      #08             ; MUTATION: A-H ONLY',
        'filter': 'S2-10',
        'expect': ['S2-10/msx/vars'],
    },
    {
        # MSX and MONO share the initial, so PARSTHM reads the second letter.
        # The parser is shared CORE: this is the one place either target
        # tells the two apart, and only the S2 gate asserts the role bytes.
        'name': 's2-theme-mono',
        'why': 'the second-letter test is gone, so THEME=MONO loads MSX',
        'target': 'S2ED',
        'file': 'CFG.Z8A',
        'old': '                LD      A, THMMONI',
        'new': '                LD      A, THMMSXI      ; MUTATION: MONO IS MSX',
        'filter': 'S2-10',
        'expect': ['S2-10/mono/vars', 'S2-10/mono/id'],
    },
    {
        # The last hardcoded colour in the target.  A shadow cell keeps the
        # document's pattern and flattens its colour, so black-on-black is a
        # shadow only where the document is not black -- which was true of
        # exactly one of the four themes.
        'name': 's2-role-shdw',
        'why': 'the drop shadow goes back to a hardcoded black, which is '
               'invisible on every theme whose document background is black',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                CALL    COLADDR
                CALL    SHDCOL          ; THE THEME'S, OR SHADOW=<HEX>""",
        'new': """                CALL    COLADDR
                LD      A, #11          ; MUTATION: HARDCODED BLACK SHADOW""",
        'filter': 'S2-11',
        'expect': ['S2-11/shadow'],
    },
    {
        'name': 's2-sett-shd-init',
        'target': 'S2ED',
        'why': 'Settings copies SHDWOFF = #FF into STTSHD again: entry 255 of '
               'a 3-entry table is printed as the Shadow value',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (SHDWOFF)
                INC     A               ; #FF (OFF) -> 0, 0 (ON) -> 1
                LD      (STTSHD), A""",
        'new': """                LD      A, (SHDWOFF)
                OR      A               ; MUTATION: THE #FF GOES STRAIGHT IN
                LD      (STTSHD), A""",
        'filter': 'S2-48',
        'expect': ['S2-48/off/index', 'S2-48/off/field'],
    },
    {
        'name': 's2-shdval-on',
        'target': 'S2ED',
        'why': 'CFGSAVE writes SHADOW=OFF whatever the setting, as it did '
               'before 2026-10-13',
        'file': 'VDP.Z8A',
        'old': """SHDVAL          LD      DE, .SVOFF
                LD      A, (SHDWOFF)
                OR      A
                RET     NZ""",
        'new': """SHDVAL          LD      DE, .SVOFF
                LD      A, (SHDWOFF)
                OR      A
                RET                     ; MUTATION: ALWAYS OFF""",
        'filter': 'S2-48',
        'expect': ['S2-48/on/saved', 'S2-48/colour/saved'],
    },
    {
        'name': 's2-shdval-digit',
        'target': 'S2ED',
        'why': 'CFGSAVE writes SHADOW=ON for a colour: saving the settings '
               'loses the digit',
        'file': 'VDP.Z8A',
        'old': """                LD      DE, .SVON
                LD      A, (SHDWCUS)
                OR      A
                RET     Z""",
        'new': """                LD      DE, .SVON
                RET                     ; MUTATION: NO DIGIT""",
        'filter': 'S2-48',
        'expect': ['S2-48/colour/saved'],
    },
    {
        'name': 's2-shdcol-theme',
        'target': 'S2ED',
        'why': 'the shadow always wears the theme role: SHADOW=<hex> is lost to '
               'a THEME= line after it, and to Settings OK',
        'file': 'VDP.Z8A',
        'old': """SHDCOL          LD      A, (SHDWCUS)
                OR      A""",
        'new': """SHDCOL          XOR     A               ; MUTATION: NEVER A DIGIT
                OR      A""",
        'filter': 'S2-48',
        'expect': ['S2-48/colour/shadow'],
    },
    {
        'name': 'ovr-stub',
        'why': 'EDOVRCHR routes to EDINSCHR again: [OVR] on the status bar, '
               'and every character inserted',
        'file': 'EDIT.Z8A',
        'old': """EDOVRCHR        PUSH    AF
                LD      HL, (DOCLINE)""",
        'new': """EDOVRCHR        JP      EDINSCHR        ; MUTATION: THE OLD STUB
                LD      HL, (DOCLINE)""",
        'filter': 'D13',
        'expect': ['D13/std/content', 'D13/vi/content'],
    },
    {
        'name': 's2-ovr-stub',
        'target': 'S2ED',
        'why': 'the same stub on S2ED: typing over shifts the line right',
        'file': 'EDIT.Z8A',
        'old': """EDOVRCHR        PUSH    AF
                LD      HL, (DOCLINE)""",
        'new': """EDOVRCHR        JP      EDINSCHR        ; MUTATION: THE OLD STUB
                LD      HL, (DOCLINE)""",
        'filter': 'S2-49',
        'expect': ['S2-49/rows', 'S2-49/content'],
    },
    {
        'name': 'ovr-sel-overwrite',
        'why': 'typing over a selection in OVR deletes it and then overwrites '
               'the character that closed the gap',
        'file': 'DISP.Z8A',
        'old': """                LD      A, C            ; AND TYPE INTO THE GAP IT LEFT, IN
                JP      EDINSCHR        ; EITHER MODE: THERE IS NOTHING TO
""",
        'new': """                ; MUTATION: FALL THROUGH TO THE MODE
""",
        'filter': 'D13',
        'expect': ['D13/sel/content'],
    },
    {
        'name': 'vi-r-cursor',
        'why': 'Vi r leaves the cursor one past the replaced character',
        'file': 'ACTION.Z8A',
        'old': """                LD      (CURX), A       ; BACK ON THE REPLACED CHARACTER
""",
        'new': """                ; MUTATION: THE CURSOR STAYS ADVANCED
""",
        'filter': 'D13',
        'expect': ['D13/vi/r'],
    },
    {
        'name': 'vi-rep-esc',
        'why': 'ESC leaves Vi R in overwrite: the next i overwrites too',
        'file': 'ACTION.Z8A',
        'old': """ACTVINRM        LD      A, INS_MODE     ; ESC ENDS R
                LD      (INSMODE), A
""",
        'new': """ACTVINRM        ; MUTATION: ESC KEEPS OVR
""",
        'also': [('ACTION.Z8A', """ACTVIINS        LD      A, INS_MODE     ; i, a, o... INSERT, WHATEVER R LEFT
                LD      (INSMODE), A
""", """ACTVIINS        ; MUTATION: i KEEPS OVR
""")],
        'filter': 'D13',
        'expect': ['D13/vi/esc', 'D13/vi/content'],
    },
    {
        'name': 'vi-rep-tag',
        'why': 'Vi R says [INS] on the status bar',
        'file': 'UI.Z8A',
        'old': """                LD      HL, .STRVIR     ; "[REP] "
""",
        'new': """                LD      HL, .STRVII     ; MUTATION: "[INS] "
""",
        'filter': 'D13',
        'expect': ['D13/vi/rep-shown'],
    },
    {
        # v0.1 shipped the UTF-8 source as SXED.TXT next to the disks, and a
        # tester on a Japanese machine read every accent as two glyphs.  Here
        # the disk itself carries it: the editor must show the wrong glyphs.
        'name': 'b6-manual-utf8',
        'why': 'the S6ED disk carries the UTF-8 source of the manual, so '
               'every accented letter shows as two glyphs',
        'file': 'Makefile',
        'old': 'add DEV $(MANUAL)=SXED.TXT $(CHANGES)=CHANGES.TXT TEST.TXT',
        'new': 'add DEV $(MANUALSRC)=SXED.TXT $(CHANGES)=CHANGES.TXT TEST.TXT',
        'filter': 'B6',
        'expect': ['B6/screen', 'B6F/screen'],
        'expect_static': ['manual-charset'],
    },
    {
        'name': 't0-dist-utf8',
        'why': 'the release bundle ships the UTF-8 source as SXED.TXT, which '
               'is exactly what v0.1 did by hand',
        'file': 'Makefile',
        'old': '\t@cp $(MANUAL) $(DISTDIR)/SXED.TXT\n',
        'new': '\t@cp $(MANUALSRC) $(DISTDIR)/SXED.TXT\n',
        'filter': 'T0',
        'expect_static': ['manual-charset'],
    },
    {
        'name': 't0-dsk-s2-utf8',
        'why': 'the S2ED disk carries the UTF-8 source of the manual',
        'file': 'Makefile',
        'old': 'add DEV $(MANUAL)=SXED.TXT $(CHANGES)=CHANGES.TXT TEST_S2.TXT=TEST.TXT',
        'new': 'add DEV $(MANUALSRC)=SXED.TXT $(CHANGES)=CHANGES.TXT TEST_S2.TXT=TEST.TXT',
        'filter': 'T0',
        'expect_static': ['manual-charset'],
    },
    {
        'name': 't0-dsk-s6only',
        'why': 'the S6ED disk stops carrying S2ED, so the one image that runs '
               'both editors on an MSX2 quietly goes out with one',
        'file': 'Makefile',
        'old': '\t\t\t  $(OUTPUT_S2) $(DATFILE_S2) $(FNTFILE_S2) $(CFGFILE_S2) \\\n',
        'new': '\t\t\t  $(DATFILE_S2) $(FNTFILE_S2) $(CFGFILE_S2) \\\n',
        'filter': 'T0',
        'expect_static': ['build-symmetry'],
    },
    {
        'name': 't0-dsk-nos61',
        'why': 'the S6ED disk stops carrying S61ED, so the image that compares '
               'the three editors on an MSX2 goes out with two',
        'file': 'Makefile',
        'old': '\t\t\t  $(OUTPUT_S61) $(DATFILE_S61) $(FNTFILE_S61) $(CFGFILE_S61)\n',
        'new': '\t\t\t  $(DATFILE_S61) $(FNTFILE_S61) $(CFGFILE_S61)\n',
        'filter': 'T0',
        'expect_static': ['build-symmetry'],
    },
    {
        # The asymmetry the user found on 2026-09-22: clean removed both
        # editors' artefacts while build assembled one, so `make clean build`
        # left the tree half built and the S2 harness died on a missing .sym.
        'name': 't0-build-s6only',
        'why': 'make build assembles S6ED alone again while clean removes '
               'both, so clean+build leaves the tree half built',
        'file': 'Makefile',
        'old': 'build: build-s6 build-s2 build-s61\n',
        'new': 'build: build-s6 build-s61\n',
        'filter': 'T0',
        'expect_static': ['build-symmetry'],
    },
    {
        'name': 't0-build-nos61',
        'why': 'make build stops assembling S61ED while clean removes it, so '
               'clean+build leaves the tree without the third editor',
        'file': 'Makefile',
        'old': 'build: build-s6 build-s2 build-s61\n',
        'new': 'build: build-s6 build-s2\n',
        'filter': 'T0',
        'expect_static': ['build-symmetry'],
    },
    {
        # The defect W2 exists to remove: on S2ED, ESC went straight to TERM.
        'name': 's2-quit-direct',
        'why': 'ACTQUIT quits without asking on S2ED, so ESC throws the '
               'document away -- the stub that stood there until W2',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        # Anchored below the FTR-BUDGET comment on purpose: that line carries
        # measured byte counts and is rewritten every time the container moves.
        'old': """                LD      A, (FTRSEG)
                LD      HL, DOQIT""",
        'new': """                JP      TERM            ; MUTATION: QUIT WITHOUT ASKING
                LD      HL, DOQIT""",
        'filter': 'S2-15',
        # ESC exits on the spot: either the displayed check goes red, or the
        # case dies waiting for a WINPOLL that never comes.
        'expect_any': ['S2-15/clean/displayed', 'S2-15-quit'],
    },
    {
        'name': 's2-quit-defsel',
        'why': 'the Quit dialog opens with YES selected, so a reflex ENTER '
               'discards the document',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                ; DEFAULT: NO SELECTED, RESULT CANCELLED
                LD      A, 1
                LD      (WINSEL), A""",
        'new': """                ; DEFAULT: NO SELECTED, RESULT CANCELLED
                XOR     A               ; MUTATION: YES SELECTED BY DEFAULT
                LD      (WINSEL), A""",
        'filter': 'S2-15',
        'expect': ['S2-15/clean/default-no'],
    },
    {
        'name': 's2-quit-nav',
        'why': 'LEFT and RIGHT are swapped, so the arrow keys move the focus '
               'the wrong way',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                CP      CLEFT
                JR      Z, .TOYES
                CP      CRIGHT
                JR      Z, .TONO""",
        'new': """                CP      CLEFT
                JR      Z, .TONO        ; MUTATION: NAVIGATION REVERSED
                CP      CRIGHT
                JR      Z, .TOYES""",
        'filter': 'S2-15',
        'expect': ['S2-15/clean/nav-left'],
    },
    {
        'name': 's2-quit-warn',
        'why': 'the unsaved-changes warning is shown on a clean buffer and '
               'hidden on a dirty one -- the test that matters inverted',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (MODIFIED)
                OR      A
                JR      Z, .NOWRN""",
        'new': """                LD      A, (MODIFIED)
                OR      A
                JR      NZ, .NOWRN      ; MUTATION: WARNING INVERTED""",
        'filter': 'S2-15',
        'expect': ['S2-15/clean/warning', 'S2-15/dirty/warning'],
    },
    {
        'name': 's2-quit-yes',
        'why': 'the Y accelerator does not set WINRES, so the editor refuses '
               'to quit however the dialog is answered',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """.YES            LD      A, 1
                LD      (WINRES), A""",
        'new': """.YES            XOR     A               ; MUTATION: Y CANCELS
                LD      (WINRES), A""",
        'filter': 'S2-15',
        # The exit breakpoint never fires, so either the check sees no exit
        # snapshot or the case dies waiting for one.
        'expect_any': ['S2-15/clean/quit-y', 'S2-15-quit'],
    },
    {
        # The stub W4 exists to remove: MNUENT was the last IFDEF S2ED in the
        # menu and dialog path.
        'name': 's2-menu-stub',
        'why': 'MNUENT returns without opening anything on S2ED, so F1..F5 '
               'and SELECT do nothing -- the stub that stood there until W4',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, (FTRSEG)
                LD      HL, DOMNU
                CALL    FCALL""",
        'new': """                RET                     ; MUTATION: MENUS DISABLED
                LD      HL, DOMNU
                CALL    FCALL""",
        'filter': 'S2-16',
        # SELECT opens nothing, so the timeline's later ESC opens the Quit
        # dialog instead and the WINPOLL gate samples THAT: WINACTV is still
        # 1 and MNUID still 0.  It is the geometry and the accelerator that
        # tell the two apart, which is why S2-16/open names both.  Since F0
        # the accelerator step waits on WINPOLL for the New dialog, which a
        # stubbed menu never opens, so the session may also die there.
        'expect_any': ['S2-16/open', 'S2-16/accel-new', 'S2-16-menu'],
    },
    {
        'name': 's2-menu-defsel',
        'why': 'a menu opens with the second item selected, so a reflex '
               'ENTER on File runs Open instead of New',
        'target': 'S2ED',
        'file': 'MENU.Z8A',
        'old': """.INITOK         XOR     A
                LD      (MNUSEL), A     ; DEFAULT SELECTION = 0""",
        'new': """.INITOK         LD      A, 1            ; MUTATION: OPENS ON ITEM 1
                LD      (MNUSEL), A""",
        'filter': 'S2-16',
        'expect': ['S2-16/open', 'S2-16/open/colour'],
    },
    {
        'name': 's2-menu-skipsep',
        'why': 'DOWN stops on the separator, so a rule can be selected and '
               'ENTER dispatches an item index that means nothing',
        'target': 'S2ED',
        'file': 'MENU.Z8A',
        'old': """.DWNCHK         CALL    MNUCHKS
                JR      NZ, .MOVE
                INC     A               ; SKIP SEPARATOR""",
        'new': """.DWNCHK         CALL    MNUCHKS
                JR      .MOVE           ; MUTATION: SEPARATOR SELECTABLE
                INC     A""",
        'filter': 'S2-16',
        'expect': ['S2-16/skip-separator'],
    },
    {
        'name': 's2-menu-title',
        'why': 'the title in row 0 is never highlighted, so nothing on the '
               'bar says which menu is open',
        'target': 'S2ED',
        'file': 'MENU.Z8A',
        'old': """MNUTITL         LD      A, (MNUID)
                ADD     A, A            ; TWO BYTES PER SPAN""",
        'new': """MNUTITL         RET                     ; MUTATION: NO HIGHLIGHT
                ADD     A, A            ; TWO BYTES PER SPAN""",
        'filter': 'S2-16',
        'expect': ['S2-16/title-highlight'],
    },
    {
        'name': 's2-menu-nav-wrap',
        'why': 'RIGHT stops at Help instead of wrapping round to File, so '
               'the bar is a dead end in one direction',
        'target': 'S2ED',
        'file': 'MENU.Z8A',
        'old': """                JR      C, .RGHTOK
                XOR     A               ; WRAP 2 -> 0""",
        'new': """                JR      C, .RGHTOK
                DEC     A               ; MUTATION: RIGHT DOES NOT WRAP""",
        'filter': 'S2-17',
        'expect': ['S2-17/walk'],
    },
    {
        'name': 's2-menu-enter',
        'why': 'RETURN cancels instead of accepting, so the only way to run a '
               'menu item is its accelerator',
        'target': 'S2ED',
        'file': 'MENU.Z8A',
        'old': """                CP      CR
                JR      Z, .ACCEPT""",
        'new': """                CP      CR
                JR      Z, .CANCEL      ; MUTATION: RETURN CANCELS""",
        'filter': 'S2-17',
        'expect_any': ['S2-17/action-settings', 'S2-17-menu-nav'],
    },
    {
        'name': 's2-menu-swtitl',
        'why': 'switching menus never un-highlights the one it came from, so '
               'the inverted titles pile up along the bar',
        'target': 'S2ED',
        'file': 'MENU.Z8A',
        'old': """                CALL    WINCLOS
                CALL    MNUTITL         ; UN-HIGHLIGHT THE OLD TITLE
                POP     BC""",
        'new': """                CALL    WINCLOS
                POP     BC""",
        'filter': 'S2-17',
        'expect': ['S2-17/r1/title'],
    },
    {
        # The defect this phase removed on the way past: five of the six Edit
        # menu items called the action ID and not the routine.
        'name': 'menu-edit-id',
        'why': 'Edit > Select All calls ACSELAL, the action ID (EQU 42), so '
               'the menu jumps to #002A in the DOS zero page instead of the '
               'routine -- which is what shipped, unnoticed, because no case '
               'had ever pressed an Edit menu item',
        'file': 'ACTION.Z8A',
        'old': """.EALL           CALL    ACTSELAL""",
        'new': """.EALL           CALL    ACSELAL         ; MUTATION: THE ID, NOT THE ROUTINE""",
        'filter': 'H23',
        # Calling into page 0 is undefined: sometimes the selection simply
        # never happens, sometimes the session does not survive it.
        'expect_any': ['H23/edit-action', 'H23-menu-nav'],
    },
    {
        'name': 'goto-nodispatch',
        'why': 'Ctrl+G and Edit > Go to Line reach nothing, the state the '
               'editor was in before this phase',
        'file': 'ACTION.Z8A',
        'old': """                DEFW    ACTGOTO         ; 59 (GO TO LINE)""",
        'new': """                DEFW    ACTNONE         ; MUTATION: GO TO LINE UNBOUND""",
        'filter': 'H24',
        # the dialog never opens, so the WINPOLL-gated snapshot never fires
        # and the session dies: caught under the case name
        'expect_any': ['H24/open', 'H24/centred', 'H24-goto-line'],
    },
    {
        # The round-3 defect class, and the reason the suite runs two gates:
        # on S6ED this mutation changes nothing at all.
        'name': 'goto-scrrows',
        'why': 'the viewport centres on SCRROWS / 2 instead of ROWSVIS / 2, '
               'which is identical on S6ED and two rows wrong on S2ED',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """.CENTRE         ; TOPLINE = DOCLINE - ROWSVIS / 2, CLAMPED
                LD      DE, ROWSVIS / 2""",
        'new': """.CENTRE         ; TOPLINE = DOCLINE - ROWSVIS / 2, CLAMPED
                LD      DE, SCRROWS / 2 ; MUTATION: THE SCREEN, NOT THE BAND""",
        'filter': 'S2-18',
        'expect': ['S2-18/centred', 'S2-18/space'],
    },
    {
        'name': 'goto-visible',
        'why': 'a line already on screen scrolls the viewport anyway, so '
               'every jump is a jolt',
        'file': 'ACTION.Z8A',
        'old': """                JP      C, SETCURY      ; VISIBLE: DO NOT MOVE THE VIEWPORT""",
        'new': """                JP      C, .CENTRE      ; MUTATION: ALWAYS RECENTRE""",
        'filter': 'H24',
        'expect': ['H24/nearby'],
    },
    {
        'name': 'goto-bs',
        'why': 'Backspace leaves the digit in the field, so a correction '
               'goes to the line the user was trying not to go to',
        'file': 'INPUT.Z8A',
        'old': """.BS             LD      A, (INPCAR)
""",
        'new': """.BS             SCF                     ; MUTATION: BACKSPACE REMOVES NOTHING
                RET
                LD      A, (INPCAR)
""",
        'filter': 'H24',
        'expect': ['H24/backspace'],
    },
    {
        'name': 'goto-esc',
        'why': 'ESC accepts instead of cancelling, so the way out of the '
               'dialog is the way into a jump nobody asked for',
        'file': 'WINDOW.Z8A',
        'old': """                CP      ESC
                JP      Z, .CANCEL
                CP      CR
                JP      Z, .ACCEPT""",
        'new': """                CP      ESC
                JP      Z, .ACCEPT      ; MUTATION: ESC ACCEPTS
                CP      CR
                JP      Z, .ACCEPT""",
        'filter': 'H24',
        'expect': ['H24/cancel'],
    },
    {
        'name': 'goto-empty',
        'why': 'ENTER on an empty field is taken as line 0, so a reflex ENTER '
               'throws the cursor to the top of the document',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (INPLEN)
                OR      A
                JR      Z, .CANCEL      ; AN EMPTY FIELD CANCELS""",
        'new': """                LD      A, (INPLEN)
                OR      A
                JR      C, .CANCEL      ; MUTATION: NEVER TAKEN AFTER OR A""",
        'filter': 'H24',
        'expect': ['H24/empty'],
    },
    {
        'name': 'goto-space',
        'why': 'SPACE accepts while the field has the focus, which is right '
               'for digits and wrong the day a class accepts a space -- the '
               'reason the focus has three positions and not two',
        'file': 'WINDOW.Z8A',
        'old': """.SPACE          LD      A, (WINSEL)
                OR      A
                JP      Z, .KEYLP       ; THE FIELD HAS IT: SPACE IS NOT A KEY""",
        'new': """.SPACE          LD      A, (WINSEL)
                OR      A               ; MUTATION: SPACE ALWAYS ACCEPTS""",
        'filter': 'H24',
        'expect': ['H24/space'],
    },
    {
        'name': 's2-mark-role',
        'why': 'COMCELL never tests ATRMARK, so the ** delimiters fall back '
               'to the document colour and VCOLMARK goes back to being a '
               'theme byte nobody reads',
        'target': 'S2ED',
        'file': 'RENDER.Z8A',
        'old': """.NOTUN          BIT     4, A            ; ATRMARK ?
                JR      Z, .MDEF
                LD      A, (VCOLMARK)""",
        'new': """.NOTUN          BIT     4, A            ; ATRMARK ?
                JR      .MDEF           ; MUTATION: DELIMITERS UNMARKED
                LD      A, (VCOLMARK)""",
        'filter': 'S2-14',
        'expect': ['S2-14/line0', 'S2-14/line1'],
    },
    {
        # The ordering decision, not the wiring.  A cell is two characters,
        # so a delimiter starting on an odd column shares its cell with
        # content; testing ATRMARK FIRST paints that content character as a
        # delimiter and it loses its own role.  Line 0 is aligned and cannot
        # see the difference -- only line 1 can, which is why it exists.
        'name': 's2-mark-prio',
        'why': 'ATRMARK is tested before ATRBOLD, so a bold letter sharing a '
               'cell with a delimiter is painted as a delimiter',
        'target': 'S2ED',
        'file': 'RENDER.Z8A',
        'old': """.MAPC           OR      A
                JR      Z, .MDEF
                BIT     0, A            ; ATRBOLD ?""",
        'new': """.MAPC           OR      A
                JR      Z, .MDEF
                BIT     4, A            ; MUTATION: DELIMITER WINS
                JR      Z, .MUTBD
                LD      A, (VCOLMARK)
                RET
.MUTBD          BIT     0, A            ; ATRBOLD ?""",
        'filter': 'S2-14',
        'expect': ['S2-14/line1'],
    },
    {
        # What S2-14/line1 exists for.  A cell is TWO characters and COMCELL
        # ORs both attributes, so a span that starts on an odd column drags
        # its delimiter into the span's colour.  Reading only the left
        # attribute leaves the aligned line looking perfect and silently
        # halves the span on every odd one.
        'name': 's2-comcell-rattr',
        'why': 'COMCELL takes the cell colour from the left character alone, '
               'so a markup span starting on an odd column loses its first '
               'cell -- invisible on any aligned example',
        'target': 'S2ED',
        'file': 'RENDER.Z8A',
        'old': """.CPAIRL         LD      A, (HL)
                INC     HL
                OR      (HL)""",
        'new': """.CPAIRL         LD      A, (HL)
                INC     HL
                NOP                     ; MUTATION: RIGHT ATTRIBUTE IGNORED""",
        'filter': 'S2-14',
        'expect': ['S2-14/line1'],
    },
    {
        'name': 's2-shadow-off',
        'why': 'WSHDW ignores SHADOW=OFF and recolours the margin anyway, so '
               'the key cannot turn the shadow off',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """WSHDW           LD      A, (SHDWOFF)
                OR      A
                RET     NZ              ; SHADOW=OFF: LEAVE THE MARGIN ALONE""",
        'new': """WSHDW           LD      A, (SHDWOFF)
                OR      A               ; MUTATION: SHADOW=OFF IGNORED""",
        'filter': 'S2-13',
        'expect': ['S2-13/off/margin'],
    },
    {
        'name': 's2-shadow-hex',
        'why': 'PARSSHD parses the colour digit and never stores it, so '
               'SHADOW=<hex> is accepted in silence and discarded -- the '
               'shape the COLOR_* keys had on S2ED before they were removed',
        'target': 'S2ED',
        'file': 'CFG.Z8A',
        'old': """.S2SET          INC     A               ; KEPT APART FROM THE THEME'S VCOLSHDW:
                LD      (SHDWCUS), A    ; A THEME= LINE OR SETTINGS OK RELOADS""",
        'new': """.S2SET          INC     A               ; KEPT APART FROM THE THEME'S VCOLSHDW:
                                        ; MUTATION: VALUE NEVER STORED""",
        'filter': 'S2-13',
        'expect': ['S2-13/colour/margin'],
    },
    {
        'name': 's2-wbox-rframe',
        'why': 'WBOX reaches the right border with a (WINNC-1)*8 offset from '
               'the cell past the left border, landing on the shadow column: '
               'no right border anywhere, and a stray #03 column in document '
               'colour one cell past the window',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (WINNC)
                SUB     2
                ADD     A, A
                ADD     A, A
                ADD     A, A
                LD      E, A
                LD      D, 0
                ADD     HL, DE          ; RIGHT CELL: (WINNC-2)*8 PAST WINC+1""",
        'new': """                LD      A, (WINNC)
                DEC     A               ; MUTATION: ONE CELL TOO FAR
                ADD     A, A
                ADD     A, A
                ADD     A, A
                LD      E, A
                LD      D, 0
                ADD     HL, DE          ; RIGHT CELL: (WINNC-2)*8 PAST WINC+1""",
        'filter': 'S2-11',
        'expect': ['S2-11/side-borders'],
    },
    {
        'name': 's2-selpain-ix',
        'why': 'SELPAIN loads IX once before its row loop and trusts it to '
               'survive SELXOR; PATINV uses IX on S2ED, so every row after '
               'the first reads its extent out of the pattern shadow.  The '
               'fresh paint survives by luck (the visible rows are covered by '
               'the first, still-valid pass and by SELDIFF); the un-XOR on '
               'deselect is what leaves residue.  Only this gate can catch '
               'it: S6ED\'s LMMV leaves IX alone',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """SELPAIN         LD      B, 0
.ROWLP          LD      IX, SELSTRL
                PUSH    BC""",
        'new': """SELPAIN         LD      IX, SELSTRL     ; MUTATION: LOADED ONCE
                LD      B, 0
.ROWLP          PUSH    BC""",
        'filter': 'S2-19',
        'expect': ['S2-19/no-residue'],
    },
    {
        'name': 's2-wbox-title',
        'why': 'WBOX clears (WINNC-2)*8 bytes of the top row for the title '
               'instead of only the cells the title occupies, so the top '
               'edge survives only at the two corner cells',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                ; SPAN: THE TITLE STARTS AT CHAR COLUMN (WINC+1)*2 AND
                ; WINPUTS CLIPS IT AT WINCLIM (OR THE RIGHT SCREEN EDGE
                ; WHEN WINCLIM IS 0), TWO CHARACTERS PER CELL
                LD      A, (WINC)
                INC     A
                ADD     A, A
                LD      C, A            ; C = START CHAR COLUMN
                LD      A, (WINCLIM)
                OR      A
                JR      NZ, .TLIM
                LD      A, SCRCOLS
.TLIM           SUB     C               ; A = COLUMNS BEFORE THE CLIP
                LD      B, A
                LD      C, 0            ; C = CHARACTERS DRAWN
                JR      Z, .TSPAN       ; NO ROOM: NOTHING TO CLEAR
.TLEN           LD      A, (HL)
                OR      A
                JR      Z, .TSPAN
                INC     HL
                INC     C
                DJNZ    .TLEN
.TSPAN          LD      A, C
                OR      A
                JR      Z, .TDRAW       ; EMPTY TITLE: NOTHING TO CLEAR
                INC     A
                SRL     A               ; CELLS = (CHARS+1)/2
                ADD     A, A
                ADD     A, A
                ADD     A, A
                LD      B, A            ; B = CELLS*8 BYTES
                LD      A, (WINR)
                ADD     A, #80          ; HIGH(PATSHAD)
                LD      H, A
                LD      A, (WINC)
                INC     A
                ADD     A, A
                ADD     A, A
                ADD     A, A
                LD      L, A            ; CELL WINC+1 OF THE TOP ROW
                XOR     A""",
        'new': """                ; MUTATION: CLEAR THE WHOLE INNER TOP EDGE
                LD      A, (WINR)
                ADD     A, #80          ; HIGH(PATSHAD)
                LD      H, A
                LD      A, (WINC)
                INC     A
                ADD     A, A
                ADD     A, A
                ADD     A, A
                LD      L, A
                LD      A, (WINNC)
                SUB     2
                ADD     A, A
                ADD     A, A
                ADD     A, A
                LD      B, A            ; (WINNC-2)*8 BYTES
                XOR     A""",
        'filter': 'S2-11',
        'expect': ['S2-11/top-edge'],
    },
    {
        # Round 2 fixed the same class in FILEIO.Z8A and stopped there.  This
        # is what was left in ACTDWLFT and ACTDLS: the attribute half of the
        # record addressed as "+ 81", right for a 1+80+80 record and 16 bytes
        # past the text on a 1+64+64 one.
        'name': 't0-layout-off',
        'why': 'CORE addresses the attribute half of a line record as + 81',
        'file': 'ACTION.Z8A',
        'old': 'LD      HL, WORKBUF + 1 + WORKATTR\n                CALL    .SHIFT          ; THE ATTRIBUTES',
        'new': 'LD      HL, WORKBUF + 81\n                CALL    .SHIFT          ; THE ATTRIBUTES',
        'filter': 'T0',
        'expect_static': ['target-params'],
    },
    {
        # EDDELBK / EDDELCHR walked the shift loop to a hard 79 and blanked
        # WORKBUF + 80.  On S2ED that drags attribute byte 0 into the last
        # text column, after which EDINSCHR sees a full record and silently
        # refuses every keystroke on that line.
        'name': 't0-geom-imm',
        'why': 'CORE bounds a record loop with the literal 79',
        'file': 'EDIT.Z8A',
        # Re-anchored 2026-09-27: the shift loop is gone since Phase B; the
        # record bound CORE checks today is MAXCOLS in EDINSCHR.
        'old': 'CP      MAXCOLS\n                RET     NC              ; AT/PAST MAXCOLS (255), NO INSERT',
        'new': 'CP      79\n                RET     NC              ; AT/PAST MAXCOLS (255), NO INSERT',
        'filter': 'T0',
        'expect_static': ['target-params'],
    },
    {
        'name': 'g2-dcreate',
        'why': 'DOS 2 _CREATE refuses an existing file when B bit 7 is set',
        'file': 'BDOS.Z8A',
        'old': 'LD      B, 0            ; B = 0: NORMAL FILE, OVERWRITE EXISTING (B7=0)',
        'new': 'LD      B, #80          ; MUTATION: DO NOT OVERWRITE',
        'filter': 'G2',
        'expect': ['G2/content'],
    },
    {
        'name': 'g4-freelist',
        'why': 'LINEDEL abandons the record instead of handing it back',
        'file': 'BUFFER.Z8A',
        'old': """                LD      A, B
                JP      Z, FREEPSH      ; A = SEGMENT, DE = OFFSET""",
        'new': """                LD      A, B
                NOP                     ; MUTATION: LEAK THE RECORD
                NOP
                NOP""",
        'filter': 'G4',
        'expect': ['G4/no-growth'],
    },
    {
        # The clock residue defect this slot used to inject (a byte-truncated
        # HMMV clear) is dead by construction since 2026-09-25: chrome glyphs
        # blit opaque from the UI-paper font copy, so a repainted cell is
        # fully overwritten whatever the clear did. The invariant that matters
        # now is the paper color itself.
        'name': 'g5-uipaper',
        'why': 'chrome glyphs lose their COL_UI paper, so every blitted cell '
               'paints a black box instead of the bar colour',
        'file': 'FONT.Z8A',
        'old': 'EXPSTAT         LD      HL, #AAAA       ; 8 PIXELS OF COLOR 2 (6 BLITTED)',
        'new': 'EXPSTAT         LD      HL, #0000       ; MUTATION: PAPER = COLOR 0',
        'filter': 'G5',
        # Which sample goes red depends on which digits happen to change, so
        # the requirement is that at least one of them does.  G5 guarantees a
        # revealing transition is in the window; see the note on SAMPLES.
        'expect_any': ['G5/c%d' % i for i in range(7)],
    },
    {
        # 2026-09-25: with exactly STATCOLS bytes the BLDSTAT NUL terminator
        # lands on STATPRV+0, the cell cache reads "never painted" forever and
        # every keystroke full-repaints the bar (HMMV + 80 blits, ~45 ms).
        'name': 'd1-statbuf',
        'why': 'STATBUF shrinks to STATCOLS, so the terminator overwrites '
               'STATPRV+0 and the status bar full-repaints on every key',
        'file': 'VARS.Z8A',
        'old': 'STATBUF         DEFS    STATCOLS + 1',
        'new': 'STATBUF         DEFS    STATCOLS      ; MUTATION: TERMINATOR ON STATPRV',
        'filter': 'D1',
        'expect_static': ['statbuf-term'],
    },
    {
        'name': 'g7-selrange',
        'why': 'the painted range overlaps SELDIFF\'s own scratch',
        'file': 'VARS.Z8A',
        'old': """DRWSTRL         DEFW    0               ; PAINTED START LINE
DRWSTRX         DEFB    0               ; PAINTED START COL
DRWENDL         DEFW    0               ; PAINTED END LINE
DRWENDX         DEFB    0               ; PAINTED END COL""",
        'new': """DRWSTRL         DEFW    0               ; PAINTED START LINE
SELTMPL2        DEFW    0               ; MUTATION: SCRATCH BEHIND THE RECORD
SELTMPXA2       DEFB    0
SELTMPXB2       DEFB    0
DRWSTRX         EQU     DRWSTRL + 2
DRWENDL         EQU     DRWSTRL + 3
DRWENDX         EQU     DRWSTRL + 5""",
        'also': [('VARS.Z8A',
                  """SELTMPL         DEFW    0               ; TEMP LINE VAR
SELTMPXA        DEFB    0               ; TEMP COL XA
SELTMPXB        DEFB    0               ; TEMP COL XB""",
                  """SELTMPL         EQU     SELTMPL2
SELTMPXA        EQU     SELTMPXA2
SELTMPXB        EQU     SELTMPXB2""")],
        'filter': 'G7',
        'expect': ['G7/render-pure'],
        'expect_static': ['record-exclusive'],
    },
    {
        'name': 'g9-dirbank',
        'why': 'DIRBANK lets PUTP2 destroy the line number in HL',
        'file': 'BUFFER.Z8A',
        'old': """DIRBANK         PUSH    HL
                LD      A, (DIRSEG)
                LD      (TXSEG), A
                CALL    PUTP2
                POP     HL
                RET""",
        'new': """DIRBANK         LD      A, (DIRSEG)
                LD      (TXSEG), A
                CALL    PUTP2
                RET""",
        'filter': 'G9',
        'expect_any': ['G9/round-trip', 'G9-directory'],
    },
    {
        'name': 'f1a-noftr',
        'why': 'SEGRESV skips the mandatory FTRSEG claim, so the text pool '
               'keeps the segment and the CHKFLEN byte ceiling doubles '
               '(8,282 -> 16,564): the G3 fixture loads instead of being '
               'refused',
        'file': 'MAPPER.Z8A',
        'old': """                CALL    SEGGET          ; 2: FEATURE SEGMENT
                JP      C, .NOFTR
                LD      (FTRSEG), A""",
        'new': """                LD      A, (DIRSEG)     ; MUTATION: SHARE DIRSEG INSTEAD OF CLAIMING FTRSEG
                LD      (FTRSEG), A""",
        'filter': 'G3-oom',
        'expect': ['G3/load-refused'],
    },
    {
        'name': 'load-rollback',
        'why': 'FILELOAD does not roll back on OOM, leaving truncated lines',
        'file': 'FILEIO.Z8A',
        'old': """                CALL    STORLINE
                JR      C, .OOM
                POP     AF""",
        'new': """                CALL    STORLINE
                JR      C, .CLSFIL      ; MUTATION: NO ROLLBACK ON OOM
                POP     AF""",
        # G3's long-line fixture never reaches the read loop: CHKFLEN refuses
        # it up front.  The mid-read OOM path is exercised by G3B, whose
        # one-char lines pass the worst-case size estimate but exhaust the
        # real 36-byte records halfway through the read.
        'filter': 'G3B',
        # .CLSFIL is entered with .EOL's three pushes still on the stack, so
        # the RET that follows is undefined: which address it lands on moves
        # with the code layout.  Measured 2026-09-27: 12 bytes added to
        # EDPSHWR turned a refused load into a dead session.  Either one is
        # the defect showing.
        'expect_any': ['G3B/load-refused', 'G3B-oomshort'],
    },
    {
        'name': 'g10-align',
        'why': 'the align gate tests CURX == length instead of CURX >= length',
        'file': 'ACTION.Z8A',
        'old': 'JR      C, .PLAIN       ; CURX < LENGTH: GENUINELY MID-LINE',
        'new': 'JR      NZ, .PLAIN      ; MUTATION: ONLY WHEN EXACTLY EQUAL',
        'filter': 'G10',
        'expect': ['G10/no-trailing-spaces'],
    },
    {
        'name': 'b2-font',
        'why': 'EXPNORM fails to expand high bit of ink color 1',
        'file': 'FONT.Z8A',
        'old': """                SET     6, H
.P1             ADD     A, A""",
        'new': """                RES     6, H            ; MUTATION: PIXEL 0 LOST
.P1             ADD     A, A""",
        'filter': 'B2',
        'expect': ['B2/vram-tables'],
    },
    {
        'name': 'b3-rom',
        'why': 'UI does not show [ROM] indicator when S6ED.FNT is missing',
        'file': 'UI.Z8A',
        'old': """                LD      HL, .STRROM
                JR      Z, .PUTFNT
                LD      HL, .STRNOFN""",
        'new': """                LD      HL, .STRNOFN    ; MUTATION: SILENT FALLBACK
                JR      Z, .PUTFNT
                LD      HL, .STRNOFN""",
        'filter': 'B3',
        'expect': ['B3/status-bar-rom'],
    },
    {
        'name': 'f1-scroll',
        'why': 'SCRLDNN scrolls to the wrong destination scanline',
        'file': 'SCROLL.Z8A',
        'old': """                LD      HL, TXORG_Y     ; DY = TOP OF ROW 1
                LD      (VDP_DY), HL""",
        'new': """                LD      HL, TXORG_Y + 8 ; MUTATION: DESTINATION SHIFTED BY ONE ROW
                LD      (VDP_DY), HL""",
        'filter': 'F1',
        'expect': ['F1/render-pure'],
    },
    {
        'name': 'f2-keyrun',
        'why': 'bottom-row scroll does not advance viewport TOPLINE',
        'file': 'EDIT.Z8A',
        'old': """                LD      HL, (TOPLINE)
                ADD     HL, DE
                LD      (TOPLINE), HL
                LD      A, E
                CP      ROWSVIS""",
        'new': """                LD      HL, (TOPLINE)
                ADD     HL, DE
                NOP                     ; MUTATION: TOPLINE NOT ADVANCED
                NOP
                NOP
                LD      A, E
                CP      ROWSVIS""",
        'filter': 'F2',
        'expect': ['F2/burst-collapsed'],
    },
    {
        'name': 'd1-insert',
        'why': 'EDINSCHR fails to shift and insert characters',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, (CURX)
                CALL    WBINS           ; TEXT + ATTRS SHIFTED, LENGTH UPDATED""",
        'new': """                LD      A, (CURX)
                NOP                     ; MUTATION: TEXT NOT INSERTED
                NOP
                NOP""",
        'filter': 'D1',
        'expect': ['D1/content'],
    },
    {
        'name': 'd2-enter',
        'why': 'EDNWLIN always splits at column 0',
        'file': 'EDIT.Z8A',
        # Re-anchored 2026-09-21: SPLITL takes its column through EFFCURX now.
        'old': """SPLITL          CALL    EFFCURX""",
        'new': """SPLITL          XOR     A               ; MUTATION: SPLIT AT COL 0""",
        'filter': 'D2',
        'expect': ['D2/content'],
    },
    {
        'name': 'd3-backspace',
        'why': 'EDDELBK does not join line in WRAP_DEV mode',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, (WRAPMODE)
                CP      WRAP_TXT
                JP      NZ, EDJNDEV     ; IN WRAP_DEV: DEV LINE JOIN / LINE DELETE""",
        'new': """                LD      A, (WRAPMODE)
                CP      WRAP_TXT
                RET     NZ              ; MUTATION: NO DEV LINE JOIN""",
        'filter': 'D3',
        'expect': ['D3/content'],
    },
    {
        'name': 'd4-delete',
        'why': 'EDDELCHR does not pull next line up at EOL in WRAP_DEV mode',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, (WRAPMODE)
                CP      WRAP_TXT
                JP      NZ, EDDELDV     ; IN WRAP_DEV: DEV LINE JOIN / LINE DELETE BELOW""",
        'new': """                LD      A, (WRAPMODE)
                CP      WRAP_TXT
                RET     NZ              ; MUTATION: NO DEV LINE PULL""",
        'filter': 'D4',
        'expect': ['D4/content'],
    },
    {
        'name': 'd5-wordline-del',
        'why': 'ACTDWLFT word delete left is disabled',
        'file': 'ACTION.Z8A',
        'old': """ACTDWLFT        LD      A, (CURX)
                OR      A
                RET     Z""",
        'new': """ACTDWLFT        RET                     ; MUTATION: WORD DELETE NO-OP
                LD      A, (CURX)
                OR      A
                RET     Z""",
        'filter': 'D5',
        'expect': ['D5/content'],
    },
    {
        'name': 'd6-reflow',
        'why': 'REFLOW cascade reflow is disabled',
        'file': 'EDIT.Z8A',
        'old': """REFLOW          PUSH    HL""",
        'new': """REFLOW          RET                     ; MUTATION: REFLOW NO-OP
                PUSH    HL""",
        'filter': 'D6',
        'expect': ['D6/content'],
    },
    {
        'name': 'w5-reflow-cascade',
        'why': 'the key join rewraps to the end of the document and merges '
               'the lines below the two it joins',
        'file': 'EDIT.Z8A',
        'old': """                LD      D, H
                LD      E, L
                INC     DE              ; DE = L + 1: THE TWO LINES JOINED""",
        'new': """                LD      DE, (TOTLINES)  ; MUTATION: THE OLD CASCADE
                DEC     DE""",
        'filter': 'W5',
        'expect': ['W5/empty/content', 'W5/text/content', 'W5/del/content'],
    },
    {
        'name': 's2-reflow-cascade',
        'target': 'S2ED',
        'why': 'the key join merges the lines below (the tester\'s AUTOEXEC.BAT)',
        'file': 'EDIT.Z8A',
        'old': """                LD      D, H
                LD      E, L
                INC     DE              ; DE = L + 1: THE TWO LINES JOINED""",
        'new': """                LD      DE, (TOTLINES)  ; MUTATION: THE OLD CASCADE
                DEC     DE""",
        'filter': 'S2-57',
        'expect': ['S2-57/empty/content', 'S2-57/text/content'],
    },
    {
        'name': 'd7-tabs',
        'why': 'ACTTAB fails to insert spaces up to next tab stop',
        'file': 'ACTION.Z8A',
        'old': """ACTTAB          LD      A, (SELACT)""",
        'new': """ACTTAB          RET                     ; MUTATION: ACTTAB NO-OP
                LD      A, (SELACT)""",
        'filter': 'D7',
        'expect': ['D7/content', 'D7/curx'],
    },
    {
        'name': 'd8-accents',
        'why': 'CHKACNT fails to scan matrix for GRAPH accent combinations',
        'file': 'INPUT.Z8A',
        'old': """CHKACNT         ; --- STEP 1: CHECK DEAD KEY (ROW 2 BIT 5) OR KANA (ROW 6 BIT 4) ---""",
        'new': """CHKACNT         OR      A               ; MUTATION: CHKACNT NO-OP
                RET
                ; --- STEP 1: CHECK DEAD KEY (ROW 2 BIT 5) OR KANA (ROW 6 BIT 4) ---""",
        'filter': 'D8',
        'expect': ['D8/content'],
    },
    {
        'name': 'd8-double',
        'why': 'the BIOS GRAPH code and the matrix scan both deliver one press',
        'file': 'DISP.Z8A',
        'old': 'LD      (HL), A         ; CLAIM IT SO CHKACNT STAYS QUIET',
        'new': 'NOP                     ; MUTATION: NEVER CLAIM THE PRESS',
        'filter': 'D8',
        'expect': ['D8/content'],
    },
    {
        'name': 'd9-kana',
        'why': 'KANARST fails to extinguish physical KANA LED via PSG R15 bit 7',
        'file': 'INPUT.Z8A',
        'old': """                OR      #80             ; BIT 7 = 1 -> KANA LED OFF""",
        'new': """                AND     #7F             ; MUTATION: FORCE KANA LED ON (BIT 7 = 0)""",
        'filter': 'D9',
        'expect': ['D9/led-off'],
    },
    {
        'name': 'd10-markup',
        'why': 'MARKUP= in the CFG is parsed but never applied, now that the '
               'CFG and Settings are the only way to choose the markup mode',
        'file': 'CFG.Z8A',
        'old': """                LD      (MKUPMD), A
                RET


; --- PARSCLK""",
        'new': """                NOP                     ; MUTATION: MARKUP= IGNORED
                NOP
                NOP
                RET


; --- PARSCLK""",
        'filter': 'D10',
        # MD is also the boot default, so only the LIT variant can tell
        'expect': ['D10/lit/mode'],
    },
    {
        'name': 'e1-cut',
        'why': 'ACTCUT copies to clipboard but skips deleting selection from document',
        'file': 'ACTION.Z8A',
        'old': """                RET     Z               ; NOTHING COPIED
                JP      ACTDLS          ; DELETE SELECTION FROM DOCUMENT""",
        'new': """                RET                     ; MUTATION: SKIP ACTDLS DELETION
                JP      ACTDLS          ; DELETE SELECTION FROM DOCUMENT""",
        'filter': 'E1',
        'expect': ['E1/totlines', 'E1/content'],
    },
    {
        'name': 'e2-paste',
        'why': 'PSTNL does not create new lines during multi-line paste',
        'file': 'ACTION.Z8A',
        'old': """PSTNL           LD      HL, (TOTLINES)
                PUSH    HL
                CALL    EDNWLIN""",
        'new': """PSTNL           LD      HL, (TOTLINES)
                PUSH    HL
                NOP                     ; MUTATION: NO NEWLINES ON PASTE
                NOP
                NOP""",
        'filter': 'E2',
        'expect': ['E2/totlines', 'E2/content'],
    },
    {
        'name': 'e3-sel-scroll',
        'why': 'ACTSLMD does not advance row on selection',
        'file': 'ACTION.Z8A',
        'old': """ACTSLMD         CALL    SELBEG
                LD      HL, (TOPLINE)""",
        'new': """ACTSLMD         RET                     ; MUTATION: ACTSLMD NO-OP
                LD      HL, (TOPLINE)""",
        'filter': 'E3',
        'expect': ['E3/docline-advanced', 'E3/viewport-scrolled'],
    },
    {
        'name': 'e4-selall-del',
        'why': 'ACTSELAL fails to set SELACT to 1',
        'file': 'ACTION.Z8A',
        'old': """                XOR     A
                LD      (SELANCX), A
                LD      A, 1
                LD      (SELACT), A""",
        'new': """                XOR     A
                LD      (SELANCX), A
                XOR     A               ; MUTATION: DO NOT ACTIVATE SELECTION
                LD      (SELACT), A""",
        'filter': 'E4',
        'expect': ['E4/sel-active'],
    },
    {
        'name': 'e5-replace',
        'why': '.DOPRINT does not call ACTDLS when typing over active selection',
        'file': 'DISP.Z8A',
        'old': """                LD      A, (SELACT)
                OR      A
                JR      Z, .NOSELDL""",
        'new': """                LD      A, (SELACT)
                OR      A
                JR      .NOSELDL        ; MUTATION: DO NOT DELETE SELECTION ON TYPING""",
        'filter': 'E5',
        'expect': ['E5/content'],
    },
    {
        'name': 'e6-sel-word-page',
        'why': 'ACTSLWRT does not advance to next word',
        'file': 'ACTION.Z8A',
        'old': """ACTSLWRT        CALL    SELBEG
                CALL    SELPRE
                CALL    ACTWRGT""",
        'new': """ACTSLWRT        CALL    SELBEG
                CALL    SELPRE
                NOP                     ; MUTATION: DO NOT ADVANCE TO NEXT WORD
                NOP
                NOP""",
        'filter': 'E6',
        'expect': ['E6/word-curx'],
    },
    {
        'name': 'e7-clip-limit',
        'why': 'ACTCOPY does not clamp copy bytes to CLIPMAX',
        'file': 'ACTION.Z8A',
        'old': """                ; CLAMP K TO REMAINING CLIPBOARD SPACE (CLIPMAX - CPYCNT)
                LD      HL, CLIPMAX
                LD      DE, (CPYCNT)""",
        'new': """                ; CLAMP K TO REMAINING CLIPBOARD SPACE (CLIPMAX - CPYCNT)
                LD      HL, 4096        ; MUTATION: EXPAND CAPACITY PAST BUFFER
                LD      DE, (CPYCNT)""",
        'filter': 'E7',
        'expect': ['E7/copy/cliplen'],
    },
    {
        'name': 'e7-cut-full',
        'why': 'ACTCUT deletes a selection the clipboard could not hold',
        'file': 'ACTION.Z8A',
        'old': """                RET     NZ              ; CLIPBOARD FULL: THE TEXT STAYS""",
        'new': """                NOP                     ; MUTATION: CUT ANYWAY""",
        'filter': 'E7',
        'expect': ['E7/cut/content', 'E7/cut/totlines'],
    },
    {
        'name': 'e7-exact-precheck',
        'why': 'ACTCOPY tests for a full clipboard before each line, so a '
               'selection of exactly CLIPMAX bytes is called short',
        'file': 'ACTION.Z8A',
        'old': """                ; ADDS NOTHING)
                LD      HL, (SELTMPL)
                CALL    LINEREAD""",
        'new': """                ; ADDS NOTHING)
                LD      HL, (CPYCNT)    ; MUTATION: THE OLD PRE-LINE TEST
                LD      DE, CLIPMAX
                CALL    CMPHLDE
                JP      NC, .CPYFULL
                LD      HL, (SELTMPL)
                CALL    LINEREAD""",
        'filter': 'E7',
        'expect': ['E7/exact/full-flag', 'E7/exact/content'],
    },
    {
        'name': 's2-cut-full',
        'target': 'S2ED',
        'why': 'ACTCUT deletes a selection the 1 KB S2ED clipboard could not hold',
        'file': 'ACTION.Z8A',
        'old': """                RET     NZ              ; CLIPBOARD FULL: THE TEXT STAYS""",
        'new': """                NOP                     ; MUTATION: CUT ANYWAY""",
        'filter': 'S2-56',
        'expect': ['S2-56/cut/content', 'S2-56/cut/totlines'],
    },
    {
        'name': 'g12-screen-restore',
        'why': 'TERM does not call RSTPAL to restore standard VDP palette',
        'file': 'BDOS.Z8A',
        'old': """                ; 5. RESTORE VDP PALETTE (ALL 16 REGISTERS)
                CALL    RSTPAL""",
        'new': """                ; 5. RESTORE VDP PALETTE (ALL 16 REGISTERS)
                NOP                     ; MUTATION: DO NOT RESTORE PALETTE
                NOP
                NOP""",
        'filter': 'G12',
        'expect': ['G12/vdp-palette'],
    },
    {
        'name': 'g12-r8',
        'why': 'RSTPAL restores the palette but not R#8, so S6ED leaves DOS '
               'with sprites off and TP=1 (CHGMOD does not touch R#8)',
        'file': 'S6ED.Z8A',
        'old': """                LD      A, (SAVRG8)
                LD      (RG8SAV), A
                OUT     (C), A
                LD      A, #88          ; REG 8 | #80
                OUT     (C), A""",
        'new': """                ; MUTATION: R#8 LEFT AS SCRINIT SET IT""",
        'filter': 'G12',
        'expect': ['G12/restored-r8'],
    },
    {
        'name': 's2-sett-valclr',
        'why': 'the Settings value field is not blanked before the value is '
               'written, so a shorter value keeps the tail of a longer one '
               '(AUTO -> DOS reads DOSO)',
        'target': 'S2ED',
        'file': 'WINDOW.Z8A',
        'old': """                LD      HL, .VALCLR
                PUSH    IX
                CALL    WINPUTS""",
        'new': """                LD      HL, .VALCLR
                PUSH    IX
                NOP                     ; MUTATION: FIELD NOT BLANKED
                NOP
                NOP""",
        'filter': 'S2-45',
        'expect': ['S2-45/values'],
    },
    {
        'name': 's2-stat-rcol',
        'why': 'the status bar right channel starts one column late and ends '
               'on column 63, past the clock, flush with the right edge',
        'target': 'S2ED',
        'file': 'UI.Z8A',
        'old': """                LD      DE, STATBUF + STBRCOL
""",
        'new': """                LD      DE, STATBUF + STBRCOL + 1 ; MUTATION
""",
        'filter': 'S2-40',
        'expect': ['S2-40/col'],
    },
    {
        'name': 'vi-vline-chars',
        'why': 'V is line-wise only on entry: once the cursor moves the range '
               'falls back to characters from the cursor column (the defect '
               'seen on real hardware)',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, (VIVLINE)
                OR      A
                JR      Z, .INCL""",
        'new': """                LD      A, (VIVLINE)
                OR      A
                JR      .INCL           ; MUTATION: NEVER LINE-WISE""",
        'filter': 'S2-46',
        'expect_any': ['S2-46-vi-visual-walk/seed1/painted',
                       'S2-46-vi-visual-walk/seed2/painted'],
    },
    {
        'name': 'undo-pnt-cursor',
        'why': 'UNDOPNT draws the cursor itself and MAINLOOP draws it again: '
               'the two XORs cancel while BLNKPH says it is up, so the next '
               'move leaves an inverted cell behind after every undo',
        'target': 'S2ED',
        'file': 'UNDO.Z8A',
        'old': """                CALL    ADJLCOL
                JP      REDRAW""",
        'new': """                CALL    ADJLCOL
                CALL    REDRAW          ; MUTATION: THE CURSOR DRAWN HERE TOO
                CALL    DRWSTAT
                JP      DRWCUR""",
        'filter': 'S2-46',
        'expect_any': ['S2-46-vi-visual-walk/seed1/painted',
                       'S2-46-vi-visual-walk/seed2/painted',
                       'S2-46-vi-visual-walk/seed3/painted'],
    },
    {
        'name': 's2-drwmenu-de',
        'why': 'the defect as it shipped: DE loaded only on the Untitled '
               'branch, so a bare S2ED measured the name from a garbage DE',
        'target': 'S2ED',
        'file': 'UI.Z8A',
        'old': """                LD      DE, FNAMBUF
                LD      A, (FILENAME)
                OR      A
                JR      NZ, .HAVEFN
                ; NO FILENAME: IF MODIFIED, USE "Untitled"
                LD      A, (MODIFIED)
                OR      A
                JR      Z, .CHKEND      ; EMPTY FNAMBUF, LENGTH 0""",
        'new': """                LD      A, (FILENAME)
                OR      A
                JR      NZ, .HAVEFN
                ; NO FILENAME: IF MODIFIED, USE "Untitled"
                LD      A, (MODIFIED)
                OR      A
                JR      Z, .CHKEND      ; MUTATION: DE NOT YET LOADED
                LD      DE, FNAMBUF""",
        'filter': 'S2-33',
        # A garbage LDIR has no single observable on screen: it once zeroed
        # the colour roles (the user's black screen), but since FNAMBUF moved
        # to page 3 it lands in the empty undo ring, clock on or off.  The
        # pointer itself is checked at .NODRAW (S2-33/name-length).
        'expect_any': ['S2-33/name-length', 'S2-33/roles', 'S2-33/status',
                       'S2-33/menubar', 'S2-33-bare-launch'],
    },
    {
        'name': 'h1-help',
        'why': 'the /H switch is missing from SWTTBL: S6ED /H boots instead '
               'of printing help and exiting in text mode',
        'file': 'PARAMS.Z8A',
        'old': """SWTTBL          DEFB    '?'
                DEFW    DOHLP
                DEFB    'H'""",
        'new': """SWTTBL          DEFB    '?'
                DEFW    DOHLP
                DEFB    'Z'             ; MUTATION: /H NOT IN TABLE""",
        'filter': 'H1',
        'expect': ['H1/help-printed', 'H1/no-screen6', 'H1/no-segments'],
    },
    {
        'name': 'h2-question',
        'why': 'the /? switch is missing from SWTTBL: S6ED /? boots instead '
               'of printing help and exiting in text mode',
        'file': 'PARAMS.Z8A',
        'old': """SWTTBL          DEFB    '?'
                DEFW    DOHLP""",
        'new': """SWTTBL          DEFB    'Z'             ; MUTATION: /? NOT IN TABLE
                DEFW    DOHLP""",
        'filter': 'H2',
        'expect': ['H2/help-printed', 'H2/no-screen6', 'H2/no-segments'],
    },
    {
        'name': 'h4-chkfile',
        'why': 'CHKFILE does not skip / switches, treating /X as the filename',
        'file': 'PARAMS.Z8A',
        'old': """                LD      A, (HL)
                CP      '/'
                JR      NZ, .FOUND      ; NOT A SWITCH → FILENAME""",
        'new': """                LD      A, (HL)
                CP      '/'
                JR      Z, .FOUND       ; MUTATION: ACCEPTS / SWITCH AS FILENAME""",
        'filter': 'H4',
        'expect': ['H4/file-loaded'],
    },
    {
        'name': 'h5-verbose',
        'why': 'the /V switch is missing from SWTTBL: S6ED /V boots quiet without verbose mode',
        'file': 'PARAMS.Z8A',
        'old': """                DEFB    'V'
                DEFW    DOVRB""",
        'new': """                DEFB    'Z'             ; MUTATION: /V NOT IN TABLE
                DEFW    DOVRB""",
        'filter': 'H5',
        'expect': ['H5/text-printed', 'H5/verbose-set'],
    },
    {
        'name': 'i1-unix-save',
        'why': 'FILESAVE always writes CRLF ignoring SAVEEOL = 1',
        'file': 'FILEIO.Z8A',
        'old': """                LD      A, (SAVEEOL)
                OR      A
                JR      Z, .WREOL2""",
        'new': """                JR      .WREOL2         ; MUTATION: ALWAYS WRITE CRLF
                LD      A, (SAVEEOL)
                OR      A""",
        'filter': 'I1',
        'expect': ['I1/no-cr', 'I1/content'],
    },
    {
        'name': 'i2-autolod-lf',
        'why': 'FILELOAD does not auto-detect standalone LF as UNIX EOL',
        'file': 'FILEIO.Z8A',
        'old': """                LD      A, C
                LD      (SAVEEOL), A    ; DETECTED: DOS (CRLF) OR UNIX (LF)""",
        'new': """                XOR     A               ; MUTATION: DO NOT DETECT UNIX
                LD      (SAVEEOL), A    ; DETECTED: DOS (CRLF) OR UNIX (LF)""",
        'filter': 'I1',
        'expect': ['I1/saveeol', 'I1/content'],
    },
    {
        'name': 'f1-homeseg',
        'why': 'FCALL leaves HOMESEG non-zero when returning to core',
        'file': 'XSEG.Z8A',
        'old': """                LD      HL, HOMESEG
                LD      (HL), B""",
        'new': """                LD      HL, HOMESEG
                LD      (HL), 1         ; MUTATION: LEAVE HOMESEG DIRTY""",
        'filter': 'G13',
        'expect': ['G13/homeseg-idle'],
    },
    {
        # What executes at #8000 when the payload lands elsewhere is
        # UNINITIALISED MAPPER RAM, so the observable is undefined by nature:
        # sometimes an editor that reached MAINLOOP unconfigured, sometimes a
        # session that never gets there.  Pinning it to the first outcome is
        # why this stopped being caught on 2026-09-22 after an unrelated
        # change moved the payload -- expect_any states the real contract.
        'name': 'f2-datload',
        'why': 'DATLOAD loads feature payload at wrong address in page 2, so '
               'the FCALL enters uninitialised segment RAM',
        'file': 'XSEG.Z8A',
        'old': """                LD      A, (DATHAND)
                LD      HL, (DATBLK + 4)
                LD      DE, (DATBLK + 2)
                CALL    DSKREAD""",
        'new': """                LD      A, (DATHAND)
                LD      HL, (DATBLK + 4)
                LD      DE, #9000       ; MUTATION: LOAD AT WRONG ADDRESS
                CALL    DSKREAD""",
        'filter': 'G13',
        'expect_any': ['G13/cfg-applied', 'G13-feature-residency'],
    },
    {
        # DATHCHK used to accept any "S?ED": S6ED loaded S2ED.DAT and S62ED
        # shipped S6ED's magic.  Checking only the 'S' brings that back.
        'name': 'dat-magic-any',
        'why': "DATHCHK ignores the magic, so a sibling editor's container "
               'renamed to S6ED.DAT is loaded and FCALLed',
        'file': 'XSEG.Z8A',
        # The loop still walks all four bytes, so HL reaches the version
        # field as before: only the verdict is dropped.  (Shortening the loop
        # instead left HL on byte 1 and the version check refused the file.)
        'old': """.MAGIC          LD      A, (DE)
                CP      (HL)
                JR      NZ, .BAD""",
        'new': """.MAGIC          LD      A, (DE)
                CP      (HL)
                NOP                     ; MUTATION: ANY MAGIC WILL DO
                NOP""",
        'filter': 'H39',
        'expect': ['H39/corrupt-printed'],
    },
    {
        'name': 'load-progress',
        'why': 'LOADDOC never advances the progress bar, so a long load '
               'shows a frozen 0% again',
        'file': 'FILEIO.Z8A',
        'old': """                PUSH    HL
                CALL    PRGADV
                POP     DE
                POP     HL
                PUSH    HL
                OR      A
                SBC     HL, DE          ; THE OTHER HALF
                CALL    PRGADV""",
        'new': """                PUSH    HL
                NOP                     ; MUTATION: THE BAR NEVER MOVES
                NOP
                NOP
                POP     DE
                POP     HL
                PUSH    HL
                OR      A
                SBC     HL, DE          ; THE OTHER HALF
                NOP
                NOP
                NOP""",
        'filter': 'H40',
        'expect': ['H40/progress'],
    },
    {
        'name': 's2-load-progress',
        'target': 'S2ED',
        'why': 'the same, measured on the S2 gate: the counter is CORE',
        'file': 'FILEIO.Z8A',
        'old': """                PUSH    HL
                CALL    PRGADV
                POP     DE
                POP     HL
                PUSH    HL
                OR      A
                SBC     HL, DE          ; THE OTHER HALF
                CALL    PRGADV""",
        'new': """                PUSH    HL
                NOP                     ; MUTATION: THE BAR NEVER MOVES
                NOP
                NOP
                POP     DE
                POP     HL
                PUSH    HL
                OR      A
                SBC     HL, DE          ; THE OTHER HALF
                NOP
                NOP
                NOP""",
        'filter': 'S2-35',
        'expect': ['S2-35/progress'],
    },
    {
        'name': 'io-flush-end',
        'why': 'FILESAVE closes the file without writing what the last, partial save buffer holds',
        'file': 'FILEIO.Z8A',
        'old': """                CALL    IOFLUSH         ; WHAT THE LAST BLOCK HOLDS
                JR      C, .WRFAIL""",
        'new': """                NOP                     ; MUTATION: NO FINAL FLUSH
                NOP
                NOP
                NOP
                NOP""",
        'filter': 'H42',
        'expect': ['H42/dos/content', 'H42/unix/content'],
    },
    {
        'name': 's2-io-flush-end',
        'target': 'S2ED',
        'why': 'the same on S2ED: the save buffer is CORE',
        'file': 'FILEIO.Z8A',
        'old': """                CALL    IOFLUSH         ; WHAT THE LAST BLOCK HOLDS
                JR      C, .WRFAIL""",
        'new': """                NOP                     ; MUTATION: NO FINAL FLUSH
                NOP
                NOP
                NOP
                NOP""",
        'filter': 'S2-37',
        'expect': ['S2-37/dos/content', 'S2-37/unix/content'],
    },
    {
        'name': 'io-split',
        'why': 'IOPUT fills the buffer and flushes it but drops the rest of a run that did not fit',
        'file': 'FILEIO.Z8A',
        'old': """                POP     HL
                POP     BC
                RET     C
                JR      IOPUT""",
        'new': """                POP     HL
                POP     BC
                RET     C
                OR      A               ; MUTATION: THE REST OF A SPLIT RUN
                RET                     ; IS DROPPED""",
        'filter': 'H42',
        'expect': ['H42/dos/content', 'H42/unix/content'],
    },
    {
        'name': 'load-crlf-split',
        'why': 'a CR that ends one read is forgotten, so the LF opening the next is a second, empty line',
        'file': 'FILEIO.Z8A',
        'old': """.CREND          INC     A
                LD      (WASCR), A""",
        'new': """.CREND          INC     A
                NOP                     ; MUTATION: THE CR IS FORGOTTEN
                NOP                     ; ACROSS THE READ
                NOP""",
        'filter': 'H42',
        'expect': ['H42/dos/lines', 'H42/dos/content'],
    },
    {
        'name': 's2-load-crlf-split',
        'target': 'S2ED',
        'why': 'the same on S2ED: the loader is CORE',
        'file': 'FILEIO.Z8A',
        'old': """.CREND          INC     A
                LD      (WASCR), A""",
        'new': """.CREND          INC     A
                NOP                     ; MUTATION: THE CR IS FORGOTTEN
                NOP                     ; ACROSS THE READ
                NOP""",
        'filter': 'S2-37',
        'expect': ['S2-37/dos/lines', 'S2-37/dos/content'],
    },
    {
        'name': 'load-trunc',
        'why': 'the loader does not stop at MAXCOLS: a longer line runs into the attribute half of WORKBUF',
        'file': 'FILEIO.Z8A',
        'old': """                JR      Z, .SKIP        ; FULL: TRUNCATE AT MAX LINE WIDTH""",
        'new': """                NOP                     ; MUTATION: NO MAXCOLS BOUND
                NOP""",
        'filter': 'H42',
        'expect': ['H42/dos/content', 'H42/unix/content'],
    },
    {
        'name': 'load-msg-stays',
        'why': 'FILELOAD leaves its message in STATMSG, which then hides '
               '[FILE TOO LARGE] and sits on the status bar after the load',
        'file': 'FILEIO.Z8A',
        'old': """                CALL    LOADDOC
                PUSH    AF
                XOR     A
                LD      (STATMSG), A""",
        'new': """                CALL    LOADDOC
                PUSH    AF
                XOR     A
                NOP                     ; MUTATION: "Loading..." STAYS UP
                NOP
                NOP""",
        'filter': 'H40',
        'expect': ['H40/cleared'],
    },
    {
        'name': 'brw-scan-silent',
        'why': 'the first directory scan says nothing again, so Ctrl+O leaves '
               'the screen unchanged while the disk works',
        'file': 'FILEIO.Z8A',
        'old': """BRWSCNM         LD      HL, STRRDIR
                CALL    SETMSG
                CALL    DRWSTAT""",
        'new': """BRWSCNM         NOP                     ; MUTATION: SILENT FIRST SCAN""",
        'filter': 'H41',
        'expect': ['H41/scan'],
    },
    {
        'name': 'brw-rescan-silent',
        'why': 'a rescan with the browser up no longer marks the information '
               'line, so entering a directory looks frozen',
        'file': 'S6/BROWSER.Z8A',
        'old': """.RESCAN         CALL    .BUSY           ; THE WINDOW IS UP: SAY SO IN IT""",
        'new': """.RESCAN         NOP                     ; MUTATION: SILENT RESCAN
                NOP
                NOP""",
        'filter': 'H41',
        # without the notice BRWBUSY.DONE never fires and the session
        # cannot finish, which reports under the case name
        'expect_any': ['H41/busy', 'H41-browse-busy'],
    },
    {
        'name': 's2-brw-rescan-silent',
        'target': 'S2ED',
        'why': 'the same on S2ED, whose browser draws the line its own way',
        'file': 'S2/BROWSER.Z8A',
        'old': """.RESCAN         CALL    BRWBUSY         ; THE WINDOW IS UP: SAY SO IN IT""",
        'new': """.RESCAN         NOP                     ; MUTATION: SILENT RESCAN
                NOP
                NOP""",
        'filter': 'S2-36',
        # without the notice BRWBUSY.DONE never fires and the session
        # cannot finish, which reports under the case name
        'expect_any': ['S2-36/busy', 'S2-36-browse-busy'],
    },
    {
        'name': 's61-cell-nx6',
        'target': 'S61ED',
        'why': 'ROWSET presets the glyph blit 6 px wide, the S6ED cell: every S61 cell loses its last two pixel columns',
        'file': 'S61/RENDER.Z8A',
        'old': """                LD      HL, CELLH
                LD      (VDP_NY), HL
                LD      HL, CELLW
                LD      (VDP_NX), HL""",
        'new': """                LD      HL, CELLH
                LD      (VDP_NY), HL
                LD      HL, 6           ; MUTATION: THE S6 CELL WIDTH
                LD      (VDP_NX), HL""",
        'filter': 'S62-1',
        'expect': ['S62-1/text'],
    },
    {
        'name': 's61-scroll-dx1cell',
        'target': 'S61ED',
        'why': 'the scroll blit starts one cell right of the text origin: the first text column never moves',
        'file': 'S61/SCROLL.Z8A',
        'old': """                LD      HL, TXORG_X
                LD      (VDP_DX), HL
                XOR     A               ; ARG = 0 (TOP-TO-BOTTOM)""",
        'new': """                LD      HL, TXORG_X + CELLW ; MUTATION: ONE CELL IN
                LD      (VDP_DX), HL
                XOR     A               ; ARG = 0 (TOP-TO-BOTTOM)""",
        'filter': 'S62-3',
        'expect': ['S62-3/down/text'],
    },
    {
        'name': 's61-title-inset6',
        'target': 'S61ED',
        'why': 'window titles go back to WINX + 6, two pixels off the body text and off the byte grid',
        'file': 'S61/WINDOW.Z8A',
        'old': """                LD      HL, (WINX)
                LD      DE, 8
                ADD     HL, DE
                EX      DE, HL          ; DE = DX
                LD      BC, WINCOMP_Y + 2""",
        'new': """                LD      HL, (WINX)
                LD      DE, 6           ; MUTATION: THE S6 INSET
                ADD     HL, DE
                EX      DE, HL          ; DE = DX
                LD      BC, WINCOMP_Y + 2""",
        'filter': 'S62-5',
        'expect': ['S62-5/about/title'],
    },
    {
        'name': 's61-menu-inset6',
        'target': 'S61ED',
        'why': 'unselected dropdown items go back to WINX + 6',
        'file': 'S61/MENU.Z8A',
        'old': """                LD      DE, 8
                ADD     HL, DE
                EX      DE, HL          ; DE = DX = WINX + 8
                LD      HL, (MNUTMPP)   ; HL = STRING POINTER
                XOR     A               ; VARIANT 0 (NORMAL)""",
        'new': """                LD      DE, 6           ; MUTATION: THE S6 INSET
                ADD     HL, DE
                EX      DE, HL          ; DE = DX = WINX + 8
                LD      HL, (MNUTMPP)   ; HL = STRING POINTER
                XOR     A               ; VARIANT 0 (NORMAL)""",
        'filter': 'S62-5',
        'expect': ['S62-5/file/items'],
    },
    {
        'name': 's61-menu-22',
        'target': 'S61ED',
        'why': 'a 22-character item reaches the right border at 8 px and WINCLIPX drops its last glyph ("Ctrl+")',
        'file': 'S61/MENU.Z8A',
        'old': '.S01            DEFM    "Open...       Ctrl+O", 0',
        'new': '.S01            DEFM    "Open...         Ctrl+O", 0',
        'filter': 'S62-5',
        'expect': ['S62-5/file/items'],
    },
    {
        'name': 's61-bic56',
        'target': 'S61ED',
        'why': 'the information line is 56 characters again: its last column falls past the clip and the count loses a digit',
        'file': 'S61/CONST_S61.Z8A',
        'old': 'BICCNTE         EQU     55',
        'new': 'BICCNTE         EQU     56',
        'also': [('S61/CONST_S61.Z8A', 'BICLEN          EQU     55', 'BICLEN          EQU     56')],
        'filter': 'S62-6',
        'expect': ['S62-6/info'],
    },
    {
        'name': 's61-col-2digit',
        'target': 'S61ED',
        'why': "the status bar's column goes back to two digits: Col 21 at column 121",
        'file': 'S61/UI.Z8A',
        'old': """                INC     HL              ; 1..256: CURX 255 MUST NOT WRAP
                LD      B, 3""",
        'new': """                INC     HL              ; 1..256: CURX 255 MUST NOT WRAP
                LD      B, 2            ; MUTATION: S2ED'S TWO DIGITS""",
        'filter': 'S62-4',
        'expect': ['S62-4/col'],
    },
    {
        'name': 's61-dat-magic',
        'target': 'S61ED',
        'why': "S61ED takes S6ED's container magic again, so a renamed S6ED.DAT is loaded and FCALLed",
        'file': 'S61ED.Z8A',
        'old': 'DEFINE  DATMAG  "S61E"',
        'new': 'DEFINE  DATMAG  "S6ED"',
        'filter': 'S62-7',
        'expect_any': ['S62-7/corrupt-printed', 'S62-7-dat-foreign'],
    },
    {
        'name': 's61-rescan-silent',
        'target': 'S61ED',
        'why': 'a rescan with the S61ED browser up no longer marks the information line',
        'file': 'S61/BROWSER.Z8A',
        'old': '.RESCAN         CALL    .BUSY           ; THE WINDOW IS UP: SAY SO IN IT',
        'new': """.RESCAN         NOP                     ; MUTATION: SILENT RESCAN
                NOP
                NOP""",
        'filter': 'S62-9',
        # without the notice BRWBUSY.DONE never fires and the session
        # cannot finish, which reports under the case name
        'expect_any': ['S62-9/busy', 'S62-9-browse-busy'],
    },
    {
        'name': 's61-autoexec-lf',
        'target': 'S61ED',
        'why': 'AUTOEXEC_S61.BAT with bare LF: COMMAND2.COM ignores it and the disk boots to the prompt',
        'file': 'AUTOEXEC_S61.BAT',
        'old': 'MODE 80\r\nPATH A:\\TOOLS\r\nCD \\DEV\r\nS61ED TEST.TXT\r\n',
        'new': 'MODE 80\nPATH A:\\TOOLS\nCD \\DEV\nS61ED TEST.TXT\n',
        'filter': 'S62-10',
        'expect_any': ['S62-10-shipped-disk', 'S62-10/booted'],
    },
    {
        'name': 'f2-datmagic',
        'why': 'S6ED.DAT header magic corrupted',
        'file': 'S6ED.Z8A',
        'old': 'DEFINE  DATMAG  "S6ED"',
        'new': 'DEFINE  DATMAG  "S6XX"',
        'filter': 'G13',
        'expect_static': ['feature-discipline'],
    },
    {
        'name': 'c1-datlen',
        'why': 'DATLOAD does not bound LENGTH or LOADADDR to the container '
               'window: a 16,385-byte payload writes past FTRTOP into the '
               'DOS area and the stack',
        'file': 'XSEG.Z8A',
        'old': """                LD      HL, (DATBLK + 4)
                LD      A, H
                OR      L
                JP      Z, .ERRCOR      ; LENGTH 0
                LD      DE, DATBLEN + 1
                OR      A
                SBC     HL, DE
                JP      NC, .ERRCOR     ; LENGTH > DATBLEN
                LD      HL, (DATBLK + 2)
                LD      DE, FTRBASE
                OR      A
                SBC     HL, DE
                JP      C, .ERRCOR      ; LOADADDR BELOW THE WINDOW
                LD      HL, FTRTOP
                LD      DE, (DATBLK + 2)
                OR      A
                SBC     HL, DE          ; HL = ROOM LEFT IN THE WINDOW
                JP      C, .ERRCOR      ; LOADADDR PAST THE WINDOW
                LD      DE, (DATBLK + 4)
                OR      A
                SBC     HL, DE
                JP      C, .ERRCOR      ; PAYLOAD OVERFLOWS FTRTOP""",
        'new': """                NOP                     ; MUTATION: NO LENGTH OR WINDOW BOUNDS""",
        'filter': 'H14',
        'expect': ['H14/corrupt-printed'],
    },
    {
        'name': 'c1-datblkid',
        'why': 'DATLOAD ignores BLKID and loads any block into FTRSEG',
        'file': 'XSEG.Z8A',
        'old': """                LD      A, (DATBLK)
                CALL    BLKSEG
                JP      C, .ERRCOR      ; UNKNOWN BLOCK ID
                LD      (DATSEG), A""",
        'new': """                LD      A, (DATBLK)
                CALL    BLKSEG
                LD      A, (FTRSEG)     ; MUTATION: UNKNOWN IDS LOAD INTO FTRSEG
                LD      (DATSEG), A""",
        'filter': 'H15',
        'expect': ['H15/corrupt-printed'],
    },
    {
        'name': 'c1-datseek',
        'why': 'DATLOAD reads the payload sequentially instead of seeking '
               'to DATAOFF: a padded or reordered container loads garbage',
        'file': 'XSEG.Z8A',
        'old': """                LD      A, (DATHAND)
                LD      HL, (DATBLK + 6)
                CALL    DSKSEEK
                JP      C, .ERRCOR""",
        'new': """                NOP                     ; MUTATION: NO SEEK, READ SEQUENTIALLY
                NOP
                NOP
                NOP""",
        'filter': 'H17',
        # The payload comes out shifted by the padding: either the editor
        # crashes before MAINLOOP (case-level failure) or it boots with the
        # CFG never applied.
        'expect_any': ['H17/cfg-applied', 'H17-dat-padded-seek'],
    },
    {
        'name': 'c2-wincarry',
        'why': 'WINOPEN applies AND %11111100 before JR NC, clearing carry and corrupting widths >= 253',
        'file': 'WINDOW.Z8A',
        'old': """                LD      HL, (WINW)
                LD      A, L
                ADD     A, 3
                LD      L, A
                JR      NC, .NOWINC
                INC     H
.NOWINC         LD      A, L
                AND     %11111100
                LD      L, A
                LD      (WINW), HL""",
        'new': """                LD      HL, (WINW)
                LD      A, L
                ADD     A, 3
                AND     %11111100
                LD      L, A
                JR      NC, .NOWINC
                INC     H
.NOWINC         LD      (WINW), HL""",
        'filter': 'H7',
        'expect_static': ['window-discipline'],
    },
    {
        'name': 'c2-winactv',
        'why': 'WINOPEN fails to set WINACTV=1 so modal window state is lost and clock is not inhibited',
        'file': 'WINDOW.Z8A',
        'old': """                ; MARK MODAL WINDOW ACTIVE TO INHIBIT CLOCK BLINK
                LD      A, 1
                LD      (WINACTV), A""",
        'new': """                ; MARK MODAL WINDOW ACTIVE TO INHIBIT CLOCK BLINK
                XOR     A
                LD      (WINACTV), A""",
        'filter': 'H7',
        'expect': ['H7/winactv-active'],
    },
    {
        'name': 'c2-winkil',
        'why': 'WINOPEN does not flush keyboard buffer so pre-queued keys dismiss modals prematurely',
        'file': 'WINDOW.Z8A',
        'old': """                ; FLUSH KEYBOARD BUFFER
                CALL    WINKIL""",
        'new': """                ; FLUSH KEYBOARD BUFFER
                NOP
                NOP
                NOP""",
        'filter': 'H18',
        'expect_any': ['H18/key-purged', 'window-discipline'],
    },
    {
        'name': 'c2-winclamp',
        'why': 'WINOPEN does not clamp geometry to screen and VRAM buffer bounds',
        'file': 'WINDOW.Z8A',
        'old': """                ; CLAMP WINX <= 504: WINX + WINW + WINSHDW <= 512, WINW >= 4
                LD      HL, (WINX)
                LD      DE, 504""",
        'new': """                ; CLAMP WINX <= 504: WINX + WINW + WINSHDW <= 512, WINW >= 4
                LD      HL, (WINX)
                LD      DE, 999         ; MUTATION: NO HORIZONTAL CLAMP""",
        'filter': 'H7',
        'expect_static': ['window-discipline'],
    },
    {
        'name': 'c3-accent',
        'why': 'the top accent band is painted in UI color instead of highlight',
        'file': 'WINDOW.Z8A',
        'old': """                ; 4. TOP ACCENT BAND (COL_HI, 1 PX)
                LD      DE, 0
                LD      HL, 1
                LD      A, CLR_HI""",
        'new': """                ; 4. TOP ACCENT BAND (COL_HI, 1 PX)
                LD      DE, 0
                LD      HL, 1
                LD      A, CLR_UI       ; MUTATION: ACCENT IN UI COLOR""",
        'filter': 'H7',
        'expect': ['H7/color-highlight'],
    },
    {
        'name': 'c3-shadow',
        'why': 'the shadow bars ignore SHADOW= and are hardcoded to the '
               'highlight colour, so the key cannot move them and the '
               'default stops being the background',
        'file': 'WINDOW.Z8A',
        'old': """                LD      HL, WINCOMP_Y + WINSHDW
                LD      (VDP_DY), HL
                LD      HL, WINSHDW
                LD      (VDP_NX), HL
                LD      HL, (WINH)
                LD      (VDP_NY), HL
                LD      A, (SHDWCLR)""",
        'new': """                LD      HL, WINCOMP_Y + WINSHDW
                LD      (VDP_DY), HL
                LD      HL, WINSHDW
                LD      (VDP_NX), HL
                LD      HL, (WINH)
                LD      (VDP_NY), HL
                LD      A, CLR_HI       ; MUTATION: SHADOW IN HIGHLIGHT""",
        'filter': 'H21',
        'expect': ['H21/bg/shadow-right', 'H21/ui/shadow-right'],
    },
    {
        'name': 'c3-winupd',
        'why': 'WINUPD blits from the save buffer instead of the composition buffer',
        'file': 'WINDOW.Z8A',
        'old': """                LD      HL, WINCOMP_Y
                ADD     HL, DE
                LD      (VDP_SY), HL    ; SY = WINCOMP_Y + REL Y""",
        'new': """                LD      HL, WINBUF_Y    ; MUTATION: WRONG SOURCE BUFFER
                ADD     HL, DE
                LD      (VDP_SY), HL    ; SY = WINCOMP_Y + REL Y""",
        'filter': 'H19',
        'expect': ['H19/nav-left'],
    },
    {
        'name': 'c2-winchtr-char',
        'why': 'WINSTR.LOOP clobbers A before calling WINCHTR so all characters become control patterns',
        'file': 'WINDOW.Z8A',
        'old': """                PUSH    AF
                LD      A, (WINVAR)
                LD      B, A
                LD      A, (WINOP)
                LD      C, A
                POP     AF
                CALL    WINCHTR""",
        'new': """                LD      A, (WINVAR)
                LD      B, A
                LD      A, (WINOP)
                LD      C, A
                CALL    WINCHTR""",
        'filter': 'H7',
        'expect': ['H7/title-text'],
    },
    {
        'name': 'wq-direct',
        'why': 'ACTQUIT jumps straight to TERM without asking (pre-3b behaviour)',
        'file': 'ACTION.Z8A',
        # Anchored below the FTR-BUDGET comment on purpose: that line carries
        # measured byte counts and is rewritten every time the container moves.
        'old': """                LD      A, (FTRSEG)
                LD      HL, DOQIT""",
        'new': """                JP      TERM            ; MUTATION: QUIT WITHOUT ASKING
                LD      HL, DOQIT""",
        'filter': 'H19',
        # ESC exits on the spot: either the dialog-displayed check goes red,
        # or the whole case dies waiting for a WINPOLL that never comes.
        'expect_any': ['H19/dialog-displayed', 'H19-quit-dialog'],
    },
    {
        'name': 'wq-defsel',
        'why': 'the Quit dialog defaults to YES, so an accidental ENTER quits',
        'file': 'WINDOW.Z8A',
        'old': """                ; DEFAULT: NO SELECTED, RESULT CANCELLED
                LD      A, 1
                LD      (WINSEL), A""",
        'new': """                ; DEFAULT: NO SELECTED, RESULT CANCELLED
                XOR     A               ; MUTATION: DEFAULT SELECTION = YES
                LD      (WINSEL), A""",
        'filter': 'H19',
        'expect': ['H19/default-no'],
    },
    {
        'name': 'wq-nav',
        'why': 'a selection change never repaints the buttons',
        'file': 'WINDOW.Z8A',
        'old': """                LD      (HL), A
                CALL    .BTNS
                CALL    WINVSY""",
        'new': """                LD      (HL), A
                CALL    WINVSY         ; MUTATION: SELECTION NEVER REPAINTS""",
        'filter': 'H19',
        'expect': ['H19/nav-left'],
    },
    {
        'name': 'wq-yes',
        'why': 'the Y accelerator records CANCEL instead of CONFIRM',
        'file': 'WINDOW.Z8A',
        'old': """.YES            LD      A, 1
                LD      (WINRES), A""",
        'new': """.YES            XOR     A               ; MUTATION: Y DOES NOT CONFIRM
                LD      (WINRES), A""",
        'filter': 'H19',
        # Y records CANCEL: either quit-y goes red, or the case dies waiting
        # for a TERM.TERMDON that never comes.
        'expect_any': ['H19/quit-y', 'H19-quit-dialog'],
    },
    {
        'name': 'menu-defsel',
        'why': 'File menu opens with item 1 selected instead of default item 0 (New)',
        'file': 'MENU.Z8A',
        'old': """.INITOK         XOR     A
                LD      (MNUSEL), A     ; DEFAULT SELECTION = 0 (NEW)""",
        'new': """.INITOK         LD      A, 1            ; MUTATION: DEFAULT SELECTION = 1
                LD      (MNUSEL), A""",
        'filter': 'H22',
        'expect': ['H22/default-new'],
    },
    {
        'name': 'menu-skipsep',
        'why': 'DOWN navigation fails to skip the separator line at item 4',
        'file': 'MENU.Z8A',
        'old': """.DWNCHK         CALL    MNUCHKS         ; SEPARATOR?
                JR      NZ, .DWNOK
                INC     A               ; SKIP SEPARATOR
.DWNOK          JR      .MOVE""",
        'new': """.DWNCHK         CALL    MNUCHKS         ; SEPARATOR?
                NOP                     ; MUTATION: NEVER SKIP SEPARATOR
                NOP
                NOP
                NOP
.DWNOK          JR      .MOVE""",
        'filter': 'H22',
        'expect': ['H22/nav-skip-sep'],
    },
    {
        'name': 'menu-title',
        'why': 'cancellation leaves the row 0 File title inverted',
        'file': 'MENU.Z8A',
        'old': """.CANCEL         CALL    WINCLOS
                CALL    MNUTITL         ; UN-HIGHLIGHT TITLE
                SCF                     ; CY = 1 (CANCELLED)""",
        'new': """.CANCEL         CALL    WINCLOS
                NOP                     ; MUTATION: DO NOT UN-HIGHLIGHT TITLE
                NOP
                NOP
                SCF                     ; CY = 1 (CANCELLED)""",
        'filter': 'H22',
        'expect': ['H22/cancel-esc'],
    },
    {
        'name': 'menu-nav-wrap',
        'why': 'RIGHT navigation fails to wrap from Help (2) to File (0)',
        'file': 'MENU.Z8A',
        'old': """.RIGHT          LD      A, (MNUID)
                INC     A
                CP      MNUCOUNT        ; 3
                JR      C, .RGHTOK
                XOR     A               ; WRAP 2 -> 0
.RGHTOK         JP      MNUSWCH""",
        'new': """.RIGHT          LD      A, (MNUID)
                INC     A
                CP      MNUCOUNT        ; 3
                JR      C, .RGHTOK
                LD      A, 2            ; MUTATION: CLAMP TO 2 INSTEAD OF WRAPPING TO 0
.RGHTOK         JP      MNUSWCH""",
        'filter': 'H23',
        'expect': ['H23/nav-right-wrap'],
    },
    {
        'name': 'menu-switch-title',
        'why': 'horizontal switch fails to un-highlight previous menu title',
        'file': 'MENU.Z8A',
        'old': """; 2. UN-HIGHLIGHT CURRENT TITLE IN ROW 0
                CALL    MNUTITL
                POP     BC""",
        'new': """; 2. UN-HIGHLIGHT CURRENT TITLE IN ROW 0
                NOP                     ; MUTATION: SKIP UN-HIGHLIGHT
                NOP
                NOP
                POP     BC""",
        'filter': 'H23',
        'expect': ['H23/title-switch-xor'],
    },
    {
        'name': 'menu-hlp-sett',
        'why': 'Help menu item 0 calls ACTHELP instead of ACTSETT',
        'file': 'ACTION.Z8A',
        'old': """.HSETT          CALL    ACTSETT
                JP      DRWSTAT""",
        'new': """.HSETT          CALL    ACTHELP         ; MUTATION: WRONG DISPATCH
                JP      DRWSTAT""",
        'filter': 'H23',
        'expect': ['H23/action-settings'],
    },
    {
        'name': 'undo-dispatch',
        'why': 'Undo action fails to execute when ACTUNDO vector is disconnected',
        'file': 'ACTION.Z8A',
        'old': '                DEFW    ACTUNDO         ; 57 (UNDO)',
        'new': '                DEFW    ACTNONE         ; MUTATION: DISABLE UNDO DISPATCH',
        'filter': 'U1',
        'expect': ['U1/undone-state'],
    },
    {
        'name': 'undo-clean-mark',
        'why': 'UNDOPNT always marks the document modified: undoing back to '
               'the file leaves the asterisk on',
        'file': 'UNDO.Z8A',
        'old': """                JR      NZ, .MODSET
                XOR     A
.MODSET""",
        'new': """                JR      NZ, .MODSET
                NOP                     ; MUTATION: NEVER CLEAN
.MODSET""",
        'filter': 'U10',
        'expect': ['U10/back/undone'],
    },
    {
        'name': 'undo-clean-burst',
        'why': 'the save leaves the typing burst open, so the next key joins '
               'the record the save point names',
        'file': 'UNDO.Z8A',
        'old': """                LD      (SAVEPTR), HL
                JP      UNDOCLS""",
        'new': """                LD      (SAVEPTR), HL
                RET                     ; MUTATION: BURST LEFT OPEN""",
        'filter': 'U10',
        'expect': ['U10/saved/back'],
    },
    {
        'name': 'undo-clean-evict',
        'why': 'eviction keeps the empty-history save point, so a full undo '
               'of a wrapped ring claims the file',
        'file': 'UNDO.Z8A',
        'old': """                CALL    UNDOSVE         ; THE SAVED STATE MAY GO WITH IT""",
        'new': """                NOP                     ; MUTATION: SAVE POINT SURVIVES
                NOP
                NOP""",
        'filter': 'U10',
        'expect': ['U10/evict/undone'],
    },
    {
        'name': 'undo-del',
        'why': 'line deletion fails to record in undo ringbuffer when UNDODEL is bypassed',
        'file': 'ACTION.Z8A',
        'old': """.DLMULT         LD      HL, (DOCLINE)
                CALL    LINEREAD
                CALL    UNDODEL""",
        'new': """.DLMULT         LD      HL, (DOCLINE)
                CALL    LINEREAD
                NOP
                NOP
                NOP""",
        'filter': 'U2',
        'expect': ['U2/undone-totlines'],
    },
    {
        'name': 'undo-split',
        'why': 'line split fails to record in undo ringbuffer when UNDOSPL is bypassed',
        'file': 'EDIT.Z8A',
        'old': """; 2. LOAD THE LINE THAT IS ABOUT TO BE SPLIT
                LD      HL, (DOCLINE)
                CALL    LINEREAD
                CALL    UNDOSPL""",
        'new': """; 2. LOAD THE LINE THAT IS ABOUT TO BE SPLIT
                LD      HL, (DOCLINE)
                CALL    LINEREAD
                NOP
                NOP
                NOP""",
        'filter': 'U3',
        'expect': ['U3/undone-totlines'],
    },
    {
        'name': 'undo-join',
        'why': 'line join fails to record in undo ringbuffer when UNDOJON is bypassed',
        'file': 'EDIT.Z8A',
        'old': """                ; HAPPENED -- AND LINE B WAS DELETED ANYWAY, ITS TEXT LOST.
                CALL    UNDOJON""",
        'new': """                ; HAPPENED -- AND LINE B WAS DELETED ANYWAY, ITS TEXT LOST.
                NOP                     ; MUTATION: JOIN NOT RECORDED
                NOP
                NOP""",
        'filter': 'U4',
        'expect': ['U4/undone-totlines'],
    },
    {
        'name': 'join-oom-delete',
        'why': 'JOIN2L ignores LINEWRT\'s carry: with no memory for the longer '
               'line A it deletes line B anyway, and records a join that never '
               'happened',
        'file': 'EDIT.Z8A',
        'old': """                RET     C               ; NO MEMORY: LINE A AS IT WAS, B KEPT""",
        'new': """                NOP                     ; MUTATION: OOM IGNORED""",
        'filter': 'R5',
        'expect': ['R5/refused', 'R5/content'],
    },
    {
        'name': 'undo-nwx-mode',
        'why': 'the undo of a join splits in the current wrap mode: in WRAP_TXT '
               'EFFCURX moves a seam on the margin of a full line one column on',
        'file': 'UNDO.Z8A',
        'old': """UNDONWX         LD      A, WRAP_DEV""",
        'new': """UNDONWX         LD      A, (WRAPMODE)   ; MUTATION: NOT EXACT""",
        'filter': 'U13',
        'expect': ['U13/content'],
    },
    {
        'name': 'undo-sel',
        'why': 'ACTUNDO fails to cancel active selection leaving inverted characters in VRAM',
        'file': 'UNDO.Z8A',
        'old': """ACTUNDO         CALL    UNDOCLS
                LD      A, (SELACT)
                OR      A
                CALL    NZ, ACTDSEL""",
        'new': """ACTUNDO         CALL    UNDOCLS
                NOP
                NOP
                NOP
                NOP
                NOP
                NOP
                NOP""",
        'filter': 'U5',
        'expect': ['U5/sel-cancelled'],
    },
    {
        'name': 'undo-seldel-rec',
        'why': 'ACTDLS records nothing again: a deleted selection cannot be '
               'undone, and older history replays on the wrong line',
        'file': 'ACTION.Z8A',
        'old': """.DLSNEMP        ; RECORD EVERY LINE THE DELETE TOUCHES, AS ONE UNDO GROUP
                LD      A, UNDOT_DEL
                CALL    UNDOSEL""",
        'new': """.DLSNEMP        ; MUTATION: NOTHING RECORDED
                LD      A, UNDOT_DEL""",
        'filter': 'U6',
        'expect': ['U6/multi/recorded', 'U6/stale/content'],
    },
    {
        'name': 'undo-group-loop',
        'why': 'ACTUNDO stops after one record, ignoring the chain: a '
               'three-line delete comes back one line at a time',
        'file': 'UNDO.Z8A',
        'old': """                LD      A, B
                AND     UNDOF_CHN
                JR      Z, .FINISH      ; THE GROUP'S FIRST RECORD: DONE""",
        'new': """                JR      .FINISH         ; MUTATION: ONE RECORD PER CTRL+Z""",
        'filter': 'U6',
        'expect': ['U6/multi/undo'],
    },
    {
        'name': 'undo-redo-loop',
        'why': 'ACTREDO re-applies only the first record of a group',
        'file': 'UNDO.Z8A',
        'old': """                AND     UNDOF_CHN
                JR      Z, .RDDONE      ; NEXT RECORD STARTS ANOTHER ACTION""",
        'new': """                JR      .RDDONE         ; MUTATION: NEVER FOLLOW THE CHAIN""",
        'filter': 'U6',
        'expect': ['U6/multi/redo'],
    },
    {
        'name': 'undo-evict-group',
        'why': 'eviction takes only the colliding record, leaving the rest of '
               'its group to be replayed without its first record',
        'file': 'UNDO.Z8A',
        'old': """                LD      IX, (UNDOBOT)
                LD      A, (IX + 4)
                AND     UNDOF_CHN
                JR      NZ, .EVICT
                JR      .EVCLP          ; CHECK IF NEXT RECORD ALSO COLLIDES""",
        'new': """                JR      .EVCLP          ; MUTATION: GROUPS EVICTED PIECEMEAL""",
        'filter': 'U7',
        'expect': ['U7/evict/content'],
    },
    {
        'name': 'undo-redo-trunc',
        'why': 'a new edit leaves the head linked to the stale redo records: '
               'evicting the head makes the new record its own predecessor',
        'file': 'UNDO.Z8A',
        'old': """                OR      L
                JR      Z, .NOREDO""",
        'new': """                OR      L
                JR      .NOREDO         ; MUTATION: REDO CHAIN LEFT LINKED""",
        'filter': 'U7',
        'expect': ['U7/selfloop/content'],
    },
    {
        'name': 'undo-group-cap',
        'why': 'a group too big for the ring drops the history but keeps '
               'recording the rest of it: a headless tail to replay',
        'file': 'UNDO.Z8A',
        'old': """                LD      A, 1
                LD      (UNDODRP), A
                JP      UNDOINIT        ; TOO BIG TO KEEP: FORGET THE HISTORY""",
        'new': """                NOP                     ; MUTATION: THE TAIL IS RECORDED
                NOP
                NOP
                NOP
                NOP
                JP      UNDOINIT        ; TOO BIG TO KEEP: FORGET THE HISTORY""",
        'filter': 'U12',
        'expect': ['U12/mixgrp/dropped', 'U12/mixgrp/content'],
    },
    {
        'name': 'undo-wrap-gap',
        'why': 'a record that does not fit under the top of the ring wraps '
               'without evicting the older records left in the gap: with '
               'three record sizes one can live there, stays UNDOBOT, and the '
               'chain runs through the records written over at the bottom',
        'file': 'UNDO.Z8A',
        'old': """                CALL    UNDOEVC
                POP     DE
                LD      (UNDORSZ), DE""",
        'new': """                NOP                     ; MUTATION: THE GAP IS NOT EVICTED
                NOP
                NOP
                POP     DE
                LD      (UNDORSZ), DE""",
        'filter': 'U14',
        # the overwritten records are not evicted, so the record after them
        # keeps a PREV_TRN into the middle of the big one: the last Ctrl+Z
        # walks into it and stops on a dead address instead of reaching 0
        'expect': ['U14/undone'],
    },
    {
        'name': 'undo-evict-window',
        'why': 'the shipped collision test: its second subtraction ran with '
               'the write base in both registers, so every record above the '
               'write point was evicted -- the whole history on each wrap',
        'file': 'UNDO.Z8A',
        'old': """                SBC     HL, DE          ; HL = UNDOBOT - WRITE BASE
                JR      C, .EVCBEL      ; BELOW THE WINDOW
                LD      DE, (UNDORSZ)
                SBC     HL, DE          ; CY = 1 INSIDE THE WINDOW (CY WAS 0)
                POP     HL              ; HL = WRITE BASE
                JR      NC, .EVCDON     ; PAST THE WINDOW -> DONE""",
        'new': """                SBC     HL, DE          ; HL = UNDOBOT - WRITE BASE
                POP     HL
                JR      C, .EVCDON
                PUSH    HL              ; MUTATION: THE 2026-09-19 TEST
                EX      DE, HL
                OR      A
                SBC     HL, DE
                LD      DE, (UNDORSZ)
                OR      A
                SBC     HL, DE
                POP     HL
                JR      NC, .EVCDON""",
        'filter': 'U7',
        'expect': ['U7/depth/content', 'U7/evict/content'],
    },
    {
        'name': 'undo-reflow-drop',
        'why': 'Rewrap moves text across lines and keeps the history, whose '
               'records then name lines the rewrap shifted',
        'file': 'EDIT.Z8A',
        'old': """                RET     NZ              ; THE KEY JOIN RECORDS ITS OWN TWO LINES
                JP      UNDOINIT""",
        'new': """                RET     NZ              ; THE KEY JOIN RECORDS ITS OWN TWO LINES
                RET                     ; MUTATION: HISTORY KEPT""",
        'filter': 'W4',
        'expect': ['W4/hist/content'],
    },
    {
        'name': 'undo-pushwrap-drop',
        'why': 'push-wrap inserts a line and keeps the history, whose records '
               'then name lines one off',
        'file': 'EDIT.Z8A',
        'old': """                ; (UNDOINIT KEEPS BC AND DE)
                CALL    UNDOINIT""",
        'new': """                ; MUTATION: HISTORY KEPT""",
        'filter': 'U8',
        'expect': ['U8/pushwrap/content'],
    },
    {
        'name': 'undo-insrun-rec',
        'why': 'a pasted run is written with no record, so Ctrl+Z skips it',
        'file': 'EDIT.Z8A',
        'old': """.IRFITS         ; ONE LINE CHANGES: RECORD IT AS IT STANDS IN WORKBUF
                CALL    UNDOCLS
                LD      A, UNDOT_MOD
                CALL    UNDOREC""",
        'new': """.IRFITS         ; MUTATION: NOT RECORDED""",
        'filter': 'U9',
        'expect': ['U9/paste/content'],
    },
    {
        'name': 'undo-dwlft-rec',
        'why': 'word delete is written with no record',
        'file': 'ACTION.Z8A',
        'old': """                ; CTRL+Z PUTS THE CURSOR BACK AFTER THE WORD
                CALL    UNDOCLS
                LD      A, UNDOT_MOD
                CALL    UNDOREC""",
        'new': """                ; MUTATION: NOT RECORDED""",
        'filter': 'U9',
        'expect': ['U9/wordel/content'],
    },
    {
        'name': 'undo-wrapsel-rec',
        'why': 'wrapping a selection in markup delimiters is not recorded',
        'file': 'MARKUP.Z8A',
        'old': """                CALL    UNDOCLS
                LD      HL, (SELSTRL)
                LD      A, UNDOT_MOD
                CALL    UNDOLNR""",
        'new': """                ; MUTATION: NOT RECORDED""",
        'filter': 'U9',
        'expect': ['U9/wrapsel/content'],
    },
    {
        'name': 'undo-dls-showln',
        'why': 'deleting a selection that starts above the viewport leaves '
               'TOPLINE alone, so CURY goes negative',
        'file': 'ACTION.Z8A',
        'old': """                LD      HL, (SELSTRL)
                LD      (DOCLINE), HL
                CALL    SHOWLN
                CALL    REDRAW""",
        'new': """                LD      HL, (SELSTRL)
                LD      (DOCLINE), HL
                CALL    SETCURY         ; MUTATION: NOT BROUGHT ON SCREEN
                CALL    REDRAW""",
        'filter': 'U6',
        'expect': ['U6/scrolled/visible'],
    },
    {
        'name': 'undo-pnt-showln',
        'why': 'the repaint after an undo trusts the recorded TOPLINE, which '
               'need not show a cursor restored above it (catchable on S2ED where '
               'UNDOGMAX 28 > ROWSVIS 22)',
        'target': 'S2ED',
        'file': 'UNDO.Z8A',
        'old': """.MODSET         LD      (MODIFIED), A
                LD      HL, (DOCLINE)
                CALL    SHOWLN""",
        'new': """.MODSET         LD      (MODIFIED), A
                CALL    SETCURY         ; MUTATION: TOPLINE TRUSTED""",
        'filter': 'S2-20',
        'expect': ['S2-20/big/cycle'],
    },
    {
        'name': 's2-undo-seldel',
        'why': 'the reported S2ED flow: select the TEST lines, DEL, Ctrl+Z '
               'restores nothing',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """.DLSNEMP        ; RECORD EVERY LINE THE DELETE TOUCHES, AS ONE UNDO GROUP
                LD      A, UNDOT_DEL
                CALL    UNDOSEL""",
        'new': """.DLSNEMP        ; MUTATION: NOTHING RECORDED
                LD      A, UNDOT_DEL""",
        'filter': 'S2-20',
        'expect': ['S2-20/fresh/cycle'],
    },
    {
        'name': 's2-undo-gmax',
        'why': 'the group budget set too low: S2ED would drop the history on '
               'any delete over 15 lines instead of 29',
        'target': 'S2ED',
        'file': 'UNDO.Z8A',
        'old': """                LD      BC, -(UNDOSIZ + 2)""",
        'new': """                LD      BC, -(UNDOSIZ / 2 + 2) ; MUTATION: BUDGET TOO LOW""",
        'filter': 'S2-20',
        'expect': ['S2-20/big/cycle'],
    },
    {
        'name': 'find-matcur',
        'why': 'SRCHFWD reaches .MATCH with the HL SCANLNF left pointing into '
               'WORKBUF, so a match on the current line stores WORKBUF+1+C '
               'into DOCLINE -- the reported "Ln 20960, cursor on the status '
               'bar" defect',
        'file': 'SEARCH.Z8A',
        'old': """.MATCUR         LD      HL, (DOCLINE)   ; SCANLNF LEAVES HL IN WORKBUF: RELOAD LINE""",
        'new': """.MATCUR                                 ; MUTATION: HL LEFT IN WORKBUF""",
        'filter': 'H26',
        'expect': ['H26/found1', 'H26/found2', 'H26/found3', 'H26/highlight'],
    },
    {
        'name': 'find-bmatcur',
        'why': 'SRCHBWD reaches .BMATCH with the HL SCANLNB left pointing '
               'into WORKBUF, so a backward match on the current line stores '
               'WORKBUF+1+C into DOCLINE',
        'file': 'SEARCH.Z8A',
        'old': """.BMATCUR        LD      HL, (DOCLINE)   ; SCANLNB LEAVES HL IN WORKBUF: RELOAD LINE""",
        'new': """.BMATCUR                                ; MUTATION: HL LEFT IN WORKBUF""",
        'filter': 'H26',
        'expect': ['H26/found4', 'H26/found5'],
    },
    {
        'name': 's2-find-matcur',
        'why': 'the same current-line forward defect seen on the 64-column '
               'target ("Ln 20575" on the status bar)',
        'target': 'S2ED',
        'file': 'SEARCH.Z8A',
        'old': """.MATCUR         LD      HL, (DOCLINE)   ; SCANLNF LEAVES HL IN WORKBUF: RELOAD LINE""",
        'new': """.MATCUR                                 ; MUTATION: HL LEFT IN WORKBUF""",
        'filter': 'S2-22',
        'expect': ['S2-22/found1', 'S2-22/found2', 'S2-22/found3',
                   'S2-22/highlight'],
    },
    {
        'name': 's2-find-bmatcur',
        'why': 'the same current-line backward defect seen on the 64-column '
               'target',
        'target': 'S2ED',
        'file': 'SEARCH.Z8A',
        'old': """.BMATCUR        LD      HL, (DOCLINE)   ; SCANLNB LEAVES HL IN WORKBUF: RELOAD LINE""",
        'new': """.BMATCUR                                ; MUTATION: HL LEFT IN WORKBUF""",
        'filter': 'S2-22',
        'expect': ['S2-22/found4', 'S2-22/found5'],
    },
    {
        'name': 'find-redraw',
        'why': 'ACTFNXT repaints after SRCHFWD already painted the match, '
               'and REDRAW clears SELDRAWN: the found word flashes selected '
               'and immediately un-highlights',
        'file': 'ACTION.Z8A',
        'old': """                CALL    SRCHFWD
                JR      C, .NOTFND
                RET                     ; SRCHFWD REPAINTS AND KEEPS THE MATCH SELECTED""",
        'new': """                CALL    SRCHFWD
                JR      C, .NOTFND
                CALL    REDRAW          ; MUTATION: REPAINTS OVER THE SELECTION
                JP      DRWSTAT""",
        'filter': 'H26',
        'expect': ['H26/highlight'],
    },
    {
        'name': 's2-find-redraw',
        'why': 'the same redundant repaint erasing the match highlight on '
               'the 64-column target',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """                CALL    SRCHFWD
                JR      C, .NOTFND
                RET                     ; SRCHFWD REPAINTS AND KEEPS THE MATCH SELECTED""",
        'new': """                CALL    SRCHFWD
                JR      C, .NOTFND
                CALL    REDRAW          ; MUTATION: REPAINTS OVER THE SELECTION
                JP      DRWSTAT""",
        'filter': 'S2-22',
        'expect': ['S2-22/highlight'],
    },
    # --- H28 PARAMETRIC TEXTWIDTH (PHASE C2) --------------------------
    {
        'name': 'h28-fixedmargin',
        'why': 'EDINSCHR measures the wrap margin against TEXTCOLS again, '
               'so TEXTWIDTH=40 still wraps at 80 and typing past column 40 '
               'never splits the line',
        'file': 'EDIT.Z8A',
        'old': """.WRTXT          ; WRAP_TXT:
                LD      A, (TXTWIDTH)
                OR      A
                JR      Z, .INSDEV      ; TXTWIDTH == 0: FREE TYPING UP TO MAXCOLS

                LD      D, A            ; D = TXTWIDTH""",
        'new': """.WRTXT          ; WRAP_TXT:
                LD      D, TEXTCOLS     ; MUTATION: FIXED 80-COLUMN MARGIN""",
        'filter': 'H28',
        'expect': ['H28/cfg40/totlines', 'H28/cfg40/content'],
    },
    {
        'name': 'h28-cfgwrap',
        'why': 'PARSTW stores the margin but forgets to switch WRAPMODE, so '
               'TEXTWIDTH= is parsed and then ignored by every edit path',
        'file': 'CFG.Z8A',
        'old': """.WOK            LD      A, L
                LD      (TXTWIDTH), A
                OR      A
                JR      Z, .TWZERO
                LD      (SAVETW), A
                LD      A, WRAP_TXT
                LD      (WRAPMODE), A
                RET""",
        'new': """.WOK            LD      A, L
                LD      (TXTWIDTH), A
                OR      A
                JR      Z, .TWZERO
                LD      (SAVETW), A     ; MUTATION: WRAPMODE LEFT IN DEV
                RET""",
        'filter': 'H28',
        'expect': ['H28/cfg40/boot-wrap', 'H28/cfg40/content'],
    },
    {
        'name': 'h28-exsavetw',
        'why': ':set tw=48 updates TXTWIDTH but not SAVETW.  Only setw48 '
               'catches it: :set nowrap re-saves TXTWIDTH into SAVETW on the '
               'unmutated path, so from there on SAVETW is right again',
        'file': 'ACTION.Z8A',
        'old': """.TW8OK          LD      A, L
                LD      (TXTWIDTH), A
                OR      A
                JR      Z, .TWEXZ
                LD      (SAVETW), A
                LD      A, WRAP_TXT
                LD      (WRAPMODE), A
                JR      .SETOUT""",
        'new': """.TW8OK          LD      A, L
                LD      (TXTWIDTH), A   ; MUTATION: SAVETW NOT UPDATED
                OR      A
                JR      Z, .TWEXZ
                LD      A, WRAP_TXT
                LD      (WRAPMODE), A
                JR      .SETOUT""",
        'filter': 'H28',
        'expect': ['H28/ex/setw48'],
    },
    {
        'name': 'h28-pwreserve',
        'why': 'EDPSHWR reserves the pushed tail a margin-sized record again. '
               'A loaded line longer than the margin sends LEN + 1 - SPLIT '
               'characters down and PUTREC does not check capacity, so the '
               'attributes overwrite the text past the record\'s capacity',
        'file': 'EDIT.Z8A',
        'old': """                LD      A, (WORKBUF)
                CP      MAXCOLS
                JR      NC, .PWRCAP     ; LEN + 1 WOULD WRAP TO 0
                INC     A
.PWRCAP         CP      C
                JR      C, .PWRES       ; LEN + 1 < MARGIN: MARGIN WINS
                LD      C, A
.PWRES          CALL    NEWREC""",
        'new': """                CALL    NEWREC          ; MUTATION: MARGIN-SIZED RESERVE""",
        'filter': 'H28',
        'expect': ['H28/longtail/content'],
    },
    {
        'name': 'f4-ovr-bypass',
        'why': 'ACTSAVAS skips checking if destination file exists and overwrites without confirmation',
        'file': 'ACTION.Z8A',
        'old': """                LD      C, _FFIRST
                CALL    BDOS
                JR      C, .SAVEIT      ; DOES NOT EXIST: SAVE DIRECTLY""",
        'new': """                LD      C, _FFIRST
                CALL    BDOS
                JR      .SAVEIT         ; MUTATION: ALWAYS SAVE DIRECTLY""",
        'filter': 'H36',
        'expect_any': ['H36/overwrite-no/asked', 'H36-browse-saveas'],
    },
    {
        'name': 'f4-ovr-no-reopen',
        'why': 'ACTSAVAS cancels instead of reopening browser when user answers No to overwrite prompt',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, (WINRES)
                OR      A
                JR      Z, .REOPEN      ; NO: REOPEN BROWSER""",
        'new': """                LD      A, (WINRES)
                OR      A
                JR      Z, .CANCEL      ; MUTATION: CANCEL INSTEAD OF REOPEN""",
        'filter': 'H36',
        'expect_any': ['H36/overwrite-no/reopened', 'H36-browse-saveas'],
    },
    {
        'name': 'f4-menu-saveas',
        'why': 'File > Save As dispatches normal Save instead of ACTSAVAS',
        'file': 'ACTION.Z8A',
        'old': """                CP      3
                JP      Z, ACTSAVAS""",
        'new': """                CP      3
                JP      Z, .FSAVE       ; MUTATION: DISPATCH NORMAL SAVE""",
        'filter': 'H36',
        'expect_any': ['H36/menu/open', 'H36-browse-saveas'],
    },
    {
        'name': 's2-f4-ovr-bypass',
        'why': 'ACTSAVAS skips checking if destination file exists on S2ED',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """                LD      C, _FFIRST
                CALL    BDOS
                JR      C, .SAVEIT      ; DOES NOT EXIST: SAVE DIRECTLY""",
        'new': """                LD      C, _FFIRST
                CALL    BDOS
                JR      .SAVEIT         ; MUTATION: ALWAYS SAVE DIRECTLY""",
        'filter': 'S2-30',
        'expect_any': ['S2-30/overwrite-no/asked', 'S2-30-browse-saveas'],
    },
    {
        'name': 's2-f4-ovr-no-reopen',
        'why': 'ACTSAVAS cancels instead of reopening browser on No on S2ED',
        'target': 'S2ED',
        'file': 'ACTION.Z8A',
        'old': """                LD      A, (WINRES)
                OR      A
                JR      Z, .REOPEN      ; NO: REOPEN BROWSER""",
        'new': """                LD      A, (WINRES)
                OR      A
                JR      Z, .CANCEL      ; MUTATION: CANCEL INSTEAD OF REOPEN""",
        'filter': 'S2-30',
        'expect_any': ['S2-30/overwrite-no/reopened', 'S2-30-browse-saveas'],
    },
    {
        'name': 'f4-new-initp',
        'why': 'the browser trusts FILENAME + 1 / + 2 on an empty name: after '
               'Open + New, Save As LDIRs the directory with BC = 0 and hangs',
        'file': 'BROWSER.Z8A',
        'old': "                JR      Z, .CWD         ; NO DOCUMENT NAME",
        'new': "                JR      NZ, $ + 2       ; MUTATION: NO GUARD",
        'filter': 'H36',
        # the hang never returns to MAINLOOP, so it may also kill the session
        'expect_any': ['H36/after-open/saved', 'H36-browse-saveas'],
    },
    {
        'name': 's2-f4-new-initp',
        'target': 'S2ED',
        'why': 'the browser trusts FILENAME + 1 / + 2 on an empty name: after '
               'Open + New, Save As LDIRs the directory with BC = 0 and hangs',
        'file': 'BROWSER.Z8A',
        'old': "                JR      Z, .CWD         ; NO DOCUMENT NAME",
        'new': "                JR      NZ, $ + 2       ; MUTATION: NO GUARD",
        'filter': 'S2-30',
        # the hang never returns to MAINLOOP, so it may also kill the session
        'expect_any': ['S2-30/after-open/saved', 'S2-30-browse-saveas'],
    },
    {
        'name': 's61-f4-new-initp',
        'target': 'S61ED',
        'why': 'the browser trusts FILENAME + 1 / + 2 on an empty name: after '
               'Open + New, Save As LDIRs the directory with BC = 0 and hangs',
        'file': 'S61/BROWSER.Z8A',
        'old': "                JR      Z, .CWD         ; NO DOCUMENT NAME",
        'new': "                JR      NZ, $ + 2       ; MUTATION: NO GUARD",
        'filter': 'S62-11',
        # the hang never returns to MAINLOOP, so it may also kill the session
        'expect_any': ['S62-11/after-open/saved', 'S62-11-saveas-after-open'],
    },
    {
        'name': 't0-theme-green-2c',
        'why': 'GREEN chrome back to medium on dark green, 1.3:1: no menu, '
               'status bar or dialog can be read',
        'file': 'S2/VDP.Z8A',
        'old': "THMGRN          DEFB    #21, #1C,",
        'new': "THMGRN          DEFB    #21, #2C,",
        'filter': 'T0',
        'expect_static': ['s2-theme-contrast'],
    },
    {
        'name': 't0-theme-amber-a6',
        'why': 'AMBER window body painted dark yellow on medium green, '
               '1.0:1: the ink vanishes into the surface',
        'file': 'S2/VDP.Z8A',
        'old': """                DEFB    #A6, #B6, #6B, #66""",
        'new': """                DEFB    #A2, #B6, #6B, #66""",
        'filter': 'T0',
        'expect_static': ['s2-theme-contrast'],
    },
    {
        'name': 's2-menu-titlebar',
        'target': 'S2ED',
        'why': 'a dropdown gets the accent title bar back on its top row, '
               'over the first item',
        'file': 'WINDOW.Z8A',
        'old': """                LD      A, (VCOLHI)     ; TOP ROW: TITLE BAR...
                JR      NZ, .CFILS""",
        'new': """                LD      A, (VCOLHI)     ; TOP ROW: TITLE BAR...
                JR      .CFILS          ; MUTATION: EVEN WITH NO TITLE""",
        'filter': 'S2-16',
        'expect': ['S2-16/open/colour'],
    },
    {
        'name': 's2-menu-topedge',
        'target': 'S2ED',
        'why': 'the top edge goes, and the dropdown no longer closes under '
               'the menu bar',
        'file': 'WINDOW.Z8A',
        'old': """                LD      DE, 8
                LD      A, #FF
.TEDG           LD      (HL), A""",
        'new': """                LD      DE, 8
                XOR     A               ; MUTATION: NO TOP EDGE
.TEDG           LD      (HL), A""",
        'filter': 'S2-16',
        'expect': ['S2-16/no-title-bar'],
    },
    {
        'name': 'btn-focus-timp',
        'why': 'the focused button text goes back to TIMP COL_FG: white '
               'on blue in DARK instead of TOR COL_HI',
        'file': 'WINDOW.Z8A',
        'old': """                JP      WINSTR3         ; COL_HI INK ON THE CLR_UI BODY (TOR)""",
        'new': """                JP      WINSTR          ; MUTATION: TIMP, COL_FG INK""",
        'filter': 'H19',
        'expect': ['H19/focus-text'],
    },
    {
        'name': 'cur-cua-ovr-under',
        'why': 'STD overwrite draws the underline, the insert shape: the two '
               'modes look the same',
        'file': 'INPUT.Z8A',
        'old': """                JR      Z, .LATCH       ; A = 0 = CURBLK
                LD      A, CURUND""",
        'new': """                LD      A, CURUND       ; MUTATION: BOTH MODES UNDERLINE
                LD      A, CURUND""",
        'filter': 'H43',
        'expect': ['H43/std/ovr'],
    },
    {
        'name': 'cur-vi-ins-block',
        'why': 'VI insert keeps the normal-mode block instead of the bar',
        'file': 'INPUT.Z8A',
        'old': """                LD      A, CURBAR
                JR      NZ, .LATCH""",
        'new': """                LD      A, CURBLK       ; MUTATION: NO BAR
                JR      NZ, .LATCH""",
        'filter': 'H43',
        'expect': ['H43/vi/insert'],
    },
    {
        'name': 's2-cur-bar-mask',
        'target': 'S2ED',
        'why': 'CURINV draws the bar as the whole previous column',
        'file': 'RENDER.Z8A',
        'old': """                LD      E, #11          ; RIGHT PIXEL OF EITHER HALF...""",
        'new': """                LD      E, #FF          ; MUTATION: BAR AS A BLOCK""",
        'filter': 'S2-50',
        'expect': ['S2-50/vi/insert'],
    },
    {
        'name': 's2-cur-under-top',
        'target': 'S2ED',
        'why': 'CURINV draws the underline on the top scanlines',
        'file': 'RENDER.Z8A',
        'old': """                LD      D, 8 - CURUNDH""",
        'new': """                LD      D, 0            ; MUTATION: UNDERLINE AT THE TOP""",
        'filter': 'S2-50',
        'expect': ['S2-50/std/ins', 'S2-50/vi/replace'],
    },
    {
        'name': 's61-cur-under-dy',
        'target': 'S61ED',
        'why': 'the underline is not moved down: a bar along the top',
        'file': 'S61/UI.Z8A',
        'old': """                LD      DE, CELLH - CURUNDH""",
        'new': """                LD      DE, 0           ; MUTATION: NOT MOVED DOWN""",
        'filter': 'S62-12',
        'expect': ['S62-12/std/ins', 'S62-12/vi/replace'],
    },
    {
        'name': 'selall-setcury',
        'why': 'Ctrl+A places the cursor with SETCURY again: on a document '
               'longer than the screen CURY lands past the text band',
        'file': 'ACTION.Z8A',
        'old': """                LD      HL, (DOCLINE)
                CALL    SHOWLN
                CALL    REDRWSL""",
        'new': """                CALL    SETCURY         ; MUTATION: NO VIEWPORT MOVE
                NOP
                NOP
                CALL    REDRWSL""",
        'filter': 'H45',
        'expect': ['H45/selall'],
    },
    {
        'name': 's2-redrsel-off',
        'target': 'S2ED',
        'why': 'REDRAW records the selection as painted without painting it: '
               'a page move leaves the new page plain',
        'file': 'ACTION.Z8A',
        'old': """REDRSEL         LD      A, (SELREDR)
                OR      A
                RET     Z""",
        'new': """REDRSEL         LD      A, (SELREDR)
                OR      A
                RET                     ; MUTATION: NEVER PAINTS""",
        'filter': 'S2-52',
        'expect': ['S2-52/selall', 'S2-52/spgu'],
    },
    {
        'name': 's2-sel-scroll-shrink',
        'target': 'S2ED',
        'why': 'shrinking a selection up across the top edge leaves the row '
               'the scroll exposed plain inside the painted range: SELDIFF '
               'then works from a screen that is not what DRWSTRL says',
        'file': 'ACTION.Z8A',
        'old': """                CALL    ACTMVU
                POP     DE              ; DE = TOPLINE BEFORE THE MOVE
                CALL    SELSCRL         ; THE SCROLL KEPT THE OVERLAY: FIX THE""",
        'new': """                CALL    ACTMVU
                POP     DE              ; DE = TOPLINE BEFORE THE MOVE
                NOP                     ; MUTATION: NO SELSCRL
                NOP
                NOP""",
        'filter': 'S2-52',
        'expect': ['S2-52/shrink'],
    },
    {
        'name': 'brw-drive-nolast',
        'why': 'the browser forgets the path left on the other drive: going '
               'A -> B -> A lands in the DOS current directory, not where '
               'you were',
        'file': 'BDOS.Z8A',
        'old': """                LD      A, (BRWLST)
                CP      B
                JR      NZ, .DOSCD""",
        'new': """                LD      A, (BRWLST)
                CP      B
                JR      .DOSCD          ; MUTATION: NEVER REMEMBERED""",
        'filter': 'H46',
        'expect': ['H46/backa', 'H46/backb'],
    },
    {
        'name': 'brw-drive-noroot',
        'why': 'a drive whose directory cannot be listed is never tried at '
               'its root: the browser stays on the old drive instead',
        'file': 'BDOS.Z8A',
        'old': """                CALL    BRWDIRX
                JR      NC, .DONE

                ; 4. NOTHING READABLE: THE OLD PATH BACK""",
        'new': """                SCF                     ; MUTATION: THE ROOT NEVER READS
                JR      NC, .DONE

                ; 4. NOTHING READABLE: THE OLD PATH BACK""",
        'filter': 'H46',
        'expect': ['H46/swapped'],
    },
    {
        'name': 'brw-drive-curdir-path',
        'why': 'CURDIR writes straight into BRWPATH again: its 68 bytes run '
               'into BRWMASK and a drive change lists directories only',
        'file': 'BDOS.Z8A',
        'old': """                LD      A, C
                LD      DE, BRWNAME
                CALL    CURDIR""",
        'new': """                LD      A, C
                LD      DE, BRWPATH     ; MUTATION: INTO THE 64-BYTE PATH
                CALL    CURDIR""",
        'filter': 'H46',
        'expect': ['H46/mask', 'H46/files'],
    },
    {
        'name': 'brw-no-drive-room',
        'why': 'the directory walk fills the whole listing again and the '
               'drives, filed last, find no slot: no way to another drive',
        'file': 'BROWSE.Z8A',
        'old': """.DRVLIM         LD      A, B
                LD      (BRWLIM), A""",
        'new': """.DRVLIM         LD      A, BRWMAX       ; MUTATION: NO ROOM KEPT
                LD      (BRWLIM), A""",
        'filter': 'H35',
        'expect': ['H35/drives'],
    },
    {
        'name': 'brw-info-never',
        'why': 'a keystroke never repaints the information line: it keeps '
               'describing the file selected before',
        'file': 'BROWSER.Z8A',
        'old': """                CALL    BRWIDIF
                RET     Z               ; THE LINE ON SCREEN IS STILL RIGHT""",
        'new': """                CALL    BRWIDIF
                RET                     ; MUTATION: NEVER PAINTED""",
        'filter': 'H35',
        'expect': ['H35/info'],
    },
    {
        'name': 's2-brw-info-never',
        'target': 'S2ED',
        'why': 'a keystroke never repaints the S2ED information line',
        'file': 'RENDER.Z8A',
        'old': """BRWIS2          CALL    BRWIDIF
                RET     Z               ; THE ROW ON SCREEN IS STILL RIGHT""",
        'new': """BRWIS2          CALL    BRWIDIF
                RET                     ; MUTATION: NEVER PAINTED""",
        'filter': 'S2-29',
        'expect': ['S2-29/info'],
    },
    {
        'name': 's2-brw-gsh-dir',
        'target': 'S2ED',
        'why': 'the browser grid is shifted the wrong way on a one-row scroll',
        'file': 'RENDER.Z8A',
        'old': """.UP             CALL    GRDSCRL         ; A = 0""",
        'new': """.UP             INC     A               ; MUTATION: THE OTHER WAY
                CALL    GRDSCRL""",
        'filter': 'S2-29',
        'expect': ['S2-29/grid'],
    },
    {
        'name': 'fkey-f3-next',
        'why': 'F3 does not find the next match in STD',
        'file': 'KEYMAP.Z8A',
        'old': "                DEFB    F3KEY,   MODANY,  ACFNXT",
        'new': "                DEFB    F3KEY,   MODANY,  0      ; MUTATION: UNBOUND",
        'filter': 'X4',
        # nothing opens on F3, so the WINPOLL-gated snapshot never fires and
        # the session dies: caught under the case name
        'expect_any': ['X4/std/f3-dialog', 'X4/std/f3', 'X4-function-keys'],
    },
    {
        'name': 'fkey-f8-prev',
        'why': 'Shift+F3 does not find the previous match in STD',
        'file': 'KEYMAP.Z8A',
        'old': "                DEFB    F8KEY,   MODANY,  ACFPRV",
        'new': "                DEFB    F8KEY,   MODANY,  0      ; MUTATION: UNBOUND",
        'filter': 'X4',
        'expect': ['X4/std/f8'],
    },
    {
        'name': 'shift-bs',
        'why': 'Shift+BS does nothing in STD, as before v0.7',
        'file': 'KEYMAP.Z8A',
        'old': "                DEFB    BS,      MODSHFT, ACDELBK\n",
        'new': "",
        'filter': 'X4',
        'expect': ['X4/shbs/deleted'],
    },
    {
        'name': 'menu-f2-switch',
        'why': 'a function key other than F1 switches menus again',
        'file': 'MENU.Z8A',
        'old': "                CP      F1KEY           ; ONLY F1 BELONGS TO THE MENUS:",
        'new': "                CP      F2KEY           ; MUTATION: F2 SWITCHES",
        'filter': 'H23',
        'expect': ['H23/direct-fkeys'],
    },
    {
        'name': 'brw-unfocus-col',
        'why': 'the selected entry keeps the accent bar with the focus on '
               'the Name field, so the arrow keys look as if they would move it',
        'file': 'BROWSER.Z8A',
        'old': "                LD      B, COL_FG       ; SELECTED, FOCUS ELSEWHERE: WHITE",
        'new': "                LD      B, COL_HI       ; MUTATION: ACCENT REGARDLESS",
        'filter': 'H34',
        'expect': ['H34/field/unfocused'],
    },
    {
        'name': 'brw-setfoc-slot',
        'why': 'a focus change does not repaint the selected entry, so it '
               'keeps the colour of the previous focus',
        'file': 'BROWSER.Z8A',
        'old': "                LD      A, (BRWSEL)     ; THE SELECTION WEARS THE FOCUS TOO\n                CALL    .SLOT\n",
        'new': "",
        'filter': 'H34',
        'expect': ['H34/field/unfocused'],
    },
    {
        'name': 's2-brw-unfocus-col',
        'why': 'S2ED: the selected entry keeps VCOLBSEL with the focus on '
               'the Name field',
        'target': 'S2ED',
        'file': 'BROWSER.Z8A',
        'old': "                LD      A, (VCOLWIN)    ; FOCUS ELSEWHERE: THE WINDOW BODY",
        'new': "                LD      A, (VCOLBSEL)   ; MUTATION: FOCUSED COLOUR",
        'filter': 'S2-28',
        'expect': ['S2-28/field/unfocused'],
    },
    {
        'name': 'fld-left',
        'why': 'LEFT does not move the caret in a text field, so typing '
               'still only appends',
        'file': 'INPUT.Z8A',
        'old': """.LEFT           LD      A, (INPCAR)
                OR      A
                SCF
                RET     Z
                DEC     A""",
        'new': """.LEFT           LD      A, (INPCAR)
                OR      A
                SCF
                RET     Z
                NOP                     ; MUTATION: THE CARET STAYS""",
        'filter': 'H34',
        'expect': ['H34/field/edit'],
    },
    {
        'name': 'fld-del',
        'why': 'DEL does not delete under the caret in a text field',
        'file': 'INPUT.Z8A',
        'old': ".DEL            LD      A, (INPCAR)\n",
        'new': ".DEL            SCF                     ; MUTATION: DEL IGNORED\n                RET\n                LD      A, (INPCAR)\n",
        'filter': 'H34',
        'expect': ['H34/field/edit'],
    },
    {
        'name': 'filechr-upcase',
        'why': 'the Name field turns what is typed into upper case while '
               'it shows names as they came',
        'file': 'INPUT.Z8A',
        'old': """.YES            POP     AF
                OR      A               ; CY = 0""",
        'new': """.YES            POP     AF
                CALL    SRCHUPC         ; MUTATION: UPPER CASE
                OR      A               ; CY = 0""",
        'filter': 'H34',
        'expect': ['H34/field/edit', 'H34/typed/opened'],
    },
]


class Applied(object):
    """Applies one mutation and always puts the sources back."""

    def __init__(self, ctx, mut):
        self.ctx = ctx
        self.mut = mut
        self.backups = {}

    def __enter__(self):
        edits = [(self.mut['file'], self.mut['old'], self.mut['new'])]
        edits += self.mut.get('also', [])
        for fname, old, new in edits:
            path = self.ctx.find_src_file(fname)
            if path not in self.backups:
                self.backups[path] = path + '.mutbak'
                shutil.copy(path, self.backups[path])
            # newline='': keep CR LF as it is, so a mutation can target line
            # endings (AUTOEXEC.BAT) and never rewrites the rest of a file.
            with open(path, newline='') as fh:
                text = fh.read()
            if old not in text:
                self.__exit__(None, None, None)
                raise RuntimeError('mutation %s: anchor not found in %s'
                                   % (self.mut['name'], fname))
            with open(path, 'w', newline='') as fh:
                fh.write(text.replace(old, new, 1))
        return self

    def __exit__(self, *exc):
        for path, bak in self.backups.items():
            if os.path.exists(bak):
                shutil.move(bak, path)
        return False
