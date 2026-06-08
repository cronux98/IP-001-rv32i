#!/bin/bash
# IP-001 RV32I — Test Program Builder
GCC="${RISCV_GCC:-/usr/bin/riscv64-unknown-elf-gcc}"
OBJCOPY="${RISCV_OBJCOPY:-/usr/bin/riscv64-unknown-elf-objcopy}"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"

for asm in "$PROJ"/verification/tests/*.S; do
  name=$(basename "$asm" .S)
  echo "Building $name..."
  # RTL binary (link at 0x00000000)
  $GCC -march=rv32i -mabi=ilp32 -nostdlib -nostartfiles -nodefaultlibs \
    -T "$PROJ/verification/link_rtl.ld" \
    -o "$PROJ/verification/tmp/${name}.elf" "$asm" && \
  $OBJCOPY -O binary --only-section=.text \
    "$PROJ/verification/tmp/${name}.elf" \
    "$PROJ/verification/tmp/${name}.bin"
  echo "  -> $(stat -c%s "$PROJ/verification/tmp/${name}.bin") bytes"
done
echo "Done."
