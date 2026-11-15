#!/bin/bash
# Build final v2 + bateria completa + conferencias extras; copia artefatos para o scratchpad.
SP="$1"; OUT="$SP/a2v2"; mkdir -p "$OUT"
bash /root/06.sh "$SP" > /root/mx5/b.log 2>&1
grep -E '^ok |compilado|rror:' /root/mx5/b.log
bash /root/07.sh "$SP" > /root/mx5/test_run.log 2>&1
cd /root/mx5/test
{
  echo; echo "=== 6. Modo automatico (quality=auto): recuperacao apos aumento de carga, em tempo real"
  d=m_auto6; rm -rf $d; mkdir -p $d; cp /root/mx5/hr/nam_core/example_models/A2.nam "$d/000 - A2.nam"; echo "quality=auto" > $d/nam_config.txt
  NEW=/root/mx5/build/blobs/libnam_hook.so
  env H_RT=1 NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=report.txt qemu-arm -L devroot ./harness $NEW 0 long.raw o_long_mono.raw 1 2>/dev/null | tail -1
  rm -f report.txt
  env H_RT=1 NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=report.txt qemu-arm -L devroot ./harness $NEW 0 long.raw o_long_st.raw 2 2>/dev/null | tail -1
  python3 - <<'EOF'
import struct
def rd(p, half=False):
    b = open(p, 'rb').read()
    if half: b = b[:len(b) // 2]
    n = len(b) // 4
    return struct.unpack('<%df' % n, b[:n * 4])
mono, L = rd('o_long_mono.raw'), rd('o_long_st.raw', True)
n = min(len(mono), len(L)); win = 2400
segs = [max(abs(a - b) for a, b in zip(mono[s:s + win], L[s:s + win])) for s in range(0, n - win + 1, win)]
bad = [i for i, e in enumerate(segs) if e > 1e-5]
tail = segs[bad[-1] + 1:] if bad else segs
print('  canal L diverge do mono de %.2f s a %.2f s (fade); depois: %.1f s com erro max %.1e -> %s' % (
    bad[0] * 0.05 if bad else 0, (bad[-1] + 1) * 0.05 if bad else 0, len(tail) * 0.05, max(tail) if tail else -1,
    'SOM VOLTA A SER IGUAL' if tail and max(tail) < 1e-5 else 'VERIFICAR'))
EOF
  echo "=== 7. Modo chave (padrao): canais diferentes NAO provocam recarga"
  env H_RT=1 NAM_MODEL_DIR=m_hilo NAM_A2_ENGINE=fma NAM_A2_REPORT=report.txt qemu-arm -L devroot ./harness $NEW 0 long.raw o_long_st2.raw 2 2>/dev/null | tail -1
  python3 - <<'EOF'
import struct
def rd(p, half=False):
    b = open(p, 'rb').read()
    if half: b = b[:len(b) // 2]
    n = len(b) // 4
    return struct.unpack('<%df' % n, b[:n * 4])
lite, L = rd('o_long_lite.raw'), rd('o_long_st2.raw', True)
n = min(len(lite), len(L))
e = max(abs(a - b) for a, b in zip(lite[:n], L[:n]))
print('  canal L x Lite mono, 12 s inteiros: erro max %.1e -> %s' % (e, 'SEM FADE, SOM IGUAL' if e < 1e-5 else 'VERIFICAR'))
EOF
} >> /root/mx5/test_run.log 2>&1
grep -E 'ESR|NAO|rc=|VERIFICAR|SOM |OK$|-> OK|contagens' /root/mx5/test_run.log | grep -vE 'controle|L = mono' | awk '{ if ($0 ~ /IDENTICO|SOM |OK|ESR  -1[0-9][0-9]/) ok++; else bad = bad "\n" $0 } END { print "linhas de verificacao OK:", ok; if (bad) print "A CONFERIR:" bad }'
cp /root/mx5/build/blobs/libnam_hook.so "$OUT/libnam_hook_new.so"
cp /root/mx5/test_run.log "$OUT/TESTES_SOM.txt"
diff -u /root/mx5/hr/patch/nam_hook.cpp /root/mx5/build/patch/nam_hook.cpp > "$OUT/nam_hook.diff"
sha1sum /root/mx5/build/blobs/libnam_hook.so
