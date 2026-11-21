#!/bin/sh
# nam-sync.sh [boot|transfer|deferred]  (v9: NAM A2 Pro no 8-Bit Crush)
# Chamado na partida (runevil) e toda vez que o drive USB e remontado (mount_usb_img: partida e
# saida da transferencia USB / Sync).
#  1) .nam sem prefixo "NNN - " ganha o proximo numero livre (vai para o fim da lista)
#  2) .nam que nao e um modelo valido (arquivo truncado, vazio, nao-JSON) vai para NAM/_com_defeito
#  3) rigs: se a posicao de um modelo mudou (ex.: apagaram um do meio), o Resample do 8-Bit Crush
#     (NAM A2 Pro) nos rigs salvos e corrigido para continuar no MESMO modelo (com copia do banco antes)
#  4) um preset do 8-Bit Crush por modelo (nome = arquivo sem .nam, Resample = posicao/1000 (1 clique = 1 modelo) na ordem
#     alfabetica, a mesma do libnam_hook), tudo neutro: INPUT/OUTPUT 0 dB, EQ plano, BLEND 100%,
#     gate em -40 dB (valor guardado -30; a v9 aplica 10 dB abaixo), NAM A2 em FULL (Bit Mode A). Sem nivelamento de volume (cada um ajusta).
#     Presets "NNN - ..." sem arquivo sao removidos; os "NNN - ..." antigos do Anxiety OD (v7) tambem
#  5) com o aplicativo aberto (saida da transferencia USB) so os passos 1 e 2 rodam na hora: o
#     aplicativo regrava o banco a partir da memoria ao terminar o proprio Sync, e o que fosse
#     gravado antes disso se perderia. Os passos 3 e 4 rodam depois, num processo separado
#     (modo deferred) que espera o banco parar; se algo mudou, ele reinicia o aplicativo
# Nunca impede a partida: qualquer falha so encerra este script. Registro em /tmp/nam_sync.log.
# Opcoes, em arquivos na pasta NAM do drive:
#   nam_sync_off.txt      desliga tudo        nam_restart_off.txt   desliga so o reinicio
#   (o script escreve NAM/nam_sync_relatorio.txt quando muda alguma coisa)
MODE=${1:-boot}
unset LD_PRELOAD   # chamado de dentro do Evil herdaria o libnam_preload em cada comando
SIG=/tmp/nam_sync.sig
NAM=${NAM_SYNC_DIR:-/media/az01-internal/Evil/usb_mnt/NAM}
DB=${NAM_SYNC_DB:-/media/az01-internal/Evil/evil.db}
STATE=${NAM_SYNC_STATE:-/media/az01-internal/Evil/nam_sync.state}
BAK=${NAM_SYNC_BAK:-/media/az01-internal/Evil/nam_sync_antes_dos_rigs.db}
SQL=/usr/Evil/Scripts/mx5bridge-sqlite3
T=/tmp/nam_sync.$$
[ -d "$NAM" ] && [ -f "$DB" ] && [ -x "$SQL" ] || { echo "nada a fazer (sem pasta NAM, banco ou sqlite)"; exit 0; }
[ -e "$NAM/nam_sync_off.txt" ] && { echo "desligado por nam_sync_off.txt"; exit 0; }

evil_pids() { for p in /proc/[0-9]*; do [ "$(cat "$p/comm" 2>/dev/null)" = "Evil" ] && echo "${p#/proc/}"; done; }

wait_quiet() {
	# espera o banco ficar parado (o aplicativo importa rigs/presets e regrava o banco no Sync)
	sleep 6; quiet=0; n=0; last=
	while [ $n -lt 180 ] && [ $quiet -lt 8 ]; do
		cur=$(ls -ln --full-time "$DB" "$DB-journal" 2>&1)
		if [ "$cur" = "$last" ] && [ ! -e "$DB-journal" ]; then quiet=$((quiet + 1)); else quiet=0; fi
		last=$cur; n=$((n + 1)); sleep 1
	done
	WAITED=$((n + 6))
}
restart_app() {
	echo "reiniciando o aplicativo"
	sync; mkdir -p /tmp/mx5bridge; touch /tmp/mx5bridge/restart
	for p in $(evil_pids); do kill -TERM $p; done
}
WAITED=0
[ "$MODE" = deferred ] && wait_quiet

echo "== $MODE $(date +%H:%M:%S)$([ $WAITED -gt 0 ] && echo " (esperou $WAITED s o banco parar)")"
( sleep 45; kill -9 $$ 2>/dev/null ) >/dev/null 2>&1 &
WD=$!
trap 'kill $WD 2>/dev/null; rm -f $T.*' EXIT
DRY=0; [ "$NAM_SYNC_DRY" = 1 ] && { DRY=1; echo "(simulacao: nada e gravado)"; }

listar() { ls -1 "$NAM" 2>/dev/null | grep -i '[.]nam$' | grep -v '^[.]_' | LC_ALL=C sort; }
q() { printf '%s' "$1" | sed "s/'/''/g"; }
say() { echo "$1"; echo "$1" >> $T.rep; }

listar > $T.lst
[ -s $T.lst ] || { echo "nenhum .nam"; exit 0; }

TARGET=-18; NIVELAR=0
if [ -f "$NAM/nam_sync.txt" ]; then
	v=$(tr -d '\r' < "$NAM/nam_sync.txt" | sed -n 's/^alvo=\(-\{0,1\}[0-9]\{1,2\}\)$/\1/p' | head -n 1)
	[ -n "$v" ] && TARGET=$v
	tr -d '\r' < "$NAM/nam_sync.txt" | grep -q '^nivelar=0$' && NIVELAR=0
fi

# 1) numerar os novos
max=-1
while IFS= read -r f; do
	case "$f" in [0-9][0-9][0-9]" - "*)
		n=$((1${f%% - *} - 1000)); [ $n -gt $max ] && max=$n ;;
	esac
done < $T.lst
ren=0
while IFS= read -r f; do
	case "$f" in [0-9][0-9][0-9]" - "*) continue ;; esac
	[ $max -ge 998 ] && { echo "sem numeros livres para: $f"; continue; }
	max=$((max + 1)); new=$(printf '%03d - %s' $max "$f")
	[ $DRY = 1 ] && { echo "numeraria: $new"; continue; }
	if [ ! -e "$NAM/$new" ] && mv "$NAM/$f" "$NAM/$new"; then say "numerado: $new"; ren=1; else echo "nao consegui numerar: $f"; fi
done < $T.lst
[ $ren -eq 1 ] && { sync; listar > $T.lst; }

# 2) validar cada arquivo e ler o volume (metadata.loudness) -- uma unica chamada ao sqlite
while IFS= read -r f; do
	echo "select case when json_valid(x) then (json_extract(x,'\$.architecture') is not null and ifnull(json_type(x,'\$.config'),'') = 'object') else 0 end, case when json_valid(x) and json_type(x,'\$.metadata.loudness') in ('real','integer') then json_extract(x,'\$.metadata.loudness') else '' end, '$(q "$f")' from (select cast(readfile('$(q "$NAM/$f")') as text) x);"
done < $T.lst > $T.chk.sql
"$SQL" -separator '|' :memory: < $T.chk.sql > $T.chk 2>/dev/null
total=$(wc -l < $T.lst); lidos=$(wc -l < $T.chk); ruins=$(grep -c '^0|' $T.chk)
if [ "$lidos" != "$total" ]; then
	echo "validacao nao rodou ($lidos de $total): nenhum arquivo e descartado, volume nao e calculado"
	sed 's/^/1||/' $T.lst > $T.chk
elif [ "$ruins" -ge "$total" ]; then
	echo "validacao suspeita (todos reprovados): nenhum arquivo e descartado"
	sed -i 's/^0|/1|/' $T.chk
elif [ "$ruins" -gt 0 ]; then
	grep '^0|' $T.chk > $T.bad
	while IFS='|' read -r ok loud f; do
		if [ $DRY = 1 ]; then echo "com defeito (iria para NAM/_com_defeito): $f"
		elif mkdir -p "$NAM/_com_defeito" && mv "$NAM/$f" "$NAM/_com_defeito/$f"; then say "COM DEFEITO, movido para NAM/_com_defeito: $f"
		else echo "com defeito, mas nao consegui mover: $f"; fi
	done < $T.bad
	[ $DRY = 1 ] || sync
fi

# aplicativo aberto: agora so arquivos; o banco fica para o processo separado (ver passo 5 no topo)
if [ "$MODE" != deferred ] && [ $DRY = 0 ] && [ -n "$(evil_pids)" ]; then
	echo "aplicativo aberto: o banco sera atualizado quando ele terminar o Sync"
	rm -f /tmp/nam_sync.rep_files; [ -s $T.rep ] && cp $T.rep /tmp/nam_sync.rep_files
	setsid sh "$0" deferred >>/tmp/nam_sync.log 2>&1 </dev/null &
	exit 0
fi
if [ "$MODE" = deferred ] && [ -s /tmp/nam_sync.rep_files ]; then
	cat /tmp/nam_sync.rep_files >> $T.rep; rm -f /tmp/nam_sync.rep_files
fi

# 3) e 4) rigs e presets, numa transacao
{
	echo "create temp table cfg(t real, niv integer); insert into cfg values($TARGET, $NIVELAR);"
	echo "create temp table want(name text primary key collate nocase, pos integer, loud real, level integer default 50);"
	r=0
	grep '^1|' $T.chk > $T.good
	while IFS='|' read -r ok loud f; do
		[ $r -gt 100 ] && break
		echo "insert or ignore into want(name, pos, loud) values('$(q "${f%.*}")', $r, ${loud:-NULL});"
		r=$((r + 1))
	done < $T.good
	echo "create temp table old(name text primary key collate nocase, pos integer, level integer);"
	if [ -f "$STATE" ]; then
		r=0
		while IFS='|' read -r lvl name; do
			case "$lvl" in ''|*[!0-9]*) continue ;; esac
			echo "insert or ignore into old values('$(q "$name")', $r, $lvl);"
			r=$((r + 1))
		done < "$STATE"
	fi
	cat <<'SQLEOF'
create temp table lv(level integer, cdb integer);
insert into lv values (1,-3398),(2,-2796),(3,-2444),(4,-2194),(5,-2000),(6,-1842),(7,-1708),(8,-1592),(9,-1489),(10,-1398),(11,-1315),(12,-1240),(13,-1170),(14,-1106),(15,-1046),(16,-990),(17,-937),(18,-887),(19,-840),(20,-796),(21,-754),(22,-713),(23,-674),(24,-638),(25,-602),(26,-568),(27,-535),(28,-504),(29,-473),(30,-444),(31,-415),(32,-388),(33,-361),(34,-335),(35,-310),(36,-285),(37,-262),(38,-238),(39,-216),(40,-194),(41,-172),(42,-151),(43,-131),(44,-111),(45,-92),(46,-72),(47,-54),(48,-35),(49,-18);
update want set level = case
	when (select niv from cfg) = 0 or loud is null then 50
	when (select t from cfg) - loud >= 0 then min(100, cast(50 + ((select t from cfg) - loud) / 12.0 * 50 + 0.5 as integer))
	else (select level from lv order by abs(cdb - ((select t from cfg) - want.loud) * 100) limit 1) end;
create temp table log(m text);
-- o estado guardado so vale se bate com os presets que estao no banco (senao: banco restaurado etc.)
create temp table st as select
	(select count(*) from old) > 0 and
	(select count(*) from blocks b join old o on o.name = b.name where b.type = '8-BIT CRUSH' and json_valid(b.content)
		and abs(ifnull(json_extract(b.content, '$.data."8-Bit Crush".children.Resampling.value'), -9) * 1000 - o.pos) > 0.5) * 10 <= (select count(*) from old) as ok;
create temp table fix as
	select r.id id, r.name rn, j.fullkey p, o.name mn, o.pos op, w.pos np,
		row_number() over (partition by r.id order by j.fullkey) k
	from rigs r, json_tree(r.content) j
	join old o on o.pos = cast(j.atom * 1000 + 0.5 as integer)
	left join want w on w.name = o.name
	where (select ok from st) and json_valid(r.content) and j.key = 'value' and j.type in ('integer', 'real')
		and j.path glob '$.data.Patch.children."8-Bit Crush*".children.Resampling'
		and (w.pos is null or w.pos != o.pos);
begin immediate;
insert into log select 'estado guardado nao bate com o banco: rigs nao foram mexidos' where (select count(*) from old) > 0 and not (select ok from st);
insert into log select 'rig corrigido: ' || rn || ': ' || mn || ' (modelo ' || op || ' -> ' || np || ')' from fix where np is not null;
insert into log select 'ATENCAO rig ' || rn || ' usa um modelo que saiu da pasta: ' || mn || ' (modelo ' || op || ')' from fix where np is null;
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 1 and f.np is not null), (select np / 1000.0 from fix f where f.id = rigs.id and f.k = 1 and f.np is not null)) where id in (select id from fix where k = 1 and np is not null);
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 2 and f.np is not null), (select np / 1000.0 from fix f where f.id = rigs.id and f.k = 2 and f.np is not null)) where id in (select id from fix where k = 2 and np is not null);
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 3 and f.np is not null), (select np / 1000.0 from fix f where f.id = rigs.id and f.k = 3 and f.np is not null)) where id in (select id from fix where k = 3 and np is not null);
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 4 and f.np is not null), (select np / 1000.0 from fix f where f.id = rigs.id and f.k = 4 and f.np is not null)) where id in (select id from fix where k = 4 and np is not null);
insert into log select 'preset removido: ' || name from blocks where type = '8-BIT CRUSH'
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
		|| '"BitGainScale":{"type":0,"value":50},"Drive":{"type":0,"value":6},"FXOut":{"type":0,"value":-12},"Freq":{"type":0,"value":500},"Mix":{"type":0,"value":100},"Mode":{"string":"A","type":4},"Q":{"type":0,"value":50},'
		|| '"Resampling":{"type":0,"value":' || (pos / 1000.0) || '},"ThresholdComp":{"type":0,"value":-15},"ThresholdExp":{"type":0,"value":-30}}}},"info":{"version":"1.0.9"}}', 0
	from want where name not in (select name from blocks where type = '8-BIT CRUSH');
-- v9.1: o Drop Starcz mora no Panner; saem os presets de fabrica do Panner e entram os do Drop Starcz
insert into log select 'preset de fabrica do Panner removido: ' || name from blocks where type = 'PANNER' and name in ('+DEFAULT','MACHINE','PING PONG','STEREO FAKE','VIBRO');
delete from blocks where type = 'PANNER' and name in ('+DEFAULT','MACHINE','PING PONG','STEREO FAKE','VIBRO');
create temp table dn(nm text, ct text);
insert into dn values
	('+ DROP 1','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":0.0},"Pan":{"type":0,"value":-100},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('+ DROP 2','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":9.091},"Pan":{"type":0,"value":-100},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('+ DROP 3','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":18.182},"Pan":{"type":0,"value":-100},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('+ DROP 4','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":27.273},"Pan":{"type":0,"value":-100},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('+ DROP 5','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":36.364},"Pan":{"type":0,"value":-100},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('+ DROP 7','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":54.545},"Pan":{"type":0,"value":-100},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('+ OITAVA ABAIXO','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":100.0},"Pan":{"type":0,"value":-40},"Rate":{"type":0,"value":0.3},"Shape":{"type":0,"value":50},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('DJENT -2','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":9.091},"Pan":{"type":0,"value":20},"Rate":{"type":0,"value":1.1},"Shape":{"type":0,"value":70},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('DJENT -4','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":27.273},"Pan":{"type":0,"value":20},"Rate":{"type":0,"value":1.1},"Shape":{"type":0,"value":70},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('DJENT -5','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":36.364},"Pan":{"type":0,"value":20},"Rate":{"type":0,"value":1.1},"Shape":{"type":0,"value":70},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('INDUSTRIAL -4','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":27.273},"Pan":{"type":0,"value":60},"Rate":{"type":0,"value":0.4},"Shape":{"type":0,"value":100},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('TCHUG MAX -4','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":27.273},"Pan":{"type":0,"value":100},"Rate":{"type":0,"value":2.9},"Shape":{"type":0,"value":60},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('SUB PESADO -4','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":27.273},"Pan":{"type":0,"value":-60},"Rate":{"type":0,"value":0.1},"Shape":{"type":0,"value":30},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}'),
	('PALHETA SECA -4','{"data":{"Panner":{"childorder":["Sync","Pan","Delay","Rate","Shape","Depth"],"children":{"Delay":{"type":0,"value":0},"Depth":{"type":0,"value":27.273},"Pan":{"type":0,"value":-10},"Rate":{"type":0,"value":5.9},"Shape":{"type":0,"value":85},"Sync":{"state":false,"type":1}}}},"info":{"version":"1.0.9"}}');
insert into log select 'novo preset do Drop Starcz: ' || nm from dn where nm not in (select name from blocks where type = 'PANNER');
insert into blocks (id, type, name, content, is_readonly)
	select lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)), 2) || '-a'
		|| substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))), 'PANNER', nm, ct, 0
	from dn where nm not in (select name from blocks where type = 'PANNER');
commit;
select m from log;
select (select count(*) from want) || ' modelos, ' || (select count(*) from log) || ' linhas de alteracao';
select 'STATE|' || level || '|' || name from want order by pos;
SQLEOF
} > $T.sql
# copia do banco antes de mexer em rigs: so quando a lista mudou em relacao ao estado guardado
if [ $DRY = 0 ] && [ -f "$STATE" ]; then
	sed 's/^[0-9]*|//' "$STATE" > $T.oldn
	sed 's/^1|[^|]*|//; s/[.][^.]*$//' $T.good > $T.newn
	if ! cmp -s $T.oldn $T.newn; then
		"$SQL" -cmd ".timeout 4000" "file:$DB?mode=ro" ".backup '$BAK'" >/dev/null 2>&1 && echo "copia do banco antes das mudancas: $BAK"
	fi
fi
if [ $DRY = 1 ]; then
	sed -i 's/^commit;$/select m from log; select "(simulacao) " || count(*) || " linhas de alteracao" from log; rollback;/' $T.sql
fi
if "$SQL" -bail -cmd ".timeout 4000" "$DB" < $T.sql > $T.out 2>&1; then
	grep -v '^STATE|' $T.out
	grep -v '^STATE|' $T.out | grep -v ' modelos, [0-9]* linhas de alteracao$' >> $T.rep
	if [ $DRY = 0 ] && grep -q '^STATE|' $T.out; then
		grep '^STATE|' $T.out | sed 's/^STATE|//' > "$STATE.tmp" && mv "$STATE.tmp" "$STATE" && sync
	fi
else
	echo "sqlite falhou (nada gravado):"; tail -n 3 $T.out
fi

# relatorio legivel no drive (so quando algo mudou), para ler no PC na proxima transferencia
if [ $DRY = 0 ] && [ -s $T.rep ]; then
	{ echo "Ultima sincronizacao NAM com mudancas ($MODE). Linhas com ATENCAO pedem conferencia."; cat $T.rep; } | sed "s/\$/$(printf '\r')/" > "$NAM/nam_sync_relatorio.txt"
fi

# 5) aplicativo aberto e algo mudou (pasta ou banco)? ele precisa reabrir para enxergar
sig=$(ls -ln --full-time "$NAM" 2>/dev/null | grep -i '[.]nam$')
if [ $DRY = 1 ]; then
	:
elif [ -z "$(evil_pids)" ]; then
	echo "$sig" > $SIG
else
	changed=0
	[ -s $T.rep ] && changed=1
	[ "$sig" != "$(cat $SIG 2>/dev/null)" ] && changed=1
	echo "$sig" > $SIG
	if [ $changed = 1 ]; then
		if [ -e "$NAM/nam_restart_off.txt" ]; then
			echo "houve mudancas; reinicio desligado por nam_restart_off.txt (desligue e ligue o MX5)"
		else
			restart_app
		fi
	fi
fi
exit 0
