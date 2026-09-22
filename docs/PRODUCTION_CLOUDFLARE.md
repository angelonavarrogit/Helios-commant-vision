# ☀️ HELIOS — Puesta en producción con Cloudflare Tunnel

Esta guía lleva HELIOS de "funciona en mi máquina (localhost)" a "funciona en
línea con HTTPS y dominio propio", usando **Cloudflare Tunnel**.

Cloudflare Tunnel expone tus servicios locales a internet **sin abrir puertos**
en tu router ni en tu firewall: un agente (`cloudflared`) crea una conexión
saliente hacia Cloudflare, y Cloudflare publica tus URLs con HTTPS gestionado.

> Convención: 🧑 **TÚ** = lo que solo tú puedes hacer (cuentas, secretos, DNS).
> 🤖 **YO (Kiro)** = lo que puedo preparar por ti en el repo.
>
> **Nunca me pegues secretos reales en el chat** (tokens, client secret,
> contraseñas). Ponlos tú en `.env`.

---

## 0. Qué vamos a publicar

HELIOS tiene dos superficies que van a internet:

| Servicio | Local | URL pública (ejemplo) |
|---|---|---|
| Frontend (HELIOS COMMAND) | `http://localhost:5173` | `https://helios.tudominio.com` |
| Backend (API) | `http://localhost:8000` | `https://api.helios.tudominio.com` |

Lo que **NO** se publica (queda solo en la red interna, como debe ser):
- **MySQL** (sin puerto al host, red `backnet` interna).
- **Ollama** (el "cerebro" local; nunca debe ser público).
- **n8n** (`http://localhost:5678`): úsalo solo en local. Si algún día lo
  publicas, ponle su propia protección; por ahora déjalo fuera del túnel.
- El **bot de Telegram** no necesita URL pública: usa long-polling saliente.

Necesitas un **dominio** gestionado en Cloudflare (puede ser uno que ya tengas;
si no, registra uno y muévele los DNS a Cloudflare — es gratis para este uso).

---

## 1. Requisitos (una vez) 🧑

1. Cuenta en **Cloudflare** (gratis): https://dash.cloudflare.com
2. Un **dominio** añadido a Cloudflare (Zona activa, nameservers apuntando a
   Cloudflare). Verás el dominio en el dashboard con estado "Active".
3. **Docker Desktop** corriendo (ya lo tienes).
4. HELIOS levantado en local y sano:
   ```powershell
   docker compose ps
   # backend, frontend, mysql, bot => healthy / up
   ```

---

## 2. Instalar `cloudflared` (el agente del túnel) 🧑

En Windows (PowerShell, con winget):
```powershell
winget install --id Cloudflare.cloudflared
```
Comprueba:
```powershell
cloudflared --version
```

> Alternativa: descarga el binario desde
> https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

---

## 3. Autenticar y crear el túnel 🧑

### 3.1 Iniciar sesión (abre el navegador y eliges tu dominio)
```powershell
cloudflared tunnel login
```
Esto guarda un certificado en `C:\Users\<tu-usuario>\.cloudflared\cert.pem`.

### 3.2 Crear el túnel (nómbralo "helios")
```powershell
cloudflared tunnel create helios
```
Te imprime un **Tunnel ID** (UUID) y crea un archivo de credenciales
`C:\Users\<tu-usuario>\.cloudflared\<TUNNEL_ID>.json`. Guárdalo; es sensible
(trátalo como un secreto, no lo subas a git).

### 3.3 Rutas DNS (crea los subdominios y apúntalos al túnel)
```powershell
cloudflared tunnel route dns helios helios.tudominio.com
cloudflared tunnel route dns helios api.helios.tudominio.com
```
Esto crea registros CNAME en Cloudflare que apuntan a tu túnel.

---

## 4. Configurar el túnel (qué URL va a qué servicio local) 🧑

Crea `C:\Users\<tu-usuario>\.cloudflared\config.yml` con este contenido
(cambia `TUNNEL_ID`, la ruta del `.json` y tu dominio):

```yaml
tunnel: TUNNEL_ID
credentials-file: C:\Users\<tu-usuario>\.cloudflared\TUNNEL_ID.json

ingress:
  # Frontend (HELIOS COMMAND) -> nginx del contenedor frontend (host:5173)
  - hostname: helios.tudominio.com
    service: http://localhost:5173
  # Backend (API) -> uvicorn del contenedor backend (host:8000)
  - hostname: api.helios.tudominio.com
    service: http://localhost:8000
  # Regla final obligatoria: todo lo demás se rechaza.
  - service: http_status:404
```

> Nota: `cloudflared` corre en tu host y habla con los puertos que Docker ya
> publica (`5173` y `8000`). No necesitas cambiar la topología de Docker.

---

## 5. Ajustar la configuración de HELIOS para producción 🧑

Edita tu `.env` (NO el `.env.example`). Cambia estos valores a tus URLs
públicas y activa el modo producción:

```dotenv
APP_ENV=prod

# API pública (usada para construir el redirect de OAuth)
PUBLIC_BASE_URL=https://api.helios.tudominio.com

# Origen del frontend permitido para CORS con cookies
CORS_ORIGINS=https://helios.tudominio.com

# URL del API que se hornea en el bundle del frontend (build time)
VITE_API_BASE_URL=https://api.helios.tudominio.com
```

Por qué cada uno importa:
- **`APP_ENV=prod`**: activa la cookie de sesión `Secure` (solo HTTPS) y oculta
  `/docs` y `/redoc`. Con Cloudflare sirviendo HTTPS, esto es correcto.
- **`PUBLIC_BASE_URL`**: el backend arma el `redirect_uri` de Google con esta
  base. Si no coincide con lo registrado en Google, el OAuth falla.
- **`CORS_ORIGINS`**: el navegador solo enviará la cookie de sesión al API si el
  origen del frontend está en esta lista.
- **`VITE_API_BASE_URL`**: el frontend es estático; la URL del API se **hornea
  al construir**. Cambiarla obliga a **reconstruir** el frontend (paso 7).

---

## 6. Registrar el nuevo redirect en Google Cloud (OAuth Gmail) 🧑

En https://console.cloud.google.com → tu proyecto → **APIs & Services →
Credentials → tu OAuth Client ID (Web application)**:

1. En **Authorized redirect URIs**, **añade** (no borres el de localhost si
   quieres seguir probando en local):
   ```
   https://api.helios.tudominio.com/api/v1/connections/gmail/callback
   ```
2. Guarda. Los cambios en Google pueden tardar unos minutos en propagarse.

> El **redirect debe coincidir exactamente** con `PUBLIC_BASE_URL` +
> `/api/v1/connections/gmail/callback`. Un solo carácter distinto = error
> `redirect_uri_mismatch`.

---

## 7. Reconstruir y relevantar HELIOS con la config de producción 🧑

El frontend hornea `VITE_API_BASE_URL` al construir, así que hay que
**reconstruirlo** (no basta reiniciar). Desde la raíz del proyecto:

```powershell
# Reconstruye frontend (con la URL del API pública) y backend, y relevanta todo
docker compose up -d --build

# Aplica migraciones (si es una base nueva)
docker compose run --rm backend alembic upgrade head
```

Verifica local:
```powershell
docker compose ps         # todo healthy / up
curl http://localhost:8000/health
```

---

## 8. Arrancar el túnel 🧑

Prueba en primer plano (para ver logs):
```powershell
cloudflared tunnel run helios
```
Deberías ver que conecta y registra las rutas. Déjalo corriendo y ve al paso 9.

Para dejarlo permanente como **servicio de Windows** (arranca solo con el PC):
```powershell
# Ejecuta PowerShell como Administrador
cloudflared service install
Start-Service cloudflared
```

---

## 9. Checklist de validación end-to-end (en línea) ✅

Hazla en orden. Si algo falla, mira la sección 10.

1. **API viva (público)**
   ```powershell
   curl https://api.helios.tudominio.com/health
   # {"status":"ok","app":"helios","env":"prod"}
   ```
   Debe decir `"env":"prod"`.

2. **Frontend carga (público)**
   Abre `https://helios.tudominio.com` en el navegador. Candado de HTTPS válido.

3. **Login**
   Entra con `owner` y tu contraseña. Si el login "no pega" (vuelve al login),
   casi siempre es CORS/cookie: revisa `CORS_ORIGINS` y que `APP_ENV=prod`
   (cookie `Secure` sobre HTTPS). Ver 10.1.

4. **Dashboard con datos reales**
   KPIs, actividad y estado del sistema deben cargar (no errores de red en la
   consola del navegador).

5. **Conectar Gmail (OAuth en línea)**
   Connections → Google Gmail → Conectar → autorizas en Google → vuelves con la
   cuenta **Conectada**. Si sale `redirect_uri_mismatch`, revisa el paso 6.

6. **Procesar un correo**
   ```powershell
   curl -X POST https://api.helios.tudominio.com/api/v1/emails/process `
     -H "X-Service-Token: <SERVICE_API_TOKEN>" `
     -H "Content-Type: application/json" `
     -d '{"account_id": <id>, "provider_message_id": "<id_de_un_correo>"}'
   ```
   Responde con categoría e importancia.

7. **Telegram**
   Escríbele a tu bot: `/estado`, `/help`, `/resumen`. Responde y `/estado`
   muestra la base de datos y la cuenta conectada. (El bot no depende del túnel.)

Si los 7 pasan: **HELIOS está en producción y validado.** 🎉

---

## 10. Problemas comunes

### 10.1 El login no persiste / 401 tras iniciar sesión
- La cookie es `HttpOnly`, `SameSite=Lax`, `Secure` (en prod). Requiere **HTTPS**
  en ambos lados — Cloudflare ya lo da.
- `CORS_ORIGINS` debe ser **exactamente** el origen del frontend
  (`https://helios.tudominio.com`, sin barra final, sin `www` si no lo usas).
- Frontend y API deben compartir dominio raíz (`*.tudominio.com`) para que la
  cookie viaje. Esta guía ya lo hace así.
- Tras cambiar `.env`, reinicia backend: `docker compose up -d backend`.

### 10.2 `redirect_uri_mismatch` al conectar Gmail
- El URI en Google debe ser idéntico a
  `https://api.helios.tudominio.com/api/v1/connections/gmail/callback`.
- Confirma que `PUBLIC_BASE_URL` en `.env` usa `https://` y tu dominio real.

### 10.3 El frontend llama a `localhost:8000` en producción
- Se te olvidó reconstruir el frontend con `VITE_API_BASE_URL`. Corre de nuevo
  `docker compose up -d --build frontend` con la variable puesta en `.env`.
  (Compruébalo en la consola del navegador → pestaña Network.)

### 10.4 502 / "no puedo alcanzar el servicio" en Cloudflare
- ¿Está HELIOS levantado? `docker compose ps`.
- ¿Los puertos `5173` y `8000` responden en local? (pasos 7).
- Revisa los logs del túnel: `cloudflared tunnel run helios` en primer plano.

### 10.5 Logs
```powershell
docker compose logs -f backend
docker compose logs -f bot
cloudflared tunnel info helios
```

---

## 11. Seguridad — antes de considerarlo "producción de verdad" 🧑

- [ ] Cambia la contraseña temporal del propietario (`helios-admin`) desde
      Settings → cambiar contraseña.
- [ ] **Rota** cualquier secreto que se haya expuesto alguna vez (token del bot
      de Telegram, Google Client Secret, refresh token de Gmail).
- [ ] Confirma que MySQL, Ollama y n8n **no** están en el `ingress` del túnel
      (esta guía deja fuera esos tres a propósito).
- [ ] Opcional pero recomendado: protege el frontend con **Cloudflare Access**
      (una capa de login de Cloudflare delante de HELIOS), así solo tu correo
      puede siquiera llegar a la pantalla de login.
- [ ] `APP_ENV=prod` (cookie `Secure`, sin `/docs` público).
- [ ] Haz respaldos del volumen `mysql-data` si vas a depender de los datos.

---

## Resumen de un vistazo

1. Instala `cloudflared` → login → `tunnel create helios`.
2. Rutas DNS: `helios.` y `api.helios.` → el túnel.
3. `config.yml` con los dos `hostname` → `localhost:5173` y `localhost:8000`.
4. `.env`: `APP_ENV=prod`, `PUBLIC_BASE_URL`, `CORS_ORIGINS`, `VITE_API_BASE_URL`.
5. Google Cloud: añade el redirect `https://api.helios..../gmail/callback`.
6. `docker compose up -d --build` + migraciones.
7. `cloudflared tunnel run helios` (o instálalo como servicio).
8. Corre la checklist §9.
```
