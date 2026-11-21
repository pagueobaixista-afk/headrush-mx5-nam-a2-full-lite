"""prepara_v91.py : arte_v91 (arte_v9 + Drop Starcz no lugar da arte do Panner), nam-sync.sh e build_v91.py da v9.1."""
import os, io, shutil, subprocess, sys
from PIL import Image
A = r"C:\Users\Starcz\Documents\arsenal\mx5\arte_MX5"
FW = r"C:\Users\Starcz\Documents\arsenal\mx5\github\mx5-nam-a2\firmware"
if os.path.isdir('arte_v91'): shutil.rmtree('arte_v91')
shutil.copytree('arte_v9', 'arte_v91')
im = Image.open(os.path.join(A, 'drop starcz.png')).convert('RGBA').resize((154, 249), Image.LANCZOS)
q = im.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
b = io.BytesIO(); q.save(b, 'PNG', optimize=True); open(os.path.join('arte_v91', 'Panner.png'), 'wb').write(b.getvalue())
print('Panner.png (Drop Starcz) 154x249, %d bytes' % len(b.getvalue()))

# nam-sync: presets do Drop Starcz no Panner (os 5 de fabrica do Panner nao servem; os do usuario ficam)
s = open(os.path.join(FW, 'v9', 'nam-sync.sh'), encoding='utf-8', newline='').read()
FAB = "('+DEFAULT','MACHINE','PING PONG','STEREO FAKE','VIBRO')"
# presets do Drop Starcz: nome, semitons, TIMBRE %, TCHUG %, TIGHT %
PRE = [('+ DROP 1', 1, 50, 0, 0), ('+ DROP 2', 2, 50, 0, 0), ('+ DROP 3', 3, 50, 0, 0), ('+ DROP 4', 4, 50, 0, 0), ('+ DROP 5', 5, 50, 0, 0),
       ('+ DROP 7', 7, 50, 0, 0), ('+ OITAVA ABAIXO', 12, 50, 30, 20),
       ('DJENT -2', 2, 70, 60, 50), ('DJENT -4', 4, 70, 60, 50), ('DJENT -5', 5, 70, 60, 50),
       ('INDUSTRIAL -4', 4, 100, 80, 30), ('TCHUG MAX -4', 4, 60, 100, 70), ('SUB PESADO -4', 4, 30, 20, 0), ('PALHETA SECA -4', 4, 85, 45, 85)]
def conteudo(st, timbre, tchug, tight):
    return ('{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":%s},'
            '"Pan":{"type":0,"value":%d},"Rate":{"type":0,"value":%s},"Shape":{"type":0,"value":%d},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'
            % (round((st - 1) * 100 / 11, 3), tchug * 2 - 100, round(0.1 * 120 ** (tight / 100), 1), timbre))
import json
for n_, *v_ in PRE: json.loads(conteudo(*v_))
VALS = ',\n\t'.join("('%s','%s')" % (n_, conteudo(*v_)) for n_, *v_ in PRE)
SQL = """-- v9.1: o Drop Starcz mora no Panner; saem os presets de fabrica do Panner e entram os do Drop Starcz
insert into log select 'preset de fabrica do Panner removido: ' || name from blocks where type = 'PANNER' and name in %s;
delete from blocks where type = 'PANNER' and name in %s;
create temp table dn(nm text, ct text);
insert into dn values
	%s;
insert into log select 'novo preset do Drop Starcz: ' || nm from dn where nm not in (select name from blocks where type = 'PANNER');
insert into blocks (id, type, name, content, is_readonly)
	select lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)), 2) || '-a'
		|| substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))), 'PANNER', nm, ct, 0
	from dn where nm not in (select name from blocks where type = 'PANNER');
commit;
""" % (FAB, FAB, VALS)
open('presets_v91.sql', 'w', encoding='utf-8', newline='').write(SQL.replace('insert into log select', '-- ').replace('commit;\n', ''))
assert s.count('\ncommit;\n') == 1
s = s.replace('\ncommit;\n', '\n' + SQL, 1)
os.makedirs(os.path.join(FW, 'v91'), exist_ok=True)
open(os.path.join(FW, 'v91', 'nam-sync.sh'), 'w', encoding='utf-8', newline='').write(s)
print(subprocess.run([sys.executable, os.path.join(FW, 'v91', 'gen_build_v91.py'), os.path.join(FW, 'v8', 'build_v8.py'), os.path.join(FW, 'v91', 'build_v91.py')], capture_output=True, text=True))
