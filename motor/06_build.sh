#!/bin/bash
# Build do libnam_hook.so com os motores A2 da tone-3000 (ARMv7) + selecao automatica.
set -euo pipefail
SP="$1"
export PATH="$PATH:/opt/toolchain/bin"
TC=arm-buildroot-linux-gnueabihf
B=/root/mx5/build; rm -rf $B; mkdir -p $B
cp -r /root/mx5/hr/patch /root/mx5/hr/nam_core $B/
rm -rf $B/blobs; mkdir -p $B/blobs $B/t3k
sed 's/\r$//' $SP/wsl/src/t3k_a2.cpp > $B/patch/t3k_a2.cpp
sed 's/\r$//' $SP/wsl/src/apply_patches.py > $B/apply_patches.py
python3 $B/apply_patches.py $B
cp /root/mx5/t3k-armv7/nam_armv7_neon.h /root/mx5/t3k-armv7/nam_a2lite.[ch] /root/mx5/t3k-armv7/nam_a2full.[ch] $B/t3k/
cd $B
ARCH="-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard"
# motores: 2 modelos x 2 variantes, simbolos publicos renomeados com prefixo fma_/mla_
for v in fma mla; do
  d=$([ $v = mla ] && echo 1 || echo 0)
  for m in a2lite a2full; do
    $TC-gcc -std=gnu11 -O3 -ffast-math -fPIC $ARCH -mtune=cortex-a17 -DNAM_V7_MLA=$d -It3k -c t3k/nam_$m.c -o t3k/${v}_$m.o
    $TC-nm --defined-only -g t3k/${v}_$m.o | awk -v p=${v}_ '{print $3" "p$3}' > t3k/${v}_$m.syms
    $TC-objcopy --redefine-syms=t3k/${v}_$m.syms t3k/${v}_$m.o
  done
done
echo "simbolos dos motores: $($TC-nm --defined-only -g t3k/*.o | grep -c ' T ') funcoes"
$TC-g++ -std=c++2a -O3 -ffast-math -fPIC -shared $ARCH \
    -DNAM_ENABLE_A2_FAST -DNAM_SAMPLE_FLOAT -DNAM_T3K_A2 \
    -static-libstdc++ -static-libgcc \
    -Inam_core -Inam_core/NAM -Inam_core/Dependencies/eigen -Inam_core/Dependencies/nlohmann -It3k \
    patch/nam_hook.cpp patch/t3k_a2.cpp nam_core/NAM/*.cpp nam_core/NAM/wavenet/*.cpp t3k/*.o \
    -lpthread -o blobs/libnam_hook.unstripped.so > build.log 2>&1 || { grep -E 'error|Error|undefined' -A3 build.log | head -40; exit 1; }
echo "compilado; erros: $(grep -c 'error' build.log || true), avisos: $(grep -c 'warning' build.log || true)"
$TC-strip --strip-unneeded -o blobs/libnam_hook.so blobs/libnam_hook.unstripped.so
ls -la blobs/
echo "--- dependencias"; $TC-readelf -d blobs/libnam_hook.so | grep NEEDED
echo "--- versoes glibc exigidas: $($TC-readelf -V blobs/libnam_hook.so | grep -oE 'Name: GLIBC_[0-9.]+' | sort -u -V | tr '\n' ' ')"
echo "--- simbolos exportados usados pelo preload:"; $TC-nm -D --defined-only blobs/libnam_hook.so | grep -E ' nam_(process|set|preload|debug|a2)'
echo "--- simbolos nao resolvidos fora de libc/libm/libpthread:"
$TC-nm -D --undefined-only blobs/libnam_hook.so | grep -vE '@GLIBC|GLIBC_' | head
echo "--- diff do nam_hook.cpp contra o do lolgab: $(diff /root/mx5/hr/patch/nam_hook.cpp patch/nam_hook.cpp | grep -c '^[<>]') linhas"
