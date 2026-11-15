"""hilo_probe.py <scratchpad> <memscan binario ARM>
Envia o leitor para /tmp do MX5, acha o objeto do Anxiety OD (vtable 0x17ee460), e descobre
qual byte muda quando a chave Hi-Lo e alternada pela Bridge. Restaura o valor original."""
import sys, time, base64, struct
sp = sys.argv[1]
sys.path.insert(0, sp + r"\pylib"); sys.path.insert(0, sp + r"\mx\MX-Edit-0.9.5\editor")
from bridge import Bridge
br = Bridge.auto()
for _ in range(5):
    try:
        br.ping(); break
    except Exception:
        time.sleep(0.5)
def sh(cmd):
    rc, out = br.shell(cmd)
    return out
VT = 0x17ee460
SIZE = 0x900
b64 = base64.b64encode(open(sys.argv[2], 'rb').read()).decode()
sh("rm -f /tmp/ms.b64 /tmp/memscan")
for i in range(0, len(b64), 1500):
    sh("printf '%%s' '%s' >> /tmp/ms.b64" % b64[i:i + 1500])
print("upload:", sh("base64 -d /tmp/ms.b64 > /tmp/memscan && chmod +x /tmp/memscan && rm /tmp/ms.b64 && ls -la /tmp/memscan").strip())
pid = sh("pidof Evil").strip()
addrs = [a for a in sh("/tmp/memscan find %s %x" % (pid, VT)).split() if a]
print("objetos com a vtable do AnxietyOD:", addrs)
def dump(a):
    h = sh("/tmp/memscan dump %s %s %d" % (pid, a, SIZE)).strip()
    return bytes.fromhex(h)
PATH = "/Engine/Patch/Anxiety OD/"
drive = br.get(PATH + "Drive")["value"]; tone = br.get(PATH + "Tone")["value"]; level = br.get(PATH + "Level")["value"]
print("pela Bridge: Drive=%.4f Tone=%.4f Level=%.4f Hi-Lo=%s" % (drive, tone, level, br.get(PATH + "Hi-Lo")["string"]))
best = None
for a in addrs:
    d = dump(a)
    if len(d) < 0x560: continue
    f = lambda o: struct.unpack_from("<f", d, o)[0]
    ok = abs(f(0x534) - drive) < 1e-4 and abs(f(0x548) - tone) < 1e-4 and abs(f(0x520) - level) < 1e-4
    print("  %s: +0x534=%.4f +0x548=%.4f +0x520=%.4f bypass(+0x26b)=%d %s" % (a, f(0x534), f(0x548), f(0x520), d[0x26b], "<- e este" if ok else ""))
    if ok and best is None: best = a
if not best:
    print("objeto nao identificado"); sys.exit(1)
orig = br.get(PATH + "Hi-Lo")["state"]
snaps = {}
try:
    for state in (False, True, False, True):
        br.set(PATH + "Hi-Lo", "state", 1 if state else 0)
        time.sleep(0.4)
        snaps.setdefault(state, []).append(dump(best))
finally:
    br.set(PATH + "Hi-Lo", "state", 1 if orig else 0)
    time.sleep(0.3)
print("Hi-Lo restaurado para:", br.get(PATH + "Hi-Lo")["string"])
lo1, lo2 = snaps[False]; hi1, hi2 = snaps[True]
cands = [o for o in range(SIZE) if lo1[o] == lo2[o] and hi1[o] == hi2[o] and lo1[o] != hi1[o]]
print("bytes estaveis em cada posicao e diferentes entre Low e High:", [hex(o) for o in cands])
for o in cands:
    w = o & ~3
    print("  +0x%x: Low=%s (float %.3f)  High=%s (float %.3f)" % (w, lo1[w:w+4].hex(), struct.unpack_from('<f', lo1, w)[0], hi1[w:w+4].hex(), struct.unpack_from('<f', hi1, w)[0]))
noisy = sum(1 for o in range(SIZE) if lo1[o] != lo2[o] or hi1[o] != hi2[o])
print("bytes que mudam sozinhos (ruido, ignorados):", noisy)
print("parametros vizinhos (+0x50c..+0x570, floats):", ["+0x%x=%.3f" % (o, struct.unpack_from('<f', lo1, o)[0]) for o in range(0x50c, 0x574, 4)])
sh("rm -f /tmp/memscan")
