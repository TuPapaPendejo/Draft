# Historial de cambios

Los cambios relevantes se registran por versión. Cada commit del repositorio también describe puntualmente su modificación.

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
- Documentación de instalación en WSL con `uv`, parámetros CLI, arquitectura, API upstream y pruebas unitarias.

### Limitaciones conocidas

- Procesa archivos `.m4a` con un `cnID` legible.
- Requiere que Apple Music devuelva letras con sincronización por línea completa; omite letras solo textuales, parcialmente sincronizadas o no disponibles.
- No crea archivos `.lrc` externos.
- La validación final contra una cuenta real de Apple Music debe realizarse manualmente con una pista de prueba.