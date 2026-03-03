#ifndef VRVM_H
#define VRVM_H

#include "pico/stdlib.h"

#define MEM_SIZE 65536
#define NUM_REGS 16

extern uint8_t memory[MEM_SIZE];
extern uint16_t regs[NUM_REGS];
extern uint16_t pc;

extern bool running;
extern bool stepping;

#define R0 0
#define AT 14 
#define LR 15

#endif // VRVM_H