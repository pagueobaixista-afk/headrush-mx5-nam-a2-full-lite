#!/bin/bash
# v8.2: parte do build8 (v8 pronto) e aplica v81_troca.py + v82_reserva.py.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$PATH:/opt/toolchain/bin"
TC=arm-buildroot-linux-gnueabihf
B=/root/mx5/build82; rm -rf $B; cp -r /root/mx5/build8 $B; cd $B
rm -f blobs/libnam_hook.so blobs/libnam_hook.unstripped.so
python3 "$HERE/v81_troca.py" patch/nam_hook.cpp
python3 "$HERE/v82_reserva.py" patch/nam_hook.cpp
ARCH="-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard"
$TC-g++ -std=c++2a -O3 -ffast-math -fPIC -shared $ARCH \
    -DNAM_ENABLE_A2_FAST -DNAM_SAMPLE_FLOAT -DNAM_T3K_A2 \
    -static-libstdc++ -static-libgcc \
    -Inam_core -Inam_core/NAM -Inam_core/Dependencies/eigen -Inam_core/Dependencies/nlohmann -It3k \
    patch/nam_hook.cpp patch/t3k_a2.cpp nam_core/NAM/*.cpp nam_core/NAM/wavenet/*.cpp t3k/*.o \
    -lpthread -o blobs/libnam_hook.unstripped.so > build.log 2>&1 || { grep -E 'error' -A3 build.log | head -40; exit 1; }
$TC-strip --strip-unneeded -o blobs/libnam_hook.so blobs/libnam_hook.unstripped.so
$TC-nm -C blobs/libnam_hook.unstripped.so | grep 'g_dbg_act'
ls -la blobs/libnam_hook.so; sha1sum blobs/libnam_hook.so
