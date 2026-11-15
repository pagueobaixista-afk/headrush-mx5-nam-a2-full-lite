#!/bin/bash
# Prepara ~/mx5: fontes do lolgab, NAM core (commit fixado por ele), tone-3000, e dados do aparelho.
set -euo pipefail
SP="$1"                      # scratchpad em /mnt/c/...
W=/root/mx5; mkdir -p $W; cd $W
[ -d hr ] || cp -r "$SP/hr/headrush-nam-mod-0.1.6" hr
cd hr
sed -i 's/\r$//' scripts/*.sh
echo "=== Dockerfile"; cat docker/Dockerfile
echo "=== fetch_nam_core.sh"; cat scripts/fetch_nam_core.sh
echo "=== build_blobs_native.sh"; cat scripts/build_blobs_native.sh
[ -d nam_core ] || bash scripts/fetch_nam_core.sh 2>&1 | tail -3
ls nam_core | head; ls nam_core/NAM | head -50
cd $W
for r in embedded nam-binary-loader; do
  [ -d t3k-$r ] || git clone -q --depth 1 https://github.com/tone-3000/$r t3k-$r
  echo "=== t3k-$r @ $(git -C t3k-$r log -1 --format='%h %ad %s' --date=short)"
done
[ -d namcore-main ] || git clone -q https://github.com/sdatkinson/NeuralAmpModelerCore namcore-main
echo "=== namcore main @ $(git -C namcore-main log -1 --format='%h %ad %s' --date=short)"
git -C namcore-main log --format='%h %ad %s' --date=short 3cde95c354d5ba6da01316cad90b05cfc4855053..HEAD | head -40
echo "=== aparelho: libs do rootfs original"
python3 - "$SP" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1] + '/mx/MX-Edit-0.9.5/firmware')
import ext4, os
fs = ext4.Ext4(open(sys.argv[1] + '/img/fs_namonly/rootfs.bin', 'rb').read())
os.makedirs('/root/mx5/dev', exist_ok=True)
for d in ('/lib', '/usr/lib'):
    for name, ino, ft in fs.listdir(fs.lookup(d)):
        if name.startswith(('libc-', 'libc.so', 'libstdc++', 'libm-', 'libm.so', 'ld-', 'libpthread', 'libgcc_s', 'libdl')):
            mode, data = fs.read(ino)
            print(d, name, oct(mode), len(data) if mode & 0xF000 != 0xA000 else '-> ' + data.decode())
            if mode & 0xF000 == 0x8000:
                open('/root/mx5/dev/' + name, 'wb').write(data)
for p in ('/usr/Evil/libnam_hook.so', '/usr/Evil/libnam_preload.so'):
    open('/root/mx5/dev/' + os.path.basename(p), 'wb').write(fs.cat(p))
EOF
cd $W/dev
echo "=== libnam_hook.so original"
file libnam_hook.so
arm-linux-gnueabihf-readelf -d libnam_hook.so | grep -E 'NEEDED|SONAME'
arm-linux-gnueabihf-readelf -V libnam_hook.so | grep -oE 'Name: [A-Z_]+[0-9.]+' | sort -u -V | tail -12
arm-linux-gnueabihf-readelf -A libnam_hook.so | grep -E 'CPU|FP|SIMD|VFP'
arm-linux-gnueabihf-readelf -p .comment libnam_hook.so | head -5
echo "=== glibc/libstdc++ do aparelho"
strings -a libc-*.so 2>/dev/null | grep -E '^GNU C Library' | head -2
strings -a libstdc++.so.6.* 2>/dev/null | grep -E '^GLIBCXX_3\.4\.[0-9]+$' | sort -V | tail -2
