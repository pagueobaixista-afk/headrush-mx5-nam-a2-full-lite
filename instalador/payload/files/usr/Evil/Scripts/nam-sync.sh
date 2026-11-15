#!/bin/sh
# nam-sync.sh [boot|transfer|deferred]  (v6)
# Chamado na partida (runevil) e toda vez que o drive USB e remontado (mount_usb_img: partida e
# saida da transferencia USB / Sync).
#  1) .nam sem prefixo "NNN - " ganha o proximo numero livre (vai para o fim da lista)
#  2) .nam que nao e um modelo valido (arquivo truncado, vazio, nao-JSON) vai para NAM/_com_defeito
#  3) rigs: se a posicao de um modelo mudou (ex.: apagaram um do meio), o Drive do Anxiety OD nos
#     rigs salvos e corrigido para continuar apontando para o MESMO modelo (com copia do banco antes)
#  4) um preset do Anxiety OD por modelo (nome = arquivo sem .nam, Drive = posicao na ordem
#     alfabetica, a mesma do libnam_hook; Level calculado para igualar o volume entre modelos);
#     presets "NNN - ..." sem arquivo sao removidos
#  5) com o aplicativo aberto (saida da transferencia USB) so os passos 1 e 2 rodam na hora: o
#     aplicativo regrava o banco a partir da memoria ao terminar o proprio Sync, e o que fosse
#     gravado antes disso se perderia. Os passos 3 e 4 rodam depois, num processo separado
#     (modo deferred) que espera o banco parar; se algo mudou, ele reinicia o aplicativo
# Nunca impede a partida: qualquer falha so encerra este script. Registro em /tmp/nam_sync.log.
# Opcoes, em arquivos na pasta NAM do drive:
#   nam_sync_off.txt      desliga tudo        nam_restart_off.txt   desliga so o reinicio
#   (o script escreve NAM/nam_sync_relatorio.txt quando muda alguma coisa)
#   nam_sync.txt          linhas "alvo=-18" (volume alvo em dB) e/ou "nivelar=0" (nao mexer no Level)
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

TARGET=-18; NIVELAR=1
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
	(select count(*) from blocks b join old o on o.name = b.name where b.type = 'ANXIETY OD' and json_valid(b.content)
		and json_extract(b.content, '$.data."Anxiety OD".children.Drive.value') is not o.pos) * 10 <= (select count(*) from old) as ok;
create temp table fix as
	select r.id id, r.name rn, j.fullkey p, o.name mn, o.pos op, w.pos np,
		row_number() over (partition by r.id order by j.fullkey) k
	from rigs r, json_tree(r.content) j
	join old o on o.pos = cast(j.atom as integer)
	left join want w on w.name = o.name
	where (select ok from st) and json_valid(r.content) and j.key = 'value' and j.type in ('integer', 'real')
		and j.path glob '$.data.Patch.children."Anxiety OD*".children.Drive' and j.path not glob '*"Anxiety OD V2*'
		and (w.pos is null or w.pos != o.pos);
begin immediate;
insert into log select 'estado guardado nao bate com o banco: rigs nao foram mexidos' where (select count(*) from old) > 0 and not (select ok from st);
insert into log select 'rig corrigido: ' || rn || ': ' || mn || ' (Drive ' || op || ' -> ' || np || ')' from fix where np is not null;
insert into log select 'ATENCAO rig ' || rn || ' usa um modelo que saiu da pasta: ' || mn || ' (Drive ' || op || ')' from fix where np is null;
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 1 and f.np is not null), (select np from fix f where f.id = rigs.id and f.k = 1 and f.np is not null)) where id in (select id from fix where k = 1 and np is not null);
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 2 and f.np is not null), (select np from fix f where f.id = rigs.id and f.k = 2 and f.np is not null)) where id in (select id from fix where k = 2 and np is not null);
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 3 and f.np is not null), (select np from fix f where f.id = rigs.id and f.k = 3 and f.np is not null)) where id in (select id from fix where k = 3 and np is not null);
update rigs set content = json_set(content, (select p from fix f where f.id = rigs.id and f.k = 4 and f.np is not null), (select np from fix f where f.id = rigs.id and f.k = 4 and f.np is not null)) where id in (select id from fix where k = 4 and np is not null);
insert into log select 'preset removido: ' || name from blocks where type = 'ANXIETY OD'
	and name glob '[0-9][0-9][0-9] - *' and name not in (select name from want);
delete from blocks where type = 'ANXIETY OD'
	and name glob '[0-9][0-9][0-9] - *' and name not in (select name from want);
insert into log select 'posicao mudou: ' || b.name || ' -> Drive ' || w.pos from blocks b join want w on w.name = b.name
	where b.type = 'ANXIETY OD' and json_valid(b.content)
	and json_extract(b.content, '$.data."Anxiety OD".children.Drive.value') is not w.pos;
update blocks set content = json_set(content, '$.data."Anxiety OD".children.Drive.value',
		(select pos from want w where w.name = blocks.name))
	where type = 'ANXIETY OD' and json_valid(content) and name in (select name from want)
	and json_extract(content, '$.data."Anxiety OD".children.Drive.value')
		is not (select pos from want w where w.name = blocks.name);
-- Level: so mexe se o preset ainda esta com o valor que este script pos (ou 50, o padrao antigo)
create temp table lvfix as select b.id id, b.name name, w.level nl from blocks b join want w on w.name = b.name
	left join old o on o.name = b.name
	where b.type = 'ANXIETY OD' and json_valid(b.content)
	and json_extract(b.content, '$.data."Anxiety OD".children.Level.value') is ifnull(o.level, 50)
	and json_extract(b.content, '$.data."Anxiety OD".children.Level.value') is not w.level;
insert into log select 'volume: ' || name || ' -> Level ' || nl from lvfix;
update blocks set content = json_set(content, '$.data."Anxiety OD".children.Level.value', (select nl from lvfix f where f.id = blocks.id))
	where id in (select id from lvfix);
insert into log select 'volume no maximo, ainda ' || cast((select t from cfg) - loud - 12 + 0.5 as integer) || ' dB abaixo do alvo: ' || name
	from want where (select niv from cfg) = 1 and loud is not null and (select t from cfg) - loud > 12.5
	and (name in (select name from lvfix) or name not in (select name from blocks where type = 'ANXIETY OD'));
insert into log select 'novo preset: ' || name || ' (Drive ' || pos || ', Level ' || level || ')' from want
	where name not in (select name from blocks where type = 'ANXIETY OD');
insert into blocks (id, type, name, content, is_readonly)
	select lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)), 2) || '-a'
		|| substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))), 'ANXIETY OD', name,
		'{"data":{"Anxiety OD":{"childorder":["Level","Drive","Tone","Hi-Lo"],"children":{"Drive":{"type":0,"value":'
		|| pos || '},"Hi-Lo":{"state":true,"type":1},"Level":{"type":0,"value":' || level || '},"Tone":{"type":0,"value":50}}}},"info":{"version":"1.0.9"}}', 0
	from want where name not in (select name from blocks where type = 'ANXIETY OD');
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
