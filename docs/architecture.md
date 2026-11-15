# Arquitectura y flujo de procesamiento

```text
M4A -> Mutagen lee cnID -> Gamdl 4.x -> Song.from_id(cnID)
                                      |
                                      +-> get_lyrics(syllable=False): TTML estándar
                                      |       +-> tiempos por segmento: Enhanced LRC
                                      |       +-> tiempos solo por línea: LRC
                                      |
                                      +-> si no hay sincronización completa:
                                              get_lyrics(syllable=True)
                                              +-> tiempos por segmento: Enhanced LRC
                                              +-> tiempos solo por línea: LRC
                                              +-> sin tiempos: extraer texto
                                                         |
                                                         +-> escribir solo si ©lyr no existe
M4A temporal -> Muxer.tag(Tags(lyrics=contenido)) -> verificar ©lyr y SHA-256 de mdat
             -> os.replace() atómico -> limpiar temporal; sin respaldo permanente
```

## Límites entre módulos

- `mp4.py` extrae el identificador de catálogo y verifica los datos multimedia del contenedor.
- `auth.py` reutiliza la configuración existente de Gamdl y crea `AppleMusicApi` o `WrapperApi` según el método configurado.
- `install_lyrics_api_observer()` registra el estado HTTP y la forma de las respuestas `standard` y `syllable`, sin almacenar sus cuerpos.
- `fetch_best_lyrics()` aplica la jerarquía: TTML estándar, endpoint `syllable-lyrics` y finalmente texto extraído de los objetos `Lyrics` ya recibidos.
- Los resultados sincronizados se renderizan como `enhanced-lrc` cuando hay tiempos por segmento, o como `lrc` cuando únicamente hay tiempos por línea.
- El formato `text` es el último recurso. Solo se permite escribirlo si `read_embedded_lyrics()` devuelve `None`, es decir, si el M4A no tiene el átomo `©lyr`. Incluso una etiqueta vacía ya existente se conserva.
- `inspect_local_ttml()` busca un sidecar TTML homónimo cuando la API no produce contenido utilizable. Solo informa sobre su presencia y sincronización; no lo aplica.
- `apply_embedded_lyrics()` modifica únicamente el campo de letras de `gamdl.download.Tags`. Los demás campos quedan en `None` para que Gamdl los conserve.
- `cli.py` administra la búsqueda de archivos, la simulación, el modo de escritura, el LOG y el resumen por archivo.

## Política ante fallos

El actualizador falla de forma conservadora. La ausencia de identificador, de letras, de contenido utilizable o de un átomo válido, así como cualquier discrepancia en `©lyr` o en los datos `mdat`, impide reemplazar el original. Las líneas parcialmente sincronizadas no se presentan como LRC completo. El M4A se copia a un archivo temporal, se etiqueta y se verifica antes de publicarse mediante reemplazo atómico. El temporal se elimina; no se crea un respaldo permanente.

## Registro

El LOG acumulativo registra endpoint, formato seleccionado, conteos de líneas y segmentos sincronizados, decisión sobre el fallback de texto, metadatos de catálogo, códigos HTTP, presencia y longitud de TTML, hashes de `mdat` y verificaciones de `©lyr`. No registra texto de letras, TTML completo, cookies, tokens ni contraseñas.
