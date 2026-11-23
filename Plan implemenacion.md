Aquí tienes un plan listo para copiar y enviar al agente del backend. Excluye completamente la implementación de fotografías.

---

# Plan de adecuación del backend para ServIA

Ruta del backend:

`C:\Users\DIEGO\Desktop\Backend-serviceIA\ServIA_BACKEND`

## Objetivo

Ajustar el backend para soportar correctamente los flujos actuales del frontend de ServIA:

- Aceptación segura de ofertas.
- Bloqueo de prestadores con trabajos activos.
- Ciclo completo de inicio, finalización y cancelación.
- Chat seguro y asociado al servicio.
- Cierre y eliminación programada de conversaciones.
- Notificaciones con navegación contextual.
- Retirada de ofertas por parte del prestador.
- Categorías e iconos consistentes.
- Migraciones y pruebas automatizadas.

## Restricción importante

No implementar todavía:

- Carga de imágenes.
- Almacenamiento de fotografías.
- Tablas de fotos.
- Endpoints de imágenes.
- Modificaciones relacionadas con imágenes de publicaciones.

Ese módulo será discutido posteriormente con el equipo.

## Normas de trabajo

1. Analizar el código y el estado de Git antes de modificarlo.
2. El repositorio tiene cambios locales sin commit; no sobrescribirlos ni descartarlos.
3. No modificar ni exponer `.env`.
4. No usar `git reset --hard`, `checkout` destructivo ni eliminar trabajo existente.
5. Implementar una fase a la vez.
6. No comenzar una fase hasta que la anterior:
   - Esté terminada.
   - Tenga pruebas.
   - Pase las validaciones.
7. Mantener compatibilidad con los endpoints consumidos actualmente por el frontend cuando sea posible.
8. No implementar pagos ni billetera.
9. No inventar reglas silenciosamente. Documentar cualquier supuesto.
10. Todas las reglas de negocio deben validarse en backend; el frontend no se considera una barrera de seguridad.

## Regla de negocio asumida

Para este plan:

- Un prestador solo puede tener un servicio activo.
- Se considera servicio activo cuando la publicación está en:
  - `acuerdo`
  - `en_progreso`
- Mientras tenga un servicio activo:
  - No puede enviar nuevas postulaciones.
  - Ningún cliente puede aceptar otra oferta suya.
- Se desbloquea cuando el servicio:
  - Se completa.
  - Se cancela.
- El backend debe ser la autoridad de esta regla.

---

# Fase 0: estabilización y diagnóstico

Antes de implementar funcionalidades:

1. Revisar `git status` y `git diff`.
2. Verificar los cambios locales relacionados con resolución de conflictos.
3. Confirmar que no queden marcadores:
   - `<<<<<<<`
   - `=======`
   - `>>>>>>>`
4. Comprobar que la aplicación puede importar y arrancar.
5. Revisar las dependencias de FastAPI.
6. Crear una lista de endpoints existentes y contratos actuales.
7. Identificar la estructura real de PostgreSQL.
8. No depender exclusivamente de `Base.metadata.create_all()`.

Problema conocido:

`get_mensaje_service()` construye `MensajeService` con un repositorio, pero el constructor necesita también `ConversacionRepository`.

Criterios para cerrar la fase:

- Backend arranca sin errores.
- OpenAPI se genera correctamente.
- Todas las dependencias pueden resolverse.
- No quedan conflictos de Git.
- Los cambios locales preexistentes están preservados.

---

# Fase 1: migraciones y estados oficiales

Incorporar Alembic o un mecanismo equivalente de migraciones versionadas.

## Estados de publicación

Definir oficialmente:

```text
activo
acuerdo
en_progreso
terminado
cancelado
expirado
en_disputa
```

Eliminar o agregar correctamente cualquier estado presente en Pydantic pero ausente en PostgreSQL.

Decidir si `con_ofertas` será:

- Un estado persistente; o
- Un valor calculado según la existencia de ofertas pendientes.

Se recomienda que sea calculado y no un estado del ciclo principal.

## Estados de postulación

Definir:

```text
pendiente
aceptada
rechazada
en_espera
retirada
```

## Campos recomendados

Publicaciones:

```text
cancelled_at
cancelled_by
cancellation_reason
completed_at
started_at
```

Postulaciones:

```text
retirada_at
```

Conversaciones:

```text
created_at
closed_at
delete_after
estado: activa | cerrada
```

## SQL inicial

Actualizar `init.sql` para incluir explícitamente:

- Conversaciones.
- Mensajes.
- Notificaciones.
- Estados nuevos.
- Índices y restricciones.

`init.sql` debe representar la estructura completa para instalaciones nuevas, pero las instalaciones existentes deben actualizarse mediante migraciones.

Criterios de cierre:

- Migraciones aplicables sobre una base existente.
- Migraciones reversibles cuando sea razonable.
- Modelos, Pydantic y PostgreSQL usan los mismos enums.
- `init.sql` coincide con el esquema final.
- Pruebas de migración aprobadas.

---

# Fase 2: seguridad y máquina de estados

Crear una máquina de transiciones explícita.

## Transiciones permitidas

```text
activo -> acuerdo
activo -> cancelado
acuerdo -> en_progreso
acuerdo -> cancelado
en_progreso -> terminado
en_progreso -> cancelado
```

No permitir transiciones arbitrarias mediante un endpoint genérico.

## Permisos

Inicio del trabajo:

- Solo el prestador cuya oferta fue aceptada.
- Publicación obligatoriamente en `acuerdo`.

Finalización:

- Cliente propietario o prestador asignado, según la regla actual del producto.
- Solo desde `en_progreso`.
- Si se desea permitir finalización directa desde `acuerdo`, debe documentarse.

Cancelación:

- Cliente propietario.
- Prestador asignado cuando ya existe acuerdo.
- Requiere razón opcional o obligatoria, según se defina.
- No se puede cancelar un trabajo ya terminado.

## Problema crítico que corregir

Actualmente `iniciar_trabajo` y `completar_trabajo` no verifican que el usuario sea participante del servicio.

Criterios de cierre:

- Ningún tercero puede modificar un servicio ajeno.
- No se puede saltar estados.
- Respuestas correctas:
  - `403` para falta de permisos.
  - `409` para conflicto de estado.
  - `404` para recursos inexistentes.
  - `422` para datos inválidos.
- Pruebas de cada transición y cada rol.

---

# Fase 3: aceptación atómica y bloqueo del prestador

Refactorizar la aceptación de ofertas como una única transacción.

## Al aceptar

1. Bloquear la fila del prestador mediante `SELECT ... FOR UPDATE`.
2. Cargar la publicación con bloqueo.
3. Verificar que:
   - El usuario autenticado sea propietario.
   - La publicación esté `activo`.
   - La oferta esté `pendiente`.
   - El prestador siga activo y disponible.
   - El prestador no tenga publicaciones en `acuerdo` o `en_progreso`.
4. Cambiar la oferta a `aceptada`.
5. Cambiar otras ofertas a `en_espera`.
6. Cambiar la publicación a `acuerdo`.
7. Marcar al prestador como no disponible.
8. Crear o reactivar la conversación.
9. Crear la notificación.
10. Confirmar todo en un único commit.

Si cualquier operación falla, debe revertirse toda la transacción.

## Al crear una postulación

Validar que:

- El usuario sea un prestador registrado.
- La publicación esté activa.
- La publicación no pertenezca al mismo usuario.
- El prestador no esté ocupado.
- El prestador tenga una especialidad compatible con la categoría.
- No exista una postulación activa previa.

## Al completar o cancelar

- Marcar al prestador como disponible.
- Cerrar la conversación.
- Generar las notificaciones correspondientes.

Criterios de cierre:

- Dos clientes no pueden aceptar concurrentemente al mismo prestador.
- No existen estados parciales.
- Solo hay una oferta aceptada por publicación.
- El prestador se bloquea y desbloquea correctamente.
- Existen pruebas de concurrencia.

---

# Fase 4: retirada segura de postulaciones

No usar eliminación física como operación normal.

Crear:

```http
PATCH /postulaciones/{postulacion_id}/retirar
```

o:

```http
POST /postulaciones/{postulacion_id}/retirar
```

## Reglas

El prestador puede retirar ofertas en:

```text
pendiente
en_espera
```

No puede retirar:

```text
aceptada
```

Para una oferta aceptada debe usarse el flujo de cancelación del servicio.

Al retirar:

- Cambiar estado a `retirada`.
- Guardar `retirada_at`.
- Conservar el registro.
- Notificar al cliente si aplica.

El endpoint `DELETE /postulaciones/{id}` debe:

- Eliminarse del uso público; o
- Restringirse a administración/desarrollo; o
- Rechazar postulaciones aceptadas y estados con historial relevante.

Criterios de cierre:

- Una postulación aceptada no puede borrarse.
- Retirar una oferta no borra conversaciones ni publicaciones.
- La oferta retirada no aparece como activa.
- El frontend puede identificar el estado `retirada`.
- Pruebas de propiedad y estados.

---

# Fase 5: reconstrucción segura del chat

## Corregir inyección de dependencias

`MensajeService` debe recibir:

- `MensajeRepository`
- `ConversacionRepository`

## Autorización

Todo acceso al chat debe verificar que el usuario sea:

- Cliente propietario de la publicación; o
- Prestador de la oferta aceptada.

Aplicar esto a:

- Consultar conversación.
- Listar conversaciones.
- Consultar mensajes.
- Enviar mensajes.
- Cerrar conversación.
- WebSocket.

## Listado de conversaciones

Implementar o corregir:

```http
GET /conversaciones
```

Debe devolver exclusivamente conversaciones del usuario autenticado.

Respuesta recomendada:

```json
{
  "items": [
    {
      "id_conversacion": "uuid",
      "estado": "activa",
      "publication": {
        "id": "uuid",
        "descripcion": "..."
      },
      "offer": {
        "id": "uuid",
        "precio_ofertado": 120000
      },
      "partner": {
        "id": "uuid",
        "nombre_completo": "..."
      },
      "last_message": {
        "contenido": "...",
        "fecha_hora": "..."
      },
      "unread_count": 0
    }
  ],
  "total": 1
}
```

## Historial

Mantener temporalmente compatibilidad con:

```http
GET /chat/conversacion/{conversation_id}
```

Pero agregar autenticación y validación de participación.

Preferiblemente normalizar a:

```http
GET /conversaciones/{conversation_id}/mensajes
```

## WebSocket

El servidor no debe confiar en:

- `destino`
- `id_conversacion`

sin validarlos.

Debe confirmar que:

- La conversación existe.
- Está activa.
- El usuario pertenece a ella.
- El destinatario es la contraparte real.
- El servicio no está terminado o cancelado.

Respuesta WebSocket estructurada:

```json
{
  "type": "message",
  "message": {
    "id_mensaje": "uuid",
    "contenido": "Hola",
    "id_conversacion": "uuid",
    "id_remitente": "uuid",
    "id_destinatario": "uuid",
    "fecha_hora": "2026-11-21T..."
  }
}
```

No enviar respuestas como:

```text
Message text was: ...
```

## Longitud

Unificar frontend y backend en máximo 1000 caracteres, salvo que el equipo decida mantener 500.

Criterios de cierre:

- Un usuario no puede leer conversaciones ajenas.
- Un usuario no puede enviar mensajes a través de conversaciones ajenas.
- El historial devuelve el formato correcto.
- El WebSocket entrega mensajes estructurados.
- El listado no necesita reconstruirse mediante publicaciones y ofertas.
- Pruebas HTTP y WebSocket aprobadas.

---

# Fase 6: cierre y retención de conversaciones

Al completar o cancelar un servicio:

- Cambiar conversación a `cerrada`.
- Guardar `closed_at`.
- Definir `delete_after`.
- Impedir nuevos mensajes.
- Mantener lectura del historial durante el periodo de conservación.

Periodo inicial recomendado:

```text
30 días
```

Debe ser configurable mediante entorno, por ejemplo:

```text
CHAT_RETENTION_DAYS=30
```

Crear un proceso programado que:

1. Busque conversaciones cerradas con `delete_after <= now()`.
2. Elimine o anonimice mensajes.
3. Elimine o archive la conversación.
4. Registre cuántos elementos procesó.
5. Sea idempotente.

No ejecutar borrado automático desde una petición del usuario.

Criterios de cierre:

- Chat cerrado al terminar o cancelar.
- No se pueden enviar mensajes después del cierre.
- El historial permanece durante la retención.
- El proceso de limpieza tiene pruebas.
- La eliminación en cascada no rompe trabajos activos.

---

# Fase 7: notificaciones estructuradas

## Contrato

La respuesta debe incluir el campo `data` existente en el modelo.

Ejemplo:

```json
{
  "id": "uuid",
  "tipo": "oferta_aceptada",
  "titulo": "Tu oferta fue aceptada",
  "mensaje": "...",
  "referencia_id": "publication-id",
  "data": {
    "publication_id": "uuid",
    "offer_id": "uuid",
    "conversation_id": "uuid",
    "destination": "chat"
  },
  "leida": false,
  "created_at": "..."
}
```

## Tipos mínimos

### `oferta_recibida`

Destinatario: cliente.

```json
{
  "destination": "publication_offers",
  "publication_id": "...",
  "offer_id": "..."
}
```

### `oferta_aceptada`

Destinatario: prestador.

```json
{
  "destination": "chat",
  "publication_id": "...",
  "offer_id": "...",
  "conversation_id": "..."
}
```

### `servicio_iniciado`

Destinatario: cliente.

```json
{
  "destination": "job_detail",
  "publication_id": "..."
}
```

### `servicio_completado`

Destinatario: cliente.

```json
{
  "destination": "review",
  "publication_id": "...",
  "provider_id": "..."
}
```

### `servicio_cancelado`

Destinatarios: cliente y prestador.

```json
{
  "destination": "job_detail",
  "publication_id": "..."
}
```

### `calificacion_recibida`

Destinatario: prestador.

```json
{
  "destination": "reviews",
  "publication_id": "...",
  "review_id": "..."
}
```

### `postulacion_retirada`

Destinatario: cliente.

```json
{
  "destination": "publication_offers",
  "publication_id": "...",
  "offer_id": "..."
}
```

`nuevo_mensaje` puede agregarse posteriormente si se requieren notificaciones persistentes además del WebSocket.

## Reglas

- Crear notificación dentro de la misma transacción del evento principal cuando sea posible.
- Evitar `try/except` que silencie errores importantes con `print`.
- Usar logging estructurado.
- Definir si el fallo de una notificación debe revertir el evento principal o quedar en una cola de reintento.

Criterios de cierre:

- `data` aparece en la API.
- Cada tipo tiene un contrato documentado.
- Todos los IDs necesarios para navegar están presentes.
- No se obliga al frontend a adivinar el destino.
- Pruebas para generación, propiedad, lectura y eliminación.

---

# Fase 8: categorías e iconos

Crear:

```http
GET /categorias
```

Respuesta:

```json
{
  "items": [
    {
      "id": "uuid",
      "nombre": "Plomería",
      "descripcion": "...",
      "icono": "water-outline"
    }
  ]
}
```

## Normalización

Todas las publicaciones deben devolver:

```json
{
  "categoria": {
    "id": "uuid",
    "nombre": "Plomería",
    "icono": "water-outline"
  }
}
```

Aplicar en:

- Listado de publicaciones del cliente.
- Solicitudes disponibles del prestador.
- Detalle de publicación.
- Trabajos activos.
- Historial.
- Ofertas enriquecidas.
- Reseñas relacionadas.

Mantener `construct-outline` como fallback si el icono no existe.

Criterios de cierre:

- Backend es la fuente única de categorías.
- Todos los endpoints usan el mismo contrato.
- Los UUID coinciden con las semillas actuales.
- No se devuelven nombres de campos distintos como `categoria_icono`, `icono_categoria`, etc.
- Pruebas de serialización.

---

# Fase 9: pruebas y documentación final

Agregar pruebas automatizadas con base aislada.

## Pruebas mínimas

### Ofertas

- Crear oferta válida.
- No ofertar a publicación propia.
- No duplicar oferta activa.
- No ofertar estando ocupado.
- Retirar oferta propia.
- No retirar oferta ajena.
- No retirar oferta aceptada.

### Aceptación

- Solo propietario acepta.
- Solo desde publicación activa.
- Solo oferta pendiente.
- Otras ofertas pasan a espera.
- Se crea conversación.
- Prestador queda ocupado.
- Concurrencia sobre el mismo prestador.

### Trabajos

- Solo participantes pueden iniciar/completar/cancelar.
- Transiciones inválidas rechazadas.
- Completar libera al prestador.
- Cancelar libera al prestador.
- Completar/cancelar cierra el chat.

### Chat

- Historial requiere autenticación.
- Solo participantes leen.
- Solo participantes envían.
- Conversación cerrada rechaza mensajes.
- WebSocket no acepta destinatarios arbitrarios.

### Notificaciones

- Tipo y `data` correctos.
- Solo propietario puede marcar o eliminar.
- IDs requeridos presentes.

### Categorías

- Iconos presentes.
- Contrato uniforme.

## Documentación

Actualizar README con:

- Diagrama del ciclo de publicación.
- Diagrama del ciclo de postulación.
- Estados del prestador.
- Eventos de notificación.
- Contrato WebSocket.
- Política de retención del chat.
- Comandos de migración.
- Comandos de pruebas.

## Validación final

Antes de entregar:

- Ejecutar todas las pruebas.
- Revisar OpenAPI.
- Probar migraciones sobre base vacía y base existente.
- Confirmar que no se modificó `.env`.
- Confirmar que no se implementó nada relacionado con imágenes.
- Entregar resumen de archivos modificados.
- Documentar cualquier cambio que requiera adaptación posterior del frontend.

---

## Resultado esperado

Al terminar, el backend deberá garantizar:

```text
Cliente acepta oferta
        ↓
Prestador queda ocupado
        ↓
Se crea chat seguro
        ↓
Solo ambas partes pueden comunicarse
        ↓
Servicio inicia
        ↓
Servicio termina o se cancela
        ↓
Prestador vuelve a estar disponible
        ↓
Chat queda cerrado
        ↓
Chat se elimina después del periodo configurado
```

Las fotografías quedan expresamente fuera de este alcance.