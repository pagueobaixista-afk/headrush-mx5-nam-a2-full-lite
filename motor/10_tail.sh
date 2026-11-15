#!/bin/bash
cd /root/mx5/test
python3 - <<'EOF'
import struct, math
def rd(p):
    b = open(p, 'rb').read(); n = len(b) // 4
    return struct.unpack('<%df' % n, b[:n * 4])
mono, L = rd('o_multi0.raw'), rd('o_diff.raw.L')
n = min(len(mono), len(L))
# onde a saida diverge (fade da recalibracao) e onde volta a coincidir
win = 2400
segs = []
for s in range(0, n - win + 1, win):
    e = max(abs(a - b) for a, b in zip(mono[s:s + win], L[s:s + win]))
    segs.append(e)
first_bad = next((i for i, e in enumerate(segs) if e > 1e-5), None)
last_bad = max((i for i, e in enumerate(segs) if e > 1e-5), default=None)
print('  janelas de 50 ms: %d no total; divergem da %s ate a %s (%.2f s a %.2f s)' % (
    len(segs), first_bad, last_bad, (first_bad or 0) * 0.05, ((last_bad or 0) + 1) * 0.05))
tail = segs[(last_bad or 0) + 1:]
print('  depois do fade: %d janelas, erro maximo %.2e -> %s' % (
    len(tail), max(tail) if tail else 0, 'som igual ao mono' if tail and max(tail) < 1e-5 else 'VERIFICAR'))
EOF
echo "  relatorio da recalibracao:"; grep -E 'calib' report.txt 2>/dev/null | tail -4 | sed 's/^/     | /'
