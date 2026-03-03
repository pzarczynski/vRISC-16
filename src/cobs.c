#include "cobs.h"


size_t cobs_encode(uint8_t *src, size_t len, uint8_t *buf) {
	assert(src && buf);

	uint8_t *encoded = buf;
	uint8_t *codep = encoded++;
	uint8_t code = 1;

	for (uint8_t *byte = (uint8_t *)src; len--; ++byte)
	{
		if (*byte) *encoded++ = *byte, ++code;

		if (!*byte || code == 0xff)
		{
			*codep = code, code = 1, codep = encoded;
			if (!*byte || len) ++encoded;
		}
	}
	*codep = code;

	return (size_t)(encoded - buf);
}


size_t cobs_decode(uint8_t *buf, size_t len, uint8_t *dst) {
	assert(buf && dst);
	uint8_t *byte = buf;
    uint8_t *decoded = dst;

	for (uint8_t code = 0xff, block = 0; byte < buf + len; --block)
	{
		if (block) *decoded++ = *byte++;
		else
		{
			block = *byte++;
			if (block && (code != 0xff)) *decoded++ = 0;
			code = block;
			if (!code) break;
		}
	}

	return (size_t)(decoded - dst);
}
