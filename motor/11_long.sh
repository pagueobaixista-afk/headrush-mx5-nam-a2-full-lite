#!/bin/bash
# Entrada longa (12 s): confirma que, apos a recalibracao por aumento de carga, o som volta ao normal.
cd /root/mx5/test
IN=/root/mx5/t3k-embedded/test/golden_input.raw
cat $IN $IN $IN $IN $IN $IN > long.raw
d=m_multi; NEW=/root/mx5/build/blobs/libnam_hook.so
env NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=report.txt qemu-arm -L devroot ./harness $NEW 0 long.raw o_long_mono.raw 1 2>/dev/null | sed 's/^/  mono:    /'
rm -f report.txt
env NAM_MODEL_DIR=$d NAM_A2_ENGINE=fma NAM_A2_REPORT=report.txt qemu-arm -L devroot ./harness $NEW 0 long.raw o_long_st.raw 2 2>/dev/null | sed 's/^/  estereo: /'
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
if not bad:
    print('  canal L identico ao mono o tempo todo')
else:
    tail = segs[bad[-1] + 1:]
    print('  canal L diverge do mono de %.2f s a %.2f s (fade da recalibracao); depois disso: %d janelas (%.1f s), erro max %.2e -> %s' % (
        bad[0] * 0.05, (bad[-1] + 1) * 0.05, len(tail), len(tail) * 0.05, max(tail) if tail else -1,
        'SOM VOLTA A SER IGUAL' if tail and max(tail) < 1e-5 else 'VERIFICAR'))
EOF
grep -cE 'calib' report.txt | sed 's/^/  calibracoes no teste estereo: /'
