#!/bin/bash
SP="$1"
cp "$SP/a2v2/rootfs_a2.bin" /root/chk.bin
e2fsck -fn /root/chk.bin > /root/chk.log 2>&1; rc=$?
echo "e2fsck rc=$rc (0 = sem erros): $(tail -1 /root/chk.log)"
debugfs -R 'dump /usr/Evil/libnam_hook.so /root/dump2.so' /root/chk.bin 2>/dev/null
echo "libnam_hook.so na imagem : $(sha1sum < /root/dump2.so | cut -c1-40)"
echo "libnam_hook.so compilado : $(sha1sum < /root/mx5/build/blobs/libnam_hook.so | cut -c1-40)"
cd /root/mx5/test
NAM_MODEL_DIR=m_hilo NAM_A2_ENGINE=fma H_HILO=1 qemu-arm -L devroot ./harness /root/dump2.so 0 /root/mx5/t3k-embedded/test/golden_input.raw o_final2.raw 2>/dev/null | tail -1
python3 cmp.py o_hilo1.raw o_final2.raw "binario da imagem final x build testado (chave High)"
rm -f /root/chk.bin
