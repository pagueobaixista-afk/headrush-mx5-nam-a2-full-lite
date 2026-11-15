#!/bin/bash
# Reproduz o build do lolgab (sem alteracoes) e compara com o .so que ele distribui.
set -euo pipefail
SP="$1"
rm -rf /opt/toolchain; mkdir -p /opt/toolchain
tar -xjf /root/bootlin.tar.bz2 -C /opt/toolchain --strip-components=1
export PATH="$PATH:/opt/toolchain/bin"
arm-buildroot-linux-gnueabihf-g++ --version | head -1
cd /root/mx5
# arquivos do aparelho (rootfs do lolgab)
python3 - "$SP" <<'EOF'
import sys, os
sys.path.insert(0, sys.argv[1] + '/mx/MX-Edit-0.9.5/firmware')
import ext4
fs = ext4.Ext4(open(sys.argv[1] + '/img/fs_namonly/rootfs.bin', 'rb').read())
os.makedirs('/root/mx5/dev', exist_ok=True)
for p in ('/usr/Evil/libnam_hook.so', '/usr/Evil/libnam_preload.so'):
    open('/root/mx5/dev/' + os.path.basename(p), 'wb').write(fs.cat(p))
for d in ('/lib', '/usr/lib'):
    try:
        ents = fs.listdir(fs.lookup(d))
    except Exception as e:
        print(d, 'erro', e); continue
    for name, ino, ft in ents:
        if name.startswith(('libc-', 'libc.so', 'libstdc++', 'libm-', 'ld-', 'libpthread-', 'libdl-')):
            mode, data = fs.read(ino)
            if mode & 0xF000 == 0xA000:
                print(d, name, '->', data.decode())
            else:
                print(d, name, len(data)); open('/root/mx5/dev/' + name, 'wb').write(data)
EOF
cd /root/mx5/hr
time bash scripts/build_blobs_native.sh > /root/mx5/baseline_build.log 2>&1 || { tail -30 /root/mx5/baseline_build.log; exit 1; }
tail -1 /root/mx5/baseline_build.log
RE=arm-buildroot-linux-gnueabihf-readelf
for f in libnam_hook.so libnam_preload.so; do
  echo "--- $f: meu build $(stat -c %s blobs/$f) bytes sha1 $(sha1sum < blobs/$f | cut -c1-12) | do lolgab $(stat -c %s ../dev/$f) bytes sha1 $(sha1sum < ../dev/$f | cut -c1-12)"
  cmp -s blobs/$f ../dev/$f && echo "    IDENTICO byte a byte" || echo "    bytes diferentes: $(cmp -l blobs/$f ../dev/$f 2>/dev/null | wc -l)"
done
echo "--- trampolim: $(xxd -p blobs/trampoline_gonk.bin | tr -d '\n')"
echo "--- dependencias e versoes de simbolo (meu build)"
$RE -d blobs/libnam_hook.so | grep NEEDED
$RE -V blobs/libnam_hook.so | grep -oE 'Name: GLIBC_[0-9.]+' | sort -u -V | tr '\n' ' '; echo
echo "--- glibc do aparelho"
strings -a ../dev/libc-*.so | grep -m1 'GNU C Library' || true
