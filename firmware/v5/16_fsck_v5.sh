#!/bin/bash
cd /mnt/c/Users/USUARIO/Documents/arsenal/mx5/MX5_NAM_A2_v5/fontes
cp rootfs_v5.bin /root/chk5.bin
e2fsck -fn /root/chk5.bin > /root/chk5.log 2>&1; rc=$?
echo "e2fsck rc=$rc (0 = sem erros)"; tail -1 /root/chk5.log
debugfs -R "dump /usr/Evil/Scripts/nam-sync.sh /root/x5" /root/chk5.bin 2>/dev/null
cmp /root/x5 nam-sync.sh && sh -n /root/x5 && echo "nam-sync.sh: imagem final = fonte, sintaxe ok"
for f in runevil mount_usb_img; do debugfs -R "dump /usr/Evil/Scripts/$f /root/y5" /root/chk5.bin 2>/dev/null; cmp /root/y5 ../../MX5_NAM_A2_v4/fontes/${f}_v4 && echo "$f = v4"; done
rm -f /root/chk5.bin /root/x5 /root/y5
