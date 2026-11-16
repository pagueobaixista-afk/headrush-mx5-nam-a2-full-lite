# MX5 NAM A2

[English](README.md) | [Português](README.pt-BR.md) | **Español**

Firmware personalizado para la **HeadRush MX5 (2.7)** que ejecuta modelos **NAM (Neural Amp Modeler)**, incluidos los modelos **A2** de tamaño completo, con una lista de modelos que se mantiene sola.

Es un trabajo derivado de [lolgab/headrush-nam-mod](https://github.com/lolgab/headrush-nam-mod) (v0.1.6), con los motores A2 de [tone-3000/embedded](https://github.com/tone-3000/embedded) portados a ARMv7 NEON y la [MX5 Bridge](#fuentes-y-créditos) para acceder al equipo desde el PC.

Proyecto desarrollado y compilado con **Claude Fable 5.2** (Anthropic).

> **Aviso.** Firmware no oficial, sin vínculo con HeadRush/inMusic. Instalar firmware modificado es bajo tu propio riesgo y puede anular la garantía; los autores no se responsabilizan por daños. El repositorio y el instalador **no** contienen el firmware ni el actualizador de HeadRush: el instalador parte del actualizador oficial, descargado del sitio de inMusic en el momento. Recuperación de la MX5: mantener los footswitches 1+2 al encender e instalar el actualizador oficial 2.7 (2+3 borra los rigs).

## Cómo instalar (paso a paso)

1. Entra en **[Releases](../../releases/latest)** y descarga **`MX5_NAM_A2_v6.zip`**.
2. Clic derecho en el zip > **Extraer todo**.
3. En la carpeta extraída, haz doble clic en **`Instalar_MX5_NAM_A2_v6.exe`**.
   - Descarga el actualizador oficial de HeadRush 2.7, arma el firmware y verifica todo (unos 2 minutos).
   - Si Windows avisa "Windows protegió su PC", haz clic en **Más información > Ejecutar de todas formas** (el programa no tiene firma digital de pago).
   - Sin internet: arrastra el actualizador oficial que ya tengas sobre el `.exe`.
4. Aparecerá la carpeta **`MX5_NAM_A2_v6_PRONTO_PARA_GRAVAR`** ("lista para instalar").
5. Conecta la MX5 a la corriente y al PC por USB. En la MX5: **Global Settings > … > Firmware Update**.
6. Abre **`FirmwareUpdater.exe`** de esa carpeta y haz clic en **Instalar NAM A2 v6**. No desconectes hasta que termine.
7. Copia tus `.nam` a la carpeta **`NAM`** de la unidad de la MX5, expulsa y toca **Sync**. Los modelos aparecen como presets del pedal Anxiety OD.
8. Para editar en el PC, abre **`MX-Edit\MX-Edit.exe`** (cierra antes cualquier otro MX-Edit abierto). El instalador coloca en `MX-Edit\arte` las mismas imágenes de pedales, amplificadores y gabinetes que la MX5 muestra en pantalla.

**Para volver al original:** instala el actualizador oficial de HeadRush 2.7 de la misma forma.

> El instalador y los mensajes del equipo están, por ahora, en portugués.

## Qué hace

- **NAM dentro del pedal Anxiety OD.** El knob Drive elige el modelo (posición en la carpeta `NAM`), Tone es la ganancia de entrada y Level la de salida.
- **A2 Lite y Full con el selector Hi-Lo.** Low = submodelo reducido (Lite), High = modelo completo (Full). Se puede cambiar mientras tocas.
- **Motores A2 más rápidos.** Los motores `t3k` portados a NEON se eligen midiendo en el propio equipo. Medido en la MX5: Full pasó de 715 µs a 451 µs por bloque de 48 muestras (1,58×), Lite de 108 a 73 µs. El bloque dura 1000 µs.
- **Menos carga innecesaria.** La señal mono (L igual a R) se procesa una sola vez; se corrigió el conteo de instancias activas; los hilos de carga de modelos quedan fuera del núcleo y de la prioridad del audio.
- **Lista de modelos como un cargador de IR.** Cada `.nam` se convierte en un preset `NNN - nombre` del Anxiety OD.
- **Sincronización automática** (`nam-sync.sh`), al arrancar y al salir de la transferencia USB (Sync):
  - numera los `.nam` nuevos con el siguiente número libre, para que las posiciones existentes no cambien;
  - valida los archivos y mueve los defectuosos a `NAM/_com_defeito`;
  - crea, actualiza y elimina los presets;
  - corrige el Drive en los rigs guardados si un modelo cambia de posición (con copia de la base de datos antes);
  - calcula el Level del preset a partir del `metadata.loudness` del modelo (opcional, ver abajo);
  - reinicia la aplicación sola cuando la lista cambió y guarda un informe en `NAM/nam_sync_relatorio.txt`.

Archivos de control en la carpeta `NAM`: `nam_config.txt` (`quality=switch|lite|full|auto`), `nam_sync.txt` (`alvo=` nivel objetivo, `nivelar=0` desactiva la nivelación), `nam_sync_off.txt`, `nam_restart_off.txt`.

**Sobre la nivelación de volumen:** iguala el volumen percibido, pero cambia cuánto empuja el modelo a los bloques siguientes del rig, y algunos terminan saturando. En la práctica el Level necesita ajuste manual por rig; usa `nivelar=0` si prefieres todos en 50.

## Qué tan fiel es al NAM oficial

Comparación directa: el mismo audio (2 s de la señal de prueba de NeuralAmpModelerCore + 10 s de bajo grabado en línea, 48 kHz) pasó por el [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) oficial compilado en el PC y por el `libnam_hook.so` idéntico al del equipo (mismo SHA1), ejecutándose en `qemu-arm` con las bibliotecas del firmware, motor `t3k-mla`, Tone y Level en 0 dB.

| Modelo (A2) | High (Full) vs oficial | Low (Lite) vs oficial |
|---|---|---|
| Tech 21 Sansamp Bass Driver 01 | residuo -130,5 dB | -24,6 dB |
| Darkglass Fuzz - OMEGA | -134,1 dB | -26,5 dB |
| PP-DI-Only | -135,3 dB | -22,7 dB |
| B7K 6505+ Distorted Bass | -125,8 dB | -16,1 dB |

El residuo es la energía de la diferencia respecto a la señal oficial. En **Full** no hay retardo ni diferencia de nivel, y el residuo queda en el redondeo de punto flotante de 32 bits: es el mismo sonido. En **Lite** se ejecuta el submodelo reducido que viene dentro del propio `.nam`, una red más pequeña, y la diferencia es audible en los modelos de más ganancia.

Lo que esta medición no cubre: los conversores y la etapa de entrada de la MX5, y lo que va antes y después del NAM en el rig. Para repetirla: `comparacao/run.sh`.

## Camino hasta aquí

1. **Base.** NAM de lolgab (2 instancias) y MX5 Bridge 0.7 para usar MX-Edit en el PC. El build de lolgab se reprodujo byte a byte antes de cualquier cambio.
2. **v1, motores A2.** Port de los motores A2 Lite/Full de tone-3000/embedded a ARMv7 NEON (variantes `fma` y `mla`), con selección automática en el equipo e informe en `/tmp/nam_a2_report.txt`. Probado en qemu-arm y luego medido en la MX5.
3. **v2, usada en vivo.** Selector Hi-Lo como Lite/Full (byte encontrado por diferencia de memoria, `memscan.c` y `hilo_probe.py`), colapso mono, conteo de instancias, hilos de carga fuera del audio, medidor `/tmp/nam_a2_stats.txt`. Un show entero sin ningún desborde de bloque.
4. **Presets por modelo.** Presets del Anxiety OD escritos en la base SQLite del equipo vía Bridge (`ferramentas/nam_presets.py`).
5. **v3.** Sincronización al arrancar (`nam-sync.sh`, llamado desde `runevil`).
6. **v4.** Sincronización también al salir de la transferencia USB (`mount_usb_img`) y reinicio automático de la aplicación.
7. **v5.** Rigs que se corrigen solos, nivelación por loudness, descarte de `.nam` defectuosos, informe.
8. **v6.** Corrección: la aplicación reescribía la base desde la memoria al terminar su propio Sync y borraba los presets recién creados. Ahora la base solo se modifica después de que la aplicación termina (modo `deferred`), y luego se reinicia.

Descartado en el camino: releer la carpeta sin reiniciar la aplicación (riesgo para el audio) y reemplazar el Anxiety OD por otro pedal.

## Estructura

| Carpeta | Contenido |
|---|---|
| `motor/` | Parches sobre lolgab (`nam_hook.diff`, `model_cpp.diff`), motores (`t3k_a2.cpp`, `nam_armv7_neon.h`), scripts de build y prueba numerados, `harness.c`, cliente de la Bridge (`brq.py`) |
| `firmware/v3` a `v6` | `nam-sync.sh` de cada versión, scripts que arman la imagen (`build_vN.py`) y la verificación del sistema de archivos |
| `ferramentas/` | Sincronización de presets desde el PC, vía Bridge |
| `comparacao/` | Comparación con el NeuralAmpModelerCore oficial |
| `editor/` | Parche sobre [MX-Edit](https://github.com/TicT4x/MX-Edit) 0.9.5 (TicT4x, MIT): arte real de los bloques (PNG de `arte/`, misma regla de nombres del QML de la MX5) y conexión confiable (pausa de 0,3 s después de abrir el puerto MIDI: sin ella el 1.er ping se perdía 8 de 8 veces; reintentos; busca la MX5 sola hasta encontrarla) |
| `instalador/` | Instalador para principiantes: `instalar.py` aplica `payload/` (archivos nuevos, solo las líneas modificadas de los scripts de HeadRush y 38 bytes de `/usr/Evil/Evil`) al firmware oficial; `dev/make_payload.py` genera `payload/` a partir de la v6; `bridge/` son las bibliotecas de MX5 Bridge 0.7 (MIT) |

## Cómo compilar

Entorno usado: WSL Ubuntu 24.04, toolchain Bootlin `arm-buildroot-linux-gnueabihf` (glibc 2.31) en `/opt/toolchain`, `qemu-arm`, Python 3.12.

1. `motor/01_setup.sh` a `06_build.sh` descargan las fuentes, reproducen el build de lolgab, aplican los parches y generan `libnam_hook.so`. De `07_test.sh` en adelante son las pruebas.
2. `motor/build_a2.py` inserta el motor en una imagen base que ya tiene la Bridge. `firmware/vN/build_vN.py` aplica cada versión sobre la anterior y ejecuta las pruebas de armado.
3. Debes conseguir por tu cuenta el `Update.img` 2.7 original y el patcher de MX5 Bridge 0.7. Los scripts tienen rutas de mi máquina; ajústalas.

## Fuentes y créditos

- [lolgab/headrush-nam-mod](https://github.com/lolgab/headrush-nam-mod): el mod de NAM para HeadRush que sirve de base (GPLv3).
- [tone-3000/embedded](https://github.com/tone-3000/embedded) 2.0.0: motores A2 Lite/Full (MIT).
- [sdatkinson/NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore): implementación de referencia de NAM (MIT).
- MX5 Bridge 0.7 y MX-Edit 0.9.5, de TicT4x: acceso al equipo por USB-MIDI y editor de PC (MIT).
- [SiulGalvan/Forge-Patch](https://github.com/SiulGalvan/Forge-Patch) ("HEADRUSH MX5 Compatibility Layer"): paquete que integra NAM, Bridge y arte; fue la base de la imagen con Bridge (GPLv3).
- [iosumurillo/GIGBOARD_NAM_AMP_PNG](https://github.com/iosumurillo/GIGBOARD_NAM_AMP_PNG): parche de arte de los pedales en pantalla (GPLv3).
- [Eigen](https://eigen.tuxfamily.org) y [nlohmann/json](https://github.com/nlohmann/json), dependencias de NAM.
- Toolchains de [Bootlin](https://toolchains.bootlin.com).

**Arte de los pedales:** las imágenes de los pedales son material de HeadRush (inMusic), integradas por iosumurillo y Forge-Patch. No forman parte de este repositorio: van aparte, en el archivo `arte_pedais.bin` del zip del Release, solo para uso en la MX5 del propio usuario. Sin ese archivo, el instalador arma el firmware sin el arte. Los titulares de derechos que quieran su retirada pueden abrir un issue; el archivo se retira inmediatamente.

HeadRush y MX5 son marcas de inMusic; este proyecto no tiene vínculo con el fabricante.

## Licencia

GPLv3, por derivar de headrush-nam-mod. Ver `LICENSE`.
