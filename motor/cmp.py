#!/usr/bin/env python3
"""cmp.py <ref.raw> <teste.raw> [rotulo] -> ESR em dB e erro maximo relativo ao pico."""
import sys, struct, math
a = open(sys.argv[1], 'rb').read(); b = open(sys.argv[2], 'rb').read()
n = min(len(a), len(b)) // 4
x = struct.unpack('<%df' % n, a[:n * 4]); y = struct.unpack('<%df' % n, b[:n * 4])
sig = sum(v * v for v in x) or 1e-30
err = sum((u - v) ** 2 for u, v in zip(x, y))
peak = max(abs(v) for v in x) or 1e-30
mx = max(abs(u - v) for u, v in zip(x, y))
esr = 10 * math.log10(err / sig + 1e-30)
ident = a[:n * 4] == b[:n * 4]
print('  %-44s %s  ESR %7.1f dB  erro max %.2e (pico %.3f)  n=%d' % (
    sys.argv[3] if len(sys.argv) > 3 else '', 'IDENTICO' if ident else '        ', esr, mx, peak, n))
sys.exit(0)
