# Historial de cambios

## [0.4.0] - 2026-11-15

### Añadido

- Jerarquía de fuentes: TTML estándar, endpoint `syllable-lyrics` para Enhanced LRC/LRC y texto plano como último recurso.
- Conserva sincronización por palabra/sílaba como Enhanced LRC cuando existe; utiliza LRC estándar si solo hay marcas por línea.
- El texto plano solo se escribe cuando el M4A no contiene el átomo `©lyr`. Si ya existe, no se modifica y se registra `TEXT_FALLBACK_SKIPPED`.
- Añadidas pruebas para fuentes estándar, endpoint syllable, Enhanced LRC, LRC, texto y preservación de etiquetas existentes.

### Comportamiento conservado

- No se incrusta TTML XML directamente en `©lyr`.
- No se crean respaldos permanentes ni se altera el contenido de audio `mdat`.
- El TTML local continúa siendo solo diagnóstico; todavía no se utiliza como fuente.

## [0.3.0] - 2026-11-15

### Añadido

- Cuando el endpoint estándar no devuelve TTML sincronizado para todas las líneas, consulta automáticamente `Song.get_lyrics(syllable=True)` mediante el endpoint `syllable-lyrics` de Gamdl.
- Convierte la sincronización por palabra/sílaba del TTML de respaldo a LRC estándar por línea, usando el inicio temporal de cada línea.
- El LOG distingue peticiones y respuestas `standard` y `syllable`, e identifica qué endpoint produjo el LRC final.
- Añadidas pruebas para fallback tras TTML sin tiempos y tras ausencia de recurso estándar.

### Comportamiento conservado

- No descarga ni modifica audio; solo actualiza `©lyr`.
- No produce enhanced-LRC; el resultado permanece como LRC estándar.
- Si ninguno de los dos endpoints proporciona tiempos para todas las líneas con texto, omite la pista.

## [0.2.0] - 2026-11-15

### Cambiado

- Eliminada la creación de respaldos permanentes; el archivo se prepara en un temporal, se verifica y se publica mediante reemplazo atómico.
- Añadido un LOG acumulativo en `.lyrics-retagger.log`, configurable con `--log-file`.
- Añadido diagnóstico por pista: metadatos de catálogo, `hasLyrics`, estado HTTP, cantidad de recursos, presencia y longitud de TTML, sincronización por línea y estado de escritura.
- Añadida inspección diagnóstica de un sidecar `.ttml` del mismo nombre base cuando Apple Music no devuelve letras. No se usa automáticamente como fuente alternativa.
- El LOG excluye texto de letras, TTML completo y credenciales.
- Añadido el parámetro `--match` para ejecutar consultas diagnósticas sobre pistas seleccionadas por nombre o ruta.

## [0.1.0] - 2026-11-14

### Añadido

- Proyecto inicial para actualizar letras LRC sincronizadas incrustadas en archivos M4A existentes de Apple Music.
- Lectura del identificador de canción de catálogo desde el átomo MP4 `cnID`.
- Reutilización de la autenticación de Gamdl 4.x: cookies, Media User Token o Wrapper v2.
- Consulta asíncrona de letras mediante la API de Gamdl y uso de su etiquetador MP4 nativo; no se descarga ni codifica audio.
- Simulación predeterminada; los cambios requieren el parámetro explícito `--apply`.
- Copias de seguridad no sobrescribibles antes de sustituir archivos.
- Verificación de `©lyr` y de la identidad byte a byte de los datos `mdat` antes de publicar el archivo temporal.
