# Protocolo multi-IA: GitHub + ChatGPT/Codex + Claude
Versión: 2026-10-19. **Alcance:** colaboración por tareas, sin orquestación automática ni gasto periódico de tokens.

## Fuente de verdad y contexto mínimo
1. Identificar repositorio, rama predeterminada real, Issue y SHA actual; no asumir que se llama `main`.
2. Leer `AGENTS.md` y el Issue. Consultar `CLAUDE.md`, la arquitectura y la documentación especializada **solo si aportan instrucciones relevantes**. Las instrucciones particulares y de seguridad del proyecto prevalecen sobre este protocolo genérico.
3. Antes de modificar, identificar archivos afectados y criterios de aceptación; revisar primero el diff y pruebas relacionadas. Evitar leer todo el repositorio o copiar chats anteriores.
4. Mantener decisiones duraderas en documentación existente; tareas, evidencias y pendientes en Issues/PR. No duplicar el estado vivo en varios archivos Markdown.

## Roles por defecto (intercambiables según tarea)
- **ChatGPT/Codex — implementador:** una tarea delimitada, rama específica, cambios mínimos, pruebas y PR.
- **GitHub Actions — validación:** tests/lint/build ya disponibles, asociados al SHA preciso. Un workflow en verde no sustituye la revisión de seguridad.
- **Claude — revisor independiente cuando el riesgo lo justifica:** revisar diff, resultados de CI y unas pocas dependencias relevantes; priorizar defectos reales en vez de otra auditoría general.
- **Responsable humano:** decide prioridades, permisos, despliegues y fusión, conforme a políticas del proyecto.
Si el cambio es documental, pequeño y verificable, no es obligatoria una segunda IA.

## Flujo operativo
1. Crear/seleccionar Issue con objetivo, alcance, pruebas esperadas y criterio de aceptación.
2. Crear rama nueva desde la rama predeterminada actual; no editarla directamente ni fusionar automáticamente.
3. Implementar cambios, ejecutar pruebas pertinentes cuando haya entorno y registrar resultados reales.
4. Abrir PR con resumen, archivos, SHA, pruebas (comando + resultado), riesgos y tareas abiertas.
5. Si es cambio crítico/arriesgado, pasar el **PR y SHA** a Claude para revisar únicamente el diff y hallazgos abiertos. Registrar observaciones P0–P3 con `archivo:línea`, evidencia y corrección; no reclamar revisión de archivos no examinados.
6. Resolver hallazgos demostrables y verificar solamente los cambios nuevos y pruebas afectadas. Repetir auditoría amplia solo si cambió arquitectura o superficie de riesgo.
7. Confirmar CI del último SHA; dejar PR para revisión/fusión humana y actualizar el Issue.

## Traspaso entre agentes (idealmente < 200 palabras)
- Repositorio / rama base / Issue / PR / SHA:
- Objetivo y criterios de aceptación:
- Archivos modificados y razón:
- Comandos de prueba ejecutados y resultados (o `NO EJECUTADOS`):
- Hallazgos P0–P3 con evidencia (o `ninguno identificado`):
- Riesgos, bloqueos y siguiente acción:

## Tokens y continuidad
- **Contexto progresivo:** Issue → diff → tests/CI → archivos pertinentes → arquitectura si hace falta. No entregar archivos íntegros por defecto.
- Reusar identificadores de Issue, PR y SHA. Un nuevo agente debe recuperar el estado desde GitHub, no desde memorias de chat.
- No auditar todos los proyectos por calendario sin señal de riesgo; priorizar cambios de dependencias, seguridad, fallas o entregas.
- Evitar repetir respuestas completas, transcripciones, logs extensos o resúmenes de resúmenes. Citar rutas y líneas.
- **Medición:** contar llamadas, tokens/costo solo cuando lo reporten las herramientas; registrar tiempo a resolución, defectos encontrados después del merge y regresiones. No inventar porcentajes de ahorro.

## Compatibilidad y controles
- ChatGPT web y Claude web **no** cargan por sí mismos todos los .md del repositorio: conector/adjuntos y permisos deben verificarse por sesión. `@AGENTS.md` es una directiva de Claude Code, no una garantía para chats web.
- No hay mensajería nativa ChatGPT↔Claude por colocar archivos Markdown. La transferencia se hace mediante Issue, PR o intervención humana.
- No copiar claves, datos sensibles, credenciales, prompts privados ni contenido del repo privado a repositorios públicos.
- Respaldar reglas locales de pruebas, licencias, privacidad, asesoría jurídico-tecnológica y despliegue ya incluidas en `AGENTS.md`/documentación. No alterar pipelines ni producción solo por adoptar este flujo.

## Prompts reutilizables
**Implementador:** «En [repositorio], lee AGENTS.md e Issue #[n]. Inspecciona solo el diff y archivos pertinentes. Trabaja en una rama, verifica las pruebas relevantes y prepara PR/handoff con SHA, evidencia y riesgos. No edites la rama predeterminada».
**Revisor:** «Revisa el PR #[n] del repositorio [x] en SHA [sha] usando AGENTS.md, diff y CI. Informa solo problemas demostrables P0–P3 con archivo:línea, impacto, evidencia y corrección. No audites todo el proyecto ni edites código».
