# Actualizador de letras para Gamdl

Actualiza las letras sincronizadas dentro de archivos Apple Music `.m4a` ya descargados, sin volver a descargar ni recodificar el audio.

Versión inicial: `0.1.0` · Objetivo: Gamdl `4.x` · Entorno principal: openSUSE Tumbleweed en WSL.

## Qué hace

El programa lee el identificador de canción del átomo MP4 `cnID`, reutiliza la autenticación guardada por Gamdl en `~/.gamdl/config.yml`, consulta únicamente las letras mediante la API asíncrona de Gamdl, convierte el TTML de Apple Music a LRC estándar sincronizado por línea y actualiza el átomo incrustado `©lyr`.

No solicita streams de audio, no descarga bytes multimedia, no descifra, no vuelve a multiplexar ni transcodifica pistas. Omite archivos sin `cnID` válido, sin letras sincronizadas o que no superen las verificaciones.

## Seguridad e integridad

- El modo predeterminado es **simulación**. Para escribir se exige `--apply`.
- Cada modificación se prepara en un archivo temporal dentro de la misma carpeta que el original.
- El programa vuelve a leer `©lyr` y compara el valor con el LRC generado.
- Calcula SHA-256, tamaño y cantidad de átomos de todos los `mdat` de nivel superior. Deben permanecer idénticos antes de publicar el archivo.
- Antes de sustituir el original crea una copia de seguridad que nunca sobrescribe otra existente.
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

Las copias de seguridad se guardan en `.lyrics-retagger-backups/` dentro de la carpeta seleccionada, conservando las rutas relativas. Si un nombre de respaldo ya existe, se elige otro nombre; nunca se sobrescribe.

Puedes seleccionar cualquier otra carpeta mediante `--directory`; `/mnt/d/Pruebas` es solo el valor predeterminado de este proyecto mientras se desarrolla.

## Parámetros de línea de comandos

| Parámetro | Función | Valor predeterminado |
|---|---|---|
| `--directory PATH` | Carpeta que contiene los M4A. La búsqueda es recursiva de forma predeterminada. | `/mnt/d/Pruebas` |
| `--config PATH` | Archivo YAML de configuración de Gamdl. | `~/.gamdl/config.yml` |
| `--storefront XX` | Sobrescribe el storefront de Apple Music, por ejemplo `mx` o `us`. | Configuración de Gamdl / valor detectado |
| `--language TAG` | Sobrescribe el idioma de metadatos/letras, por ejemplo `es-MX`. | `auth.language` o `en-US` |
| `--limit N` | Limita la cantidad de M4A que se inspeccionan. Útil para la prueba inicial. | Sin límite |
| `--recursive` | Incluye subcarpetas. | Activado |
| `--no-recursive` | Busca únicamente en la carpeta indicada. | — |
| `--apply` | Escribe los cambios después de verificar el archivo temporal. | Desactivado |
| `--version` | Muestra la versión del programa. | — |

## Detalles y limitaciones de esta versión

- `cnID` es el identificador de catálogo de la **canción**. Los identificadores de álbum (`plID`) y artista (`atID`) no sirven como sustitutos para el endpoint de letras.
- La primera versión genera LRC estándar con marcas de tiempo por línea. No solicita `enhanced-lrc` ni sincronización por palabra/sílaba.
- Todas las líneas no vacías deben tener una marca de tiempo. Si la letra es parcial, de texto plano o no está disponible, el archivo se omite; nunca se inventan marcas de tiempo ni se degrada a texto.
- El LRC incrustado se almacena como texto en el átomo MP4 `©lyr`. La forma en que se presenta la sincronización depende del reproductor; algunos muestran literalmente las marcas de tiempo.
- Esta versión no crea archivos `.lrc` externos.
- Apple Music puede no ofrecer letras para todas las canciones, tiendas o cuentas. El endpoint de letras utilizado por Gamdl es privado y puede cambiar independientemente de la API pública.

## Pruebas

Ejecuta las pruebas unitarias desde la raíz del repositorio:

```bash
uv run python -m unittest discover -s tests -v
```

Consulta `docs/architecture.md` para el diseño interno, `docs/upstream-api.md` para la integración con Gamdl 4.x y `CHANGELOG.md` para el historial de versiones. Cada commit de GitHub tiene un mensaje que describe el cambio incluido.