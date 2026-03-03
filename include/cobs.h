#ifndef COBS_H
#define COBS_H

#include "pico/stdlib.h"

size_t cobs_encode(uint8_t *src, size_t len, uint8_t *buf);
size_t cobs_decode(uint8_t *buf, size_t len, uint8_t *dst);

#endif // COBS_H