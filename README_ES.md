# DBZK_Fix para Linux / Steam Deck — Fix de FPS y Ultrawide para Dragon Ball Z: Kakarot

**DBZK_Fix** es una versión mantenida del mod/fix para **Dragon Ball Z: Kakarot**, centrada especialmente en la compatibilidad y estabilidad con **Linux, Proton y Steam Deck**, manteniendo las funciones originales para Windows.

Este fork elimina el **límite de 60 FPS**, añade soporte para **21:9 ultrawide, 16:10 y 4:3**, permite ajustes de FOV y cámara y modifica el proceso de inicialización de **UE4SS** para reducir los cierres provocados por acceder a objetos de Unreal Engine antes de que estén disponibles.

> English documentation: **[README.md](README.md)**

## Características principales

- Eliminación del límite de **60 FPS** durante el juego.
- Soporte para **21:9 ultrawide**, **16:10** y **4:3**.
- Desactivación opcional del motion blur.
- Ajustes de Temporal AA / escalado.
- Ajustes de FOV y cámara.
- Reaplicación de los ajustes de framerate durante determinadas transiciones y cinemáticas.
- Validación más segura de UObjects.
- Inicialización diferida de objetos de Unreal Engine.
- Gestión más segura de hooks y callbacks de UE4SS.
- Mayor estabilidad en **Linux / Proton / Steam Deck**.

## Compatibilidad

### Probado

- **Steam Deck / SteamOS**
- **Linux + Proton**

### Compatibilidad esperada

- Windows 10
- Windows 11

La compatibilidad con Windows se espera porque el mod continúa utilizando las APIs Lua estándar de UE4SS y no depende de rutas o comandos exclusivos de Linux o SteamOS. Aun así, debe considerarse **pendiente de revalidación directa en Windows**.

## Por qué existe este fork

El DBZK_Fix original podía ejecutar determinadas operaciones de Unreal Engine demasiado pronto durante el inicio. Bajo **Proton y Steam Deck**, algunos objetos necesarios pueden no existir todavía o no ser válidos, provocando violaciones de acceso y cierres.

Este fork modifica ese comportamiento:

- Espera a que existan los objetos relevantes antes de modificarlos.
- Valida los UObjects antes de utilizarlos.
- Retrasa los cambios de FPS hasta disponer de un `ATCheatManager` válido.
- Evita ejecutar inmediatamente el `Fix()` original durante el arranque.
- Ejecuta los cambios sensibles en puntos más seguros del ciclo de vida de Unreal.
- Corrige el tratamiento de parámetros de hooks de UE4SS cuando es necesario.
- Conserva las funciones originales de framerate, FOV, cámara y gráficos.

## Instalación — Instalador Linux 0.4.2

**Esta actualización solo facilita la instalación. El mod, las DLL y el funcionamiento de la versión 0.4.1 permanecen intactos.**

1. Descarga **DBZK-Fix-Linux-0.4.2.run** desde [Releases](https://github.com/N3ruk/DBZK_Fix_LINUX/releases).
2. En Steam Deck/SteamOS usa **modo Escritorio**. Guarda las partidas y cierra los juegos.
3. Ejecuta el archivo descargado. Si tu escritorio no abre scripts, abre una terminal en esa carpeta y ejecuta:

   ```bash
   bash DBZK-Fix-Linux-0.4.2.run
   ```

4. Acepta la instalación detectada. **El instalador cierra Steam, espera a que guarde sus ajustes y después instala el mod y configura las opciones de lanzamiento.**
5. Abre Steam de nuevo y juega a cualquiera de las ediciones instaladas.

Alternativa: extrae **DBZK-Fix-Linux-0.4.2.zip** y ejecuta **Instalar.sh**. No copies el paquete entero a Win64. Ambos formatos incluyen el mod para instalar sin conexión. Necesitas **Python 3.8+**, pero no sudo, paquetes de pip ni protontricks. Hay diálogos opcionales kdialog/zenity y alternativa de terminal.

### Detección y activación automáticas

- Steam nativo, Flatpak y Snap, con bibliotecas en discos externos o tarjetas SD.
- Localiza el juego por AppID **851850**, sin rutas personales fijas.
- Instala y activa el mod en la versión **normal y Remastered** que estén presentes: `AT/Binaries/Win64/` y `dlc/Remaster/AT/Binaries/Win64/`.
- Configura `WINEDLLOVERRIDES="dwmapi=n,b" %command%` en los perfiles locales existentes, conservando otras opciones y overrides de DLL.
- Conserva `Config.ini`, ajustes UE4SS y otros mods; crea copias de seguridad de lo reemplazado y permite restaurar.

Para comprobar sin cerrar Steam ni instalar: `bash DBZK-Fix-Linux-0.4.2.run --check`. Consulta [la documentación del instalador](docs/INSTALLER.md) para rutas manuales, requisitos y restauración.

El instalador no depende de una distribución concreta. Las pruebas de instalación se realizan con entornos simulados; no implican nuevas pruebas de juego en todas las distribuciones ni revalidación de la versión base, que mantiene las limitaciones indicadas en 0.4.1. El nuevo instalador automático es solo para Linux; no cambia el uso manual del mod en otras plataformas. Descarga el asset .run o .zip de la release, no el ZIP automático de código fuente de GitHub, que no incluye las DLL.

## Configuración

La configuración continúa realizándose mediante `Config.ini`.

La sección de framerate permite controlar:

- FPS máximos.
- Framerate fijo o variable.
- Intervalo de VSync.

El resto de opciones gráficas originales continúan disponibles cuando el juego las admite.

## Problemas conocidos

Algunas limitaciones heredadas del proyecto original pueden seguir presentes:

- Algunos elementos de interfaz pueden utilizar anclajes incorrectos en relaciones de aspecto distintas de 16:9.
- Determinados menús y elementos del HUD pueden no quedar perfectamente centrados.
- Algunas cinemáticas pueden mostrarse incorrectamente en relaciones ultrawide.
- El comportamiento del FOV puede variar dependiendo de la escena.

Al informar de un problema, incluye:

- Sistema operativo.
- Versión de Proton / Wine, si corresponde.
- Versión de Dragon Ball Z: Kakarot.
- Versión de UE4SS.
- `UE4SS.log` relevante.
- Volcado del crash, si se generó.

## Créditos

Este repositorio es un fork modificado del **DBZK_Fix** original.

Agradecimientos especiales a:

- [KingKrouch](https://github.com/KingKrouch) / Bryce Q. por el proyecto e implementación originales.
- [NicNamed](https://github.com/NicNamed) por el trabajo posterior y el soporte para HD Update.
- [Special Week (real)](https://steamcommunity.com/sharedfiles/filedetails/?id=3527702022) por identificar correcciones relacionadas con actualizaciones de UE4SS para HD Update.
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) y sus colaboradores.

## Licencia

DBZK_Fix deriva del proyecto original de Bryce Q. y continúa distribuyéndose bajo licencia MIT.

Consulta **[LICENSE](LICENSE)** para ver el texto completo de la licencia.
