# Chat de Vitruvius

La entrada principal es Chat. No se necesita crear un proyecto ni conectar otro cliente.

- Nueva conversación: seleccione las perspectivas con fuentes habilitadas y escriba. El historial permite continuar conversaciones anteriores.
- Adjuntar: PDF, texto, Markdown, PNG, JPEG o WebP; hasta 12 por mensaje. La selección no envía archivos hasta pulsar Enviar. Los adjuntos pertenecen exclusivamente a la conversación y expiran a las 24 horas. Las imágenes tienen un presupuesto de 16 MiB y 25 millones de píxeles; esto no reintroduce el límite de 20 MB de los libros.
- Las imágenes se validan por formato real antes de interpretarse con el modelo visual de OpenRouter. Su descripción automática se identifica como contexto no verificado, nunca como fundamento del autor.
- Crear imagen: petición explícita al modelo multimodal de OpenRouter, consumiendo los créditos existentes. Modelo configurable con OPENROUTER_IMAGE_MODEL, predeterminado google/gemini-3.1-flash-lite-image. La imagen se guarda privadamente durante 24 horas y se identifica como ilustración generada, sin atribución a los autores.
- Las intervenciones aparecen conforme terminan su cotejo de citas y revisión por modelo. No se emiten tokens sin revisar. Una desconexión conserva las intervenciones guardadas. Detener cancela la espera/discusión; la generación de imagen iniciada puede terminar en el servidor y aparecer al abrir de nuevo el historial.
- Markdown y Mermaid se muestran dentro de los mensajes. HTML deshabilitado, sanitización DOMPurify, diagramas en modo estricto y sin imágenes externas cargadas automáticamente. Un diagrama inválido conserva su código legible.
- Las citas muestran título, página y pasaje. Una cita cotejada y revisada por modelo no garantiza que toda interpretación sea correcta. No se promete cero alucinaciones.
- Memoria y Especificaciones siguen siendo resultados opcionales con aprobación explícita. Ningún adjunto se incorpora automáticamente a las fuentes del experto ni a memoria permanente.

No se requiere comprar un componente de chat. Se utilizan Vue/Vuetify existentes y markdown-it, DOMPurify y Mermaid. La primera versión no pretende tener todas las funciones de ChatGPT/Gemini: no incluye voz, navegación web autónoma ni edición de imágenes.

## Verificación

Pruebas del servidor: aislamiento y expiración de adjuntos, autenticación, subconjunto de expertos, validación de imágenes, generación con almacenamiento privado y prohibición de promover imágenes a bibliografía. Prueba del lector de eventos con UTF-8 dividido por byte y corte de conexión. Compilación de producción y revisión visual de Markdown, etiquetas Mermaid y selección/retiro de archivos.

Las pruebas visuales locales usan datos sintéticos explícitamente identificados; no se presentan como libros o respuestas reales de los autores.
