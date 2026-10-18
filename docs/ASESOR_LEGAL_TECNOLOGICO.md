# Revisión jurídico-tecnológica transversal

**Marco:** adaptación operativa del archivo de usuario `asesor-legal-tecnologico.skill` (v1.1.0, recibido 2026-10-18). Aplica a nuevas funcionalidades, incidentes, cambios de arquitectura, publicación, proveedores, IA, contratos y tratamiento de datos. No constituye certificación legal ni sustituye asesoría profesional habilitada.

## Capas obligatorias cuando sean pertinentes
1. **Legal:** identificar países implicados, normas vigentes verificadas en fuentes oficiales, y diferenciar obligación legal, contractual, estándar y buena práctica.
2. **Técnica:** diagrama real de flujos, componentes, dependencias y control sobre repositorio, dominio, hosting y credenciales; no inventar arquitectura.
3. **Seguridad:** autenticación, autorización real del servidor, secretos, menor privilegio, registros, pruebas y recuperación.
4. **Datos:** inventario de datos personales, finalidad, acceso, almacenamiento y terceros, retención, exportación y eliminación.
5. **Evidencia:** preservar fuentes, consentimientos, versiones, commits, logs y trazabilidad verificable de incidentes.
6. **Responsabilidad:** separar actores y obligaciones sin atribuir culpas sin evidencia.
7. **Negocio:** proporcionalidad de costo, riesgo, mantenimiento, continuidad, dependencia y alternativas simples.

## Criterio de aceptación previo al despliegue
- Registrar hechos **confirmados / probables / posibles / no verificados** y jurisdicciones; verificar vigencia de legislación, políticas de plataforma, licencias y estándares cuando sean relevantes.
- Para cambios que tratan datos: identificar quién es responsable, qué datos entran y salen, base/finalidad, minimización, acceso, plazo de retención y retiro.
- Para proveedores externos: revisar contratos/licencia, control de datos, portabilidad, SLA, rescisión, subprocesadores y riesgos de dependencia.
- Para uso de IA: justificar su necesidad, evitar ingresar secretos o información personal innecesaria y comprobar términos actuales del proveedor.
- Para consentimiento, uso de imagen/voz, contenido de terceros o firma electrónica: verificar autorización y jurisdicción. Un hash, OTP o registro de IP **no** equivale por sí solo a una categoría jurídica de firma avanzada.
- Ante incidentes: contener sin destruir evidencia; registrar fecha UTC, alcance, acciones y criterios de recuperación.
- Abrir issue P0/P1 ante exposición real de datos, secretos o permisos inseguros; no afirmar cumplimiento ni cerrar hallazgos sin prueba.
- Anotar `riesgo → evidencia → control → prueba → responsable → estado` en el PR o issue.

## Prioridades específicas del repositorio

Chile/Región del Biobío; licencias de datos e imágenes de agendas de terceros, eventos para menores, términos de entradas y cambios de programación, procedencia de horarios/ubicaciones, recolección respetuosa y registros de corrección.

**Puerta de salida:** documentar controles pertinentes con pruebas; si falta normativa verificable o validación operativa, mantener el riesgo en abierto. Las funciones ajenas a este alcance no se declaran revisadas.
