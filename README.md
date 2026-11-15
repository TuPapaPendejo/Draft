# Actualizador de letras para Gamdl

Actualiza las letras sincronizadas dentro de archivos Apple Music `.m4a` ya descargados, sin volver a descargar ni recodificar el audio.

Versión actual: `0.4.0` · Objetivo: Gamdl `4.x` · Entorno principal: openSUSE Tumbleweed en WSL.

## Qué hace

El programa lee el identificador de canción del átomo MP4 `cnID`, reutiliza la autenticación guardada por Gamdl en `~/.gamdl/config.yml`, consulta únicamente las letras mediante la API asíncrona de Gamdl, convierte el TTML de Apple Music a Enhanced LRC o LRC cuando hay sincronización completa; si no existe, usa texto plano solo cuando el átomo `©lyr` todavía no está presente.

No solicita streams de audio, no descarga bytes multimedia, no descifra, no vuelve a multiplexar ni transcodifica pistas. Omite archivos sin `cnID` válido, sin letras utilizables o que no superen las verificaciones. Nunca sustituye una etiqueta `©lyr` existente por texto sin sincronización.

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
| `--log-file PATH` | Ubicación alternativa del LOG acumulativo. | `<directory>/.lyrics-retagger.log` |
| `--apply` | Escribe los cambios después de verificar el archivo temporal. | Desactivado |
| `--version` | Muestra la versión del programa. | — |

## Jerarquía de recuperación de letras

1. **TTML estándar:** se consulta `Song.get_lyrics(syllable=False)`. Si todas las líneas tienen inicio temporal, se genera LRC; si también existen marcas por segmento, se conservan como Enhanced LRC.
2. **Enhanced LRC:** si el TTML estándar no permite obtener sincronización completa, se consulta `Song.get_lyrics(syllable=True)` (`syllable-lyrics`) y se conservan las marcas por palabra/sílaba.
3. **LRC estándar:** cuando el recurso alternativo solo tiene marcas por línea, se genera LRC normal. No se aceptan líneas parcialmente sincronizadas como sincronización completa.
4. **Texto plano:** si ninguno de los recursos proporciona sincronización utilizable, `LyricsFormat.TEXT` extrae el texto del objeto `Lyrics` ya obtenido. No existe una petición independiente llamada `lyrics_text`.

**El texto plano solo se escribe cuando el M4A no contiene el átomo `©lyr`.** Si el átomo ya existe, incluso vacío, se deja intacto y se registra `TEXT_FALLBACK_SKIPPED`. El TTML XML nunca se incrusta directamente en ese átomo.

El TTML local homónimo sigue siendo diagnóstico; no se utiliza como fuente automática.

## Detalles y limitaciones de esta versión

- `cnID` es el identificador de catálogo de la **canción**. Los identificadores de álbum (`plID`) y artista (`atID`) no sirven como sustitutos para el endpoint de letras.
- El resultado sincronizado puede ser Enhanced LRC (marcas por palabra/sílaba) o LRC estándar (una marca por línea). Ambos se almacenan en `©lyr`.
- Todas las líneas no vacías deben tener un tiempo para aceptar un resultado sincronizado; si no, se recurre a texto plano sin inventar marcas temporales.
- El texto plano no reemplaza una etiqueta `©lyr` existente.
- El LRC incrustado se almacena como texto en el átomo MP4 `©lyr`. La forma en que se presenta la sincronización depende del reproductor; algunos muestran literalmente las marcas de tiempo.
- Esta versión no crea archivos `.lrc` externos ni respaldos permanentes. El registro de ejecución se guarda en `.lyrics-retagger.log`.
- Apple Music puede no ofrecer letras para todas las canciones, tiendas o cuentas. El endpoint de letras utilizado por Gamdl es privado y puede cambiar independientemente de la API pública.

## Pruebas

Ejecuta las pruebas unitarias desde la raíz del repositorio:

```bash
uv run python -m unittest discover -s tests -v
```

Consulta `docs/architecture.md` para el diseño interno, `docs/upstream-api.md` para la integración con Gamdl 4.x y `CHANGELOG.md` para el historial de versiones. Cada commit de GitHub tiene un mensaje que describe el cambio incluido.