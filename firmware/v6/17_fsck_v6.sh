#!/bin/bash
cd /mnt/c/Users/USUARIO/Documents/arsenal/mx5/MX5_NAM_A2_v6/fontes
cp rootfs_v6.bin /root/chk6.bin
e2fsck -fn /root/chk6.bin > /root/chk6.log 2>&1; rc=$?
echo "e2fsck rc=$rc (0 = sem erros)"; tail -1 /root/chk6.log
debugfs -R "dump /usr/Evil/Scripts/nam-sync.sh /root/x6" /root/chk6.bin 2>/dev/null
cmp /root/x6 nam-sync.sh && sh -n /root/x6 && echo "nam-sync.sh: imagem final = fonte, sintaxe ok"
for f in runevil mount_usb_img; do debugfs -R "dump /usr/Evil/Scripts/$f /root/y6" /root/chk6.bin 2>/dev/null; cmp /root/y6 ../../MX5_NAM_A2_v4/fontes/${f}_v4 && echo "$f = v4"; done
rm -f /root/chk6.bin /root/x6 /root/y6
