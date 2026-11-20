"""Gera build_v8.py a partir do build_v7.py (mesmo pipeline testado; so muda o que e da v8).
uso: python gen_build_v8.py <build_v7.py> <saida build_v8.py>"""
import sys, os
s = open(sys.argv[1], encoding='utf-8').read()


def tr(a, b, n=1):
    global s
    if s.count(a) != n:
        sys.exit('trecho %dx (esperado %d): %r' % (s.count(a), n, a[:80]))
    s = s.replace(a, b)


tr('"""Monta o firmware MX5 NAM A2 v7 = v6 (NAM A2 + Bridge) + arte propria + NAM A2 + atalho + abertura + creditos.',
   '"""Monta o firmware MX5 NAM A2 v8 = v6 (base) + arte propria + NAM A2 Pro no 8-Bit Crush + nucleos livres + abertura + creditos.\n'
   '(gerado por gen_build_v8.py a partir do build_v7.py)')
tr('uso: python -I build_v7.py <libdir Bridge> <pasta MX5_NAM_A2_v6> <pasta arte_usada> <splash.xz> <outdir> [--so-evil]',
   'uso: python -I build_v8.py <libdir Bridge> <pasta MX5_NAM_A2_v6> <pasta arte> <splash.xz> <outdir> <libnam_hook.so v8> <nam-sync.sh v8> [--so-evil]')
tr("lib, v6dir, artedir, splash_xz, outdir = sys.argv[1:6]", "lib, v6dir, artedir, splash_xz, outdir, hook_so, namsync_sh = sys.argv[1:8]")
tr("VERSAO = 'v7'", "VERSAO = 'v8'")
tr("open(os.path.join(outdir, 'Evil_v7'), 'wb').write(newevil)\n    print('Evil de teste: %s  sha1 %s' % (os.path.join(outdir, 'Evil_v7'), sha1(newevil)))",
   "open(os.path.join(outdir, 'Evil_v8'), 'wb').write(newevil)\n    print('Evil de teste: %s  sha1 %s' % (os.path.join(outdir, 'Evil_v8'), sha1(newevil)))")

# B) nomes curtos: o Anxiety OD fica original; o 8-Bit Crush vira NAM PRO
tr("troca_cstr(b'Anxty OD', b'NAM A2')\ntroca_cstr(b'Anx OD 2', b'NAM A2 2')",
   "troca_cstr(b'8-Bit', b'NAM PRO')\ntroca_cstr(b'8-Bit 2', b'NAMPRO2')")

# C) nome exibido, Model Selector
tr("""NAM_RX = '.replace(/^Anxiety OD( 2)?$/, "NAM A2$1")'""", """NAM_RX = '.replace(/^8-Bit Crush( 2)?$/, "NAM A2 Pro$1")'""")
tr('a=ix("Anxiety OD")', 'a=ix("8-Bit Crush")')
tr("""'\\t\\t\\ttext: model.name === "Anxiety OD" ? "NAM A2" : model.name\\n'""",
   """'\\t\\t\\ttext: model.name === "8-Bit Crush" ? "NAM A2 Pro" : model.name\\n'""")

# tela do pedal: troca o bloco do Anxiety OD (v7) pelo do 8-Bit Crush
a = s.index('# --- Tela do pedal NAM (AnxietyOD.qml')
b = s.index("for caminho, novo in telas.items():")
s = s[:a] + open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bloco_tela_v8.py'), encoding='utf-8').read() + s[b:]

# Evil: o desvio do NAM sai do Anxiety OD e vai para o 8-Bit Crush (3 palavras; T4/T5 adaptados)
tr("newevil = bytes(B)\ne = evil", '''# NAM A2 Pro: slot 8 (process) da vtable do BitDist -> trampolim; Anxiety OD volta ao original
DESVIO = [(0x17ee460 + 32, 0x3046cf4, 0x302ed0),   # Anxiety OD: process() original de volta
          (0x17ee3e4 + 32, 0x30a010, 0x3046cf4),   # 8-Bit Crush (BitDist): trampolim do NAM
          (0x3046d0c, 0x302ed0, 0x30a010)]         # plano B do trampolim: process() original do BitDist
for va, velho, novo in DESVIO:
    o_ = va - 0x8000
    test('E1 palavra em 0x%x era 0x%x' % (va, velho), struct.unpack_from('<I', B, o_)[0] == velho)
    struct.pack_into('<I', B, o_, novo)
DESVIO_OFF = {va - 0x8000 + k for va, _, _ in DESVIO for k in range(4)}
newevil = bytes(B)
e = evil''')
tr("difs = [i for i in range(0, len(evil)) if newevil[i] != evil[i]]",
   "difs = [i for i in range(0, len(evil)) if newevil[i] != evil[i] and i not in DESVIO_OFF]")
a = s.index("# o sequestro do NAM (vtable/trampolim) nao foi tocado")
b = s.index("if SO_EVIL:")
s = s[:a] + "test('T5 desvio do NAM: so as 3 palavras previstas fora do .rodata', all(newevil[o_:o_ + 4] != evil[o_:o_ + 4] for o_ in {x & ~3 for x in DESVIO_OFF}))\n\n" + s[b:]

# rootfs: Evil no lugar + libnam_hook.so e nam-sync.sh novos
tr("grava_no_lugar(fs, PE, newevil)\n", """grava_no_lugar(fs, PE, newevil)
PH, PN = '/usr/Evil/libnam_hook.so', '/usr/Evil/Scripts/nam-sync.sh'
hook_new, ns_new = rd(hook_so), rd(namsync_sh)
for pth, dat in ((PH, hook_new), (PN, ns_new)):
    md_, _ = fs.read(fs.lookup(pth))
    fs.write_file(pth, dat, md_)
""")
tr("test('D3 entre %d arquivos, so mudou o /usr/Evil/Evil' % len(inew), dd == [PE] and len(inew) == len(ibase), str(dd))",
   "test('D3 entre %d arquivos, so mudaram Evil, libnam_hook.so e nam-sync.sh' % len(inew), dd == sorted([PE, PH, PN]) and len(inew) == len(ibase), str(dd))\n"
   "test('D3 hook e nam-sync relidos iguais', chk.cat(PH) == hook_new and chk.cat(PN) == ns_new)")
open(sys.argv[2], 'w', encoding='utf-8').write(s)
print('ok build_v8.py')

# pacote: nomes da v8 e fontes da v8
s = open(sys.argv[2], encoding='utf-8').read()
for a, b in (("'1_INSTALAR_NAM_A2_v7'", "'1_INSTALAR_NAM_A2_v8'"),
             ("+ NAM A2 v7 + MX5Bridge 0.7 (mod nao oficial)'", "+ NAM A2 v8 (Pro no 8-Bit Crush) + MX5Bridge 0.7 (mod nao oficial)'"),
             ("'Instalar NAM A2 v7'", "'Instalar NAM A2 v8'"),
             ("for f in ('build_v7.py', 'v7lib.py', 'qrc.py'):", "for f in ('build_v8.py', 'gen_build_v8.py', 'bloco_tela_v8.py', 'gen_namsync.py', 'nam-sync.sh', 'v7lib.py', 'qrc.py'):"),
             ('credito "MX5 NAM A2 v7 - unofficial', 'credito "MX5 NAM A2 v8 - unofficial')):
    assert s.count(a) == 1, a
    s = s.replace(a, b)
open(sys.argv[2], 'w', encoding='utf-8').write(s)
print('ok nomes v8')
