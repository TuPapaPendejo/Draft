# Notas de integración con la API de Gamdl 4.x

Este proyecto utiliza la API de alto nivel de Gamdl 4.x y declara `gamdl>=4.0.1,<5`.

## Puntos de entrada upstream

- [Modelo de canción](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/media/song/media.py): `Song.get_lyrics()` devuelve un objeto `Lyrics` tras consultar TTML.
- [Endpoints de catálogo](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/api/apple_music/catalog.py): `get_lyrics()` y `get_syllable_lyrics()`.
- [Analizador y exportadores](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/media/song/lyrics.py): `LyricsFormat` incluye `ttml`, `enhanced-lrc`, `lrc` y `text`.
- [Selección de formatos en Gamdl](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/download/downloader.py): Gamdl solicita el endpoint syllable cuando el formato elegido es Enhanced LRC y puede recurrir al endpoint estándar si la sincronización por segmento no existe.

## Jerarquía de recuperación

1. **TTML estándar:** `Song.get_lyrics(syllable=False)` consulta `/songs/{id}/lyrics`. Si todas las líneas con texto tienen inicio temporal, se genera LRC. Si además contiene tiempos por segmento, se preservan como Enhanced LRC.
2. **Enhanced LRC:** si el primer recurso no permite obtener sincronización completa, `Song.get_lyrics(syllable=True)` consulta `/songs/{id}/syllable-lyrics`. Los tiempos de palabras/sílabas se convierten a Enhanced LRC.
3. **LRC:** si la fuente alternativa solo tiene marcas por línea, se genera LRC estándar. No se aceptan líneas parcialmente sincronizadas como LRC completo.
4. **Texto:** si ninguna fuente ofrece sincronización utilizable, `LyricsFormat.TEXT` extrae el texto de los objetos `Lyrics` ya recuperados. No hay un endpoint independiente denominado `lyrics_text`. El texto solo se escribe si el M4A no tiene el átomo `©lyr`; una etiqueta existente, incluso vacía, se conserva y se registra como `TEXT_FALLBACK_SKIPPED`.

El TTML XML no se incrusta directamente en `©lyr`: el átomo recibe Enhanced LRC, LRC o texto plano según la fuente disponible y las reglas anteriores.

## Flujo de datos

1. Mutagen lee `cnID` del M4A local.
2. `Song.from_id(song_id, api=api)` crea un objeto diferido; no solicita un stream de audio.
3. Se consulta `Song.get_lyrics(syllable=False)`.
4. Si la respuesta no tiene sincronización completa, se consulta `Song.get_lyrics(syllable=True)`.
5. `Lyrics.render(ENHANCED_LRC)`, `Lyrics.render(LRC)` o `Lyrics.render(TEXT)` genera la representación seleccionada.
6. `Muxer.tag(staged_path, tags=Tags(lyrics=content))` escribe únicamente el campo de letras.
7. Se vuelve a leer `©lyr`, se verifica la identidad de los datos `mdat` y se publica la copia temporal con `os.replace()`.

## Autenticación y límites

El programa reutiliza `~/.gamdl/config.yml` (cookies, Media User Token o Wrapper v2) sin registrar credenciales. Los endpoints de letras de Apple Music son privados y pueden cambiar. La disponibilidad depende de canción, storefront, idioma y autorización.

El TTML local homónimo continúa como diagnóstico y no forma parte de la cascada de fuentes.

## Compatibilidad

El rango de dependencia es `gamdl>=4.0.1,<5`. Deben ejecutarse las pruebas unitarias y validar manualmente una pista antes de actualizar Gamdl.
