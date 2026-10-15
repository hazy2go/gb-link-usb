ROMS = linktest.gb printtest.gb
all: $(ROMS)

%.gb: %.asm
	rgbasm -o $*.o $<
	rgblink -o $@ $*.o
	rgbfix -v -p 0xFF -t $(shell echo $* | tr a-z A-Z | cut -c1-11) $@

clean:
	rm -f *.o *.gb
.PHONY: all clean
