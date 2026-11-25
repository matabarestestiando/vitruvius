## Corrección del fallo de conversación — 25 de noviembre de 2026

Se investigó el incidente real de la conversación «Hola». El checkpoint guardó ValueError por selección de experto inválido en el moderador, con cero intervenciones en esa consulta. El aviso anterior afirmaba erróneamente que habían quedado intervenciones verificadas de esa ejecución.

El moderador valida tipos e identificadores; acepta un nombre solo si corresponde exactamente a un experto elegible único, reintenta una decisión inválida y recupera el enrutamiento entre expertos con fuentes revisadas. La recuperación no aporta afirmaciones técnicas: siguen siendo obligatorios la recuperación documental, el cotejo literal y la revisión semántica.

Se añadieron saludos sin inferencia técnica, errores con estado real de guardado, diagnóstico por identificador/tipo sin registrar contenido sensible y reintento de la última pregunta sin respuesta. El reintento comprueba conversación, autor, texto, adjuntos y ausencia de intervenciones posteriores; reutiliza el mensaje existente. El navegador recupera esa opción al reabrir la conversación y vacía el borrador cuando el envío fue aceptado. El chat limita cada ejecución a dos intervenciones; puede continuarse con otra pregunta.

La comprobación posterior de idioma también pasó con una explicación en español y tres citas; el saludo respondió en 0,12 segundos en esa prueba. La pregunta original se reintentó desde el navegador en su misma conversación: sigue registrada una sola vez y obtuvo una respuesta de Gulli con tres citas de Agentic Design Patterns, páginas 241 y 440. Lanham se abstuvo; no se presenta esa abstención como respuesta verificada. Las intervenciones antiguas se conservan como historial.

Se añadió traducción de la prosa de las afirmaciones para consultas en español: no cambia citas, identificadores ni tipo de afirmación y se aplica antes de la revisión semántica contra los originales. Las citas permanecen en su idioma original.

Verificación automatizada: 91 pruebas del servidor y 4 del cliente, incluida selección inválida de moderador, recuperación sin publicar afirmaciones no verificadas, saludo sin evasión de consultas técnicas, aislamiento y reutilización del mensaje pendiente, error de stream sin divulgación de diagnósticos y preservación de evidencia durante la traducción. Compilación de producción y reintento visual real completados. Se limpiaron únicamente sesiones temporales de diagnóstico y sus propuestas de memoria, sin borrar la conversación del propietario ni sus libros.

## Actualización: chat nativo — 25 de noviembre de 2026

Por decisión posterior del propietario, Chat vuelve a ser la entrada principal. Ya no es necesario configurar Gemini, Claude o ChatGPT para conversar en Vitruvius. MCP sigue disponible como alternativa. Se mantienen conversaciones sin proyecto y resultados opcionales de memoria/especificación.

Se implementaron historial, selección de expertos con fuentes, adjuntos PDF/texto/Markdown/imágenes, análisis visual temporal, generación real de imágenes vía OpenRouter, Markdown, diagramas Mermaid y revisión de citas. No se compraron componentes de pago. Detalles y límites en CHAT.md.

Verificación: 84 pruebas Python y 3 pruebas del lector de eventos; compilación Vue; revisión visual local y de la versión desplegada mediante acceso local de solo lectura. HTTPS público saludable. Pruebas reales: OpenRouter interpretó una imagen sintética, generó una imagen JPEG privada y la carga por Spaces/Celery quedó ready con interpretación marcada no verificada; aislamiento entre sesiones y acceso anónimo denegado. Solo se limpiaron los registros/archivos sintéticos creados para esa prueba.

Los libros reales de Antonio Gulli y Michael Lanham están cargados y habilitados. Una respuesta real de Gulli cotejó pasajes de Agentic Design Patterns (páginas 118 y 129). La primera consulta amplia produjo abstenciones; otra respuesta de Lanham falló el cotejo literal. Se añadió una única corrección con los mismos pasajes y las mismas comprobaciones. La prueba posterior de MCP en la sesión de Lanham devolvió una afirmación con cita cotejada de la página 31. Esto no asegura que todas las preguntas puedan responderse: se mantiene la abstención y no se promete cero alucinaciones.

No se modificó el despliegue de vitruvius-memory ni se abrieron puertos de memoria o Neo4j. Los apartados siguientes conservan antecedentes de despliegues previos; las referencias al portal sin chat describen la decisión anterior, reemplazada por esta actualización.

# Estado actual: consejo y conversaciones libres

## Corrección del autor del experto

Corregida la errata inicial «Micheal Lanham» por «Michael Lanham» en el experto existente y en los datos iniciales. Se conservan su identificador, métodos, fuentes y asociaciones. El comparador bibliográfico no se ha flexibilizado: obras de otros autores siguen sin poder sustituir su fundamento primario.

La revisión de autoría del propietario ya estaba registrada; se reintentó únicamente la habilitación primaria de AI Agents in Action (Second Edition), que había fallado por esa errata, y pasó correctamente. 78 pruebas backend y comprobación real de la habilitación mediante API autenticada.


## Recuperación de tareas pendientes

Se recuperó el tercer libro, AI Agents in Action (Second Edition), desde el objeto privado ya existente: ready con 392 páginas y 590/590 fragmentos indexados. Su entrega anterior no figuraba en la cola ni entre los trabajos activos/reservados. No se volvió a subir el archivo ni se aprobaron sus fuentes automáticamente.

La reconciliación periódica context.recover revisa documentos queued con archivo guardado y antigüedad mínima de dos minutos. Comprueba la cola celery y las entregas reservadas/activas antes de reenviar. Los bloqueos de fila con SKIP LOCKED evitan tocar una ingestión activa; la marca de envío se confirma antes de publicar, sin escrituras posteriores que pudieran sobrescribir ready. Un fallo de publicación conserva la solicitud durable para reintentar. La comprobación se omite si no se pueden verificar las entregas; no publica a ciegas. El worker y Redis deben estar disponibles para recuperar. Los posibles duplicados tardíos siguen protegidos por el guard de estado y la transacción atómica de ingestión.

Validación: 77 pruebas backend, prueba real de bloqueo PostgreSQL que impide reenviar trabajo activo, recuperación única de una entrega faltante, comprobación real del broker y programación periódica. Los tres libros del propietario están procesados.


## Procesamiento de libros y avance real

Los PDF con texto digital se extraen primero con pypdf conservando el número de página; Docling se mantiene para el análisis de diseño cuando no se detecta texto en la muestra inicial o se solicita PDF_EXTRACTION_MODE=layout. No se activa OCR ni se simula lectura de imágenes. Se registran páginas leídas, páginas sin texto y método de extracción. El texto nativo puede representar tablas sin su estructura de diseño; consulte el PDF original para verificarlas.

La interfaz distingue espera, lectura de páginas, análisis de diseño y preparación de búsquedas. Los contadores se publican en Redis sin contenido del documento y fuera de la transacción atómica del corpus. La pérdida de telemetría no hace fallar la carga. La extracción y los embeddings siguen siendo atómicos; la reejecución borra fragmentos parciales dentro de la misma transacción. Celery confirma después de completar y permite redelivery si se pierde el worker. Los fallos controlados conservan el estado failed.

Verificación real: Agentic Design Patterns quedó ready con 518/518 fragmentos indexados; building ai agents se retomó desde su objeto privado existente, leyó 340/340 páginas con texto y quedó ready con 391/391 fragmentos indexados. No se volvió a subir ningún archivo ni se aprobó su autoría o uso por el experto automáticamente. 74 pruebas backend correctas y frontend compilado.


## Carga de libros simplificada

La navegación muestra Biblioteca. La acción principal «Añadir libro o contenido» abre un recorrido de archivo primero y datos después: seleccionar PDF, confirmar título/autor y autorización, cargar. No se muestran dos formularios ni se exige registrar una referencia como tarea separada. Los registros existentes sin contenido ofrecen «Cargar PDF». La carga se puede retomar con una URL renovada y la misma clave privada; solo se permite para documentos pendientes/fallidos no revisados, nunca para sustituir fuentes procesadas o revisadas.

Después del procesamiento, cada tarjeta ofrece «Revisar y habilitar». La aprobación de autoría y el rol primario/complementario se mantienen explícitos. Perfil y administración avanzada están plegados. El texto aportado manualmente admite referencias sin URL inventada; X/YouTube requieren texto/transcripción para incorporarse como contenido.

Corregida la configuración de iconos: casillas, estados y selectores usan SVG incluidos en Vuetify y ya son visibles sin descargar fuentes. Diálogos sin transición. Validación: 71 pruebas backend, compilación de producción, recorrido visual aislado de carga/revisión y prueba real en Spaces/Docling/pgvector de PDF sintético, reanudación e imposibilidad de reemplazarlo una vez revisado. Datos sintéticos de producción limpiados. Los libros del propietario no fueron modificados.


- El propietario invoca al consejo desde un cliente MCP conectado. `start_conversation` no requiere proyecto. Se retiraron el menú y la creación de proyectos del portal, además de los antiguos tools MCP de configuración de proyectos. El chat del portal sigue eliminado.
- Una conversación puede terminar sin artefactos. La especificación solo se genera a petición y su exportación exige aprobar la revisión actual de esa conversación.
- Vitruvius evalúa declaraciones del propietario y propone recuerdos duraderos con razón y cita literal. No guarda automáticamente las propuestas. El propietario puede aprobarlas, descartarlas o pedir expresamente que se guarde un texto.
- Las peticiones explícitas escriben en la memoria privada y conservan el texto aprobado como registro canónico recuperable. La búsqueda no depende de que Graphiti haya extraído relaciones de ese texto. El catálogo general no expone los textos de memoria.
- Producción verificada: inicio sin proyecto; revisión real por modelo con propuesta sin escritura; consentimiento obligatorio; guardado real en Graphiti privado y recuperación del texto aprobado; especificación solicitada, aprobada y exportada; limpieza completa de datos sintéticos.
- 78 pruebas backend y compilación frontend correctas. El procesamiento de carpetas conserva sus tres pruebas de navegador. Vista aislada del portal validada sin proyectos ni chat.
- No se probó la conexión desde las cuentas particulares del propietario en Gemini, ChatGPT y Claude Code; cada cliente debe admitir MCP remoto y la autenticación existente. Actualice las herramientas del cliente para usar el nuevo recorrido.
- Datos y asociaciones anteriores conservados. Los ámbitos internos de compatibilidad son privados por conversación y no son una configuración del producto. Véase CONVERSATION_MODEL.md.

## Historial de despliegue anterior

# Deployment status — 2026-11-25

## Operational prototype

- Main: 142.93.15.239 / 10.116.0.4. HTTPS portal https://vitruvius.work, REST /api, authenticated MCP /mcp/. Caddy TLS certificate verified. API on loopback behind proxy; Redis, worker and scheduler have no public ports.
- Memory: 157.245.85.152 / 10.116.0.5. Graphiti API bound to private 8001, Bearer authentication, Docker-aware source restrictions allowing main VPC host only. Neo4j 5.26.27 has no published ports. Public 7474, 7687 and 8001 were tested closed.
- Managed PostgreSQL authenticated with the exact corrected private-file password; pgvector 0.8.7 active, embeddings and checkpoint persistence tested. No local production database substitute.
- OpenRouter authentication and real model/embedding calls passed. The owner confirmed rotation. Keys injected through root-only environment files; never committed.
- Spaces private ACL verified, real bounded presigned upload, extraction, embedding and deletion passed. Browser CORS installed for the public portal and local SSH-tunnel origins.
- LangSmith API authentication, synthetic trace write/read and actual Board trace redaction verified. Inputs and outputs were empty in eight inspected actual spans. Memory, context, tool, repository and artifact events record identifiers/counts rather than contents. US default endpoint accepted this account's key.
- Owner login details: `/root/vitruvius-access.txt` on the main server, mode 0600. Runtime secrets under `/etc/vitruvius/runtime.env` and `/etc/vitruvius-memory/runtime.env`. No secrets in this repository or deployment report.

## Implemented scope

| Module | Implementation |
|---|---|
| Skill Registry | Immutable Markdown versions, safe Markdown/ZIP import, explicit version references. |
| Knowledge Engine | Real text/Markdown/PDF ingestion, pgvector semantic retrieval, page/chunk provenance and owner-supplied source metadata. Empty founding libraries. |
| Expert Builder and Boards | Persistent named literature-inspired virtual specialists, skills and configurable models; seven-member founding Board. |
| Board Orchestrator | Dynamic LangGraph moderator, objections/replies/questions, bounded context/turn/tool budgets, durable checkpoints and session history. |
| Long-term memory | Independent Graphiti/Neo4j, OpenRouter inference/embeddings/reranking, explicit curation, scoped search and episode deletion. |
| Projects and code intelligence | Project/session association; owner-mounted Git sources read-only, safe tracked-file listing/search/read and commit provenance. No code execution. |
| Requirements, ADRs and artifacts | Discussion-derived drafts or manual revisions, acceptance criteria, hash-bound owner approvals, current-revision gate. |
| Development handoff | Approved specification prompt export for Codex and Claude Code. |
| Implementation Reviewer | Read-only repository evidence compared to approved artifacts, bounded findings, no invented test execution. |
| MCP inbound | Standard Streamable HTTP; shared session tools, project/session creation, contextual text, presigned temporary upload and draft/export. |
| MCP outbound and tool permissions | Origin allowlist, discovery, per-expert read/write permissions. Writes become owner-reviewable exact-argument requests and one-use approvals. |
| Observability and evaluation | Sanitized LangSmith model/token/session metadata and operation events; 18 deterministic automated tests plus live integration checks. |
| Context Management Engine | SESSION default/24h, REQUEST expiry, all six scopes, expert restrictions, configurable retention, explicit promotion, deletion of originals/chunks/vectors, repeat-deletion tombstones and cross-client continuity. |
| Multimodal extension | Future scope preserved; no claim of audio/video/podcast processing. |

Docling runs in the production worker with CPU-only PyTorch, two threads, one concurrent ingestion, persistent model cache and a 55-minute soft task limit and 60-minute hard task limit. A real synthetic PDF was uploaded through Spaces, extracted with page 1 provenance, embedded and removed successfully. OCR remains disabled. Plain-text/PDF ingestion does not claim EPUB, HTML synchronization or multimedia support.

## Verification evidence

- 16 main-service automated tests, 2 memory-service automated tests passed. These include authentication, context isolation/expiry/promotion/deletion, approval-gated export, repository traversal and sensitive-file exclusion, skill versions/import, exact write-tool approvals, dynamic graph routing, MCP protocol, bounded context and curated-memory episode tracking/deletion.
- Vue/Vuetify production build passed. Visual portal review checked the council, decision and context controls at mobile and desktop layout breakpoints.
- Full live synthetic run passed: pgvector embedding → dynamic Board → shared MCP history → generated draft → approval → handoff → Spaces upload → worker → deletion → Graphiti ingestion/search/isolation → session/history/checkpoint deletion.
- Graphiti relation check extracted 4 nodes and 3 edges, returned 3 facts and returned no facts in another namespace. Synthetic episodes were deleted.
- LangSmith trace write/read and actual content redaction passed; public API and MCP without credentials returned 401, portal returned 200 with valid TLS.
- No books or papers were ingested. All verification data was explicitly synthetic. Interrupted verification sessions are cleaned separately before final handoff.

## Limits and follow-up validation

- This is an operational single-owner prototype. There is no claim of high availability, load testing, backup restoration validation or production security certification.
- Actual books/papers, licensing/provenance review, bibliographic quality evaluation, dataset-based expert evaluations and automated source synchronization await owner-supplied sources. No author opinions are asserted.
- Individual ChatGPT/Claude/Gemini connector setup and OAuth support are not verified; standard Bearer MCP protocol continuity was tested. External VueForge/Alexandria MCP URLs, credentials and allowed tools were not supplied, so no remote integration is represented as connected.
- OCR, EPUB, richer office-file conversion, audio/video/podcasts and automatic failed-graph resumption are not enabled. Completed messages survive failures; retries create visible new turns.
- Original attachment expiry does not erase quotations already generated in private conversation history/checkpoints, provider retention or backups. Session deletion removes local temporary context, messages and checkpoints; permanent knowledge/approved artifacts/curated memories retain independent policies.
- Managed database and droplet backups/restore have not been verified through the DigitalOcean control plane. The supplied doadmin database role is used initially; create a restricted application role and mount the provider CA for verify-full TLS as follow-up hardening. Supplied sslmode=require is active.
- DNS was updated by the owner and public resolver A now returns 142.93.15.239 with no AAAA. Some recursive resolvers may retain the old parking answers until their cache expires. TLS was verified directly against the target address with the real hostname.

## Grounding and expert content correction

The previous ungrounded opinion behavior is disabled. Experts need reviewed primary libraries, retrieved exact quotations and claim review. References, extracted content and reviewed foundations are separate states. Professional profiles remain drafts until owner approval. X/YouTube URLs alone are not ingested evidence. The 20 MiB upload limit has been removed across the pipeline. See GROUNDING.md for behavior, retained operational limits and validation.


## Conversaciones desde clientes; repositorios locales

El portal ya no tiene chat ni menú Conversación. Claude, ChatGPT o Gemini conectado a MCP mantiene la conversación; el portal administra fuentes, expertos y acuerdos y abre la selección de carpeta a petición del cliente.

`prepare_local_repository` devuelve un enlace autenticado al propietario para la sesión. La carpeta se selecciona en el navegador y se comparte explícitamente como copia temporal de 24 horas. El mismo cliente puede listar, buscar y leer el código real; `discuss` lo incorpora como contexto del caso, sin sustituir las fuentes del experto. Las copias se pueden desconectar y vencen incluso si el worker tarda en limpiarlas.

No es acceso en vivo al disco, no requiere publicar el repo privado y no necesita configurar repositorios en un panel. No se verificó la conexión individual de los tres clientes: cada uno debe admitir MCP remoto y la autenticación existente. Véase LOCAL_REPOSITORIES.md para límites y verificación.
