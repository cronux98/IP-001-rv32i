/* IP-001 RV32I — Linker script for verification test programs
 * Spike default base: 0x80000000 (I-mem mapped at +0 offset)
 * D-mem region: 0x80001000 */

SECTIONS {
  . = 0x80000000;
  .text : { *(.text*) }
  . = 0x80001000;
  .data : { *(.data*) }
  .bss : { *(.bss*) }
}
