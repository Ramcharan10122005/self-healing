CC=gcc
CFLAGS=-Wall -Wextra -std=c99 -O2
BIN=c_monitor
SRC=c_monitor.c

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) -o $(BIN) $(SRC)

run: all
	./heal.sh start

clean:
	rm -f $(BIN) *.o healing.log selfhealer.pid

.PHONY: all run clean


