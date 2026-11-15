"""Sincroniza a pasta NAM do MX5 com a lista de presets do pedal Anxiety OD (via MX5 Bridge).
  1) .nam sem prefixo "NNN - " ganha o proximo numero livre (vai para o fim: nada muda de posicao)
  2) cria/atualiza/remove um preset por modelo (nome = nome do arquivo, Drive = posicao)
Uso: nam_presets.py [--simular]"""
import sys, os, re, json, time, uuid
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "lib"))
from bridge import Bridge, BridgeError, sql_lit, sh_quote

DRY = "--simular" in sys.argv
NAM = "/media/az01-internal/Evil/usb_mnt/NAM"
TYPE, KEY = "ANXIETY OD", "Anxiety OD"
PREF = re.compile(r"^(\d{3}) - ")
MAXM = 101  # Drive 0..100

def fail(msg):
    print("\nERRO: " + msg); sys.exit(1)

def listar(br):
    rc, out = br.shell("ls -1 %s/ | grep -i '[.]nam$' | grep -v '^[.]_' | LC_ALL=C sort" % NAM)
    return [l for l in out.splitlines() if l.strip()]

def main():
    try:
        br = Bridge.auto()
    except Exception as e:
        fail("nao achei o MX5. Confira: cabo USB ligado, MX5 na tela normal (fora do modo de\n"
             "transferencia USB) e MX-Edit fechado.\n(%s)" % e)
    for i in range(6):
        try:
            br.ping(); break
        except Exception:
            if i == 5: fail("o MX5 nao respondeu. Tente de novo.")
            time.sleep(0.5)
    files = listar(br)
    if not files: fail("nenhum .nam encontrado na pasta NAM do MX5.")

    # 1) numerar os novos
    novos = [f for f in files if not PREF.match(f)]
    usados = [int(PREF.match(f).group(1)) for f in files if PREF.match(f)]
    prox = max(usados) + 1 if usados else 0
    renomeou = False
    for f in novos:
        alvo = "%03d - %s" % (prox, f); prox += 1
        print("numerar:  %s  ->  %s" % (f, alvo))
        if not DRY:
            rc, out = br.shell("mv %s %s" % (sh_quote(NAM + "/" + f), sh_quote(NAM + "/" + alvo)))
            if rc != 0: fail("nao consegui renomear %s: %s" % (f, out.strip()))
            renomeou = True
    if renomeou:
        br.shell("sync"); files = listar(br)
    if len(files) > MAXM:
        fail("ha %d modelos; o botao Drive so alcanca %d. Remova %d." % (len(files), MAXM, len(files) - MAXM))

    # 2) presets
    alvo = {f[:-4]: rank for rank, f in enumerate(files)}
    alvo_low = {k.lower(): k for k in alvo}
    rows = br.sql("select id, name, content from blocks where type = %s" % sql_lit(TYPE))
    stmts, mudou_pos, vistos = [], [], set()
    for r in rows:
        nome = r["name"]
        if nome.lower() in alvo_low:
            real = alvo_low[nome.lower()]; vistos.add(real)
            c = json.loads(r["content"])
            d = c["data"][KEY]["children"]["Drive"]
            if d.get("value") != alvo[real]:
                mudou_pos.append((real, d.get("value"), alvo[real]))
                d["value"] = alvo[real]
                stmts.append("update blocks set content = %s where id = %s"
                             % (sql_lit(json.dumps(c, separators=(",", ":"))), sql_lit(r["id"])))
        elif PREF.match(nome):
            print("remover preset (arquivo nao existe mais):  %s" % nome)
            stmts.append("delete from blocks where id = %s" % sql_lit(r["id"]))
    criados = 0
    for nome, rank in alvo.items():
        if nome in vistos: continue
        c = {"data": {KEY: {"childorder": ["Level", "Drive", "Tone", "Hi-Lo"], "children": {
            "Drive": {"type": 0, "value": rank}, "Hi-Lo": {"state": True, "type": 1},
            "Level": {"type": 0, "value": 50}, "Tone": {"type": 0, "value": 50}}}}, "info": {"version": "1.0.9"}}
        print("novo preset:  %s  (Drive %d)" % (nome, rank)); criados += 1
        stmts.append("insert into blocks (id, type, name, content, is_readonly) values (%s, %s, %s, %s, 0)"
                     % (sql_lit(str(uuid.uuid4())), sql_lit(TYPE), sql_lit(nome), sql_lit(json.dumps(c, separators=(",", ":")))))
    for nome, a, b in mudou_pos:
        print("posicao mudou:  %s  (Drive %s -> %s)" % (nome, a, b))
    if stmts and not DRY:
        br.sql_write("; ".join(stmts))
    print("\n%d modelos na pasta NAM | %d presets novos | %d alteracoes no total%s"
          % (len(files), criados, len(stmts), "  [SIMULACAO: nada gravado]" if DRY else ""))
    if mudou_pos:
        print("\nATENCAO: %d modelo(s) mudaram de posicao. Rigs salvos que usam o Anxiety OD guardam o\n"
              "numero do Drive e podem estar apontando para outro modelo. Confira esses rigs." % len(mudou_pos))
    if renomeou or criados:
        print("\nReinicie o MX5 (desligar e ligar) para ele enxergar os modelos novos.")
    elif not stmts:
        print("Ja estava tudo em dia.")

try:
    main()
except BridgeError as e:
    fail("falha na comunicacao com o MX5: %s" % e)
