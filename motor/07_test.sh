#!/bin/bash
# Testes no qemu-arm com as bibliotecas REAIS do aparelho (rootfs do firmware).
set -uo pipefail
SP="$1"
export PATH="$PATH:/opt/toolchain/bin"
TC=arm-buildroot-linux-gnueabihf
T=/root/mx5/test; mkdir -p $T; cd $T
# --- sysroot do aparelho: /usr/lib inteiro do rootfs ---
if [ ! -f devroot/usr/lib/libc.so.6 ]; then
python3 - "$SP" <<'EOF'
import sys, os
sys.path.insert(0, sys.argv[1] + '/mx/MX-Edit-0.9.5/firmware')
import ext4
fs = ext4.Ext4(open(sys.argv[1] + '/img/fs_stock/rootfs.bin', 'rb').read())
root = '/root/mx5/test/devroot'
os.makedirs(root + '/usr/lib', exist_ok=True)
n = 0
for name, ino, ft in fs.listdir(fs.lookup('/usr/lib')):
    if name in ('.', '..'): continue
    mode, data = fs.read(ino)
    p = root + '/usr/lib/' + name
    if mode & 0xF000 == 0xA000:
        if not os.path.lexists(p): os.symlink(data.decode(), p)
    elif mode & 0xF000 == 0x8000:
        open(p, 'wb').write(data); n += 1
if not os.path.lexists(root + '/lib'): os.symlink('usr/lib', root + '/lib')
print('devroot: %d arquivos de /usr/lib do aparelho' % n)
EOF
fi
DEV=$T/devroot
sed 's/\r$//' $SP/wsl/src/harness.c > harness.c
sed 's/\r$//' $SP/wsl/src/cmp.py > cmp.py
$TC-gcc -O2 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard harness.c -ldl -lm -o harness || exit 1
OLD=/root/mx5/hr/blobs/libnam_hook.so      # build identico ao do lolgab
NEW=/root/mx5/build/blobs/libnam_hook.so
IN=/root/mx5/t3k-embedded/test/golden_input.raw
EX=/root/mx5/hr/nam_core/example_models
echo "=== modelos de exemplo (NeuralAmpModelerCore)"
python3 - <<EOF
import json, glob, os
for p in sorted(glob.glob('$EX/*.nam')):
    j = json.load(open(p))
    c = j.get('config', {})
    extra = ''
    if j['architecture'] == 'SlimmableContainer' or 'submodels' in c:
        extra = 'submodelos: ' + ', '.join('%s/%d pesos' % (s['model']['architecture'], len(s['model']['weights'])) for s in c.get('submodels', []))
    la = c.get('layers') or []
    if la: extra += ' canais=%s' % [l.get('channels') for l in la]
    print('  %-28s %-20s pesos=%-6d %s' % (os.path.basename(p), j['architecture'], len(j.get('weights', [])), extra))
EOF
run() { # rotulo, lib, dir de modelos, indice, saida, [env...]
  local label="$1" lib="$2" dir="$3" idx="$4" out="$5"; shift 5
  rm -f $T/report.txt
  echo "--- $label"
  env NAM_MODEL_DIR="$dir" NAM_A2_REPORT=$T/report.txt "$@" qemu-arm -L $DEV ./harness "$lib" "$idx" $IN "$out" 2>$T/stderr.txt
  local rc=$?
  [ -f $T/report.txt ] && sed 's/^/     | /' $T/report.txt
  [ $rc -ne 0 ] && { echo "  rc=$rc"; tail -3 $T/stderr.txt; }
  return 0
}
mk() { rm -rf "$1"; mkdir -p "$1"; shift; }

echo; echo "=== 1. Modelos NAO-A2: o binario novo tem de soar igual ao do lolgab"
i=0
for m in wavenet_a1_standard lstm wavenet; do
  d=$T/m_$m; rm -rf $d; mkdir -p $d; cp $EX/$m.nam "$d/000 - $m.nam"
  run "$m / lolgab" $OLD $d 0 $T/o_${m}_old.raw
  run "$m / novo"   $NEW $d 0 $T/o_${m}_new.raw
  python3 cmp.py $T/o_${m}_old.raw $T/o_${m}_new.raw "$m: novo x lolgab"
done

echo; echo "=== 2. A2: cada motor, em Lite e em Full (nivel forcado por nam_config.txt)"
for m in A2 slimmable_container; do
  [ -f $EX/$m.nam ] || continue
  for q in lite full; do
    d=$T/m_${m}_$q; rm -rf $d; mkdir -p $d; cp $EX/$m.nam "$d/000 - $m.nam"; echo "quality=$q" > $d/nam_config.txt
    for e in core fma mla; do
      run "$m / $q / motor=$e" $NEW $d 0 $T/o_${m}_${q}_$e.raw NAM_A2_ENGINE=$e
    done
    python3 cmp.py $T/o_${m}_${q}_core.raw $T/o_${m}_${q}_fma.raw "$m $q: t3k-fma x core"
    python3 cmp.py $T/o_${m}_${q}_core.raw $T/o_${m}_${q}_mla.raw "$m $q: t3k-mla x core"
  done
  python3 cmp.py $T/o_${m}_lite_core.raw $T/o_${m}_full_core.raw "$m: (controle) lite x full devem diferir"
done

echo; echo "=== 3. A2 em modo automatico (selecao de motor + calibracao), novo x lolgab"
d=$T/m_auto; rm -rf $d; mkdir -p $d; cp $EX/A2.nam "$d/000 - A2.nam"; echo "quality=auto" > $d/nam_config.txt
run "A2 auto / lolgab" $OLD $d 0 $T/o_auto_old.raw
run "A2 auto / novo"   $NEW $d 0 $T/o_auto_new.raw
python3 cmp.py $T/o_auto_old.raw $T/o_auto_new.raw "A2 auto: novo x lolgab"

echo; echo "=== 4. Estereo (2 canais independentes) e varios modelos na pasta"
d=$T/m_multi; rm -rf $d; mkdir -p $d
cp $EX/A2.nam "$d/000 - A2.nam"; cp $EX/wavenet_a1_standard.nam "$d/001 - A1.nam"; printf 'lixo{' > "$d/002 - corrompido.nam"; cp $EX/lstm.nam "$d/003 - lstm.nam"
run "indice 0 (A2), 2 canais" $NEW $d 0 $T/o_multi0.raw NAM_A2_ENGINE=fma
run "indice 1 (A1)"           $NEW $d 1 $T/o_multi1.raw
run "indice 2 (lstm; o corrompido e ignorado)" $NEW $d 2 $T/o_multi2.raw
python3 cmp.py $T/o_wavenet_a1_standard_new.raw $T/o_multi1.raw "indice 1 = A1 sozinho"
python3 cmp.py $T/o_lstm_new.raw $T/o_multi2.raw "indice 2 = lstm sozinho"
echo; echo "=== 5. Correcoes v2"
split() { python3 - "$1" <<'EOF'
import sys
b = open(sys.argv[1], 'rb').read(); h = len(b) // 2
open(sys.argv[1] + '.L', 'wb').write(b[:h]); open(sys.argv[1] + '.R', 'wb').write(b[h:])
EOF
}
echo "--- 5a. dois canais com o MESMO sinal: processa uma vez e copia"
rm -f $T/report.txt $T/stats.txt
env NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt NAM_A2_STATS=$T/stats.txt H_SAME=1 H_TAIL=1 qemu-arm -L $DEV ./harness $NEW 0 $IN $T/o_same.raw 2 2>/dev/null
split $T/o_same.raw
python3 cmp.py $T/o_same.raw.L $T/o_same.raw.R "L x R (devem ser identicos)"
python3 cmp.py $T/o_multi0.raw $T/o_same.raw.L "mono x estereo-igual (mesmo som)"
echo "  medidor: $(cat $T/stats.txt 2>/dev/null)"
echo "--- 5b. dois canais DIFERENTES continuam independentes"
rm -f $T/stats.txt
env NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt NAM_A2_STATS=$T/stats.txt H_TAIL=1 qemu-arm -L $DEV ./harness $NEW 0 $IN $T/o_diff.raw 2 2>/dev/null
split $T/o_diff.raw
python3 cmp.py $T/o_multi0.raw $T/o_diff.raw.L "L = mono (canal esquerdo inalterado)"
python3 cmp.py $T/o_diff.raw.L $T/o_diff.raw.R "(controle) L x R devem diferir"
echo "  medidor: $(cat $T/stats.txt 2>/dev/null)"
echo "--- 5c. tres trocas de rig antes: a carga contada tem de voltar a 1"
rm -f $T/report.txt
env NAM_MODEL_DIR=$d NAM_A2_REPORT=$T/report.txt H_RIGS=3 qemu-arm -L $DEV ./harness $NEW 0 $IN $T/o_rigs.raw 2>/dev/null
grep -oE '[0-9]+ inst\.' $T/report.txt | sort | uniq -c | sed 's/^/     contagens nas calibracoes: /'
python3 cmp.py $T/o_auto_new.raw $T/o_rigs.raw "som apos trocas de rig = som direto"
echo "--- 5d. dois pedais NAM ativos ao mesmo tempo: carga 2"
rm -f $T/report.txt
env NAM_MODEL_DIR=$d NAM_A2_REPORT=$T/report.txt H_DUAL=1 qemu-arm -L $DEV ./harness $NEW 0 $IN $T/o_dual.raw 2>/dev/null
grep -oE '[0-9]+ inst\.' $T/report.txt | sort | uniq -c | sed 's/^/     contagens nas calibracoes: /'
echo "--- 5f. chave Hi-Lo (sem nam_config.txt): Low = Lite, High = Full"
dh=$T/m_hilo; rm -rf $dh; mkdir -p $dh; cp $EX/A2.nam "$dh/000 - A2.nam"
for h in 0 1; do
  rm -f $T/report.txt
  env NAM_MODEL_DIR=$dh NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt H_HILO=$h qemu-arm -L $DEV ./harness $NEW 0 $IN $T/o_hilo$h.raw 2>/dev/null | tail -1
  grep -E 'calib' $T/report.txt | sed 's/^/     | /'
done
python3 cmp.py $T/o_A2_lite_fma.raw $T/o_hilo0.raw "chave Low  = Lite forcado"
python3 cmp.py $T/o_A2_full_fma.raw $T/o_hilo1.raw "chave High = Full forcado"
echo "--- 5g. virar a chave tocando (Low -> High aos 3 s, em tempo real)"
cat $IN $IN $IN $IN $IN $IN > $T/long.raw
rm -f $T/report.txt
env NAM_MODEL_DIR=$dh NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt H_RT=1 H_HILO=1 qemu-arm -L $DEV ./harness $NEW 0 $T/long.raw $T/o_long_full.raw 2>/dev/null | tail -1
env NAM_MODEL_DIR=$dh NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt H_RT=1 H_HILO=0 qemu-arm -L $DEV ./harness $NEW 0 $T/long.raw $T/o_long_lite.raw 2>/dev/null | tail -1
rm -f $T/report.txt
env NAM_MODEL_DIR=$dh NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt H_RT=1 H_HILO=0 H_FLIP_AT=3000 qemu-arm -L $DEV ./harness $NEW 0 $T/long.raw $T/o_long_flip.raw 2>/dev/null | tail -1
python3 - <<EOF
import struct
def rd(p):
    b = open(p, 'rb').read(); n = len(b) // 4
    return struct.unpack('<%df' % n, b[:n * 4])
lite, full, flip = rd('$T/o_long_lite.raw'), rd('$T/o_long_full.raw'), rd('$T/o_long_flip.raw')
win = 2400
def err(a, b, s): return max(abs(x - y) for x, y in zip(a[s:s + win], b[s:s + win]))
n = min(len(lite), len(full), len(flip))
before = max(err(flip, lite, s) for s in range(0, 3000 * 48 - win, win))
first_full = next((s for s in range(3000 * 48, n - win, win) if err(flip, full, s) < 1e-5), None)
after = max(err(flip, full, s) for s in range(first_full, n - win + 1, win)) if first_full is not None else -1
print('  antes de virar: igual ao Lite (erro max %.1e)' % before)
print('  depois de virar: passa a ser igual ao Full a partir de %s s (erro max %.1e ate o fim) -> %s' % (
    None if first_full is None else '%.2f' % (first_full / 48000), after,
    'OK' if before < 1e-5 and first_full is not None and after < 1e-5 else 'VERIFICAR'))
EOF
grep -E 'calib' $T/report.txt | sed 's/^/     | /'
echo "--- 5e. threads de carga: politica e afinidade (emulador)"
grep -c 'sched_setaffinity\|sched_setscheduler' /root/mx5/build/patch/nam_hook.cpp | sed 's/^/     chamadas no codigo: /'

env NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=$T/report.txt qemu-arm -L $DEV ./harness $NEW 0 $IN $T/o_st.raw 2 2>/dev/null
python3 - <<EOF
import struct
b = open('$T/o_st.raw','rb').read(); n = len(b)//8
L = struct.unpack('<%df'%n, b[:n*4]); R = struct.unpack('<%df'%n, b[n*4:])
print('  estereo: L e R diferentes=%s, L finito=%s, pico L=%.3f R=%.3f' % (L != R, all(abs(v) < 100 for v in L), max(map(abs, L)), max(map(abs, R))))
EOF
