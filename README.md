# Actualizador de letras para Gamdl

Actualiza las letras sincronizadas dentro de archivos Apple Music `.m4a` ya descargados, sin volver a descargar ni recodificar el audio.

Versión actual: `0.3.0` · Objetivo: Gamdl `4.x` · Entorno principal: openSUSE Tumbleweed en WSL.

## Qué hace

El programa lee el identificador de canción del átomo MP4 `cnID`, reutiliza la autenticación guardada por Gamdl en `~/.gamdl/config.yml`, consulta únicamente las letras mediante la API asíncrona de Gamdl, convierte el TTML de Apple Music a LRC estándar sincronizado por línea y actualiza el átomo incrustado `©lyr`.

No solicita streams de audio, no descarga bytes multimedia, no descifra, no vuelve a multiplexar ni transcodifica pistas. Omite archivos sin `cnID` válido, sin letras sincronizadas o que no superen las verificaciones.

## Seguridad e integridad

- El modo predeterminado es **simulación**. Para escribir se exige `--apply`.
- Cada modificación se prepara en un archivo temporal dentro de la misma carpeta que el original.
- El programa vuelve a leer `©lyr` y compara el valor con el LRC generado.
- Calcula SHA-256, tamaño y cantidad de átomos de todos los `mdat` de nivel superior. Deben permanecer idénticos antes de publicar el archivo.
- No crea copias de seguridad permanentes. Conserva únicamente un archivo temporal durante la escritura y lo elimina al terminar.
- Si falla una comprobación, el archivo original permanece en su sitio.

## Prerrequisitos

- Python 3.10 o posterior.
- `uv` instalado.
- Una sesión de Apple Music configurada con Gamdl 4.x (`gamdl auth`).
- Archivos `.m4a` descargados que contengan el identificador de canción Apple Music en `cnID`.

Gamdl se instala como dependencia del entorno del proyecto mediante `uv sync`; no es necesario modificar la instalación global de Gamdl que ya utilizas.

## Instalación en WSL

Clona el repositorio y entra en la carpeta:

```bash
git clone https://github.com/TuPapaPendejo/Draft.git
cd Draft
```

Instala las dependencias del proyecto:

```bash
uv sync
uv run gamdl-lyrics-retagger --version
```

El actualizador reutiliza la configuración existente de Gamdl. Si todavía no está configurada, autentícate:

```bash
uv run gamdl auth
```

Se admiten los modos `cookies`, `media-user-token` y `wrapper`. En el modo `wrapper`, el servicio Wrapper v2 debe estar disponible y tener una sesión autenticada. El actualizador no solicita ni guarda contraseñas.

## Primera ejecución: simulación

La carpeta predeterminada es `/mnt/d/Pruebas`, como entorno de trabajo inicial del proyecto. Primero limita la ejecución a una pista:

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --limit 1
```

El programa mostrará si la pista tiene `cnID`, si Apple Music devuelve letras sincronizadas y si se propone actualizar `©lyr`. No realizará cambios.

Para revisar únicamente una pista concreta por su nombre o parte de la ruta (útil para diagnosticar un archivo omitido):

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --match 'Baby Come On (Acoustic Version)'
```

Para revisar todos los M4A de la carpeta y sus subcarpetas:

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas
```

## Aplicar cambios

Después de revisar la simulación, ejecuta primero la prueba de una sola pista con `--apply`:

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --limit 1 --apply
```

Cuando verifiques el resultado, puedes procesar el resto:

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --apply
```

El programa ya no crea copias de seguridad permanentes. Durante cada cambio conserva temporalmente una copia de trabajo junto al M4A; solo la publica después de verificar `©lyr` y `mdat`, y elimina el temporal al finalizar.

El LOG predeterminado es `/mnt/d/Pruebas/.lyrics-retagger.log` (o `<directory>/.lyrics-retagger.log` si eliges otra carpeta). Es acumulativo: cada ejecución agrega una nueva sección con fecha y hora. Puedes elegir otra ubicación mediante `--log-file PATH`.

El LOG registra por pista el `cnID`, título, artista, ISRC, `hasLyrics`, estado y forma de las respuestas de ambos endpoints (`standard` y `syllable`), presencia/tamaño del TTML, marcas de tiempo válidas, resultado de `©lyr`, hashes SHA-256 de `mdat`, errores y resumen de ejecución. No registra el texto de las letras, TTML completo, tokens, cookies ni contraseñas.

Para revisar las entradas de la última pista omitida, por ejemplo:

```bash
grep -n -E '1444116875|Baby Come On' /mnt/d/Pruebas/.lyrics-retagger.log
```

Para ver el final del registro:

```bash
tail -n 100 /mnt/d/Pruebas/.lyrics-retagger.log
```

Cuando Apple Music no devuelve letras, también busca un `.ttml` con el mismo nombre base que el M4A y registra si existe y cuántas líneas sincronizadas contiene. Esta inspección es diagnóstica; no utiliza automáticamente el TTML local como sustituto.

Puedes seleccionar cualquier otra carpeta mediante `--directory`; `/mnt/d/Pruebas` es solo el valor predeterminado de este proyecto mientras se desarrolla. La carpeta `.lyrics-retagger-backups` creada por la versión 0.1.0 no se elimina automáticamente; puedes borrarla manualmente después de confirmar que ya no necesitas esos respaldos.

## Parámetros de línea de comandos

| Parámetro | Función | Valor predeterminado |
|---|---|---|
| `--directory PATH` | Carpeta que contiene los M4A. La búsqueda es recursiva de forma predeterminada. | `/mnt/d/Pruebas` |
| `--config PATH` | Archivo YAML de configuración de Gamdl. | `~/.gamdl/config.yml` |
| `--storefront XX` | Sobrescribe el storefront de Apple Music, por ejemplo `mx` o `us`. | Configuración de Gamdl / valor detectado |
| `--language TAG` | Sobrescribe el idioma de metadatos/letras, por ejemplo `es-MX`. | `auth.language` o `en-US` |
| `--limit N` | Limita la cantidad de M4A que se inspeccionan. Útil para la prueba inicial. | Sin límite |
| `--match TEXT` | Procesa únicamente archivos cuya ruta relativa contenga el texto indicado (sin distinguir mayúsculas). | Todos |
| `--recursive` | Incluye subcarpetas. | Activado |
| `--no-recursive` | Busca únicamente en la carpeta indicada. | — |
| `--log-file PATH` | Ubicación alternativa del LOG acumulativo. | `<directory>/.lyrics-retagger.log` |\n| `--apply` | Escribe los cambios después de verificar el archivo temporal. | Desactivado |
| `--version` | Muestra la versión del programa. | — |

## Recuperación de letras sincronizadas

El actualizador primero consulta el endpoint estándar de Gamdl (`Song.get_lyrics(syllable=False)`). Si la respuesta no contiene marcas de tiempo para todas las líneas, o no devuelve un recurso de letras, intenta automáticamente el endpoint de letras con sincronización por palabra/sílaba (`Song.get_lyrics(syllable=True)`).

Aunque la segunda fuente pueda contener tiempos por palabra o sílaba, el programa la convierte a **LRC estándar por línea**: utiliza el primer instante temporal de cada línea. No escribe el formato enhanced-LRC. El LOG identifica qué endpoint produjo el resultado mediante `LYRICS_READY endpoint=standard` o `LYRICS_READY endpoint=syllable`.

Si ninguno de los dos endpoints produce una línea de tiempo completa, la pista se omite. Un TTML local homónimo se inspecciona para diagnóstico, pero no se aplica automáticamente.

## Detalles y limitaciones de esta versión

- `cnID` es el identificador de catálogo de la **canción**. Los identificadores de álbum (`plID`) y artista (`atID`) no sirven como sustitutos para el endpoint de letras.
- Esta versión genera LRC estándar con marcas de tiempo por línea. No solicita `enhanced-lrc` ni sincronización por palabra/sílaba.
- Todas las líneas no vacías deben tener una marca de tiempo. Si la letra es parcial, de texto plano o no está disponible, el archivo se omite; nunca se inventan marcas de tiempo ni se degrada a texto.
- El LRC incrustado se almacena como texto en el átomo MP4 `©lyr`. La forma en que se presenta la sincronización depende del reproductor; algunos muestran literalmente las marcas de tiempo.
- Esta versión no crea archivos `.lrc` externos ni respaldos permanentes. El registro de ejecución se guarda en `.lyrics-retagger.log`.
- Apple Music puede no ofrecer letras para todas las canciones, tiendas o cuentas. El endpoint de letras utilizado por Gamdl es privado y puede cambiar independientemente de la API pública.

## Pruebas

Ejecuta las pruebas unitarias desde la raíz del repositorio:

```bash
uv run python -m unittest discover -s tests -v
```

Consulta `docs/architecture.md` para el diseño interno, `docs/upstream-api.md` para la integración con Gamdl 4.x y `CHANGELOG.md` para el historial de versiones. Cada commit de GitHub tiene un mensaje que describe el cambio incluido.