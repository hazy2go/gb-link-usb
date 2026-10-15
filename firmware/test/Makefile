# Host tests for the firmware's portable parts. Run: make -C firmware/test
CFLAGS = -std=c11 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined

test: test_printer
	./test_printer

test_printer: test_printer.c ../src/printer.c ../src/printer.h
	$(CC) $(CFLAGS) -o $@ test_printer.c ../src/printer.c

clean:
	rm -rf test_printer test_printer.dSYM
.PHONY: test clean
