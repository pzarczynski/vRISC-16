#include <stdio.h>
#include "pico/stdlib.h"

#include "ioctl.h"
#include "cobs.h"


uint8_t rx_buffer[1024];
volatile size_t rx_ptr = 0;
volatile bool packet_ready = false;

extern uint16_t regs[16];
extern uint16_t pc;


void send_ack() {
    uart_putc(UART_ID, '\0');
}

void on_uart_rx() {
    while (uart_is_readable(UART_ID)) {
        uint8_t ch = uart_getc(UART_ID);
        if (ch == 0x00) {
            packet_ready = true;
        } else if (rx_ptr < RX_BUF_SIZE) {
            rx_buffer[rx_ptr++] = ch;
        }
    }
}

void send_register_dump() {
    uint8_t raw[34]; // 16 reg * 2B + PC * 2B
    
    for (int i = 0; i < 16; i++) {
        raw[i*2] = (regs[i] >> 8) & 0xFF;
        raw[i*2+1] = regs[i] & 0xFF;
    }

    raw[32] = (pc >> 8) & 0xFF;
    raw[33] = pc & 0xFF;

    uint8_t encoded[64];
    size_t e_len = cobs_encode(raw, 34, encoded);
    
    for (size_t i = 0; i < e_len; i++) uart_putc(UART_ID, encoded[i]);
    uart_putc(UART_ID, 0x00);
}
