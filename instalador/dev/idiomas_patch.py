"""Aplica no instalar.py o suporte a 3 idiomas (pt / en / es). Rodar uma vez: python idiomas_patch.py ../instalar.py"""
import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
if 'def tr(t)' in s:
    sys.exit('ja aplicado')

BLOCO = r'''# --- idiomas: o texto e escrito em portugues e traduzido aqui (trechos fixos -> en / es)
LANG = 'pt'
FRASES = [
    ('instalador (nao oficial; use por sua conta e risco)', 'installer (unofficial; use at your own risk)', 'instalador (no oficial; uselo bajo su propio riesgo)'),
    ('Qual arte voce quer?', 'Which art do you want?', 'Que arte quiere?'),
    ('arte Starcz: pedais e tela de abertura novos, desenhados para o mod (recomendado)', 'Starcz art: new pedals and boot screen, drawn for the mod (recommended)', 'arte Starcz: pedales y pantalla de inicio nuevos, dibujados para el mod (recomendado)'),
    ('arte original de fabrica da HeadRush (so o NAM A2 Pro e os menus novos)', 'original HeadRush factory art (only NAM A2 Pro and the new menus)', 'arte original de fabrica de HeadRush (solo NAM A2 Pro y los menus nuevos)'),
    ('Digite 1 ou 2 e aperte Enter', 'Type 1 or 2 and press Enter', 'Escriba 1 o 2 y pulse Enter'),
    ('original de fabrica', 'factory original', 'original de fabrica'),
    ('Usando o atualizador oficial ja baixado:', 'Using the official updater already downloaded:', 'Usando el actualizador oficial ya descargado:'),
    ('Abrindo o atualizador oficial', 'Opening the official updater', 'Abriendo el actualizador oficial'),
    ('Abrindo o sistema de arquivos do firmware oficial', 'Opening the official firmware file system', 'Abriendo el sistema de archivos del firmware oficial'),
    ('Gravando ', 'Writing ', 'Escribiendo '),
    (' arquivos ...', ' files ...', ' archivos ...'),
    ('Tudo conferido. Comprimindo (leva um ou dois minutos)', 'All verified. Compressing (takes a minute or two)', 'Todo verificado. Comprimiendo (tarda uno o dos minutos)'),
    ('Arte do editor:', 'Editor art:', 'Arte del editor:'),
    (' imagens em ', ' images in ', ' imagenes en '),
    ('ERRO:', 'ERROR:', 'ERROR:'),
    ('PRONTO:', 'DONE:', 'LISTO:'),
    ('Para gravar:', 'To flash it:', 'Para grabarlo:'),
    ('Ligue o MX5 na tomada e no computador pelo USB.', 'Plug the MX5 into power and into the computer over USB.', 'Conecte el MX5 a la corriente y al ordenador por USB.'),
    ('No MX5:', 'On the MX5:', 'En el MX5:'),
    ('Abra FirmwareUpdater.exe nessa pasta e clique em', 'Open FirmwareUpdater.exe in that folder and click', 'Abra FirmwareUpdater.exe en esa carpeta y haga clic en'),
    ('Nao desconecte ate terminar.', 'Do not disconnect until it finishes.', 'No desconecte hasta que termine.'),
    ('Para voltar ao original: grave o atualizador oficial da HeadRush 2.7.', 'To go back to stock: flash the official HeadRush 2.7 updater.', 'Para volver al original: grabe el actualizador oficial de HeadRush 2.7.'),
    ('Para ter a outra arte: rode o instalador de novo e escolha a outra opcao.', 'For the other art: run the installer again and pick the other option.', 'Para la otra arte: ejecute el instalador otra vez y elija la otra opcion.'),
    ('Se o MX5 nao ligar: segure os footswitches 1 e 2 ao ligar e grave o atualizador oficial.', 'If the MX5 does not boot: hold footswitches 1 and 2 while powering on and flash the official updater.', 'Si el MX5 no arranca: mantenga los footswitches 1 y 2 al encenderlo y grabe el actualizador oficial.'),
    ('Aperte Enter para fechar.', 'Press Enter to close.', 'Pulse Enter para cerrar.'),
    ('arquivo nao encontrado:', 'file not found:', 'archivo no encontrado:'),
    ('este nao e o firmware oficial HeadRush MX5 2.7 (use o atualizador baixado do site da HeadRush)', 'this is not the official HeadRush MX5 2.7 firmware (use the updater downloaded from the HeadRush website)', 'este no es el firmware oficial HeadRush MX5 2.7 (use el actualizador descargado del sitio de HeadRush)'),
    ('o Update.img oficial esta danificado', 'the official Update.img is damaged', 'el Update.img oficial esta danado'),
    ('nao e o do firmware oficial 2.7', 'is not the one from the official 2.7 firmware', 'no es el del firmware oficial 2.7'),
    ('conferencia', 'check', 'verificacion'),
    ('falhou', 'failed', 'fallo'),
    ('Arte:', 'Art:', 'Arte:'),
]


def tr(t):
    if LANG == 'pt':
        return t
    k = 1 if LANG == 'en' else 2
    for f in FRASES:
        t = t.replace(f[0], f[k])
    return t


def escolhe_idioma():
    global LANG
    for a, l in (('--pt', 'pt'), ('--en', 'en'), ('--es', 'es')):
        if a in sys.argv:
            LANG = l
            return
    auto = 'en'
    try:
        import ctypes
        pri = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        auto = {0x16: 'pt', 0x0A: 'es'}.get(pri, 'en')
    except Exception:
        pass
    padrao = {'pt': '1', 'en': '2', 'es': '3'}[auto]
    print('Idioma / Language / Idioma:  1 = Portugues   2 = English   3 = Espanol', flush=True)
    try:
        r = input('[%s]: ' % padrao).strip() or padrao
    except EOFError:
        r = padrao
    LANG = {'1': 'pt', '2': 'en', '3': 'es'}.get(r, auto)


def diga(*a):
    print(tr(' '.join(str(x) for x in a)), flush=True)
'''


def troca(velho, novo):
    global s
    if s.count(velho) != 1:
        sys.exit('trecho %dx: %r' % (s.count(velho), velho[:60]))
    s = s.replace(velho, novo)


troca("def diga(*a):\n    print(' '.join(str(x) for x in a), flush=True)\n", BLOCO)
troca("esc = input('Digite 1 ou 2 e aperte Enter [1]: ')", "esc = input(tr('Digite 1 ou 2 e aperte Enter [1]: '))")
troca("def main():\n    diga(", "def main():\n    escolhe_idioma()\n    diga(")
s, n = re.subn(r"input\('\\nAperte Enter para fechar\.'\)", "input(tr('\\\\nAperte Enter para fechar.'))", s)
if n != 1:
    sys.exit('Enter: %d' % n)
s = s.replace('Opcoes de linha de comando: --starcz / --fabrica."""', 'Opcoes de linha de comando: --starcz / --fabrica, --pt / --en / --es (idioma)."""')
open(p, 'w', encoding='utf-8').write(s)
print('ok idiomas')
