import sys, struct, math, wave
def rdwav(p):
    b = open(p, 'rb').read(); i = 12; fmt = None
    while i < len(b):
        cid, sz = b[i:i+4], struct.unpack('<I', b[i+4:i+8])[0]
        if cid == b'fmt ': fmt = struct.unpack('<HHIIHH', b[i+8:i+24])
        if cid == b'data': d = b[i+8:i+8+sz]; break
        i += 8 + sz + (sz & 1)
    tag, ch, sr, _, _, bits = fmt
    if tag == 3 and bits == 32: v = struct.unpack('<%df' % (len(d)//4), d)
    elif bits == 16: v = [x/32768 for x in struct.unpack('<%dh' % (len(d)//2), d)]
    elif bits == 24: v = [int.from_bytes(d[k:k+3], 'little', signed=True)/8388608 for k in range(0, len(d)-2, 3)]
    elif bits == 32: v = [x/2147483648 for x in struct.unpack('<%di' % (len(d)//4), d)]
    else: raise SystemExit('fmt %s' % (fmt,))
    return list(v[::ch]), sr, (tag, bits)
def rdraw(p):
    b = open(p, 'rb').read(); n = len(b)//4; return list(struct.unpack('<%df' % n, b[:n*4]))
def rd(p): return rdwav(p)[0] if p.endswith('.wav') else rdraw(p)
def db(r): return 10*math.log10(r + 1e-30)
if sys.argv[1] == 'mkin':
    out = sys.argv[2]; s = []
    for p in sys.argv[3:]:
        v, sr, f = rdwav(p)
        if sr != 48000: print('  pulado (sr=%d): %s' % (sr, p)); continue
        if len(v) > 480000:   # 10 s mais fortes
            w = 48000; e = [sum(x*x for x in v[k:k+w:16]) for k in range(0, len(v)-w, w)]
            best = max(range(len(e)-10), key=lambda k: sum(e[k:k+10])); v = v[best*w:(best+10)*w]
        pk = max(abs(x) for x in v); print('  entrada %s: %.1f s, pico %.3f, fmt %s' % (p.split('/')[-1], len(v)/48000, pk, f)); s += v
    open(out + '.raw', 'wb').write(struct.pack('<%df' % len(s), *s))
    d = struct.pack('<%df' % len(s), *s)
    open(out + '.wav', 'wb').write(b'RIFF' + struct.pack('<I', 36+len(d)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 3, 1, 48000, 192000, 4, 32) + b'data' + struct.pack('<I', len(d)) + d)
else:
    x, y = rd(sys.argv[1]), rd(sys.argv[2]); n = min(len(x), len(y)); x, y = x[:n], y[:n]
    seg = range(48000, min(n, 48000+24000) - 64)
    lag = max(range(-32, 33), key=lambda L: sum(x[i]*y[i+L] for i in seg))
    if lag > 0: y = y[lag:]; x = x[:len(y)]
    elif lag < 0: x = x[-lag:]; y = y[:len(x)]
    sxx = sum(a*a for a in x); syy = sum(b*b for b in y); sxy = sum(a*b for a, b in zip(x, y))
    g = sxy/syy; esr = sum((a-b)**2 for a, b in zip(x, y))/sxx; esrg = sum((a-g*b)**2 for a, b in zip(x, y))/sxx
    print('  %-34s atraso %+d am | nivel %+.3f dB | residuo %7.1f dB (com nivel casado %7.1f dB) | correl %.6f' % (sys.argv[3], lag, -20*math.log10(abs(g)), db(esr), db(esrg), sxy/math.sqrt(sxx*syy)))
