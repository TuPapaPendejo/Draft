# Historial de cambios

Los cambios relevantes se registran por versión. Cada commit del repositorio también describe puntualmente su modificación.

## [0.3.0] - 2026-11-15

### Añadido

- Cuando el endpoint estándar no devuelve TTML sincronizado para todas las líneas, consulta automáticamente `Song.get_lyrics(syllable=True)` mediante el endpoint `syllable-lyrics` de Gamdl.
- Convierte la sincronización por palabra/sílaba del TTML de respaldo a LRC estándar por línea, usando el inicio temporal de cada línea.
- El LOG distingue peticiones y respuestas `standard` y `syllable`, e identifica qué endpoint produjo el LRC final.
- Añadidas pruebas para fallback tras TTML sin tiempos y tras ausencia de recurso estándar.

### Comportamiento conservado

- No descarga ni modifica audio; solo actualiza `©lyr`.
- No produce enhanced-LRC; el resultado permanece como LRC estándar.
- Si ninguno de los endpoints proporciona tiempos para todas las líneas con texto, omite la pista.

## [0.2.0] - 2026-11-15

### Cambiado

- Eliminada la creación de respaldos permanentes; el archivo se prepara en un temporal, se verifica y se publica mediante reemplazo atómico.
- Añadido un LOG acumulativo en `.lyrics-retagger.log`, configurable con `--log-file`.
- Añadido diagnóstico por pista: metadatos de catálogo, `hasLyrics`, estado HTTP, cantidad de recursos, presencia y longitud de TTML, sincronización por línea y estado de escritura.
- Añadida inspección diagnóstica de un sidecar `.ttml` del mismo nombre base cuando Apple Music no devuelve letras. No se usa automáticamente como fuente alternativa.
- El LOG excluye texto de letras, TTML completo y credenciales.
- Añadido el parámetro `--match` para ejecutar consultas diagnósticas sobre pistas seleccionadas por nombre o ruta.
- Añadidas pruebas para observación segura de respuestas, estados HTTP 404, detección de TTML local, filtro de archivos y ausencia de respaldos.

### Limitaciones

- Las carpetas de respaldo creadas por versiones anteriores no se borran automáticamente.
- Un TTML local se detecta solo si está junto al M4A y comparte el nombre base.

## [0.1.0] - 2026-11-14

### Añadido

- Proyecto inicial para actualizar letras LRC sincronizadas incrustadas en archivos M4A existentes de Apple Music.
- Lectura del identificador de canción de catálogo desde el átomo MP4 `cnID`.
- Reutilización de la autenticación de Gamdl 4.x: cookies, Media User Token o Wrapper v2.
- Consulta asíncrona de letras mediante la API de Gamdl y uso de su etiquetador MP4 nativo; no se descarga ni codifica audio.
- Simulación predeterminada; los cambios requieren el parámetro explícito `--apply`.
- Copias de seguridad no sobrescribibles antes de sustituir archivos.
- Verificación de `©lyr` y de la identidad byte a byte de los datos `mdat` antes de publicar el archivo temporal.
- Rechazo de letras parcialmente sincronizadas: toda línea con texto debe tener marca de tiempo.
- Documentación de instalación en WSL con `uv`, parámetros CLI, arquitectura, API upstream y 13 pruebas unitarias.

### Limitaciones conocidas

- Procesa archivos `.m4a` con un `cnID` legible.
- Requiere que Apple Music devuelva letras con sincronización por línea completa; omite letras solo textuales, parcialmente sincronizadas o no disponibles.
- No crea archivos `.lrc` externos.
- La validación final contra una cuenta real de Apple Music debe realizarse manualmente con una pista de prueba.