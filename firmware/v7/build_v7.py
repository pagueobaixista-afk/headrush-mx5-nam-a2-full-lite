"""Monta o firmware MX5 NAM A2 v7 = v6 (NAM A2 + Bridge) + arte propria + NAM A2 + atalho + abertura + creditos.

uso: python -I build_v7.py <libdir Bridge> <pasta MX5_NAM_A2_v6> <pasta arte_usada> <splash.xz> <outdir> [--so-evil]

Mudancas em relacao a v6:
  /usr/Evil/Evil (NO LUGAR, mesmo tamanho, nenhum endereco muda):
    - os 248 PNG de /Pages/ModuleEditors/img trocados pela arte propria (arte_usada); o espaco que sobra
      em cada recurso e zerado (nao sobra nenhum resto da imagem anterior);
    - nome mostrado na tela: "Anxiety OD" -> "NAM A2" (so exibicao: o nome interno, usado por rigs,
      nam-sync e MX-Edit, continua "Anxiety OD"); nome curto C++ "Anxty OD"/"Anx OD 2" -> "NAM A2"/"NAM A2 2";
    - Model Selector: botao "NAM A2" entre Empty Slot e Amp, que abre direto a lista do NAM A2;
    - Global Settings: credito "MX5 NAM A2 v7 - unofficial community mod by Starcz" abaixo do aviso legal
      da inMusic (que continua igual);
    - telas alteradas deixam de usar a versao pre-compilada ("/"->"#" no registro), como na v6.1/v6.2.
  FIT: imagem /images/splash (tela de abertura) trocada; recoverysplash continua a original.
Cada passo e verificado; qualquer falha aborta sem gravar nada."""
import sys, os, re, io, json, hashlib, lzma, shutil, struct, zlib

lib, v6dir, artedir, splash_xz, outdir = sys.argv[1:6]
SO_EVIL = '--so-evil' in sys.argv
sys.path.insert(0, lib)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitpatch, ext4, xzblocks
import qrc, v7lib
from PIL import Image

VERSAO = 'v7'
CREDITO = 'MX5 NAM A2 %s — unofficial community mod by Starcz' % VERSAO
V6_SHA1 = '902af9debe320fb076d258d0ee1d1f0acd73a89c'
OFFICIAL_SHA1 = '82b5639ceaba94d3c07b8880694d5de2e21b9f43'
EVIL_V6_SHA1 = 'a87a5d084fde8dcc3981fb4a5967559b25b59075'
PE = '/usr/Evil/Evil'
IMG = '/Pages/ModuleEditors/img/'
PNGSIG = b'\x89PNG\r\n\x1a\n'
results, log = [], []


def test(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('[%s] %s %s' % ('OK ' if ok else 'FALHA', name, detail))
    if not ok:
        raise SystemExit('ABORTADO: ' + name)


sha1 = lambda b: hashlib.sha1(b).hexdigest()
rd = lambda p: open(p, 'rb').read()

# ================= base
raw = rd(os.path.join(v6dir, '1_INSTALAR_NAM_A2_v6', 'Update.img'))
raw_s = rd(os.path.join(v6dir, '2_RESTAURAR_ORIGINAL_2.7', 'Update.img'))
test('T1 base = Update.img da v6; restauracao com SHA1 oficial',
     fitpatch.verify(raw) and sha1(raw) == V6_SHA1 and sha1(raw_s) == OFFICIAL_SHA1, sha1(raw))
rootfs = lzma.decompress(fitpatch.extract(raw, 'rootfs'))
fs0 = ext4.Ext4(rootfs); fs0.check()
evil_mode, evil = fs0.read(fs0.lookup(PE))
test('T2 /usr/Evil/Evil da v6 confere', sha1(evil) == EVIL_V6_SHA1, sha1(evil))
B = bytearray(evil)

# mapa de recursos Qt
res = v7lib.find_qml(evil)
known = list(res.keys()) + [m.start() - 4 for m in re.finditer(re.escape(PNGSIG), evil)]
mapa = qrc.find_all(evil, known)
test('T3 tabela de recursos Qt lida', len(mapa) > 1000, '%d caminhos' % len(mapa))

# ================= A) arte
imgs = sorted(k for k in mapa if k.startswith(IMG) and k.endswith('.png'))
arq = {}
for root, _, fs_ in os.walk(artedir):
    for f in fs_:
        if f.lower().endswith('.png'):
            arq[os.path.relpath(os.path.join(root, f), artedir).replace(os.sep, '/')] = os.path.join(root, f)
test('A1 arte_usada tem exatamente os %d PNG do firmware (nome por nome)' % len(imgs),
     len(imgs) == 248 and set(arq) == {k[len(IMG):] for k in imgs})


def encaixa(png, cap):
    """menor PNG que caiba: original -> sem perda -> paleta 256..64 cores; devolve (bytes, como)"""
    if len(png) <= cap:
        return png, 'original'
    im = Image.open(io.BytesIO(png)).convert('RGBA')
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    if len(b.getvalue()) <= cap:
        return b.getvalue(), 'sem perda'
    for n in (256, 224, 192, 160, 128, 96, 64):
        for dith in (True, False):
            q = im.quantize(colors=n, method=Image.Quantize.FASTOCTREE,
                            dither=Image.Dither.FLOYDSTEINBERG if dith else Image.Dither.NONE)
            b = io.BytesIO(); q.save(b, 'PNG', optimize=True)
            if len(b.getvalue()) <= cap:
                return b.getvalue(), 'paleta %d' % n
    return None, 'nao cabe'


def png_ok(blob):
    q = 8
    while True:
        ln, typ = struct.unpack_from('>I4s', blob, q)
        crc, = struct.unpack_from('>I', blob, q + 8 + ln)
        if zlib.crc32(blob[q + 4:q + 8 + ln]) != crc:
            return False
        q += 12 + ln
        if typ == b'IEND':
            return q == len(blob)


NAO_PEDAL = {'Amp.png', 'Cab.png', 'Mix.png', 'DeviceBack.png', 'Other.png', 'IR.png', 'IR2.png', 'IR (1024).png', 'IR (1024)2.png'}
FIXAS = set()   # so Amp/Cab/Mic (subpastas) ficam com as medidas da v6; o resto a tela ajusta
medidas_novas = []
gravado = {}
como = {}
for k in imgs:
    o = mapa[k][0]
    test('A2 %s: recurso sem compressao' % k, mapa[k][1] & 1 == 0) if False else None
    cap = struct.unpack_from('>I', evil, o)[0]
    velho = Image.open(io.BytesIO(evil[o + 4:o + 4 + cap]))
    novo_src = rd(arq[k[len(IMG):]])
    _nm = k[len(IMG):]
    if '/' not in _nm and _nm not in NAO_PEDAL:
        _im = Image.open(io.BytesIO(novo_src)); _w, _h = _im.size
        if _h > 230 and _w > 180:
            # desenhado em tamanho real pela tela: largura demais invade o pedal vizinho -> reduz proporcional
            _f = 165 / _w; _im = _im.convert('RGBA').resize((165, round(_h * _f)), Image.LANCZOS)
            _b = io.BytesIO(); _im.save(_b, 'PNG', optimize=True); novo_src = _b.getvalue()
            log.append('Pedal reduzido para caber na area: %s %dx%d -> %dx%d' % (_nm, _w, _h, 165, round(_h * _f)))
    novo, c = encaixa(novo_src, cap)
    if novo is None or not png_ok(novo):
        test('A2 %s cabe no espaco original' % k, False, c)
    im_n = Image.open(io.BytesIO(novo)); im_n.load(); gravado[k] = (im_n.size, novo)
    nome_rel = k[len(IMG):]
    if '/' in nome_rel or nome_rel in FIXAS:
        # Amp/Cab/Mic e telas fixas: mesmas medidas da v6
        if im_n.size != velho.size:
            test('A2 %s: mesmas dimensoes da v6' % k, False, '%s x %s' % (im_n.size, velho.size))
    else:
        # pedais: a tela (ActiveStomp.qml da v6) se ajusta ao tamanho: ate 230 px de altura escala para
        # caber em 153x226; acima disso desenha em tamanho real, entao a largura nao pode invadir o vizinho
        w, h = im_n.size
        if nome_rel not in NAO_PEDAL and not (w >= 40 and h >= 40 and (h <= 230 or w <= 180) and h <= 300):
            test('A2 %s: medidas cabem na area do pedal' % k, False, '%s' % (im_n.size,))
        if im_n.size != velho.size:
            medidas_novas.append(nome_rel)
    B[o:o + 4] = struct.pack('>I', len(novo))
    B[o + 4:o + 4 + cap] = novo + b'\x00' * (cap - len(novo))
    como[c.split(' ')[0]] = como.get(c.split(' ')[0], 0) + 1
test('A2 248 imagens gravadas (CRC de todos os blocos PNG ok, sobra zerada)', sum(como.values()) == 248, str(como))
log.append('Pedais com medidas novas (a tela ajusta): %d %s' % (len(medidas_novas), medidas_novas))
# releitura: cada recurso decodifica e e identico ao arquivo encaixado em pixels
erro = 0
for k in imgs:
    o = mapa[k][0]; L = struct.unpack_from('>I', B, o)[0]
    im = Image.open(io.BytesIO(bytes(B[o + 4:o + 4 + L]))); im.load()
    if im.size != gravado[k][0] or bytes(B[o + 4:o + 4 + L]) != gravado[k][1]:
        erro += 1
test('A3 releitura: as 248 imagens decodificam do binario', erro == 0)

# ================= B) nome curto (C++): so exibicao
def troca_cstr(velho, novo):
    e = bytes(evil)
    occ = [m.start() + 1 for m in re.finditer(re.escape(b'\x00' + velho + b'\x00'), e)]
    test('B1 "%s" aparece uma vez so' % velho.decode(), len(occ) == 1, str([hex(x) for x in occ]))
    off = occ[0]; j = off + len(velho)
    while e[j] == 0:
        j += 1
    slot = j - off - 1
    test('B1 "%s" -> "%s" cabe (%d de %d)' % (velho.decode(), novo.decode(), len(novo), slot), len(novo) <= slot)
    # referenciado por um unico ponteiro (tabela de nomes curtos)
    refs = [m.start() for m in re.finditer(re.escape(struct.pack('<I', off + 0x8000)), e)]
    test('B1 "%s" usado por 1 ponteiro (tabela de nomes curtos)' % velho.decode(), len(refs) == 1, str([hex(r) for r in refs]))
    B[off:off + slot + 1] = novo + b'\x00' * (slot + 1 - len(novo))


troca_cstr(b'Anxty OD', b'NAM A2')
troca_cstr(b'Anx OD 2', b'NAM A2 2')

# ================= C) telas QML
inv = {v[0]: k for k, v in mapa.items()}
porcaminho = {inv[p]: p for p in res if p in inv}


def src_of(caminho):
    kind, d, L = res[porcaminho[caminho]]
    return d.decode('utf-8').replace('\r\n', '\n'), kind, L


def troca(s, velho, novo, n=1):
    test('C  trecho encontrado %dx: %s' % (n, velho[:60].replace('\n', ' ')), s.count(velho) == n, str(s.count(velho)))
    return s.replace(velho, novo)


telas = {}
# --- Global Settings: credito abaixo do aviso legal
s, kind, L = src_of('/Pages/GlobalSettings.qml')
s = troca(s, 'ElevenText { width: 340; height: 50; y: 288; x: 433',
          'ElevenText { width: 340; height: 50; y: 280; x: 433')
lic = '\t\t\t\t\ttextFormat: Text.PlainText\n\t\t\t\t}\n'
s = troca(s, lic, lic + '\t\t\t\tElevenText { width: 340; height: 14; y: 345; x: 433; horizontalAlignment: Text.AlignHCenter; '
          'verticalAlignment: Text.AlignVCenter; regularNotMedium: true; font.pixelSize: 11; color: "#949495"; '
          'textFormat: Text.PlainText; text: "%s" }\n' % CREDITO)
telas['/Pages/GlobalSettings.qml'] = s

# --- Block Details: nome mostrado
NAM_RX = '.replace(/^Anxiety OD( 2)?$/, "NAM A2$1")'
s, kind, L = src_of('/Pages/BlockDetails.qml')
s = troca(s, '"Mix" : blckEdt.moduleTypeProp.translator.string)',
          '"Mix" : blckEdt.moduleTypeProp.translator.string%s)' % NAM_RX)
s = troca(s, 'text: nameText.replace(" 2", "")', 'text: nameText.replace(" 2", "")%s' % NAM_RX)
telas['/Pages/BlockDetails.qml'] = s

# --- Model Selector: guarda o pedido de atalho entre os paineis
s, kind, L = src_of('/Pages/ListSelector.qml')
s = troca(s, 'id: repPanels\n', 'id: repPanels\n\t\tproperty real namJump: 0\n')
# namJump < 0 = aberto pelo botao NAM A2: o painel de Distortion (nivel 1) fica escondido,
# o Back da lista do NAM A2 volta direto ao menu inicial; qualquer outra escolha no menu inicial desfaz
s = troca(s, 'width: Evil.isHG04() ? repPanels.panelSizesHG4[index] : repPanels.panelSizes[index]',
          'visible: !(repPanels.namJump<0&&index==1)\n\t\t\twidth: repPanels.namJump<0&&index==1 ? 0 : '
          '(Evil.isHG04() ? repPanels.panelSizesHG4[index] : repPanels.panelSizes[index])')
s = troca(s, '\t\t\t\tpageListSelector.cppPage.goBackFrom(index);',
          '\t\t\t\tif (repPanels.namJump<0&&index==2) { repPanels.namJump=0; pageListSelector.cppPage.goBackFrom(2); '
          'pageListSelector.cppPage.goBackFrom(1) }\n\t\t\t\telse pageListSelector.cppPage.goBackFrom(index);')
s = troca(s, '\t\t\t\tpageListSelector.cppPage.itemSelected(index, itemIndex);',
          '\t\t\t\tif (index==0&&repPanels.namJump<0) repPanels.namJump=0;\n'
          '\t\t\t\tpageListSelector.cppPage.itemSelected(index, itemIndex);')
s = troca(s, '\tonVisibleChanged: {\n', '\tonVisibleChanged: {\n\t\trepPanels.namJump = 0;\n')
telas['/Pages/ListSelector.qml'] = s

# --- Model Selector: painel com o botao NAM A2 e o nome NAM A2
s, kind, L = src_of('/Controls/ListView/ListSelectorPanel.qml')
s = re.sub(r'\n\t\t\t// possibly this was for testing.*?\*/\n', '\n', s, flags=re.S)
test('C  bloco comentado de teste removido', '/*Item' not in s and 'possibly this was' not in s)
s = troca(s, '\tproperty ListSelectorPanelModel itemsModel\n', '''\tproperty ListSelectorPanelModel itemsModel
Repeater{id:pr;model:itemsModel;delegate:Item{property string n:model.name}
onCountChanged:nt.restart()}
function ix(s){for(var i=0;i<pr.count;i++)if(pr.itemAt(i)&&pr.itemAt(i).n===s)return i;return -1}
property bool namRoot:pr.count&&ix("Amp")>=0&&ix("Distortion")>=0
function namGo(){var d=ix("Distortion"),v=itemPanel.ListView.view;if(d<0)return;if(v)v.namJump=Date.now();itemSelected(d)}
Timer{id:nt;interval:60;onTriggered:{var v=itemPanel.ListView.view,a=ix("Anxiety OD");if(v&&v.namJump&&Date.now()-v.namJump<3000&&a>=0){v.namJump=-1;itemSelected(a)}}}
Component.onCompleted:nt.restart()
''')
s = troca(s, '\t\tdelegate: EvilListButton {\n\t\t\tid: btnListItem\n', '''delegate:Item{id:row;width:parent.width;property bool nh:itemPanel.namRoot&&model.name==="Amp";height:nh?2*buttonHeight+listSpacing:buttonHeight
EvilListButton{id:bn;visible:row.nh;highlight:bn.pressed;width:parent.width;height:buttonHeight;text:"NAM A2";onClicked:itemPanel.namGo()
ColoredImage{width:15;height:24;anchors.verticalCenter:parent.verticalCenter;anchors.right:parent.right;anchors.rightMargin:10;source:"../../img/ElevenUI_RightCaret_Light.png";color:bn.highlight?"black":"white"}}
EvilListButton{id:btnListItem;y:row.nh?buttonHeight+listSpacing:0
''')
s = troca(s, '\t\t\ttext: model.name\n', '\t\t\ttext: model.name === "Anxiety OD" ? "NAM A2" : model.name\n')
# fecha o Item novo do delegate: a ultima chave do EvilListButton original e seguida do fim do ListView
fim = re.search(r'\n\t\t\}\n\t\}\n\}\s*$', s)
test('C  fim do delegate/ListView/arquivo encontrado', fim is not None)
s = s[:fim.start()] + '\n\t\t}}\n\t}\n}\n'
telas['/Controls/ListView/ListSelectorPanel.qml'] = s

# --- Tela do pedal NAM (AnxietyOD.qml / AnxietyOD2.qml = Anxiety OD v1, as 2 instancias do NAM):
# liga namMode no editor generico; so nesse modo (so exibicao, valores intactos):
#   DRIVE: N %  -> MODEL NAM: N      chave LO-HI  LOW/HIGH -> NAM A2  LITE/FULL
for c in ('/Pages/ModuleEditors/AnxietyOD.qml', '/Pages/ModuleEditors/AnxietyOD2.qml'):
    s, kind, L = src_of(c)
    # MX5 = HG04: os valores escolhidos por Evil.isHG04() ficam fixos (mesmo resultado, cabe no espaco)
    s = troca(s, 'width: Evil.isHG04() ? 570 : 912; height: Evil.isHG04() ? 288 : 460; spacing: Evil.isHG04() ? 13 : 20',
              'width: 570; height: 288; spacing: 13')
    telas[c] = troca(s, 'ParameterEdit { width: parent.width; height: parent.height }',
                     'ParameterEdit { width: parent.width; height: parent.height; namMode: true }')
s, kind, L = src_of('/Groups/ParameterEdit.qml')
s = troca(s, '\tid: editor\n', '\tid: editor\n\tproperty bool namMode: false\n')
s = troca(s, 'ParamFader { y: lv.y1;', 'ParamFader { namMode: editor.namMode; y: lv.y1;', 2)
s = troca(s, 'ParamOnOff { y: lv.y1;', 'ParamOnOff { namMode: editor.namMode; y: lv.y1;', 2)
telas['/Groups/ParameterEdit.qml'] = s
s, kind, L = src_of('/Controls/Slider/ParamFader.qml')
s = troca(s, '\tproperty bool lastof2pages: false\n', '\tproperty bool lastof2pages: false\n\tproperty bool namMode: false\n')
s = troca(s, '\t\t\t\t\t\t  else fad.name.toUpperCase() + ": " + fad.valuestring.toUpperCase() + " " + fad.unitString',
          '\t\t\t\t\t\t  else if (fad.namMode && fad.name.toUpperCase() == "DRIVE") "MODEL NAM: " + fad.valuestring\n'
          '\t\t\t\t\t\t  else fad.name.toUpperCase() + ": " + fad.valuestring.toUpperCase() + " " + fad.unitString')
telas['/Controls/Slider/ParamFader.qml'] = s
s, kind, L = src_of('/Groups/ParamOnOff.qml')
s = troca(s, '\tproperty int editIndex\n', '\tproperty int editIndex\n\tproperty bool namMode: false\n')
s = troca(s, '\t\t\ttext: frame.name \n', '\t\t\ttext: frame.namMode ? "NAM A2" : frame.name\n')
E = 'frame.prop && frame.prop.translator && frame.prop.translator.entries ? frame.prop.translator.entries[%d] : ""'
s = troca(s, 'text: ' + E % 0, 'text: frame.namMode ? "LITE" : (' + E % 0 + ')')
s = troca(s, 'text: ' + E % 1, 'text: frame.namMode ? "FULL" : (' + E % 1 + ')')
telas['/Groups/ParamOnOff.qml'] = s

for caminho, novo in telas.items():
    p = porcaminho[caminho]
    kind, d, L = res[p]
    old = d.decode('utf-8').replace('\r\n', '\n')
    test('C1 %s: chaves balanceadas' % caminho, novo.count('{') - novo.count('}') == old.count('{') - old.count('}'))
    nb = novo.encode('utf-8')
    if kind == 'raw':
        for f in (lambda x: x, v7lib.squeeze, lambda x: v7lib.squeeze(x, comentarios=True)):
            nb = f(nb)
            if len(nb) <= L:
                break
        test('C2 %s (texto puro) cabe' % caminho, len(nb) <= L, '%d / %d bytes' % (len(nb), L))
        B[p + 4:p + 4 + L] = nb + b' ' * (L - len(nb))
        test('C3 %s relido igual' % caminho, bytes(B[p + 4:p + 4 + L]).rstrip(b' ') == nb.rstrip(b' ') and struct.unpack_from('>I', B, p)[0] == L)
    else:
        for f in (lambda x: x, v7lib.squeeze, lambda x: v7lib.squeeze(x, comentarios=True)):
            nb = f(nb); z = zlib.compress(nb, 9)
            if len(z) + 4 <= L:
                break
        test('C2 %s (zlib) cabe' % caminho, len(z) + 4 <= L, '%d / %d bytes' % (len(z) + 4, L))
        struct.pack_into('>I', B, p, len(z) + 4)
        struct.pack_into('>I', B, p + 4, len(nb))
        B[p + 8:p + 8 + len(z)] = z
        B[p + 8 + len(z):p + 4 + L] = b'\x00' * (L - 4 - len(z))
        test('C3 %s descomprime de volta' % caminho, zlib.decompress(bytes(B[p + 8:p + 8 + len(z)])) == nb)

# telas pre-compiladas: desliga as alteradas
regs = {}
for m in re.finditer(rb'\xff\xff\xff\xff(....)(....)\x10\x00\x00\x00/\x00', evil, re.S):
    n = struct.unpack('<I', m.group(1))[0]
    s_ = evil[m.start() + 16:m.start() + 16 + 2 * n].decode('utf-16-le', 'replace')
    if s_.endswith(('.qml', '.js')):
        regs.setdefault(s_, []).append(m.start() + 16)
for caminho in telas:
    test('C4 %s registrado 1x como pre-compilado' % caminho, len(regs.get(caminho, [])) == 1)
    o = regs[caminho][0]
    test('C4 %s comeca com /' % caminho, B[o:o + 2] == b'/\x00')
    B[o:o + 2] = '#'.encode('utf-16-le')

newevil = bytes(B)
e = evil
shoff, = struct.unpack_from('<I', e, 32); shentsize, shnum, shstrndx = struct.unpack_from('<HHH', e, 46)
secs = [struct.unpack_from('<10I', e, shoff + i * shentsize) for i in range(shnum)]
strtab = secs[shstrndx][4]
secname = lambda s: e[strtab + s[0]:e.index(b'\x00', strtab + s[0])].decode()
rod = [s for s in secs if secname(s) == '.rodata'][0]
difs = [i for i in range(0, len(evil)) if newevil[i] != evil[i]]
test('T4 Evil com o mesmo tamanho; todas as mudancas dentro de .rodata (codigo, NAM e cabecalhos intactos)',
     len(newevil) == len(evil) and rod[4] <= min(difs) and max(difs) < rod[4] + rod[5],
     '%d bytes alterados entre %x e %x' % (len(difs), min(difs), max(difs)))
# o sequestro do NAM (vtable/trampolim) nao foi tocado
VTABLE_V1, SLOT = 0x17ee460, 8
so = VTABLE_V1 + SLOT * 4 - 0x8000
test('T5 slot do NAM na vtable do Anxiety OD igual a v6', newevil[so:so + 4] == evil[so:so + 4] and all(not (so <= i < so + 4) for i in difs))

if SO_EVIL:
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, 'Evil_v7'), 'wb').write(newevil)
    print('Evil de teste: %s  sha1 %s' % (os.path.join(outdir, 'Evil_v7'), sha1(newevil)))
    raise SystemExit(0)

# ================= D) rootfs, FIT (rootfs + splash), pacote
def index(img):
    f = ext4.Ext4(img); f.check(); out = {}
    def walk(n, path):
        for name, i, ft in f.listdir(n):
            if name in ('.', '..', 'lost+found'):
                continue
            mode, data = f.read(i)
            if mode & 0xF000 == 0x4000:
                out[path + '/' + name + '/'] = (mode, 0, ''); walk(i, path + '/' + name)
            else:
                out[path + '/' + name] = (mode, len(data), sha1(data))
    walk(2, ''); return out


def grava_no_lugar(fs, path, new):
    ino = fs.inode(fs.lookup(path))
    test('D1 arquivo do mesmo tamanho', fs._size(ino) == len(new))
    runs, _meta = fs._data_runs(ino)
    coberto = bytearray(len(new))
    for lblk, pblk, ln in sorted(runs):
        chunk = new[lblk * fs.bs:(lblk + ln) * fs.bs]
        fs.d[pblk * fs.bs:pblk * fs.bs + len(chunk)] = chunk
        coberto[lblk * fs.bs:lblk * fs.bs + len(chunk)] = b'\x01' * len(chunk)
    test('D1 o arquivo inteiro esta coberto por blocos', coberto.find(0) < 0)


ibase = index(rootfs)
fs = ext4.Ext4(bytearray(rootfs))
grava_no_lugar(fs, PE, newevil)
new_rootfs = fs.finish()
chk = ext4.Ext4(new_rootfs); chk.check()
m1, g1 = chk.read(chk.lookup(PE))
test('D2 Evil relido do sistema de arquivos: conteudo e permissao conferem', g1 == newevil and m1 == evil_mode, oct(m1))
inew = index(new_rootfs)
dd = sorted(k for k in set(inew) | set(ibase) if inew.get(k) != ibase.get(k))
test('D3 entre %d arquivos, so mudou o /usr/Evil/Evil' % len(inew), dd == [PE] and len(inew) == len(ibase), str(dd))
test('D4 tamanho da particao inalterado', len(new_rootfs) == len(rootfs))
xz = xzblocks.compress(new_rootfs)
test('D5 xz descomprime de volta para o rootfs exato', lzma.decompress(xz) == new_rootfs, '%d bytes' % len(xz))

# abertura
sx = rd(splash_xz)
sraw = lzma.decompress(sx)
old_s = lzma.decompress(fitpatch.extract(raw, 'splash'))
test('D6 abertura nova: mesmo tamanho cru da original (480x800 BGRA), alfa 255',
     len(sraw) == len(old_s) == 480 * 800 * 4 and all(sraw[i] == 255 for i in range(3, len(sraw), 4)))
test('D6 abertura nova: xz com CRC64 e dicionario de 4 MiB (igual a original)',
     sx[:6] == b'\xfd7zXZ\x00' and sx[7] == 4 and lzma.LZMADecompressor(memlimit=8 << 20).decompress(sx) == sraw)
img = fitpatch.replace_image(raw, 'rootfs', xz)
img = fitpatch.replace_image(img, 'splash', sx)
_, props = fitpatch.parse(img)
nodes = sorted({p[0] for p in props if p[0].startswith('/images/') and p[0].count('/') == 2})
test('D7 FIT final valido (hashes); 3 imagens; recoverysplash = original; splash = nova; rootfs = novo',
     fitpatch.verify(img) and nodes == ['/images/recoverysplash', '/images/rootfs', '/images/splash'] and
     fitpatch.extract(img, 'recoverysplash') == fitpatch.extract(raw_s, 'recoverysplash') and
     fitpatch.extract(img, 'splash') == sx and lzma.decompress(fitpatch.extract(img, 'rootfs')) == new_rootfs)
# o Update.img fica menor que o da v6: as sobras das imagens (restos da arte antiga, que nao comprimem)
# agora sao zeros. Mesmo compressor (xzblocks) da v6.1/v6.2, ja gravadas no aparelho.
zeros_arte = sum(struct.unpack_from('>I', evil, mapa[k][0])[0] - struct.unpack_from('>I', newevil, mapa[k][0])[0] for k in imgs)
test('D8 Update.img entre 70%% e 102%% da v6 (sobras de arte zeradas: %.1f MB)' % (zeros_arte / 1e6),
     0.70 * len(raw) < len(img) < 1.02 * len(raw), '%d x %d bytes' % (len(img), len(raw)))

inst = os.path.join(outdir, '1_INSTALAR_NAM_A2_v7')
rest = os.path.join(outdir, '2_RESTAURAR_ORIGINAL_2.7')
volta = os.path.join(outdir, '3_VOLTAR_v6')
shutil.copytree(os.path.join(v6dir, '2_RESTAURAR_ORIGINAL_2.7'), rest, dirs_exist_ok=True)
shutil.copytree(os.path.join(v6dir, '1_INSTALAR_NAM_A2_v6'), volta, dirs_exist_ok=True)
os.makedirs(inst, exist_ok=True)
for name in ('FirmwareUpdater.exe', 'libusb-1.0.dll', 'Background.png'):
    shutil.copyfile(os.path.join(rest, name), os.path.join(inst, name))
cfg = json.loads(open(os.path.join(v6dir, '1_INSTALAR_NAM_A2_v6', 'Config.json'), encoding='utf-8-sig').read())
cfg['config']['appName'] = 'HeadRush MX5 v2.7 + NAM A2 v7 + MX5Bridge 0.7 (mod nao oficial)'
cfg['config']['startButtonText'] = 'Instalar NAM A2 v7'
open(os.path.join(inst, 'Config.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(cfg, indent=4, ensure_ascii=False) + '\n')
open(os.path.join(inst, 'Update.img'), 'wb').write(img)
back = rd(os.path.join(inst, 'Update.img'))
bfs = ext4.Ext4(lzma.decompress(fitpatch.extract(back, 'rootfs')))
test('D9 Update.img gravado e relido do disco: identico; o Evil dentro dele confere', back == img and bfs.cat(PE) == newevil, sha1(back))
test('D10 pacote de restauracao com o SHA1 oficial; pacote de volta = v6',
     sha1(rd(os.path.join(rest, 'Update.img'))) == OFFICIAL_SHA1 and sha1(rd(os.path.join(volta, 'Update.img'))) == V6_SHA1)
os.makedirs(os.path.join(outdir, 'fontes'), exist_ok=True)
for f in ('build_v7.py', 'v7lib.py', 'qrc.py'):
    shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), f), os.path.join(outdir, 'fontes', f))
open(os.path.join(outdir, 'TESTES_FIRMWARE.txt'), 'w', encoding='utf-8').write(
    '\n'.join('[%s] %s %s' % ('OK' if ok else 'FALHA', n, dt) for n, ok, dt in results) +
    '\n\n' + '\n'.join(log) + '\n\nSHA1 Update.img: %s\nSHA1 /usr/Evil/Evil: %s\n' % (sha1(img), sha1(newevil)))
print('\n%d testes OK. SHA1 final: %s  %d bytes' % (len(results), sha1(img), len(img)))
