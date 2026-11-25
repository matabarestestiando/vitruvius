# Expertos sustentados en fuentes

El nombre de un panelista no constituye conocimiento ni evidencia. Desde esta corrección, el Board no permite opiniones técnicas de un experto sin fuentes primarias revisadas y disponibles para el proyecto. El comportamiento anterior de responder con conocimiento general del modelo queda deshabilitado en el Board.

## Biblioteca y contenido de cada experto

En Expertos, seleccione el experto y registre su contenido: título, autor o responsable, tipo y URL. Se admiten registros de artículos, publicaciones de X, PDF y videos de YouTube.

Un registro conserva procedencia, pero no significa contenido ingerido. Artículos públicos y enlaces PDF pueden importarse mediante un trabajo de procesamiento. Los PDF también pueden cargarse directamente. Para publicaciones de X y videos de YouTube, esta versión conserva el enlace y permite incorporar texto, transcripción con tiempos o PDF aportados por el propietario. No se afirma haber leído un post o visto un video a partir del enlace solo. No se ha configurado una API de X ni una integración autorizada de subtítulos de YouTube.

La importación de artículos recupera el texto público accesible, sin ejecutar scripts, enviar credenciales ni sortear autenticación. Se bloquean destinos privados/locales/metadatos y cada redirección se resuelve y valida por separado, fijando la dirección de conexión y conservando la validación TLS del hostname. La extracción de HTML requiere revisión humana: una página puede estar incompleta o contener solo una parte pública. La importación por red está limitada a 64 MiB por operación. Para recursos remotos mayores se utiliza la carga directa, que ya no tiene el tope de 20 MiB de la aplicación.

El contenido aportado a un experto se conserva en ámbito EXPERT con autorización explícita. No se convierte automáticamente en fundamento. La incorporación y el índice vectorial tienen estados separados; una fuente no revisada no habilita al experto.

## Fundamento primario y bibliografía complementaria

Las fuentes primarias son obras del autor que inspira al panelista o documentación técnica oficial cuyo autor/entidad y procedencia haya revisado el propietario. Las obras de otro autor se asignan como bibliografía complementaria. Por ejemplo, una obra de Roberto Infante puede enriquecer a Harrison, pero no sustituir por sí sola el fundamento primario de ese panelista.

La documentación de LangGraph puede sustentar análisis sobre el framework; no demuestra una opinión personal de Harrison Chase. Los metadatos de autoría se registran y revisan por el propietario, no se verifican automáticamente contra Internet. El sistema no promete representar a la persona real.

## Intervenciones y evidencia

El moderador solo convoca expertos con fuentes primarias disponibles bajo los permisos y ámbitos del contexto actual. Sin biblioteca primaria no hay llamadas generativas de opinión ni conclusión técnica sustitutiva. Si no se recuperan fragmentos o la respuesta no supera las comprobaciones, el experto se abstiene.

Cada afirmación se estructura como contenido de fuente o interpretación propuesta. Se exigen IDs reales de fragmentos recuperados, citas literales de esos fragmentos y al menos una premisa primaria. No se admite bibliografía complementaria como único fundamento. Un segundo paso de revisión con el modelo contrasta las afirmaciones con los pasajes citados; el fallo, la referencia inventada o la cita inexistente producen abstención. La memoria, Skills, historial y resultados de herramientas no cuentan por sí solos como evidencia bibliográfica. Los requisitos y documentos del proyecto se recuperan por separado como contexto del caso; no se convierten en fundamento del autor. Cada interpretación profesional exige una premisa primaria y la revisión contrasta también la pertinencia con la consulta.

La revisión semántica con un LLM es falible: estas barreras no constituyen una prueba formal de verdad ni eliminan la necesidad de curación y revisión humana. Las citas permiten examinar título, autor registrado, página o tiempo aportado, fragmento literal y procedencia; los originales PDF se abren con un enlace privado de 60 segundos para el propietario. Las intervenciones antiguas sin esta revisión se muestran como no verificadas.

El resumen del moderador ya no añade una conclusión técnica generada libremente: conserva la distinción entre intervenciones y aprobación del propietario.

## Perfil profesional documentado

A partir de las fuentes primarias se propone un borrador de criterios, principios, método y formas profesionales de argumentar. Cada punto incluye evidencia y distingue extracción e interpretación. Los puntos de un borrador que no superan la revisión semántica se descartan; si no queda ninguno, no se genera un perfil. No se infieren rasgos psicológicos, emociones, creencias privadas ni opiniones no expresadas.

El perfil no entra al contexto de los agentes hasta que el propietario lo aprueba. Un perfil basado íntegramente en bibliotecas EXPERT/GLOBAL puede usarse por ese experto entre proyectos; si usa material de ámbito más restringido queda limitado al proyecto de origen. Si desaparecen las fuentes o los permisos, no se aplica el perfil. Nuevos contenidos pueden dar lugar a nuevos borradores, sin sustituir automáticamente el aprobado.

## Estado y verificación

Las bibliotecas fundadoras no se rellenan con fuentes ficticias. Los expertos existentes sin fundamento quedan bloqueados para emitir opiniones hasta que se incorporen fuentes reales y se revisen. Se prueban rechazo de citas/IDs inventados, afirmaciones que no superan revisión, obras de otros autores como complemento, fuentes temporales, registros de videos sin contenido, consentimiento de incorporación y aprobación/invalidación de perfiles. Las pruebas con datos sintéticos no prueban que el sistema reproduzca el criterio de un autor real.

## Archivos grandes

Se retiró el tope de 20 MiB de la política de subida, de la confirmación de carga, del worker y del conversor. También se retiraron los topes de 500 páginas y dos millones de caracteres. Los originales se descargan por bloques a un archivo temporal privado; el índice se genera en lotes de 32 fragmentos sin liberar anticipadamente la transacción del worker. Los temporales se eliminan al terminar y los restos de un proceso interrumpido se limpian desde el worker de retención.

El procesamiento conserva un límite operativo de 55 minutos antes de interrupción controlada y 60 minutos como máximo por tarea, una sola tarea concurrente y una reserva de espacio temporal. No se promete capacidad física infinita: siguen aplicando los límites de Spaces, disco, memoria y extracción. OCR sigue desactivado. El tope artificial de 20 MiB ya no es una condición de aceptación de archivos.

La lectura automática de subtítulos de cualquier canal de YouTube no se presume: la [API oficial de descarga de subtítulos](https://developers.google.com/youtube/data/reference/rest/v3/captions/download) exige autorización y permiso de edición del video. Esta versión usa una transcripción aportada por el propietario y conserva su procedencia.
