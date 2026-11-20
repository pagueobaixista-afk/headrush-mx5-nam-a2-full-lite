"""Gera o nam-sync.sh da v8 (presets e rigs no 8-Bit Crush = NAM A2 Pro, tudo neutro, sem nivelamento)
a partir do nam-sync.sh da v6.  uso: python gen_namsync.py <nam-sync.sh da v6> <saida>"""
import sys
src = open(sys.argv[1], encoding='utf-8', newline='').read()


def tr(a, b, n=1):
    global src
    if src.count(a) != n:
        sys.exit('trecho %dx (esperado %d): %r' % (src.count(a), n, a[:70]))
    src = src.replace(a, b)


tr('# nam-sync.sh [boot|transfer|deferred]  (v6)', '# nam-sync.sh [boot|transfer|deferred]  (v8: NAM A2 Pro no 8-Bit Crush)')
tr('''#  3) rigs: se a posicao de um modelo mudou (ex.: apagaram um do meio), o Drive do Anxiety OD nos
#     rigs salvos e corrigido para continuar apontando para o MESMO modelo (com copia do banco antes)
#  4) um preset do Anxiety OD por modelo (nome = arquivo sem .nam, Drive = posicao na ordem
#     alfabetica, a mesma do libnam_hook; Level calculado para igualar o volume entre modelos);
#     presets "NNN - ..." sem arquivo sao removidos''', '''#  3) rigs: se a posicao de um modelo mudou (ex.: apagaram um do meio), o Resample do 8-Bit Crush
#     (NAM A2 Pro) nos rigs salvos e corrigido para continuar no MESMO modelo (com copia do banco antes)
#  4) um preset do 8-Bit Crush por modelo (nome = arquivo sem .nam, Resample = posicao/1000 (1 clique = 1 modelo) na ordem
#     alfabetica, a mesma do libnam_hook), tudo neutro: INPUT/OUTPUT 0 dB, EQ plano, BLEND 100%,
#     gate desligado, NAM A2 em AUTO. Sem nivelamento de volume (cada um ajusta).
#     Presets "NNN - ..." sem arquivo sao removidos; os "NNN - ..." antigos do Anxiety OD (v7) tambem''')
tr('#   nam_sync.txt          linhas "alvo=-18" (volume alvo em dB) e/ou "nivelar=0" (nao mexer no Level)\n', '')
tr('TARGET=-18; NIVELAR=1\n', 'TARGET=-18; NIVELAR=0\n')
tr('''(select count(*) from blocks b join old o on o.name = b.name where b.type = 'ANXIETY OD' and json_valid(b.content)
		and json_extract(b.content, '$.data."Anxiety OD".children.Drive.value') is not o.pos) * 10 <= (select count(*) from old) as ok;''',
   '''(select count(*) from blocks b join old o on o.name = b.name where b.type = '8-BIT CRUSH' and json_valid(b.content)
		and abs(ifnull(json_extract(b.content, '$.data."8-Bit Crush".children.Resampling.value'), -9) * 1000 - o.pos) > 0.5) * 10 <= (select count(*) from old) as ok;''')
tr('join old o on o.pos = cast(j.atom as integer)', 'join old o on o.pos = cast(j.atom * 1000 + 0.5 as integer)')
tr('''and j.path glob '$.data.Patch.children."Anxiety OD*".children.Drive' and j.path not glob '*"Anxiety OD V2*\'''',
   '''and j.path glob '$.data.Patch.children."8-Bit Crush*".children.Resampling\'''')
tr("(Drive ' || op || ' -> ' || np || ')' from fix", "(modelo ' || op || ' -> ' || np || ')' from fix")
tr("(Drive ' || op || ')' from fix", "(modelo ' || op || ')' from fix")
for k in range(1, 5):
    tr("(select np from fix f where f.id = rigs.id and f.k = %d and f.np is not null)) where" % k,
       "(select np / 1000.0 from fix f where f.id = rigs.id and f.k = %d and f.np is not null)) where" % k)
a = src.index("insert into log select 'preset removido: ' || name from blocks where type = 'ANXIETY OD'")
b = src.index("commit;\nselect m from log;")
src = src[:a] + """insert into log select 'preset removido: ' || name from blocks where type = '8-BIT CRUSH'
	and name glob '[0-9][0-9][0-9] - *' and name not in (select name from want);
delete from blocks where type = '8-BIT CRUSH'
	and name glob '[0-9][0-9][0-9] - *' and name not in (select name from want);
-- presets de fabrica do 8-Bit Crush nao servem para o NAM A2 Pro (so estes nomes; os do usuario ficam)
insert into log select 'preset de fabrica do 8-Bit Crush removido: ' || name from blocks where type = '8-BIT CRUSH'
	and name in ('+A DEFAULT','+B DEFAULT','+C DEFAULT','+D DEFAULT','+E DEFAULT','+F DEFAULT','+G DEFAULT','+H DEFAULT','+I DEFAULT','+RECTIFY DEFAULT','REPOSSESED','RESAMPLE 1','RESAMPLE 2','RESO CRUSH');
delete from blocks where type = '8-BIT CRUSH'
	and name in ('+A DEFAULT','+B DEFAULT','+C DEFAULT','+D DEFAULT','+E DEFAULT','+F DEFAULT','+G DEFAULT','+H DEFAULT','+I DEFAULT','+RECTIFY DEFAULT','REPOSSESED','RESAMPLE 1','RESAMPLE 2','RESO CRUSH');
-- a v7 guardava os presets do NAM no Anxiety OD; na v8 ele voltou a ser o pedal original
insert into log select 'preset antigo do Anxiety OD (NAM da v7) removido: ' || name from blocks where type = 'ANXIETY OD'
	and name glob '[0-9][0-9][0-9] - *' and name in (select name from want);
delete from blocks where type = 'ANXIETY OD' and name glob '[0-9][0-9][0-9] - *' and name in (select name from want);
insert into log select 'posicao mudou: ' || b.name || ' -> modelo ' || w.pos from blocks b join want w on w.name = b.name
	where b.type = '8-BIT CRUSH' and json_valid(b.content)
	and abs(ifnull(json_extract(b.content, '$.data."8-Bit Crush".children.Resampling.value'), -9) * 1000 - w.pos) > 0.5;
update blocks set content = json_set(content, '$.data."8-Bit Crush".children.Resampling.value',
		(select pos / 1000.0 from want w where w.name = blocks.name))
	where type = '8-BIT CRUSH' and json_valid(content) and name in (select name from want)
	and abs(ifnull(json_extract(content, '$.data."8-Bit Crush".children.Resampling.value'), -9) * 1000
		- (select pos from want w where w.name = blocks.name)) > 0.5;
insert into log select 'novo preset: ' || name || ' (modelo ' || pos || ')' from want
	where name not in (select name from blocks where type = '8-BIT CRUSH');
insert into blocks (id, type, name, content, is_readonly)
	select lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)), 2) || '-a'
		|| substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))), '8-BIT CRUSH', name,
		'{"data":{"8-Bit Crush":{"childorder":["Freq","Q","Drive","FXOut","Mix","ThresholdExp","ThresholdComp","Resampling","AntiAliasing","Mode","BitGainScale","Bit1","Bit2","Bit3","Bit4","Bit5","Bit6","Bit7","Bit8"],"children":{'
		|| '"AntiAliasing":{"type":0,"value":50},"Bit1":{"string":"Thru","type":4},"Bit2":{"string":"Thru","type":4},"Bit3":{"string":"Thru","type":4},"Bit4":{"string":"Thru","type":4},"Bit5":{"string":"Thru","type":4},"Bit6":{"string":"Thru","type":4},"Bit7":{"string":"Thru","type":4},"Bit8":{"string":"Thru","type":4},'
		|| '"BitGainScale":{"type":0,"value":50},"Drive":{"type":0,"value":6},"FXOut":{"type":0,"value":-12},"Freq":{"type":0,"value":500},"Mix":{"type":0,"value":100},"Mode":{"string":"Off","type":4},"Q":{"type":0,"value":50},'
		|| '"Resampling":{"type":0,"value":' || (pos / 1000.0) || '},"ThresholdComp":{"type":0,"value":-15},"ThresholdExp":{"type":0,"value":-60}}}},"info":{"version":"1.0.9"}}', 0
	from want where name not in (select name from blocks where type = '8-BIT CRUSH');
""" + src[b:]
open(sys.argv[2], 'w', encoding='utf-8', newline='').write(src)
print('ok nam-sync v8', len(src))
