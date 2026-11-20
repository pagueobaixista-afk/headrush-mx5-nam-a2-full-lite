# --- Tela do NAM A2 Pro (BitDist.qml = 8-Bit Crush): no lugar das chaves BIT 1-8 (so valem no modo Cust),
# 3 botoes LITE / FULL / AUTO que escrevem o Bit Mode (A / B / Off); o motor le o padrao do modo.
s, kind, L = src_of('/Pages/ModuleEditors/BitDist.qml')
telas['/Pages/ModuleEditors/BitDist.qml'] = """import QtQuick 2.2
import StateMap 1.0
import "../../Controls"
import "../../Fonts"
import "../../Groups"
import "../../PageController"
BlockDetailsSubPage {
property bool namPro: true
function lab(n, v, u) { var m = {"DRIVE":"INPUT","CRUSH GAIN":"OUTPUT","MIX":"BLEND","BIT MODE":"NAM A2","BIT POWER":"BASS","RESAMPLE":"MODEL NAM","RES SMOOTH":"TREBLE","THRESH":"GATE","CRUSH COMP":"MID","FREQ":"MID FREQ","Q":"MID Q"}
var x = n == "Q" && v < 1 ? "EQ OFF" : n == "BIT MODE" ? (v == "A" ? "LITE" : v == "B" ? "FULL" : "AUTO") : n == "RESAMPLE" ? "" + Math.round(v * 1000) : v + " " + u
return (m[n] || n) + ": " + x }
property var md: Evil.getProperty("/Engine/Patch/8-Bit Crush/Mode")
Column { width: parent.width; spacing: 6
Row { spacing: 9; height: 48
Repeater { model: [["LITE",1],["FULL",2],["AUTO",0]]
Rectangle { width: 184; height: 48
property int ix: md.translator.index
property bool on: modelData[1] ? ix == modelData[1] : (ix == 0 || ix > 2)
color: on ? "#FCD73F" : "#3B3B3D"
ElevenText { anchors.fill: parent; text: modelData[0]; font.pixelSize: 21; color: parent.on ? "black" : "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
MouseArea { anchors.fill: parent; onClicked: md.translator.index = modelData[1] } } } }
ParameterEdit { width: parent.width; height: 217; itemsPerPage: 8 }
}
}
"""
# rotulos do NAM A2 Pro: so quando a tela-mae tem namPro (procura subindo pelos pais)
s, kind, L = src_of('/Controls/Slider/ParamFader.qml')
T6 = '\t' * 6
s = troca(s, '\tproperty bool lastof2pages: false\n',
          '\tproperty bool lastof2pages: false\n\tproperty var pg: { for (var p = parent; p; p = p.parent) if (p.namPro) return p; return null }\n')
s = troca(s, T6 + '  else fad.name.toUpperCase() + ": " + fad.valuestring.toUpperCase() + " " + fad.unitString',
          T6 + '  else if (fad.pg) fad.pg.lab(fad.name.toUpperCase(), fad.valuestring.toUpperCase(), fad.unitString)\n'
          + T6 + '  else fad.name.toUpperCase() + ": " + fad.valuestring.toUpperCase() + " " + fad.unitString')
telas['/Controls/Slider/ParamFader.qml'] = s

