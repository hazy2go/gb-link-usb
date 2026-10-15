linktest.gb: linktest.asm
	rgbasm -o linktest.o linktest.asm
	rgblink -o linktest.gb linktest.o
	rgbfix -v -p 0xFF -t LINKTEST linktest.gb

clean:
	rm -f linktest.o linktest.gb
.PHONY: clean
