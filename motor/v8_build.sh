#!/bin/bash
# v8: parte do build da v7 (/root/mx5/build, ja com os patches) e aplica v8_nucleos.py.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$PATH:/opt/toolchain/bin"
TC=arm-buildroot-linux-gnueabihf
B=/root/mx5/build8; rm -rf $B; cp -r /root/mx5/build $B; cd $B
rm -f blobs/libnam_hook.so blobs/libnam_hook.unstripped.so
python3 "$HERE/v8_nucleos.py" patch/nam_hook.cpp
python3 "$HERE/v8_pro.py" patch/nam_hook.cpp "$HERE/v8_resampling_tab.json"
ARCH="-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard"
$TC-g++ -std=c++2a -O3 -ffast-math -fPIC -shared $ARCH \
    -DNAM_ENABLE_A2_FAST -DNAM_SAMPLE_FLOAT -DNAM_T3K_A2 \
    -static-libstdc++ -static-libgcc \
    -Inam_core -Inam_core/NAM -Inam_core/Dependencies/eigen -Inam_core/Dependencies/nlohmann -It3k \
    patch/nam_hook.cpp patch/t3k_a2.cpp nam_core/NAM/*.cpp nam_core/NAM/wavenet/*.cpp t3k/*.o \
    -lpthread -o blobs/libnam_hook.unstripped.so > build.log 2>&1 || { grep -E 'error' -A3 build.log | head -40; exit 1; }
$TC-strip --strip-unneeded -o blobs/libnam_hook.so blobs/libnam_hook.unstripped.so
echo "glibc: $($TC-readelf -V blobs/libnam_hook.so | grep -oE 'Name: GLIBC_[0-9.]+' | sort -u -V | tr '\n' ' ')"
ls -la blobs/libnam_hook.so; sha1sum blobs/libnam_hook.so
