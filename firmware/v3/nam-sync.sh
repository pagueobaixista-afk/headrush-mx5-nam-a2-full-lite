#!/bin/sh
# nam-sync.sh -- chamado pelo runevil a cada partida, antes de o aplicativo abrir.
#  1) .nam sem prefixo "NNN - " ganha o proximo numero livre (vai para o fim da lista)
#  2) um preset do Anxiety OD por modelo (nome = arquivo sem .nam, Drive = posicao na ordem
#     alfabetica, a mesma que o libnam_hook usa); presets "NNN - ..." sem arquivo sao removidos
# Nunca impede a partida: qualquer falha so encerra este script. Registro em /tmp/nam_sync.log.
# Para desligar: crie o arquivo NAM/nam_sync_off.txt no drive do MX5.
NAM=${NAM_SYNC_DIR:-/media/az01-internal/Evil/usb_mnt/NAM}
DB=${NAM_SYNC_DB:-/media/az01-internal/Evil/evil.db}
SQL=/usr/Evil/Scripts/mx5bridge-sqlite3
T=/tmp/nam_sync.$$
[ -d "$NAM" ] && [ -f "$DB" ] && [ -x "$SQL" ] || { echo "nada a fazer (sem pasta NAM, banco ou sqlite)"; exit 0; }
[ -e "$NAM/nam_sync_off.txt" ] && { echo "desligado por nam_sync_off.txt"; exit 0; }
( sleep 25; kill -9 $$ 2>/dev/null ) >/dev/null 2>&1 &
WD=$!
trap 'kill $WD 2>/dev/null; rm -f $T.*' EXIT

listar() { ls -1 "$NAM" 2>/dev/null | grep -i '[.]nam$' | grep -v '^[.]_' | LC_ALL=C sort; }

listar > $T.lst
[ -s $T.lst ] || { echo "nenhum .nam"; exit 0; }

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
	if [ ! -e "$NAM/$new" ] && mv "$NAM/$f" "$NAM/$new"; then echo "numerado: $new"; ren=1; else echo "nao consegui numerar: $f"; fi
done < $T.lst
[ $ren -eq 1 ] && { sync; listar > $T.lst; }

# 2) presets
{
	echo "create temp table want(name text primary key collate nocase, pos integer);"
	r=0
	while IFS= read -r f; do
		[ $r -gt 100 ] && break
		b=$(printf '%s' "${f%.*}" | sed "s/'/''/g")
		echo "insert or ignore into want values('$b', $r);"
		r=$((r + 1))
	done < $T.lst
	cat <<'SQLEOF'
create temp table log(m text);
begin immediate;
insert into log select 'removido: ' || name from blocks where type = 'ANXIETY OD'
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
insert into log select 'novo: ' || name || ' (Drive ' || pos || ')' from want
	where name not in (select name from blocks where type = 'ANXIETY OD');
insert into blocks (id, type, name, content, is_readonly)
	select lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)), 2) || '-a'
		|| substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))), 'ANXIETY OD', name,
		'{"data":{"Anxiety OD":{"childorder":["Level","Drive","Tone","Hi-Lo"],"children":{"Drive":{"type":0,"value":'
		|| pos || '},"Hi-Lo":{"state":true,"type":1},"Level":{"type":0,"value":50},"Tone":{"type":0,"value":50}}}},"info":{"version":"1.0.9"}}', 0
	from want where name not in (select name from blocks where type = 'ANXIETY OD');
commit;
select m from log;
select (select count(*) from want) || ' modelos, ' || (select count(*) from log) || ' alteracoes';
SQLEOF
} > $T.sql
if [ "$NAM_SYNC_DRY" = 1 ]; then
	sed -i 's/^commit;$/select m from log; rollback;/' $T.sql
	echo "(simulacao: nada gravado)"
fi
"$SQL" -bail -cmd ".timeout 4000" "$DB" < $T.sql 2>&1 || echo "sqlite falhou (nada gravado)"
exit 0
