#ifndef IOCTL_H
#define IOCTL_H

#include "pico/stdlib.h"

#define UART_ID uart0
#define RX_BUF_SIZE 1024

extern uint8_t rx_buffer[1024];
extern volatile size_t rx_ptr;
extern volatile bool packet_ready;

void send_ack();
void on_uart_rx();
void send_register_dump();

#endif // IOCTL_H