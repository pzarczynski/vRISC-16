add_executable(vrvm
    vrvm.c
    cobs.c
    ioctl.c
)

target_link_libraries(vrvm
    pico_stdlib  
    pico_status_led
    hardware_irq
)

target_include_directories(vrvm
    PRIVATE 
        ${CMAKE_SOURCE_DIR}/include
)

pico_enable_stdio_usb(vrvm 0)
pico_enable_stdio_uart(vrvm 1)

pico_add_extra_outputs(vrvm)

file(MAKE_DIRECTORY "${CMAKE_SOURCE_DIR}/bin")

add_custom_command(TARGET vrvm POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:vrvm>"               "${CMAKE_SOURCE_DIR}/bin/vrvm.elf"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_CURRENT_BINARY_DIR}/vrvm.uf2" "${CMAKE_SOURCE_DIR}/bin/vrvm.uf2"
)