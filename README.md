# CV-Api — Documentación Técnica

---

## 1. Descripción General

**CV-Api** es una REST API construida con FastAPI (Python) que evalúa currículums vitae utilizando el modelo de IA **Gemini 2.5 Flash** de Google, genera reportes PDF almacenados en **Cloudinary**, y produce **quizzes de perfil profesional** adaptados tanto al candidato como a los requerimientos de una empresa.

La API gestiona usuarios, autenticación mediante JWT, API Keys propias como credenciales de acceso, y registra cada operación en base de datos junto al número de tokens consumidos y el tiempo de respuesta.

---

## 2. Stack Tecnológico

| Tecnología | Versión | Rol en el proyecto |
|---|---|---|
| Python | 3.10+ | Lenguaje principal |
| FastAPI | 0.136.1 | Framework web / HTTP |
| PostgreSQL | Cualquier versión | Base de datos relacional |
| psycopg | 3.3.4 | Driver PostgreSQL (context manager) |
| Google GenAI (Gemini) | gemini-2.5-flash | Motor de IA para evaluación y quiz |
| PyJWT | 2.12.1 | Generación y validación de JWT |
| pwdlib[argon2] | 0.3.0 | Hashing seguro de contraseñas |
| python-dotenv | 1.2.2 | Variables de entorno |
| Cloudinary | 1.44.2 | CDN para almacenar PDFs generados |
| markdown-pdf | 1.13.1 | Conversión de Markdown a PDF |
| fastapi-limiter | 0.2.0 | Rate limiting por endpoint |
| pyrate-limiter | 4.1.0 | Motor de rate limiting |

---

## 3. Arquitectura del Proyecto

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Entrada (HTTP) | `src/routes/` | Endpoints FastAPI (auth, user, curriculum) |
| Lógica de negocio | `src/model/model.py` | Comunicación con Gemini, generación de PDF y quiz |
| Acceso a datos | `src/data/db.py` | CRUD contra PostgreSQL via context manager |
| DTOs / Schemas | `src/dto/` | Modelos Pydantic para validación |
| Servicios | `src/services/` | JWT (tokenizer) y Cloudinary (cdn) |
| Prompts del modelo | `role.md`, `quiz_role.md` | System prompts cargados en startup |
| Entry point | `src/app.py` | Instancia FastAPI, CORS, routers |

### 3.1 Estructura de directorios

```
CV-Api/
├── role.md                     # System prompt para evaluación de CV
├── quiz_role.md                # System prompt para generación de quiz (con soporte de requerimientos de empresa)
├── src/
│   ├── app.py                  # Entry point
│   ├── requirements.txt        # Dependencias (dentro de src/)
│   ├── data/
│   │   └── db.py               # Acceso a datos con context manager get_db()
│   ├── dto/
│   │   ├── cv.py               # DTO del currículum
│   │   ├── logs.py             # DTO de logs
│   │   └── user.py             # DTO de usuario y API Key
│   ├── model/
│   │   └── model.py            # Gemini AI + generación de PDF
│   ├── routes/
│   │   ├── auth.py             # Login y registro
│   │   ├── curriculum.py       # Evaluación CV, quiz y documentos
│   │   └── user.py             # API Keys y dashboard
│   └── services/
│       ├── cdn.py              # Subida de PDFs a Cloudinary
│       └── tokenizer.py        # JWT encode/decode
└── README.md
```

---

## 4. Endpoints de la API

### 4.1 Health Check

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/` |
| Autenticación | Ninguna |
| Respuesta | `{ "up": true, "datetime": "<timestamp>" }` |

---

### 4.2 Registro de usuario

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/register` |
| Autenticación | Ninguna |
| Body | `OAuth2PasswordRequestForm` (username, password) |
| Respuesta OK | `{ "created": true }` |
| Respuesta Error | `{ "error": "try again and check request" }` |

---

### 4.3 Login

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/login` |
| Autenticación | Ninguna |
| Body | `OAuth2PasswordRequestForm` (username, password) |
| Respuesta OK | `{ "access_token": "<JWT>" }` |
| Notas | El token expira según `EXPIRE_TIME` (default: 60 min) |

---

### 4.4 Obtener API Key

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/key` |
| Autenticación | `OAuth2PasswordRequestForm` (username, password) |
| Respuesta OK | `{ "api_key": "<hash>" }` |

---

### 4.5 Crear API Key

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/key` |
| Autenticación | `OAuth2PasswordRequestForm` (username, password) |
| Descripción | Genera una nueva API Key (una por usuario). Si ya existe, la retorna. |
| Respuesta OK | `{ "created": true, "api_key": "<hash>" }` |
| Respuesta Error | `{ "error": "Invalid data to create api key" }` |

---

### 4.6 Dashboard de uso

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/dashboard` |
| Autenticación | Bearer JWT (header `Authorization`) |
| Descripción | Retorna logs de uso del API Key del usuario |
| Respuesta OK | `{ "data": [[tokens_used, status, response_time], ...] }` |

---

### 4.7 Evaluar CV

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/curriculum` |
| Autenticación | Bearer Token (API Key en header `Authorization`) |
| Rate Limit | 20 solicitudes cada 15 minutos |
| Body JSON | `{ "content": "<texto del CV>" }` |
| Descripción | Evalúa el CV con Gemini, genera reporte PDF y lo sube a Cloudinary |
| Respuesta OK | `{ "result": { ...evaluación JSON..., "document": "<url_pdf>" } }` |
| Respuesta Error | HTTP 501 con `{ "error": "...", "raw": "..." }` |

---

### 4.8 Generar Quiz de perfil profesional ⭐

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/curriculum/quiz` |
| Autenticación | Bearer Token (API Key en header `Authorization`) |
| Rate Limit | 5 solicitudes cada 2 minutos |
| Body JSON | `{ "content": "<info del candidato>", "requirements": "<requerimientos de la empresa>" }` |
| Descripción | Genera formulario adaptativo de perfil profesional, con sección específica al puesto si se envían requerimientos |
| Respuesta OK | `{ "result": { ...quiz JSON... } }` |
| Notas | `requirements` es **obligatorio** en el body (puede enviarse vacío `""` para omitir sección 3) |

---

### 4.9 Obtener documentos generados

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/curriculum/documents` |
| Autenticación | Bearer Token (API Key en header `Authorization`) |
| Rate Limit | 5 solicitudes cada 5 minutos |
| Descripción | Retorna las URLs de todos los PDFs generados por esa API Key |
| Respuesta OK | `{ "result": { "documents": [["<url>"], ...] } }` |
| Respuesta Error | HTTP 400 si no hay documentos |

---

## 5. Estructura de las Respuestas de IA

### 5.1 Evaluación de CV (`/api/curriculum`)

El modelo recibe `role.md` como system prompt y retorna:

```json
{
  "global_score": 85,
  "evaluation": {
    "structure_and_quality":   { "score": 90, "comment": "..." },
    "relevant_experience":     { "score": 80, "comment": "..." },
    "formation_and_education": { "score": 85, "comment": "..." },
    "habilities":              { "score": 88, "comment": "..." },
    "goals_and_impact":        { "score": 75, "comment": "..." },
    "adaption_for_position":   { "score": 82, "comment": "..." }
  },
  "suggestions": ["...", "..."],
  "document": {
    "file_name": "reporte_cv.md",
    "content": "<markdown del reporte>"
  }
}
```

> El campo `document` es procesado internamente: se convierte a PDF con `markdown-pdf`, se sube a Cloudinary, y la URL se guarda en la tabla `documents`. La respuesta al cliente reemplaza el objeto `document` por la URL del PDF.

---

### 5.2 Quiz de perfil profesional (`/api/curriculum/quiz`)

El modelo recibe `quiz_role.md` y genera hasta **3 secciones**:

| Sección | Siempre presente | Descripción |
|---|---|---|
| 1 — Datos Personales | Solo si faltan campos | Completa datos personales faltantes del candidato |
| 2 — Perfil Profesional | Siempre | Situación laboral, fortalezas, preferencias, metas, salario |
| 3 — Evaluación del Puesto | Solo si se envía `requirements` | Preguntas específicas derivadas de los requerimientos de la empresa |

```json
{
  "form_title": "Perfil Profesional — Desarrollador Backend",
  "form_description": "Completa este formulario para que podamos conocerte mejor.",
  "total_questions": 25,
  "sections": [
    {
      "section_id": 1,
      "section_title": "Datos Personales",
      "section_description": "...",
      "questions": [...]
    },
    {
      "section_id": 2,
      "section_title": "Perfil Profesional",
      "section_description": "...",
      "questions": [...]
    },
    {
      "section_id": 3,
      "section_title": "Evaluación del Puesto",
      "section_description": "...",
      "questions": [...]
    }
  ]
}
```

**Tipos de pregunta disponibles:**

| Tipo | Descripción |
|---|---|
| `text` | Respuesta corta libre |
| `email` | Campo de email |
| `phone` | Teléfono con código de país |
| `date` | Fecha |
| `single_choice` | Selección única (3-5 opciones) |
| `multiple_choice` | Selección múltiple (3-6 opciones) |
| `open_text` | Respuesta larga / reflexiva |
| `scale` | Escala del 1 al 5 |
| `boolean` | Sí / No |

---

## 6. Modelos de Datos (DTOs)

### 6.1 UserDTO

```python
class UserDTO(BaseModel):
    id: int | None = None
    username: str | None = None
    email: str | None = None
    password: str | None = None
    role: str | None = None
    dateRegistered: str | None = None
```

### 6.2 APIKey

```python
class APIKey(BaseModel):
    id: int | None = None
    owner_id: int | None = None
    key_hash: str | None = None
    rate_limit: int | None = None
    usage_count: int | None = None
    created_at: datetime | None = None
```

### 6.3 Log

```python
class Log(BaseModel):
    id: int | None = None
    api_key_id: int | None = None
    request_timestamp: datetime | None = None
    tokens_used: int | None = None
    status: str | None = None
    response_time: int | None = None
```

### 6.4 CVDTO

```python
class CVDTO(BaseModel):
    id: int
    title: str | None = None
    content: str | None = None
    grade: float | None = None
    feedback: str | None = None
    state: str | None = None
    date: str | None = None
```

---

## 7. Esquema de Base de Datos

Inferido del código en `db.py`:

| Tabla | Columnas principales |
|---|---|
| `Users` | `user_id`, `username`, `password_hash`, `role` |
| `ApiKeys` | `key_id`, `owner_id`, `key_hash`, `usage_count`, `rate_limit` |
| `apilogusage` | `log_id`, `api_key_id`, `tokens_used`, `response_time`, `status` |
| `documents` | `api_key_id`, `file_url` |

---

## 8. Configuración y Variables de Entorno

El archivo `.env` debe estar en `src/`:

```env
POSTGRES_CONNECTION_STRING=postgresql://user:pass@localhost:5432/cvapi
API_KEY=AIza...                  # Google Generative AI API Key
SECRET_KEY=mi_clave_secreta      # Clave secreta para firmar JWT
ALGORITHIM=HS256                 # Algoritmo JWT (mantener typo)
EXPIRE_TIME=60                   # Expiración del JWT en minutos
MODEL=gemini-2.5-flash           # Modelo Gemini a usar

# Cloudinary
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

---

## 9. Flujo Interno: Evaluación de CV

```
POST /api/curriculum  (Bearer <API_KEY>)
  │
  ├─ Valida API Key en DB
  ├─ Aplica rate limit (20/15min)
  │
  ▼
evaluate_cv_document()
  ├─ count_tokens()
  ├─ register_log() en DB
  ├─ Llama Gemini con role.md + CV
  ├─ Parsea JSON de respuesta
  ├─ update_log() con tiempo de respuesta
  │
  ├─ create_and_save_document()
  │     ├─ Markdown → PDF (markdown-pdf)
  │     └─ Sube a Cloudinary
  │           └─ save_doc_url() en tabla documents
  │
  └─ Retorna evaluación JSON con URL del PDF
```

---

## 10. Flujo Interno: Quiz

```
POST /api/curriculum/quiz  (Bearer <API_KEY>)
  Body: { content, requirements }
  │
  ├─ Valida API Key en DB
  ├─ Aplica rate limit (5/2min)
  │
  ▼
generate_quiz()
  ├─ Construye prompt:
  │     CANDIDATE: {content}
  │     COMPANY REQUIREMENTS: {requirements}  ← omitido si vacío
  ├─ count_tokens()
  ├─ register_log() en DB
  ├─ Llama Gemini con quiz_role.md + prompt
  ├─ update_log() con tiempo de respuesta
  └─ Retorna quiz JSON (1, 2 o 3 secciones)
```

---

## 11. Seguridad

### Contraseñas
- Almacenadas con hashing **Argon2** via `pwdlib`.
- Verificación con `password_hash.verify()`.

### JWT
- Firmado con `SECRET_KEY` y algoritmo `ALGORITHIM` (configurable).
- Incluye `iat` y `exp` automáticamente.
- Decodificado por `get_token()` en cada endpoint protegido con Bearer JWT.

### API Keys
- Generadas como hash SHA-256 de `os.urandom(32)`.
- Se almacena el hash directamente en `ApiKeys.key_hash`.
- Validadas en cada request a `/api/curriculum*` via `get_api_key()`.

### Rate Limiting
| Endpoint | Límite |
|---|---|
| `POST /api/curriculum` | 20 req / 15 minutos |
| `POST /api/curriculum/quiz` | 5 req / 2 minutos |
| `GET /api/curriculum/documents` | 5 req / 5 minutos |

### CORS
- `allow_origins=["*"]` — **restringir en producción**.

---

## 12. Conexión a Base de Datos

La conexión usa un **context manager** `get_db()` que abre y cierra la conexión por cada operación, compatible con entornos serverless como Vercel:

```python
@contextmanager
def get_db():
    conn = psycopg.connect(getenv("POSTGRES_CONNECTION_STRING"))
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    finally:
        cursor.close()
        conn.close()
```

---

## 13. Observaciones y Bugs Identificados

| # | Archivo | Descripción |
|---|---|---|
| 1 | `db.py` | `remove_user` tiene typo `ownter_id` en lugar de `owner_id` en el DELETE de ApiKeys. |
| 2 | `db.py` | `remove_api_key` usa `hash_key` en la query pero la columna correcta es `key_hash`. |
| 3 | `db.py` | `update_user` usa la columna `password` en el UPDATE, pero el INSERT usa `password_hash`. |
| 4 | `db.py` | `get_api_information` tiene lógica invertida: retorna `None` cuando `api_key_data != None`, lo que impide que el dashboard funcione. La condición debería ser `if not api_key_data`. |
| 5 | `model/model.py` | `res_txt.replace("```", "")` no modifica la variable (strings son inmutables). Debe ser `res_txt = res_txt.replace(...)`. |
| 6 | `routes/curriculum.py` | `generate_quizziz` lanza HTTP 400 si `requirements` no está presente, pero debería ser opcional. |
| 7 | `services/tokenizer.py` | Typo `ALGORITHIM` en lugar de `ALGORITHM`. Mantener consistente con `.env`. |

---

## 14. Flujo de Uso Típico

| Paso | Acción | Endpoint |
|---|---|---|
| 1 | Registrar usuario | `POST /api/register` |
| 2 | Login y obtener JWT | `POST /api/login` |
| 3 | Crear API Key | `POST /api/key` |
| 4a | Evaluar CV | `POST /api/curriculum` |
| 4b | Generar quiz de perfil | `POST /api/curriculum/quiz` |
| 5 | Ver PDFs generados | `GET /api/curriculum/documents` |
| 6 | Ver estadísticas de uso | `GET /api/dashboard` |

---

*Documentación generada automáticamente por Claude · github.com/MyDiDev/CV-Api*
