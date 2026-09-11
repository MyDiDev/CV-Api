# CV-Api

## Descripción General

**CV-Api** es una REST API de alto rendimiento construida con FastAPI (Python) que evalúa currículums vitae utilizando el modelo de IA **Gemini 2.5 Flash** de Google, genera reportes PDF almacenados en **Cloudinary**, y produce **quizzes de perfil profesional** adaptados tanto al candidato como a los requerimientos de una empresa.

La API cuenta con una arquitectura optimizada para alta concurrencia y resiliencia:
- **Caché en memoria con Redis** para evaluaciones de CV, quizzes y validación de API Keys.
- **Balanceador de carga multi-key** para la API de Gemini con rotación Round-Robin y reintentos automáticos.
- **Control de concurrencia** mediante semáforos asíncronos para limitar llamadas simultáneas a Gemini.
- **Rate limiting distribuido** basado en Redis por IP y por API Key.
- **Autenticación y registro de métricas** (tokens consumidos, tiempo de respuesta) en PostgreSQL.


## Stack Tecnológico

| Tecnología | Versión | Rol en el proyecto |
|---|---|---|
| Python | 3.10+ | Lenguaje principal |
| FastAPI | 0.136.1 | Framework web / HTTP asíncrono |
| Redis | >=5.0.0 (`redis.asyncio`) | Caché en memoria y backend de rate limiting distribuido |
| PostgreSQL | Cualquier versión | Base de datos relacional para usuarios, llaves y logs |
| psycopg | 3.3.4 | Driver PostgreSQL con context manager asíncrono |
| Google GenAI (Gemini) | gemini-2.5-flash | Motor de IA para evaluación y quizzes |
| PyJWT | 2.12.1 | Generación y validación de JWT |
| pwdlib[argon2] | 0.3.0 | Hashing seguro de contraseñas |
| python-dotenv | 1.2.2 | Gestión de variables de entorno |
| Cloudinary | 1.44.2 | CDN para almacenar reportes PDF generados |
| markdown-pdf | 1.13.1 | Conversión de Markdown a PDF |
| fastapi-limiter | 0.2.0 | Rate limiting distribuido por endpoint |
| pyrate-limiter | 4.1.0 | Motor de control de tasa de peticiones |
| pytest / pytest-asyncio | >=8.0.0 / >=0.23.0 | Suite de pruebas unitarias e integración |


## Arquitectura del Proyecto

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Entrada (HTTP) | `src/routes/` | Endpoints FastAPI (auth, user, curriculum) y rate limits |
| Lógica de negocio | `src/model/model.py` | Lógica de evaluación de CV, quizzes, interacción con IA y PDF |
| Balanceador de IA | `src/services/gemini_balancer.py` | Rotación multi-key Round-Robin, reintentos y límite de concurrencia |
| Capa de Caché | `src/services/redis_service.py` | Operaciones asíncronas con Redis (get/set JSON, TTL, borrado) |
| Acceso a datos | `src/data/db.py` & `src/repository/` | CRUD contra PostgreSQL via context manager y repositorios |
| DTOs / Schemas | `src/dto/` | Modelos Pydantic para validación estricta de entrada/salida |
| Servicios auxiliares | `src/services/cdn.py`, `src/services/tokenizer.py` | Cloudinary CDN y generación/validación de JWT |
| Prompts del modelo | `role.md`, `quiz_role.md` | System prompts estructurados cargados en startup |
| Entry point | `src/app.py` | Instancia FastAPI, middleware CORS, lifespan y rate limiting |

### Estructura de directorios

```
CV-Api/
├── role.md                     # System prompt para evaluación de CV
├── quiz_role.md                # System prompt para generación de quiz
├── requirements.txt            # Dependencias del proyecto
├── .env.example                # Plantilla de variables de entorno
├── tests/                      # Suite de pruebas automatizadas
│   ├── test_caching.py
│   ├── test_gemini_balancer.py
│   ├── test_rate_limiter.py
│   └── test_redis_service.py
├── src/
│   ├── app.py                  # Entry point y lifespan
│   ├── data/
│   │   └── db.py               # Conexión a PostgreSQL (context manager get_db())
│   ├── dto/
│   │   ├── cv.py               # DTOs del currículum
│   │   ├── logs.py             # DTOs de logs y dashboard
│   │   └── user.py             # DTOs de usuario y API Key
│   ├── model/
│   │   └── model.py            # Orquestación de IA, caché y PDF
│   ├── repository/
│   │   ├── api_key_repository.py # Acceso a datos de API Keys y caché
│   │   ├── document_repository.py# Almacenamiento de URLs de documentos
│   │   ├── log_repository.py     # Registro de consumo y métricas
│   │   └── user_repository.py    # Gestión de usuarios
│   ├── routes/
│   │   ├── auth.py             # Login y registro
│   │   ├── curriculum.py       # Evaluación CV, quiz y documentos
│   │   ├── user.py             # API Keys y dashboard
│   │   └── v1.py               # Agregador de rutas v1 y legacy
│   └── services/
│       ├── cdn.py              # Subida de PDFs a Cloudinary
│       ├── gemini_balancer.py  # Balanceador multi-key y limitador de concurrencia
│       ├── redis_service.py    # Cliente y utilidades de Redis
│       └── tokenizer.py        # Hashing de contraseñas y JWT
└── README.md
```

## Sistema de Caché con Redis

Para maximizar el rendimiento y reducir el consumo de cuotas de tokens con la API de Google Gemini, el sistema implementa una capa de caché con Redis en `src/services/redis_service.py`:

| Tipo de Caché | Clave Redis | TTL por Defecto | Comportamiento |
|---|---|---|---|
| **Evaluación de CV** | `cv_eval:{sha256(content)}` | 24 horas (`AI_CACHE_TTL=86400`) | Si el contenido del CV es idéntico, retorna la evaluación almacenada sin invocar a Gemini. |
| **Quiz de Perfil** | `quiz:{sha256(content:requirements)}` | 24 horas (`AI_CACHE_TTL=86400`) | Retorna el formulario de preguntas generado previamente para el mismo candidato y requerimientos. |
| **Validación de API Key** | `api_key:{key_hash}` | 5 minutos (`API_KEY_CACHE_TTL=300`) | Evita consultas repetitivas a PostgreSQL en cada petición autorizada. Se invalida al revocar la llave. |

> **Resiliencia:** Si Redis se encuentra apagado o no responde, el sistema degrada elegantemente realizando la consulta directa a la base de datos o al modelo Gemini sin interrumpir el servicio.


## Balanceador de Carga y Concurrencia de Gemini

El módulo `src/services/gemini_balancer.py` gestiona las llamadas al modelo de IA:
1. **Multi-Key Round-Robin:** Permite configurar múltiples API Keys (`GEMINI_API_KEYS=key1,key2,key3`) rotando entre ellas en cada solicitud para distribuir el consumo. Si no se especifican, utiliza `API_KEY`.
2. **Reintentos automáticos (Failover):** Si un cliente falla (por ejemplo por cuota agotada o error transitorio), reintenta inmediatamente con la siguiente llave disponible.
3. **Limitador de Concurrencia:** Emplea un `asyncio.Semaphore` configurable con `MAX_CONCURRENT_GEMINI_REQUESTS` (default: 5) para prevenir saturación de hilos y sobrepasar límites de tasa concurrentes de Google GenAI.


## Rate Limiting Distribuido

Protección implementada en `src/app.py` y las rutas mediante `fastapi-limiter` conectado a Redis. Identifica al cliente por Bearer Token (API Key / JWT), cabecera `X-Forwarded-For` o IP del host:

| Endpoint | Método | Límite Estricto | Identificador |
|---|---|---|---|
| `/api/curriculum` | `POST` | **10 req / 10 min** | API Key |
| `/api/curriculum/quiz` | `POST` | **5 req / 5 min** | API Key |
| `/api/curriculum/documents` | `GET` | **10 req / 5 min** | API Key |
| `/api/login` | `POST` | **10 req / 1 min** | IP / Formulario |
| `/api/register` | `POST` | **5 req / 1 min** | IP / Formulario |
| `/api/key` | `POST` | **5 req / 1 min** | IP / Formulario |
| `/api/create/key` | `POST` | **5 req / 1 min** | IP / Formulario |
| `/api/dashboard` | `GET` | **20 req / 1 min** | JWT Bearer |


## Endpoints de la API

### Health Check

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/` |
| Autenticación | Ninguna |
| Respuesta | `{ "up": true, "datetime": "<timestamp_iso>" }` |

### Registro de usuario

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/register` |
| Autenticación | Ninguna |
| Rate Limit | 5 req / 1 min |
| Body | `OAuth2PasswordRequestForm` (`username`, `password`) |
| Respuesta OK | `{ "created": true }` |
| Respuesta Error | `{ "detail": "User creation failed" }` |

### Login

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/login` |
| Autenticación | Ninguna |
| Rate Limit | 10 req / 1 min |
| Body | `OAuth2PasswordRequestForm` (`username`, `password`) |
| Respuesta OK | `{ "access_token": "<JWT>" }` |

### Obtener API Key

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/key` |
| Autenticación | `OAuth2PasswordRequestForm` (`username`, `password`) |
| Rate Limit | 5 req / 1 min |
| Respuesta OK | `{ "api_key": "<hash>" }` |

### Crear API Key

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/create/key` |
| Autenticación | `OAuth2PasswordRequestForm` (`username`, `password`) |
| Rate Limit | 5 req / 1 min |
| Descripción | Genera una nueva API Key para el usuario. |
| Respuesta OK | `{ "created": true, "api_key": "<hash>" }` |

### Dashboard de uso

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/dashboard` |
| Autenticación | Bearer JWT (header `Authorization: Bearer <token>`) |
| Rate Limit | 20 req / 1 min |
| Descripción | Retorna métricas de uso acumuladas asociadas a la API Key del usuario. |
| Respuesta OK | `{ "data": [[tokens_used, status, response_time], ...] }` |

### Evaluar CV

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/curriculum` |
| Autenticación | Bearer Token (API Key en header `Authorization: Bearer <API_KEY>`) |
| Rate Limit | 10 req / 10 min |
| Caché | 24 horas por hash de contenido |
| Body JSON | `{ "content": "<texto_del_cv>" }` |
| Descripción | Evalúa el CV con Gemini, genera reporte PDF y lo sube a Cloudinary |
| Respuesta OK | `{ "result": { ...evaluación JSON..., "document": "<url_pdf>" } }` |

### Generar Quiz de perfil profesional

| Campo | Detalle |
|---|---|
| Método | `POST` |
| Ruta | `/api/curriculum/quiz` |
| Autenticación | Bearer Token (API Key en header `Authorization: Bearer <API_KEY>`) |
| Rate Limit | 5 req / 5 min |
| Caché | 24 horas por hash de contenido + requerimientos |
| Body JSON | `{ "content": "<info_candidato>", "requirements": "<requerimientos_puesto>" }` |
| Descripción | Genera formulario adaptativo de perfil profesional y preguntas técnicas del puesto. |
| Respuesta OK | `{ "result": { ...quiz JSON... } }` |

### Obtener documentos generados

| Campo | Detalle |
|---|---|
| Método | `GET` |
| Ruta | `/api/curriculum/documents` |
| Autenticación | Bearer Token (API Key en header `Authorization: Bearer <API_KEY>`) |
| Rate Limit | 10 req / 5 min |
| Descripción | Retorna las URLs de todos los PDFs generados con la API Key autenticada. |
| Respuesta OK | `{ "result": [["<url>"], ...] }` |


## Configuración y Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto o dentro de `src/`:

```env
# JWT & Seguridad
SECRET_KEY=mi_clave_secreta_para_firmar_jwt
ALGORITHIM=HS256
EXPIRE_TIME=60

# Google Gemini AI & Balanceador
API_KEY=AIzaSy...                        # Llave primaria Gemini (fallback)
GEMINI_API_KEYS=AIzaSyA...,AIzaSyB...    # Múltiples llaves para rotación round-robin
MODEL=gemini-2.5-flash
MAX_CONCURRENT_GEMINI_REQUESTS=5         # Límite de semáforo de llamadas simultáneas

# Redis Caching y Rate Limiting
REDIS_URL=redis://localhost:6379/0
AI_CACHE_TTL=86400                       # TTL para respuestas de CV y Quiz (segundos)
API_KEY_CACHE_TTL=300                    # TTL para validación de API Keys (segundos)

# Cloudinary CDN
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# PostgreSQL
POSTGRES_CONNECTION_STRING=postgresql://usuario:password@localhost:5432/cvapi
```


## Flujo Interno de Ejecución

```
POST /api/curriculum (Bearer <API_KEY>)
  │
  ├─ 1. Valida API Key en Redis (si falla el hit, consulta PostgreSQL y guarda en caché)
  ├─ 2. Aplica Rate Limit con FastAPILimiter (Redis)
  │
  ▼
evaluate_cv_document()
  ├─ 3. Verifica Caché Redis: 'cv_eval:{sha256(content)}'
  │     └─ Hit: Retorna directamente evaluación JSON cacheada.
  │
  ├─ 4. Miss: Pasa por GeminiBalancer (concurrencia controlada + rotación de llaves)
  │     ├─ count_tokens()
  │     ├─ register_log()
  │     ├─ generate_content() con role.md + CV
  │     └─ update_log()
  │
  ├─ 5. Convierte Markdown a PDF (markdown-pdf) y sube a Cloudinary (CDN)
  ├─ 6. Guarda URL del documento en PostgreSQL
  ├─ 7. Almacena resultado en Redis (TTL 24h)
  └─ 8. Retorna respuesta JSON con URL del PDF
```


## Ejecución de Pruebas

Para ejecutar la suite completa de pruebas unitarias y de integración:

```bash
PYTHONPATH=src pytest tests/ -v
```
