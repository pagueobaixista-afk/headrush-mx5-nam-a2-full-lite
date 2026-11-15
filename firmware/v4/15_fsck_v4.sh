#!/bin/bash
cd /mnt/c/Users/USUARIO/Documents/arsenal/mx5/MX5_NAM_A2_v4/fontes
cp rootfs_v4.bin /root/chk4.bin
e2fsck -fn /root/chk4.bin > /root/chk4.log 2>&1; rc=$?
echo "e2fsck rc=$rc (0 = sem erros)"; tail -1 /root/chk4.log
for f in nam-sync.sh:nam-sync.sh runevil:runevil_v4 mount_usb_img:mount_usb_img_v4; do
  debugfs -R "dump /usr/Evil/Scripts/${f%%:*} /root/x4" /root/chk4.bin 2>/dev/null
  cmp /root/x4 "${f##*:}" && sh -n /root/x4 && echo "${f%%:*}: imagem final = fonte, sintaxe ok"
done
rm -f /root/chk4.bin /root/x4
