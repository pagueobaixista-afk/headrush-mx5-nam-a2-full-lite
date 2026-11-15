#!/bin/bash
SP="$1"
for f in img/fs_stock/rootfs.bin a2/rootfs_1b.bin a2/rootfs_a2.bin; do
  cp "$SP/$f" /root/chk.bin
  echo "== $f"
  e2fsck -fn /root/chk.bin > /root/chk.log 2>&1; rc=$?
  tail -3 /root/chk.log; echo "   e2fsck rc=$rc (0 = sem erros)"
done
echo "== libnam_hook.so lido da imagem final por um leitor independente (debugfs)"
debugfs -R 'dump /usr/Evil/libnam_hook.so /root/dump.so' "$SP/a2/rootfs_a2.bin" 2>/dev/null
echo "   da imagem : $(sha1sum < /root/dump.so | cut -c1-40)"
echo "   compilado : $(sha1sum < /root/mx5/build/blobs/libnam_hook.so | cut -c1-40)"
debugfs -R 'stat /usr/Evil/libnam_hook.so' "$SP/a2/rootfs_a2.bin" 2>/dev/null | grep -E 'Mode:|Size:|EXTENTS' -A1 | grep -v '^--' | head -6
echo "== o harness carrega o .so extraido da imagem, com as libs do aparelho"
cd /root/mx5/test
NAM_MODEL_DIR=/root/mx5/test/m_auto NAM_A2_REPORT=/root/mx5/test/report.txt qemu-arm -L devroot ./harness /root/dump.so 0 /root/mx5/t3k-embedded/test/golden_input.raw /root/mx5/test/o_final.raw 2>/dev/null
python3 cmp.py o_auto_new.raw o_final.raw "imagem final x build testado"
rm -f /root/chk.bin
