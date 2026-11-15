# Notas de integración con la API de Gamdl 4.x

Este proyecto apunta a la rama fuente `4.0` de Gamdl (el `pyproject.toml` inspeccionado declara la versión `4.0.1`). Se utilizan las clases de alto nivel de Gamdl en lugar de recrear la autenticación de Apple Music o implementar otro analizador TTML.

## Puntos de entrada upstream

- [README de Gamdl 4.0 — Python API](https://github.com/glomatico/gamdl/blob/4.0/README.md#-python-api): documenta el uso asíncrono de `AppleMusicApi`, `MediaResolver` y `Song`.
- [Endpoints de catálogo de Apple Music](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/api/apple_music/catalog.py): implementa `get_lyrics(song_id, language=...)` y `get_syllable_lyrics(...)`.
- [Modelo de canción](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/media/song/media.py): `Song.get_lyrics()` resuelve el ID de catálogo, consulta TTML y devuelve un objeto `Lyrics` sin solicitar un stream de audio.
- [Analizador y exportadores Lyrics](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/media/song/lyrics.py): analiza TTML y genera LRC estándar o mejorado.
- [Interfaz nativa de etiquetado MP4](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/muxer/muxer.py): `Muxer.tag()` recibe un objeto `gamdl.download.Tags`; los campos no especificados permanecen intactos.
- [Mapeo de átomos MP4](https://github.com/glomatico/gamdl/blob/4.0/native/src/tags.rs): asocia el campo `lyrics` con el átomo MP4 `©lyr` y el campo `title_id` con `cnID`.

## Flujo exacto de datos

1. Mutagen lee `cnID` del M4A local. Es el ID de catálogo de la **canción**. Los IDs de álbum y artista no se usan como sustitutos.
2. `Song.from_id(song_id, api=api)` crea un objeto diferido. Esta operación no resuelve ni descarga audio.
3. `await song.get_lyrics(syllable=False, language=api.language)` solicita primero las letras TTML estándar.
4. Si el TTML estándar no tiene marcas de tiempo en todas las líneas con texto, `await song.get_lyrics(syllable=True, language=api.language)` utiliza el endpoint `syllable-lyrics` de Gamdl. La API de Gamdl analiza las marcas de tiempo de los elementos `span` y calcula el inicio de cada línea desde su primer segmento temporizado.
5. `Lyrics.render(LyricsFormat.LRC, embedded=False)` convierte la fuente seleccionada en LRC estándar `[mm:ss.xx]`. Aunque la fuente alternativa pueda tener temporización por palabra/sílaba, `LyricsFormat.LRC` desactiva la salida enhanced y conserva una marca de tiempo por línea.
6. `Muxer.tag(staged_path, tags=Tags(lyrics=lrc))` escribe únicamente el campo de letras. Los demás campos quedan en `None`, que el etiquetador de Gamdl trata como «no modificar».
7. El programa vuelve a leer el átomo de letras, verifica la identidad de los datos `mdat`, publica la copia temporal mediante `os.replace()` solo después de ambas verificaciones; no crea un respaldo permanente.

## Reutilización de autenticación

El programa lee `~/.gamdl/config.yml` y admite los valores de `auth.mode` de Gamdl 4.x:

- `cookies`: `AppleMusicApi.from_cookies(auth.cookies_path, ...)`.
- `media-user-token`: `AppleMusicApi.create(media_user_token=..., ...)`.
- `wrapper`: `WrapperApi.create(...)` y después `AppleMusicApi.from_wrapper(...)`.

Las credenciales permanecen en memoria durante la ejecución. El actualizador no cambia el archivo de configuración de Gamdl ni escribe tokens en los registros. El LOG registra códigos HTTP y forma de la respuesta, nunca sus cuerpos ni el TTML. En modo `wrapper`, el servicio Wrapper v2 debe estar disponible y autenticado previamente.

## Disponibilidad y advertencias sobre el endpoint privado

La implementación de letras de catálogo de Gamdl puede consultar dos endpoints AMP de Apple: `/v1/catalog/{storefront}/songs/{song_id}/lyrics` y `/v1/catalog/{storefront}/songs/{song_id}/syllable-lyrics`. El propio código upstream advierte que este endpoint es privado y puede cambiar independientemente de la superficie de API soportada por Gamdl. La disponibilidad de letras también depende de la canción, el storefront, los permisos de la cuenta y el idioma. Si no hay respuesta, TTML o marcas temporales por línea, el programa omite la pista; nunca inventa tiempos.

El actualizador intenta primero `syllable=False` y recurre a `syllable=True` cuando la respuesta estándar carece de sincronización completa. El resultado incrustado sigue siendo LRC estándar por línea, nunca enhanced-LRC ni texto plano.

## Compatibilidad de versiones

El rango de dependencias es `gamdl>=4.0.1,<5`. Si Gamdl modifica la interfaz `Song`, `Lyrics`, autenticación o `Muxer` dentro de una futura versión 4.x, deben ejecutarse las pruebas unitarias y la validación manual con una sola pista real antes de actualizar el entorno.