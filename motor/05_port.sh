#!/bin/bash
# Porta os motores A2 da tone-3000 (gerados para AArch64) para ARMv7 NEON-VFPv4 e roda o
# selftest de referencia deles no qemu-arm, em 3 variantes: escalar (sem patch), FMA e MLA.
set -euo pipefail
export PATH="$PATH:/opt/toolchain/bin"
CC=arm-buildroot-linux-gnueabihf-gcc
SYS=/opt/toolchain/arm-buildroot-linux-gnueabihf/sysroot
T=/root/mx5/t3k-embedded
P=/root/mx5/t3k-armv7; rm -rf $P; mkdir -p $P
cat > $P/nam_armv7_neon.h <<'EOF'
/* Camada ARMv7 para os motores A2 da tone-3000 (gerados para AArch64).
   O unico intrinsic usado que nao existe em ARMv7 e vfmaq_laneq_f32 (FMA por escalar de uma lane).
   NAM_V7_MLA=0: VFMA (fused, VFPv4) com a lane duplicada num registrador.
   NAM_V7_MLA=1: VMLA por escalar (nao fused), uma instrucao a menos por tap. */
#ifndef NAM_ARMV7_NEON_H
#define NAM_ARMV7_NEON_H
#include <arm_neon.h>
#if !defined(__aarch64__)
  #ifndef NAM_V7_MLA
    #define NAM_V7_MLA 0
  #endif
  #if NAM_V7_MLA
    #define vfmaq_laneq_f32(acc, x, w, lane) \
      vmlaq_lane_f32((acc), (x), ((lane) < 2 ? vget_low_f32(w) : vget_high_f32(w)), ((lane) & 1))
  #else
    #define vfmaq_laneq_f32(acc, x, w, lane) \
      vfmaq_f32((acc), (x), vdupq_lane_f32(((lane) < 2 ? vget_low_f32(w) : vget_high_f32(w)), ((lane) & 1)))
  #endif
#endif
#endif
EOF
for m in a2lite a2full; do
  src=$T/engines/cortex-a76/$m/nam_$m.c
  n=$(grep -c '^#if defined(__aarch64__) && defined(__ARM_NEON)$' $src)
  [ "$n" = 1 ] || { echo "guarda NEON inesperada em $src ($n)"; exit 1; }
  # unica mudanca no arquivo gerado: a guarda passa a aceitar qualquer ARM com NEON e inclui a camada
  sed -e 's|^#if defined(__aarch64__) \&\& defined(__ARM_NEON)$|#if defined(__ARM_NEON)|' \
      -e 's|^  #include <arm_neon.h>$|  #include "nam_armv7_neon.h"|' $src > $P/nam_$m.c
  cp $T/engines/cortex-a76/$m/nam_$m.h $P/
  echo "patch $m: $(diff $src $P/nam_$m.c | grep -c '^[<>]') linhas alteradas"
done
cd $T/example
BASE="-O3 -ffast-math -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard"
build() { # nome, dir dos motores, flags extras
  $CC $BASE $3 -I. -I$2 -I$T/namb host_example.c a2_engine.c $2/nam_a2lite.c $2/nam_a2full.c $T/namb/namb_reader.c -lm -o $P/host_$1
}
mkdir -p $P/orig; cp $T/engines/cortex-a76/a2lite/nam_a2lite.[ch] $T/engines/cortex-a76/a2full/nam_a2full.[ch] $P/orig/
build scalar $P/orig ""
build fma    $P "-I$P -DNAM_V7_MLA=0"
build mla    $P "-I$P -DNAM_V7_MLA=1"
build fma_a17 $P "-I$P -DNAM_V7_MLA=0 -mtune=cortex-a17"
build mla_a17 $P "-I$P -DNAM_V7_MLA=1 -mtune=cortex-a17"
for v in scalar fma mla fma_a17 mla_a17; do
  for m in a2lite a2full; do
    echo "=== $v / $m"
    s=$(date +%s.%N)
    qemu-arm -L $SYS $P/host_$v selftest $T/weights/$m.namb $T/test/golden_input.raw $T/test/golden_${m}_output.raw | sed 's/^/   /'
    e=$(date +%s.%N); echo "   tempo no emulador: $(echo "$e - $s" | bc) s"
  done
done
echo "=== instrucoes do laco quente (a2full, contagem por tipo)"
for v in fma mla; do
  $CC $BASE -I$P -DNAM_V7_MLA=$([ $v = mla ] && echo 1 || echo 0) -c $P/nam_a2full.c -o $P/a2full_$v.o
  arm-buildroot-linux-gnueabihf-objdump -d $P/a2full_$v.o | awk '{print $3}' | grep -E '^v(fma|mla|dup|ld1|st1|mov|add|mul|max|ldr|str|push|pop)' | sort | uniq -c | sort -rn | head -12 | tr '\n' ';'; echo
done
