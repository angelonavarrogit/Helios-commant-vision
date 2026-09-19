# ☀️ HELIOS — Puesta en marcha (paso a paso)

Esta guía te lleva desde "el código está listo" hasta "HELIOS está leyendo mi
Gmail y avisándome por Telegram". Está ordenada; sigue los pasos en orden.

Al final de cada sección marco quién hace qué:
- 🧑 **TÚ**: algo que solo tú puedes hacer (crear cuentas, generar secretos).
- 🤖 **YO (Kiro)**: algo que puedo hacer por ti si me pasas lo indicado.

> Recordatorio de seguridad: **nunca me pegues secretos reales en el chat**
> (contraseñas, tokens, client secret). Ponlos tú en `.env` o en `secrets/`.
> A mí pásame solo lo que aquí se marca como "seguro de compartir".

---

## 0. Requisitos previos (una vez)

🧑 **TÚ** necesitas instalado:
- **Docker Desktop** (ya lo tienes; el proyecto se probó con él).
- **Python 3.12+** solo si vas a correr scripts fuera de Docker (opcional).

Comprueba que Docker responde:
```powershell
docker --version
docker compose version
```

---

## 1. Crear tu archivo `.env` (secretos locales)

El repo trae `.env.example` (plantilla, sin secretos). Tú creas el `.env` real,
que **nunca** se sube a git.

🧑 **TÚ**:
```powershell
Copy-Item .env.example .env
```

Luego vas rellenando `.env` con los valores de los pasos siguientes. Los que ya
puedes dejar como están para desarrollo local: `APP_ENV=local`, las credenciales
de MySQL (`changeme`), `LLM_PROVIDER=ollama`.

---

## 2. Generar los secretos internos de HELIOS

Estos NO vienen de terceros; los generas tú. Son 4 valores.

### 2.1 Clave de cifrado (para los tokens OAuth en reposo)
🧑 **TÚ**, en PowerShell (con el backend ya construido, ver paso 4) o con Python:
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copia el resultado a `ENCRYPTION_KEY=` en `.env`.

### 2.2 Secreto de sesión (firma de cookies de login)
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copia a `SESSION_SECRET=`.

### 2.3 Token de servicio (para que N8N llame al backend)
```powershell
python -c "import secrets; print(secrets.token_urlsafe(24))"
```
Copia a `SERVICE_API_TOKEN=`.

### 2.4 Contraseña del propietario (login de HELIOS COMMAND)
Genera el **hash** de la contraseña que usarás para entrar a la interfaz:
```powershell
docker compose run --rm backend python scripts/hash_password.py
```
Te pedirá una contraseña y te imprimirá algo como
`OWNER_PASSWORD_HASH=scrypt$...`. Copia esa línea completa a `.env`.
(La contraseña en claro no se guarda en ningún sitio; solo el hash.)

> 🤖 **YO** no puedo hacer este paso: implican secretos que deben quedarse en tu
> máquina. Pero puedo guiarte si algún comando falla.

---

## 3. Configurar Telegram (para recibir alertas y usar comandos)

🧑 **TÚ**:
1. En Telegram, habla con **@BotFather** → `/newbot` → sigue los pasos.
   Te dará un **token de bot** (ej. `8123456:AAG...`).
2. Averigua **tu user id**: habla con **@userinfobot**, te devuelve un número
   (ej. `12345678`).
3. En `.env`:
   ```
   TELEGRAM_BOT_TOKEN=<el token de BotFather>
   TELEGRAM_ALLOWED_USER_IDS=<tu user id>   # puedes poner varios: 111,222
   ```

Qué es seguro pasarme: **tu user id** (no es secreto). **El token del bot NO**
me lo pases; ponlo tú en `.env`.

---

## 4. Levantar el stack

🧑 **TÚ**, desde la raíz del proyecto:
```powershell
docker compose up -d --build
```
Esto arranca: `backend` (API), `frontend` (HELIOS COMMAND), `mysql`, `ollama`, `n8n`.

Aplica las migraciones de base de datos (crea las tablas):
```powershell
docker compose run --rm backend alembic upgrade head
```

Comprueba que el backend responde:
```powershell
curl http://localhost:8000/health
# {"status":"ok","app":"helios","env":"local"}
```

---

## 5. Descargar un modelo para Ollama (el "cerebro" local)

HELIOS usa Ollama en local (privado, sin enviar tus correos fuera).

🧑 **TÚ**:
```powershell
docker compose exec ollama ollama pull llama3.1
```
(En el último intento esto quedó al 96% por velocidad de red; si va lento puedes
usar un modelo más pequeño y cambiarlo en `.env` con `OLLAMA_MODEL=llama3.2:1b`.)

> Alternativa: si prefieres OpenAI, pon `LLM_PROVIDER=openai` y tu
> `OPENAI_API_KEY=` en `.env`. El contenido minimizado saldría a OpenAI en ese
> caso; con Ollama todo queda local.

---

## 6. Crear las credenciales OAuth de Google (para leer Gmail)

Esto autoriza a HELIOS a **leer** tu Gmail (scope de solo lectura; no puede
enviar ni borrar).

🧑 **TÚ**, en Google Cloud Console (https://console.cloud.google.com):
1. Crea un proyecto (o usa uno).
2. **APIs & Services → Enable APIs** → habilita **Gmail API**.
3. **OAuth consent screen** → tipo "External" → añade tu correo como
   **usuario de prueba**.
4. **Credentials → Create credentials → OAuth client ID** → tipo
   **Web application**.
5. En **Authorized redirect URIs** añade exactamente:
   ```
   http://localhost:8000/api/v1/connections/gmail/callback
   ```
6. Descarga el JSON del client (o copia el Client ID y Client Secret).

En `.env`:
```
GOOGLE_CLIENT_ID=<client id>
GOOGLE_CLIENT_SECRET=<client secret>
```
(Ya me pasaste antes un `client_secret_...json`; lo dejé en `secrets/` ignorado
por git. Puedes sacar de ahí el Client ID/Secret, o regenerarlos si prefieres.)

Reinicia el backend para tomar los nuevos valores:
```powershell
docker compose up -d backend
```

Qué es seguro pasarme: el **Client ID** (semi-público). El **Client Secret NO**.

---

## 7. Conectar tu Gmail desde HELIOS COMMAND (la interfaz)

🧑 **TÚ**:
1. Abre **http://localhost:5173**.
2. Inicia sesión con `OWNER_USERNAME` (por defecto `owner`) y la contraseña que
   pusiste en el paso 2.4.
3. Ve a **Connections** → tarjeta **Google Gmail** → **Conectar**.
4. Te redirige a Google, autorizas el permiso de **solo lectura**, y vuelves a
   HELIOS con la cuenta **Conectada**.

Con esto HELIOS ya tiene un *refresh token* cifrado en su base de datos y puede
leer tu correo cuando se lo pidan.

---

## 8. Procesar correos (disparar el pipeline)

HELIOS procesa un correo cuando alguien llama al endpoint de ingesta. Hay dos
formas:

### 8.1 Prueba manual (rápida, para verificar)
Necesitas el `account_id` (id de la cuenta que conectaste) y un
`provider_message_id` (id de un correo en tu buzón). El endpoint pide el
**token de servicio** del paso 2.3:
```powershell
curl -X POST http://localhost:8000/api/v1/emails/process `
  -H "X-Service-Token: <SERVICE_API_TOKEN>" `
  -H "Content-Type: application/json" `
  -d '{"account_id": 1, "provider_message_id": "<id_de_un_correo>"}'
```
Responde con la categoría e importancia detectadas.

### 8.2 Automático con N8N (lo normal)
🧑 **TÚ** (o 🤖 **YO** puedo prepararte el workflow de ejemplo):
- Abre N8N en **http://localhost:5678**.
- Crea un flujo: **Gmail Trigger (nuevo correo)** → **HTTP Request** a
  `POST http://backend:8000/api/v1/emails/process` con la cabecera
  `X-Service-Token` y el cuerpo `{account_id, provider_message_id}`.
- Actívalo. A partir de ahí, cada correo nuevo se procesa solo.

---

## 9. Usar HELIOS por Telegram

Con el bot configurado (paso 3), escríbele a tu bot:
- `/start`, `/help`
- `/resumen`, `/urgentes`, `/pendientes`
- `/finanzas`, `/seguros`, `/trabajo`, `/seguridad`
- `/hoy`, `/semana`
- `/buscar banco` (búsqueda por palabra)

Y recibirás **alertas automáticas** cuando llegue algo importante
(critical/high), sin spam (se agrupan los eventos repetidos).

---

## 10. Informes automáticos (opcional)

Para recibir el informe diario/semanal sin pedirlo:
- N8N con un **Schedule** que llame a
  `GET http://backend:8000/api/v1/emails/reports/daily`
  (cabecera `X-Service-Token`) y reenvíe el texto por Telegram.
- 🤖 **YO** puedo prepararte ese workflow si me lo pides.

---

## Resumen: qué me puedes pasar a mí (seguro) y qué NO

| Seguro de pasarme 🤖 | NO me lo pases (ponlo tú en `.env`) 🧑 |
|---|---|
| Tu Telegram user id | Token del bot de Telegram |
| Google Client ID | Google Client Secret |
| Mensajes de error / logs (sin secretos) | `ENCRYPTION_KEY`, `SESSION_SECRET` |
| Qué modelo de Ollama quieres | `SERVICE_API_TOKEN`, contraseñas |
| Preferencias (categorías, umbrales) | Cualquier token/refresh token |

## Si algo falla
- `docker compose logs backend` / `logs mysql` / `logs ollama`.
- Revisa `docs/hardening.md` (controles) y `docs/operations.md` (runbook).
- Pásame el **mensaje de error** (sin secretos) y te ayudo a diagnosticar.

## Qué queda como mejora futura (no bloquea el uso)
- OCR de imágenes adjuntas (hoy: PDF/Excel/Word por texto).
- Búsqueda semántica / memoria vectorial (hoy: búsqueda por palabra).
- Dashboard web ampliado (hoy: Dashboard mínimo + Connections).
