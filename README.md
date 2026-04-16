# Second Opinion Clinical Decision Support System

Production-ready AI-assisted clinical decision support for oncology teams. The system ingests structured patient EHR data, searches PubMed evidence and guideline references, computes patient-specific risk, and returns recommendation objects with end-to-end citation traceability.

## Architecture

### Backend (`backend/`)
- FastAPI app with routers for health, evidence, and recommendation workflows
- Services for EHR validation, PubMed retrieval, guideline search, risk analysis, recommendation generation, and citation formatting
- Pydantic models for EHR, evidence, and recommendation payloads
- Async PubMed + PMC Open Access integration (NCBI Entrez + PMC OAI/full-text parsing) with in-memory query caching

### Frontend (`frontend/`)
- React + TypeScript + Tailwind CSS + React Router
- Patient intake workflow with core oncology inputs (cancer type, stage, biomarkers, genetics, ECOG, age, comorbidities, metastases, progression)
- Recommendation display with risk visualization and citation viewer

### Deployment
- `Dockerfile.backend` (Python 3.11 + Uvicorn)
- `Dockerfile.frontend` (Node build + Nginx serving)
- `docker-compose.yml` for local full-stack runs

## Backend API

- `GET /api/health`
- `POST /api/recommendations`
- `GET /api/recommendations/{recommendation_id}`
- `GET /api/recommendations/patient/{patient_id}`
- `GET /api/evidence/{pmid}`
- `GET /api/evidence/search?query=...`
- `GET /api/guidelines/search?cancer_type=...&treatment=...`
- `GET /api/trials/{trial_id}`

## Environment

`backend/.env.example`

```env
LLM_BACKEND=ollama
LLM_MODEL=mistral
LLM_ENDPOINT=http://localhost:11434
NCBI_EMAIL=your_email@example.com
PMC_EMAIL=your_email@example.com
PMC_BATCH_SIZE=5
FASTAPI_ENV=development
LOG_LEVEL=INFO
```

## Local Development

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Full stack (Docker)
```bash
docker-compose up --build
```

Frontend: `http://localhost:3000`  
Backend docs: `http://localhost:8000/docs`

## Example Clinical Inputs

- NSCLC with EGFR mutation and metastatic progression
- HER2+ breast cancer
- MSI-H colorectal cancer

Each recommendation response includes treatment details, indications, contraindications, risk score (1–10), confidence interval, supporting efficacy evidence, and citations with PMID/DOI links.
