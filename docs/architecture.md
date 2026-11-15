# Arquitectura y flujo de procesamiento

```text
Carpeta de M4A
   |
   +--> Mutagen lee cnID (ID de canción de catálogo)
              |
              v
       Gamdl 4.x AppleMusicApi
              |
              +--> Song.from_id(cnID)
              |
              +--> Song.get_lyrics(syllable=False)
                         |
                  si no hay tiempos completos
                         v
              +--> Song.get_lyrics(syllable=True)
                         |
                         v
                 TTML -> Lyrics de Gamdl -> LRC estándar
                         |
                         v
             Copia temporal -> Muxer.tag(Tags(lyrics=LRC))
                         |
                         +--> vuelve a leer ©lyr
                         +--> compara SHA-256 de mdat
                         +--> os.replace() atómico; sin respaldo permanente
                         +--> elimina el archivo temporal
                         |
                         +--> registra los detalles en .lyrics-retagger.log
```

## Límites entre módulos

- `mp4.py` extrae el identificador de catálogo y verifica los datos multimedia del contenedor.
- `auth.py` reutiliza la configuración existente de Gamdl y crea `AppleMusicApi` o `WrapperApi` según el método configurado.
- `install_lyrics_api_observer()` registra el estado HTTP y la forma de las respuestas `standard` y `syllable`, sin almacenar sus cuerpos.
- `fetch_synchronized_lrc()` intenta primero el TTML estándar y utiliza el endpoint de sincronización por palabra/sílaba como respaldo si faltan marcas de tiempo. El destino siempre es LRC estándar por línea.
- `fetch_synchronized_lrc()` registra metadatos, consulta TTML, analiza y convierte a LRC mediante Gamdl.
- `inspect_local_ttml()` busca un sidecar TTML homónimo cuando la consulta remota no produce LRC. Solo informa sobre su presencia y sincronización; no lo aplica.
- `apply_embedded_lrc()` modifica únicamente el campo de letras de `gamdl.download.Tags`. El resto de campos quedan en `None` para que Gamdl los conserve.
- `cli.py` administra la búsqueda de archivos, la simulación, el modo de escritura, el LOG y el resumen por archivo.

## Política ante fallos

El actualizador falla de forma conservadora. La ausencia de identificador, letras, sincronización completa o un átomo válido, así como cualquier discrepancia en `©lyr` o en los datos `mdat`, impide reemplazar el original. El M4A se copia a un archivo temporal en la misma carpeta, se etiqueta y se verifica antes de publicarse mediante reemplazo atómico. El temporal se elimina en un bloque `finally`; no se crea un respaldo permanente.

## Registro

El archivo `.lyrics-retagger.log` es acumulativo. En la versión 0.3.0 se registra por separado si la letra utilizable provino de `standard` o `syllable`. Cada ejecución registra la configuración no secreta, el estado de cada archivo, los metadatos de catálogo, los códigos HTTP, la presencia y longitud de TTML, los conteos de líneas sincronizadas, los hashes SHA-256 de `mdat`, las verificaciones del átomo `©lyr` y el resumen. No se registran texto de letras, TTML completo, cookies, tokens ni contraseñas.