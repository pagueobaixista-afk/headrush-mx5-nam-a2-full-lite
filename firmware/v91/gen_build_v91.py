"""Gera build_v91.py a partir do build_v8.py (mesmo pipeline testado; so muda o que e da v9.1).
uso: python gen_build_v91.py <build_v8.py> <saida build_v91.py>

v9.1 = v8 + motor novo (troca de NAM imediata, Drop Starcz, IR longo) e, nas telas:
  - o Drop Starcz mora no pedal "Panner" (pedal a parte no menu; o "Drop Tune" volta a ser 100% o original):
    nome "Drop Starcz" (lista e tela do pedal), arte propria no lugar da arte do Panner, e os botoes do Panner
    com outro rotulo: DEPTH -> DROP (Down 1..12), SHAPE -> TIMBRE, DELAY -> LEVEL (dB); PAN -> TCHUG (0..100 %), RATE -> TIGHT (0..100 %, com SYNC em OFF);
  - botao "DROP STARCZ" no menu inicial, entre "NAM A2" e "Amp";
  - NAM A2 Pro: FULL por padrao (Bit Mode A, o valor de fabrica, = FULL; B = FULL; C = LITE; Off = AUTO) e gate mostrado/aplicado
    10 dB abaixo do valor guardado (o padrao de fabrica do parametro, -30, passa a valer -40 dB).
(a v9 tinha o Drop Starcz no proprio "Drop Tune", com a arte num arquivo a parte; isso saiu.)"""
import sys
s = open(sys.argv[1], encoding='utf-8').read()


def tr(a, b, n=1):
    global s
    if s.count(a) != n:
        sys.exit('trecho %dx (esperado %d): %r' % (s.count(a), n, a[:80]))
    s = s.replace(a, b)


tr('"""Monta o firmware MX5 NAM A2 v8 = v6 (base) + arte propria + NAM A2 Pro no 8-Bit Crush + nucleos livres + abertura + creditos.',
   '"""Monta o firmware MX5 NAM A2 v9.1 = v8 + troca de NAM imediata + Drop Starcz (no Panner) + IR longo + FULL/gate por padrao.\n'
   '(gerado por gen_build_v91.py a partir do build_v8.py)')
tr('uso: python -I build_v8.py <libdir Bridge> <pasta MX5_NAM_A2_v6> <pasta arte> <splash.xz> <outdir> <libnam_hook.so v8> <nam-sync.sh v8> [--so-evil]',
   'uso: python -I build_v91.py <libdir Bridge> <pasta MX5_NAM_A2_v6> <pasta arte> <splash.xz> <outdir> <libnam_hook.so v9.1> <nam-sync.sh v9.1> [--so-evil]')
tr("VERSAO = 'v8'", "VERSAO = 'v9.1'")
tr("'Evil_v8'", "'Evil_v91'", 2)

# nome mostrado na tela do pedal
tr('''NAM_RX = '.replace(/^8-Bit Crush( 2)?$/, "NAM A2 Pro$1")\'''',
   '''NAM_RX = '.replace(/^8-Bit Crush( 2)?$/, "NAM A2 Pro$1").replace(/^Panner( 2)?$/, "Drop Starcz$1")\'''')

# funcao de enxugar + tela do Panner (Drop Starcz)
tr("# --- Model Selector: guarda o pedido de atalho entre os paineis",
   '''def enxuga(t):
    """Tira espacos que a linguagem nao precisa (fora de textos entre aspas): as telas tem vaga fixa no binario."""
    BS = chr(92)
    linhas = []
    for ln in t.replace(chr(13), '').split(chr(10)):
        ln = ln.strip()
        if not ln:
            continue
        o = []
        q = ''
        i = 0
        while i < len(ln):
            c = ln[i]
            if q:
                o.append(c)
                if c == BS and i + 1 < len(ln):
                    o.append(ln[i + 1])
                    i += 1
                elif c == q:
                    q = ''
            elif c in '"' + "'":
                q = c
                o.append(c)
            elif c in ' ' + chr(9):
                prev = o[-1] if o else ''
                j = i
                while j < len(ln) and ln[j] in ' ' + chr(9):
                    j += 1
                nxt = ln[j] if j < len(ln) else ''
                if prev and nxt and prev not in '{}();,:=?|&' and nxt not in '{}();,:=?|&':
                    o.append(' ')
                i = j - 1
            else:
                o.append(c)
            i += 1
        linhas.append(''.join(o))
    return chr(10).join(linhas) + chr(10)


# --- Pedal na cadeia (ActiveStomp): nome do Drop Starcz (a arte vem da vaga do Panner)
s, kind, L = src_of('/Groups/SignalChainModuleStomps/ActiveStomp.qml')
s = troca(s, 'text: signalChainModule.moduleName.replace(" 2","\\\\n2")',
          'text: signalChainModule.moduleName.replace(/^Panner/,"Drop Starcz").replace(" 2","\\\\n2")')
telas['/Groups/SignalChainModuleStomps/ActiveStomp.qml'] = enxuga(s)

# --- Botao de pe e Hardware Assign: o nome do Panner aparece como Drop Starcz
DSRX = '.replace(/^Panner/,"Drop Starcz").replace(/^PANNER/,"DROP STARCZ")'
s, kind, L = src_of('/Groups/FootSwitchInfoField.qml')
s = troca(s, 'text: fld.highText', 'text: fld.highText' + DSRX)
telas['/Groups/FootSwitchInfoField.qml'] = enxuga(s)
for _t in ('/Controls/ListView/FSAssignmentControl.qml', '/Controls/ListView/AssignmentControl.qml'):
    s, kind, L = src_of(_t)
    s = troca(s, 'text: moduleText', 'text: moduleText' + DSRX)
    telas[_t] = enxuga(s)

# --- O Panner e do tipo "pedal de expressao" (contorno e medidas proprios): como Drop Starcz e desenhado como pedal comum
s, kind, L = src_of('/Groups/SignalChainModuleStomps/SignalChainModule.qml')
s = troca(s, 'property int effectType: effectTypeProp && effectTypeProp.translator ? effectTypeProp.translator.index : 0',
          'property int effectType: moduleTypeName.indexOf("Panner") == 0 ? 0 : effectTypeProp && effectTypeProp.translator ? effectTypeProp.translator.index : 0')
telas['/Groups/SignalChainModuleStomps/SignalChainModule.qml'] = enxuga(s)

# --- Chave SYNC do Drop Starcz: escondida (ligada, ela troca o valor do Rate/TIGHT pelo andamento)
s, kind, L = src_of('/Groups/ParamOnOff.qml')
s = troca(s, 'signal tapped()', 'property bool ds: { if (name.toUpperCase() != "SYNC") return false; for (var p = parent; p; p = p.parent) if (p.namPro) return true; return false }@signal tapped()'.replace('@', chr(10)))
s = troca(s, 'property int inBord: 6', 'property int inBord: 6@opacity: ds ? 0 : 1@enabled: !ds'.replace('@', chr(10)))
telas['/Groups/ParamOnOff.qml'] = enxuga(s)

# --- Tela do Panner = Drop Starcz: os botoes do Panner com rotulos do drop (o motor le os mesmos parametros)
s, kind, L = src_of('/Pages/ModuleEditors/Panner.qml')
telas['/Pages/ModuleEditors/Panner.qml'] = """import QtQuick 2.2
import "../../Groups"
import "../../PageController"
BlockDetailsSubPage{
property bool namPro:true
function lab(n,v,u){var c=n[0],p=" %";return c=="D"?n[2]=="P"?"DROP: DOWN "+(1+Math.round(v*.11)):"LEVEL: "+(v/2500).toFixed(1)+" dB":c=="S"?"TIMBRE: "+v+p:u[0]=="%"?"TCHUG: "+Math.round(v/2+50)+p:"TIGHT: "+(v>0?Math.round(Math.log(v*10)/.047875)+p:"-")}
ParameterEdit{width:570;height:288}}
"""

# --- Model Selector: guarda o pedido de atalho entre os paineis''')
tr("s = troca(s, 'id: repPanels\\n', 'id: repPanels\\n\\t\\tproperty real namJump: 0\\n')",
   "s = troca(s, 'id: repPanels\\n', 'id: repPanels\\n\\t\\tproperty real namJump: 0\\n\\t\\tproperty string namItem: \"\"\\n\\t\\tproperty var namCats: []\\n\\t\\tproperty var namNext: null\\n')")

# painel do Model Selector: dois botoes (NAM A2, DROP STARCZ) acima de "Amp"; procura o item nas categorias
tr('''function namGo(){var d=ix("Distortion"),v=itemPanel.ListView.view;if(d<0)return;if(v)v.namJump=Date.now();itemSelected(d)}
Timer{id:nt;interval:60;onTriggered:{var v=itemPanel.ListView.view,a=ix("8-Bit Crush");if(v&&v.namJump&&Date.now()-v.namJump<3000&&a>=0){v.namJump=-1;itemSelected(a)}}}''',
   '''property var vw:itemPanel.ListView.view
function nT(){while(vw&&vw.namCats.length){var d=ix(vw.namCats.shift());if(d>=0){vw.namJump=1;itemSelected(d);return}}if(vw)vw.namJump=0}
function namGo(i,c){if(vw){vw.namItem=i;vw.namCats=c;vw.namNext=nT;nT()}}
Timer{id:nt;interval:60;onTriggered:{if(!vw||vw.namJump<=0||namRoot)return;var a=ix(vw.namItem);if(a>=0){vw.namJump=-1;itemSelected(a)}else vw.namNext()}}''')
tr('''delegate:Item{id:row;width:parent.width;property bool nh:itemPanel.namRoot&&model.name==="Amp";height:nh?2*buttonHeight+listSpacing:buttonHeight
EvilListButton{id:bn;visible:row.nh;highlight:bn.pressed;width:parent.width;height:buttonHeight;text:"NAM A2";onClicked:itemPanel.namGo()
ColoredImage{width:15;height:24;anchors.verticalCenter:parent.verticalCenter;anchors.right:parent.right;anchors.rightMargin:10;source:"../../img/ElevenUI_RightCaret_Light.png";color:bn.highlight?"black":"white"}}
EvilListButton{id:btnListItem;y:row.nh?buttonHeight+listSpacing:0
''', '''delegate:Item{id:row;width:parent.width;property bool nh:itemPanel.namRoot&&model.name==="Amp";height:nh?3*buttonHeight+2*listSpacing:buttonHeight
Repeater{model:row.nh?[["NAM A2","8-Bit Crush",["Distortion"]],["DROP STARCZ","Panner",["Modulation","Expression","Dynamics/EQ"]]]:[]
EvilListButton{y:index*(buttonHeight+listSpacing);highlight:pressed;width:row.width;height:buttonHeight;text:modelData[0];onClicked:itemPanel.namGo(modelData[1],modelData[2])
ColoredImage{width:15;height:24;x:parent.width-25;y:(parent.height-24)/2;source:"../../img/ElevenUI_RightCaret_Light.png";color:parent.highlight?"black":"white"}}}
EvilListButton{id:btnListItem;y:row.nh?2*(buttonHeight+listSpacing):0
''')
tr('''s = troca(s, '\\t\\t\\ttext: model.name\\n', '\\t\\t\\ttext: model.name === "8-Bit Crush" ? "NAM A2 Pro" : model.name\\n')''',
   '''s = troca(s, '\\t\\t\\ttext: model.name\\n', '\\t\\t\\ttext: model.name === "8-Bit Crush" ? "NAM A2 Pro" : model.name === "Panner" ? "Drop Starcz" : model.name\\n')''')

# tela do NAM A2 Pro: FULL e o padrao (Bit Mode A), LITE = C, AUTO = Off; gate mostrado 10 dB abaixo
tr('''var x = n == "Q" && v < 1 ? "EQ OFF" : n == "BIT MODE" ? (v == "A" ? "LITE" : v == "B" ? "FULL" : "AUTO") : n == "RESAMPLE" ? "" + Math.round(v * 1000) : v + " " + u''',
   '''var x = n == "Q" && v < 1 ? "EQ OFF" : n == "BIT MODE" ? (v == "A" || v == "B" ? "FULL" : v == "C" ? "LITE" : "AUTO") : n == "RESAMPLE" ? "" + Math.round(v * 1000) : n == "THRESH" ? (v <= -59 ? "OFF" : v - 10 + " " + u) : v + " " + u''')
tr('''Repeater { model: [["LITE",1],["FULL",2],["AUTO",0]]''', '''Repeater { model: [["LITE",3,3,3],["FULL",1,1,2],["AUTO",0,4,99]]''')
tr('''property bool on: modelData[1] ? ix == modelData[1] : (ix == 0 || ix > 2)''', '''property bool on: ix >= modelData[2] && ix <= modelData[3] || !ix && !modelData[1]''')

# o painel do Model Selector ficou maior que a vaga (texto puro, 3116 bytes): enxuga os espacos
tr("telas['/Controls/ListView/ListSelectorPanel.qml'] = s", '''s = enxuga(s)
# ainda nao cabe: tira o que nao e usado no MX5 (o MX5 e o aparelho "HG04"; os outros valores sao de modelos maiores)
for a_, b_ in (('import QtQuick.Controls 1.2\\n', ''), ('import QtQuick.Layouts 1.1\\n', ''),
               ('Evil.isHG04()?54:90', '54'), ('Evil.isHG04()?3:5', '3'),
               ('Evil.isHG04()?457 - buttonHeight - listSpacing:731 - buttonHeight - listSpacing', '457-buttonHeight-listSpacing'),
               ('Evil.isHG04()?15:21', '15'), ('Evil.isHG04()?24:37', '24'), ('Evil.isHG04()?10:16', '10')):
    s = troca(s, a_, b_)
test('C  tela do seletor: sem restos de outros modelos', 'isHG04' not in s)
telas['/Controls/ListView/ListSelectorPanel.qml'] = s''')
# a tela do pedal na cadeia ja vem com o pre-compilado desligado na base v6 (registrada como XctiveStomp)
tr("    test('C4 %s registrado 1x como pre-compilado' % caminho, len(regs.get(caminho, [])) == 1)",
   "    if caminho.endswith('/ActiveStomp.qml') and caminho not in regs:\n"
   "        test('C4 ActiveStomp: pre-compilado ja desligado na base', len(regs.get(caminho.replace('/ActiveStomp', '/XctiveStomp'), [])) == 1)\n"
   "        continue\n"
   "    test('C4 %s registrado 1x como pre-compilado' % caminho, len(regs.get(caminho, [])) == 1)")
# a tela do NAM A2 Pro tambem precisa enxugar (vaga de 784 bytes comprimidos)
tr('# rotulos do NAM A2 Pro: so quando a tela-mae tem namPro', "telas['/Pages/ModuleEditors/BitDist.qml'] = enxuga(telas['/Pages/ModuleEditors/BitDist.qml'])\n"
   "# rotulos do NAM A2 Pro: so quando a tela-mae tem namPro")
# copia das telas alteradas, para conferencia
tr('for caminho, novo in telas.items():', 'os.makedirs(os.path.join(outdir, "telas"), exist_ok=True)\n'
   'for caminho, novo in telas.items():\n'
   '    open(os.path.join(outdir, "telas", caminho.strip("/").replace("/", "__")), "w", encoding="utf-8", newline="").write(novo)')
# pacote: nomes e fontes da v9.1
tr("inst = os.path.join(outdir, '1_INSTALAR_NAM_A2_v8')", "inst = os.path.join(outdir, '1_INSTALAR_NAM_A2_v9.1')")
tr("'HeadRush MX5 v2.7 + NAM A2 v8 (Pro no 8-Bit Crush) + MX5Bridge 0.7 (mod nao oficial)'",
   "'HeadRush MX5 v2.7 + NAM A2 v9.1 (NAM Pro, Drop Starcz, IR longo) + MX5Bridge 0.7 (mod nao oficial)'")
tr("cfg['config']['startButtonText'] = 'Instalar NAM A2 v8'", "cfg['config']['startButtonText'] = 'Instalar NAM A2 v9.1'")
tr("for f in ('build_v8.py', 'gen_build_v8.py', 'bloco_tela_v8.py', 'gen_namsync.py', 'nam-sync.sh', 'v7lib.py', 'qrc.py'):",
   "for f in ('build_v91.py', 'gen_build_v91.py', 'bloco_tela_v8.py', 'nam-sync.sh', 'v7lib.py', 'qrc.py'):")
open(sys.argv[2], 'w', encoding='utf-8').write(s)
print('ok build_v91', len(s))
