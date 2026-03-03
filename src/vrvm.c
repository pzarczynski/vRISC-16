#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/irq.h"

#include "vrvm.h"
#include "ioctl.h"
#include "cobs.h"

uint8_t memory[MEM_SIZE];
uint16_t regs[NUM_REGS];
uint16_t pc = 0;

bool running = false;
bool stepping = false;


void vrvm_execute_single() {
    if (!running) return;

    uint16_t ins = (memory[pc] << 8) | memory[pc + 1];

    uint8_t opc = (ins >> 12) & 0x0F;
    uint8_t rd  = (ins >> 8)  & 0x0F;
    uint8_t rs1 = (ins >> 4)  & 0x0F;
    uint8_t rs2 = ins & 0x0F;
    uint8_t imm = ins & 0xFF; // for I and B-type

    regs[R0] = 0;
    uint16_t target_pc = pc + 2;

    switch (opc) {
        case 0x0: // ADD
            regs[rd] = regs[rs1] + regs[rs2];
            break;
        case 0x1: // SUB
            regs[rd] = regs[rs1] - regs[rs2];
            break;
        case 0x2: // AND
            regs[rd] = regs[rs1] & regs[rs2];
            break;
        case 0x3: // OR
            regs[rd] = regs[rs1] | regs[rs2];
            break;
        case 0x4: // XOR
            regs[rd] = regs[rs1] ^ regs[rs2];
            break;

        case 0x5: // LD rd, [rs1 + off]
            {
                uint16_t addr = (regs[rs1] + rs2) & 0xFFFF; // rs2 -> offset
                regs[rd] = (memory[addr] << 8) | memory[(addr + 1) & 0xFFFF];
            }
            break;

        case 0x6: // ST rs, [rb + off]
            {
                uint16_t addr = (regs[rs1] + rs2) & 0xFFFF; // rs2 -> offset
                memory[addr] = (regs[rd] >> 8) & 0xFF;
                memory[(addr + 1) & 0xFFFF] = regs[rd] & 0xFF;
            }
            break;

        case 0x7: // LHI
            regs[rd] = (imm << 8);
            break;
        case 0x8: // LLI
            regs[rd] |= imm;
            break;

        case 0x9: // BZ
            if (regs[rd] == 0) target_pc = pc + 2 + 2 * (int8_t)imm;
            break;
        case 0xA: // BNZ
            if (regs[rd] != 0) target_pc = pc + 2 + 2 * (int8_t)imm;
            break;
        case 0xB: // BLT (Branch if Less Than Zero - signed)
            if ((int16_t)regs[rd] < 0) target_pc = pc + 2 + 2 * (int8_t)imm;
            break;

        case 0xC: // JMP rs
            target_pc = regs[rd];
            break;
        case 0xD: // JAL rd, rs
            regs[rd] = pc + 2;
            target_pc = regs[rs1]; // rs1 -> rs
            break;

        case 0xE: // SHL
            regs[rd] = regs[rs1] << rs2;
            break;
        case 0xF: // SHR
            regs[rd] = regs[rs1] >> rs2;
            break;

        default: // unknown opcode
            running = false;
            printf("CPU Halted: Unknown opcode 0x%X at PC 0x%04X\n", opc, pc);
            return;
    }

    pc = target_pc;
}


bool vrvm_tick(struct repeating_timer *t) {
    if (running && !stepping) vrvm_execute_single();
    return true;
}


void vrvm_process_packet(uint8_t* buf, size_t len) {
    uint8_t decoded[1024];
    size_t d_len = cobs_decode(buf, len, decoded);
    if (d_len < 1) return;

    uint8_t type = decoded[0];

    switch (type) {
        case 0x01: { // WRITE BLOCK
            uint16_t addr = (decoded[1] << 8) | decoded[2];
            uint16_t size = (decoded[3] << 8) | decoded[4];
            
            if (addr == 0xFFFF && size == 0) {
                // EOF
                send_ack();
            } else if (addr == 0xFFFE && size == 2) {
                // Reset vector
                pc = (decoded[5] << 8) | decoded[6];
                send_ack();
            } else {
                memcpy(&memory[addr], &decoded[5], size);
                send_ack();
            }
            break;
        }

        case 0x02: { // CTRL COMMAND
            uint16_t cmd = (decoded[1] << 8) | decoded[2];
            if (cmd == 'r') { running = true; stepping = false; }
            if (cmd == 'h') { running = false; }
            if (cmd == 's') { running = true; stepping = true; vrvm_execute_single(); send_register_dump(); }
            if (cmd == 'd') { send_register_dump(); }
            break;
        }

        case 0x03: { // QUERY STATUS
            send_register_dump();
            break;
        }
    }
}

int main() {
    stdio_init_all();
    
    uart_init(UART_ID, 115200);
    gpio_set_function(0, GPIO_FUNC_UART); // TX
    gpio_set_function(1, GPIO_FUNC_UART); // RX

    uart_set_format(UART_ID, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(UART_ID, true);

    int UART_IRQ = UART_ID == uart0 ? UART0_IRQ : UART1_IRQ;
    irq_set_exclusive_handler(UART_IRQ, on_uart_rx);
    irq_set_enabled(UART_IRQ, true);

    uart_set_irq_enables(UART_ID, true, false);

    struct repeating_timer timer;
    add_repeating_timer_us(-10, vrvm_tick, NULL, &timer);

    while (true) {
        if (packet_ready) {
            packet_ready = false;
            irq_set_enabled(UART_IRQ, false);
            size_t len = rx_ptr;
            rx_ptr = 0;
            irq_set_enabled(UART_IRQ, true);
            vrvm_process_packet(rx_buffer, len);
        }
    }

    return 0;
}