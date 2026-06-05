/* IP-001 RV32I — Linker script for GRM test binaries
 * 
 * Relocated to 0x80000000 (Spike default memory).
 * Includes tohost/fromhost symbols for Spike HTIF exit.
 * 
 * Usage: riscv64-unknown-elf-gcc -T link.ld test.S -o test.elf
 */

OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    IMEM (rx)  : ORIGIN = 0x80000000, LENGTH = 4K
    DMEM (rw)  : ORIGIN = 0x80001000, LENGTH = 4K
}

SECTIONS
{
    /* Code and read-only data in instruction memory */
    .text : {
        *(.text.init)
        *(.text)
        *(.text.*)
    } > IMEM

    .rodata : {
        *(.rodata)
        *(.rodata.*)
    } > IMEM

    /* HTIF tohost/fromhost for Spike communication */
    .htif 0x80001000 (NOLOAD) : {
        . = ALIGN(8);
        tohost = .;
        . += 8;
        fromhost = .;
        . += 8;
    }

    /* Initialized data in data memory (above HTIF) */
    .data 0x80001020 : {
        *(.data)
        *(.data.*)
        *(.sdata)
        *(.sdata.*)
    } > DMEM

    /* BSS (zero-initialized data) */
    .bss : {
        *(.bss)
        *(.bss.*)
        *(.sbss)
        *(.sbss.*)
    } > DMEM

    /* Stack: grows downward from top of data memory */
    . = ALIGN(16);
    _stack_top = ORIGIN(DMEM) + LENGTH(DMEM);
    _stack_bottom = _stack_top - 512;

    /* Entry point */
    _start_address = ADDR(.text);
}
