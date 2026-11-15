#!/bin/bash
cd /mnt/c/Users/USUARIO/Documents/arsenal/mx5/MX5_NAM_A2_v3/fontes
cp rootfs_v3.bin /root/chk3.bin
e2fsck -fn /root/chk3.bin > /root/chk3.log 2>&1; rc=$?
echo "e2fsck rc=$rc (0 = sem erros)"; tail -3 /root/chk3.log
debugfs -R "dump /usr/Evil/Scripts/nam-sync.sh /root/s3" /root/chk3.bin 2>/dev/null; cmp /root/s3 nam-sync.sh && echo "nam-sync.sh na imagem final = fonte testada no aparelho"; rm -f /root/chk3.bin
