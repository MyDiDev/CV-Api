# CV-Api

## Descripción General

**CV-Api** es una REST API construida con FastAPI (Python) que evalúa currículums vitae utilizando el modelo de IA **Gemini 2.5 Flash** de Google, genera reportes PDF almacenados en **Cloudinary**, y produce **quizzes de perfil profesional** adaptados tanto al candidato como a los requerimientos de una empresa.

La API gestiona usuarios, autenticación mediante JWT, API Keys propias como credenciales de acceso, y registra cada operación en base de datos junto al número de tokens consumidos y el tiempo de respuesta.


## Stack Tecnológico

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


## Arquitectura del Proyecto

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Entrada (HTTP) | `src/routes/` | Endpoints FastAPI (auth, user, curriculum) |
| Lógica de negocio | `src/model/model.py` | Comunicación con Gemini, generación de PDF y quiz |
| Acceso a datos | `src/data/db.py` | CRUD contra PostgreSQL via context manager |
| DTOs / Schemas | `src/dto/` | Modelos Pydantic para validación |
| Servicios | `src/services/` | JWT (tokenizer) y Cloudinary (cdn) |
| Prompts del modelo | `role.md`, `quiz_role.md` | System prompts cargados en startup |
| Entry point | `src/app.py` | Instancia FastAPI, CORS, routers |

### Estructura de directorios

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

## Endpoints de la API

### Health Check

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/` |
| Autenticación | Ninguna |
| Respuesta | `{ "up": true, "datetime": "<timestamp>" }` |


### Registro de usuario

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/register` |
| Autenticación | Ninguna |
| Body | `OAuth2PasswordRequestForm` (username, password) |
| Respuesta OK | `{ "created": true }` |
| Respuesta Error | `{ "error": "try again and check request" }` |

### Login

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/login` |
| Autenticación | Ninguna |
| Body | `OAuth2PasswordRequestForm` (username, password) |
| Respuesta OK | `{ "access_token": "<JWT>" }` |
| Notas | El token expira según `EXPIRE_TIME` (default: 60 min) |

### Obtener API Key

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/key` |
| Autenticación | `OAuth2PasswordRequestForm` (username, password) |
| Respuesta OK | `{ "api_key": "<hash>" }` |

### Crear API Key

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/key` |
| Autenticación | `OAuth2PasswordRequestForm` (username, password) |
| Descripción | Genera una nueva API Key (una por usuario). Si ya existe, la retorna. |
| Respuesta OK | `{ "created": true, "api_key": "<hash>" }` |
| Respuesta Error | `{ "error": "Invalid data to create api key" }` |

### Dashboard de uso

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/dashboard` |
| Autenticación | Bearer JWT (header `Authorization`) |
| Descripción | Retorna logs de uso del API Key del usuario |
| Respuesta OK | `{ "data": [[tokens_used, status, response_time], ...] }` |

### Evaluar CV

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

### Generar Quiz de perfil profesional 

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

### Obtener documentos generados

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/curriculum/documents` |
| Autenticación | Bearer Token (API Key en header `Authorization`) |
| Rate Limit | 5 solicitudes cada 5 minutos |
| Descripción | Retorna las URLs de todos los PDFs generados por esa API Key |
| Respuesta OK | `{ "result": { "documents": [["<url>"], ...] } }` |
| Respuesta Error | HTTP 400 si no hay documentos |

## Estructura de las Respuestas de IA

### Evaluación de CV (`/api/curriculum`)

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

### Quiz de perfil profesional (`/api/curriculum/quiz`)

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

## Esquema de Base de Datos

Inferido del código en `db.py`:

| Tabla | Columnas principales |
|---|---|
| `Users` | `user_id`, `username`, `password_hash`, `role` |
| `ApiKeys` | `key_id`, `owner_id`, `key_hash`, `usage_count`, `rate_limit` |
| `apilogusage` | `log_id`, `api_key_id`, `tokens_used`, `response_time`, `status` |
| `documents` | `api_key_id`, `file_url` |


## Configuración y Variables de Entorno

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

## Evaluación de CV

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

## Flujo Interno: Quiz

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

### Rate Limiting
| Endpoint | Límite |
|---|---|
| `POST /api/curriculum` | 20 req / 15 minutos |
| `POST /api/curriculum/quiz` | 5 req / 2 minutos |
| `GET /api/curriculum/documents` | 5 req / 5 minutos |

### CORS
- `allow_origins=["*"]` — **restringir en producción**.

## Flujo de Uso Típico

| Paso | Acción | Endpoint |
|---|---|---|
| 1 | Registrar usuario | `POST /api/register` |
| 2 | Login y obtener JWT | `POST /api/login` |
| 3 | Crear API Key | `POST /api/key` |
| 4a | Evaluar CV | `POST /api/curriculum` |
| 4b | Generar quiz de perfil | `POST /api/curriculum/quiz` |
| 5 | Ver PDFs generados | `GET /api/curriculum/documents` |
| 6 | Ver estadísticas de uso | `GET /api/dashboard` |
