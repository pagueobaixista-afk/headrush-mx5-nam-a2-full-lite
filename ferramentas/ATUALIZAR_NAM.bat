@echo off
rem Deixe este arquivo dentro da pasta NAM do MX5. Rode antes de dar Sync no aparelho.
rem 1) numera os .nam novos (proximo numero livre)  2) gera os presets em Blocks\ANXIETY OD
set "SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllLines($env:SELF); $i=[Array]::IndexOf($t,'#PS#'); iex ($t[($i+1)..($t.Length-1)] -join [char]10)"
echo.
pause
exit /b
#PS#
$ErrorActionPreference = 'Stop'
$nam = Split-Path -Parent $env:SELF
$root = Split-Path -Parent $nam
$dir = Join-Path $root 'Blocks\ANXIETY OD'
function Listar { @(Get-ChildItem -LiteralPath $nam -File | Where-Object { $_.Extension -ieq '.nam' -and $_.Name -notlike '._*' }) }
$files = Listar
if ($files.Count -eq 0) { Write-Host 'Nenhum .nam nesta pasta.'; return }
$max = -1
foreach ($f in $files) { if ($f.Name -match '^(\d{3}) - ') { $n = [int]$Matches[1]; if ($n -gt $max) { $max = $n } } }
$novos = 0
foreach ($f in ($files | Where-Object { $_.Name -notmatch '^\d{3} - ' } | Sort-Object Name)) {
  $max++; $alvo = ('{0:000} - {1}' -f $max, $f.Name)
  Rename-Item -LiteralPath $f.FullName -NewName $alvo
  Write-Host ('numerado:  ' + $alvo); $novos++
}
$nomes = [string[]]@(Listar | ForEach-Object { $_.Name })
[Array]::Sort($nomes, [StringComparer]::Ordinal)
if ($nomes.Count -gt 101) { Write-Host ('ERRO: ' + $nomes.Count + ' modelos; o botao Drive so alcanca 101. Remova alguns.'); return }
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$md5 = [Security.Cryptography.MD5]::Create()
$enc = New-Object Text.UTF8Encoding($false)
$vivos = @{}; $feitos = 0; $mudou = 0
for ($r = 0; $r -lt $nomes.Count; $r++) {
  $base = $nomes[$r].Substring(0, $nomes[$r].Length - 4)
  $vivos[$base.ToLowerInvariant()] = 1
  $id = ([guid]::new($md5.ComputeHash($enc.GetBytes($base.ToLowerInvariant())))).ToString()
  $path = Join-Path $dir ($base + '.block')
  $drive = '\"Drive\":{\"type\":0,\"value\":' + $r + '}'
  if (Test-Path -LiteralPath $path) {
    $old = [IO.File]::ReadAllText($path)
    if ($old.Contains($drive)) { continue }
    $mudou++; Write-Host ('posicao mudou:  ' + $base + '  (agora Drive ' + $r + ')')
  } else { Write-Host ('preset novo:  ' + $base + '  (Drive ' + $r + ')') }
  $inner = '{\"data\":{\"Anxiety OD\":{\"childorder\":[\"Level\",\"Drive\",\"Tone\",\"Hi-Lo\"],\"children\":{' + $drive + ',\"Hi-Lo\":{\"state\":true,\"type\":1},\"Level\":{\"type\":0,\"value\":50},\"Tone\":{\"type\":0,\"value\":50}}}},\"info\":{\"version\":\"1.0.9\"}}'
  $json = "{`n  `"content`": `"" + $inner + "`",`n  `"id`": `"" + $id + "`",`n  `"readonly`": false,`n  `"type`": `"ANXIETY OD`"`n}`n"
  [IO.File]::WriteAllText($path, $json, $enc); $feitos++
}
foreach ($b in @(Get-ChildItem -LiteralPath $dir -Filter *.block -File)) {
  if ($b.BaseName -match '^\d{3} - ' -and -not $vivos.ContainsKey($b.BaseName.ToLowerInvariant())) {
    Remove-Item -LiteralPath $b.FullName; Write-Host ('removido (sem .nam):  ' + $b.Name)
  }
}
Write-Host ''
Write-Host ('' + $nomes.Count + ' modelos | ' + $novos + ' numerados | ' + $feitos + ' presets gravados em Blocks\ANXIETY OD')
if ($mudou -gt 0) { Write-Host ('ATENCAO: ' + $mudou + ' modelo(s) mudaram de posicao. Confira os rigs que usam o Anxiety OD.') }
if ($feitos -gt 0 -or $novos -gt 0) { Write-Host 'Agora ejete o MX5, toque em Sync e depois reinicie o aparelho.' } else { Write-Host 'Ja estava tudo em dia.' }
