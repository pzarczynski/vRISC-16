### Installation 
Project can be built using CMake:

```{bash}
> cmake -S . -B build -DPICO_BOARD=pico2_w
> cmake --build build
```
Output can be found in the `bin/` subdirectory.

To install `vrasm` and `vrctl` systemwide:
```{bash}
> sudo cmake --install build
```

### Usage
You have to flash Pico with `bin/vrvm.uf2` or `bin/vrvm.elf` first.
After that you have to connect Pico to the serial port via its UART0 interface.

Then you can compile and run a simple program with:
```{bash}
> vrasm main.vrasm -o main.bin
> vrctl /dev/ttyACM0 -b 115200
vRISC-16 shell. Type 'exit' to quit.
(vrctl) load main.bin
(vrctl) run     # or `step` to run instructions one-by-one
```
