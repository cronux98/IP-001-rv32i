SECTIONS {
  . = 0x40000000;
  .text : { *(.text*) }
  . = 0x40001000;
  .data : { *(.data*) }
  .bss : { *(.bss*) }
}
