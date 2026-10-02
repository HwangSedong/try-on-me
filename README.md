# Try-On-Me

> AI-powered multi-garment virtual styling pipeline

Try-On-Me began as a university virtual try-on project based on VITON-HD. v2 is a clean rebuild for current multimodal generation workflows: it accepts a full-body photograph plus one or more fashion references, produces a styled image, and validates it before showing it to the user.

## v1 → v2

The previous Angular app, VITON-HD integration, authentication, community, closet, product management, shopping search, polling, and external localhost API dependencies have been removed. v2 has no database or account system; its focus is the AI workflow.

## Workflow

```mermaid
flowchart LR
    A[Full-body photo + garment images] --> B[Optional background removal]
    B --> C[Multimodal outfit generation]
    C --> D[Safety validation]
    D -->|Pass| E[Vision quality validation]
    D -->|Fail: retry context| C
    E -->|Pass| F[Result]
    E -->|Fail: missing garment / anatomy issue| C
```

The pipeline is deliberately split into preprocessing, generation, safety, quality, and orchestration responsibilities. Quality validation checks person preservation, anatomy, full clothing, and every requested garment category. Validation failures become retry context for the next generation. `MAX_GENERATION_RETRIES` defaults to `3` (three retries after the initial attempt).

## Input and output

Required: one full-body person image. Optional but at least one required: `top`, `bottom`, `outer`, `shoes`, `hat`, and `accessory`. The client and API both enforce these rules. `POST /api/generate` accepts multipart form data and returns a JSON response such as:

```json
{ "status": "completed", "result_url": "/api/results/<id>", "retry_count": 0 }
```

The MVP holds returned image bytes in process memory only; restarting the backend clears results.

## Architecture

```text
frontend/                         React + Vite + TypeScript studio
backend/app/api/generation.py     Multipart API and ephemeral result endpoint
backend/app/pipeline/             Retry orchestration
backend/app/services/             Provider-agnostic domain services
backend/app/providers/            Background, generation, moderation, vision adapters
backend/tests/                    Pipeline and request validation tests
```

The provider interfaces isolate external services:

- `BackgroundRemovalProvider` → `BackgroundRemover`
- `ImageGenerationProvider` → `OutfitGenerator`
- `ModerationProvider` → `SafetyValidator`
- `VisionValidationProvider` → `QualityValidator`

`mock` is the default for every provider so the application runs end-to-end without credentials. The mock image generator returns the person image unchanged and the mock moderation/vision validators approve it. They are development scaffolding only and are explicitly **not production-safe**.

### OpenAI image editing

Set `IMAGE_GENERATION_PROVIDER=openai` to use the OpenAI Images Edit API. The backend sends the person photograph first, then the selected garment references in a fixed `top`, `bottom`, `outer`, `shoes`, `hat`, `accessory` order. Its prompt explicitly maps each reference image to a garment category and instructs the model to preserve the source person and every non-requested garment.

The default model is `gpt-image-2.5-sunburst`, selected for precise reference-based editing. OpenAI's Images API supports multiple reference images in an edit request and returns the generated image as base64, which this service keeps in memory for the existing result endpoint. The provider derives a valid API generation size from the person's original aspect ratio, then resizes the final result to the **exact original width and height** before returning it. See [OpenAI's image generation guide](https://developers.openai.com/api/docs/guides/image-generation).

## Run locally

Use two terminals from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && python3 -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. To point the frontend to a deployed API, set `VITE_API_BASE_URL` in `frontend/.env.local`.

## Environment

Copy `.env.example` to `backend/.env`. Mock mode needs no key:

```env
IMAGE_GENERATION_PROVIDER=mock
VISION_PROVIDER=mock
BACKGROUND_REMOVAL_PROVIDER=mock
MODERATION_PROVIDER=mock
MAX_GENERATION_RETRIES=3
```

For actual try-on generation, use:

```env
IMAGE_GENERATION_PROVIDER=openai
OPENAI_API_KEY=sk-...
IMAGE_GENERATION_MODEL=gpt-image-2.5-sunburst
IMAGE_GENERATION_QUALITY=high
IMAGE_GENERATION_SIZE=1024x1536
IMAGE_GENERATION_FORMAT=png
VISION_PROVIDER=mock
BACKGROUND_REMOVAL_PROVIDER=mock
MODERATION_PROVIDER=mock
```

The API key stays exclusively in `backend/.env`; never put it in a Vite environment variable or client-side source. The OpenAI account may require billing and organization verification before GPT Image requests can run.

### Generation observability

Every `POST /api/generate` writes readable step-by-step events to the backend terminal. A single `request_id` connects the request input metadata, preprocessing, retries, safety/quality checks, and final status. Each real OpenAI Images call also logs its model, requested API size, original/final dimensions, duration, OpenAI request ID (when returned), output metadata, and the usage object returned by the API, including image/text input tokens and output tokens when available.

Logs intentionally exclude image bytes, uploaded filenames, prompts, and API keys. Keep `LOG_LEVEL=INFO` (the default) in `backend/.env` to see them. OpenAI only returns fields that its selected model/API response exposes, so unavailable token fields are omitted rather than guessed. See [OpenAI's image generation guide](https://developers.openai.com/api/docs/guides/image-generation) for usage reporting details.

No API keys are committed or exposed to browser code. The legacy repository contained Naver credentials in its former frontend and proxy configuration; those files were removed. Because credentials may remain in Git history, revoke and reissue them before any further use rather than rewriting history blindly.

## Test and build

```bash
cd backend && pytest
cd frontend && npm run build
```

## Known limits and next steps

- Mock mode does not perform real background removal, generation, moderation, or vision validation. OpenAI image editing is available when selected, while background removal, moderation, and vision validation remain mock adapters in this release.
- Results are temporary and are not persisted.
- Production work should add authenticated, provider-specific adapters; strong image moderation; source-image quality checks; object storage with retention rules; and progress delivery via SSE or polling.
