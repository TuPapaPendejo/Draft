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
              +--> Song.get_lyrics()
                         |
                         v
                 TTML -> Lyrics de Gamdl -> LRC estándar
                         |
                         v
             Copia temporal -> Muxer.tag(Tags(lyrics=LRC))
                         |
                         +--> vuelve a leer ©lyr
                         +--> compara SHA-256 de mdat
                         +--> guarda el original como respaldo
                         +--> reemplazo atómico
```

## Límites entre módulos

- `mp4.py` extrae el identificador de catálogo y verifica los datos multimedia del contenedor.
- `auth.py` reutiliza la configuración existente de Gamdl y crea `AppleMusicApi` o `WrapperApi` según el método configurado.
- `fetch_synchronized_lrc()` delega en Gamdl la consulta de TTML, el análisis y la conversión a LRC.
- `apply_embedded_lrc()` modifica únicamente el campo de letras de `gamdl.download.Tags`. El resto de campos quedan en `None` para que Gamdl los conserve.
- `cli.py` administra la búsqueda de archivos, la simulación, el modo de escritura y el resumen por archivo.

## Política ante fallos

El actualizador falla de forma conservadora. La ausencia de identificador, letras, sincronización completa o un átomo válido, así como cualquier discrepancia en `©lyr` o en los datos `mdat`, impide reemplazar el original. Los temporales se eliminan en un bloque `finally`. El respaldo se crea antes de publicar la copia etiquetada.