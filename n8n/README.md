# n8n — Automatizar el análisis de correos de HELIOS

Este workflow hace que HELIOS analice **cada correo nuevo automáticamente**, sin
que tengas que pedirlo. El flujo es:

```
Gmail Trigger (correo nuevo)  →  HTTP Request  →  HELIOS pipeline
                                 POST /api/v1/emails/process
```

HELIOS recibe solo el **id del correo** (no su contenido); él mismo lee el correo
de tu Gmail (solo lectura) y ejecuta la clasificación + agentes + supervisor, y
te alerta por Telegram si algo es importante.

---

## Archivo a importar
`helios-gmail-auto-process.json`

## Requisitos previos
- HELIOS levantado (`docker compose up -d`) — n8n está en `http://localhost:5678`.
- Tu Gmail ya conectado en HELIOS (lo está: cuenta `account_id = 4`).
- Tu `SERVICE_API_TOKEN` (está en tu `.env`, línea `SERVICE_API_TOKEN=`).

---

## Pasos (una sola vez)

### 1. Importar el workflow
1. Abre **http://localhost:5678**.
2. Menú (arriba a la derecha) → **Import from File** (o *Workflows → Import*).
3. Elige `n8n/helios-gmail-auto-process.json`.

### 2. Conectar tu Gmail en n8n (credencial OAuth)
El **Gmail Trigger** necesita su propia credencial de Google dentro de n8n
(es independiente de la conexión de HELIOS):
1. Abre el nodo **"Gmail Trigger (correo nuevo)"**.
2. En **Credential**, crea una nueva **Gmail OAuth2**.
3. n8n te pedirá un Client ID / Client Secret de Google y un redirect propio de
   n8n. Puedes reusar el mismo proyecto de Google Cloud que ya usas para HELIOS:
   añade en *Authorized redirect URIs* la URL que n8n te muestre
   (algo como `http://localhost:5678/rest/oauth2-credential/callback`).
4. Autoriza y guarda. El nodo quedará enlazado a esa credencial.

> Nota: aquí el scope puede requerir lectura de Gmail para que el trigger detecte
> correos. HELIOS sigue siendo quien lee el contenido en modo solo-lectura; n8n
> solo necesita saber que **llegó** un correo (su id).

### 3. Poner tu SERVICE_API_TOKEN
1. Abre el nodo **"HELIOS: procesar correo"**.
2. En **Headers**, busca `X-Service-Token` y reemplaza el valor
   `__PON_TU_SERVICE_API_TOKEN__` por el valor real de `SERVICE_API_TOKEN`
   (el que está en tu `.env`).
   - Más seguro (recomendado): en vez de pegarlo en claro, crea una credencial
     tipo *Header Auth* en n8n con ese token y úsala en el nodo.

### 4. Verificar el `account_id`
El nodo ya envía `account_id: 4` (tu Gmail conectado). Si algún día conectas
otra cuenta y quieres procesarla, cambia ese número por el `id` correcto
(lo ves en HELIOS → Connections, o en `GET /api/v1/connections`).

### 5. Activar
Pulsa el switch **Active** (arriba a la derecha del workflow). ¡Listo!
Desde ahora, cada correo nuevo se procesa solo.

---

## Probar que funciona
1. Con el workflow **activo**, envíate un correo de prueba a tu Gmail.
2. En n8n → pestaña **Executions**: debería aparecer una ejecución en verde.
3. En HELIOS COMMAND → **Dashboard**: el contador de correos y la actividad
   reciente deben aumentar.
4. Si el correo es importante (crítico/alto), te llega una **alerta por Telegram**.

## Si algo falla
- **401 Invalid service token**: el `X-Service-Token` no coincide con tu
  `SERVICE_API_TOKEN`. Revisa el paso 3.
- **404 Account not found**: el `account_id` no existe. Revisa el paso 4.
- **429 Rate limit**: llegaron demasiados correos muy rápido; es una protección,
  se normaliza solo.
- **El HTTP node no alcanza el backend**: la URL debe ser `http://backend:8000`
  (nombre de servicio en la red Docker), no `localhost`.

---

## Nota de arquitectura (por qué así)
- HELIOS **no acepta el contenido** del correo desde n8n: solo `account_id` +
  `provider_message_id`. Así, aunque alguien manipulara n8n, no puede inyectar
  cuerpos de correo falsos — HELIOS lee el original de Gmail (read-only).
- El endpoint está protegido con un token de servicio (máquina-a-máquina),
  distinto del login de la interfaz.
