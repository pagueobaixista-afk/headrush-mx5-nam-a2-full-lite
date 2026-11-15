"""brq.py <scratchpad> <comando> [args] -- consultas a Bridge do MX5.
  get <path>...            le propriedades
  set <path> <campo> <valor>
  entries <path>
  sh <arquivo.sh>          roda script no aparelho"""
import sys, time, json
sp = sys.argv[1]
sys.path.insert(0, sp + r"\pylib"); sys.path.insert(0, sp + r"\mx\MX-Edit-0.9.5\editor")
from bridge import Bridge
br = Bridge.auto()
for _ in range(5):
    try:
        br.ping(); break
    except Exception:
        time.sleep(0.5)
cmd = sys.argv[2]
if cmd == "get":
    for p in sys.argv[3:]:
        try:
            print(p, "=>", json.dumps(br.get(p), ensure_ascii=False)[:400])
        except Exception as e:
            print(p, "ERRO", e)
elif cmd == "set":
    v = sys.argv[5]
    try:
        v = float(v) if "." in v else int(v)
    except ValueError:
        pass
    print(json.dumps(br.set(sys.argv[3], sys.argv[4], v), ensure_ascii=False)[:400])
elif cmd == "entries":
    print(br.entries(sys.argv[3]))
elif cmd == "sh":
    rc, out = br.shell(open(sys.argv[3], encoding="utf-8").read().replace("\r", ""))
    print("rc=%s" % rc); print(out)
