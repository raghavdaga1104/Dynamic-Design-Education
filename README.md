# DDE — Dynamic Design Education

> AI-powered adaptive learning for Python programming and Data Structures — personalised to your pace, goals, and gaps.

DDE uses a combination of Monte Carlo Tree Search, Bayesian Knowledge Tracing, and Item Response Theory to personalise every student's learning path. Quiz questions are generated fresh on-demand by a Groq LLM. No two students take the same journey.

---

## Screenshots

| Landing | Dashboard |
|---|---|
| Enter any student ID to get started. The system creates a unique learner profile automatically. | Progress overview showing day streak, units completed, flashcards due, and skill mastery levels. |

| Skill Tree | Learn — Notes |
|---|---|
| Visual map of all 14 units. Completed units show Study button for revisiting. Locked units require prerequisites. Current unit is highlighted. | Unit notes displayed with key concepts, naming rules, and code examples. AI Tutor sidebar answers questions using RAG over the course notes. |

| Weak Areas | Flashcards |
|---|---|
| Mistake tracking across all quizzes. Shows weekly mistake count, top weak concepts, wrong-answer rate per topic, and difficulty level breakdowns. | SM-2 spaced repetition. Cards become due at optimally spaced intervals. Shows full schedule with interval, ease factor, and due day. |

| ATS Resume Analyser |
|---|
| Paste a resume and job description. The AI scores ATS compatibility and identifies missing keywords. |

---

## What it does

Students take a **Placement Test** on first login. Based on their score, the system places them at the right point in the 14-unit curriculum — beginners start at Unit 1, advanced students skip ahead.

From there, every session is personalised:

- **MCTS recommends the next unit** — simulates future study sessions to pick the unit most likely to maximise long-term mastery, not just the easiest next step
- **BKT tracks skill mastery** — a Bayesian model updates after every quiz, tracking how well each skill has been learned and whether it is likely to slip
- **IRT scores quizzes** — a 2-Parameter Logistic model estimates the student's true ability from their responses, accounting for question difficulty and discrimination
- **Groq generates fresh questions** — every quiz session gets 15 new AI-generated questions (5 easy + 5 medium + 5 hard). A 24-hour cooldown prevents repeated attempts on the same unit
- **SM-2 schedules flashcard reviews** — passing a unit creates a flashcard that resurfaces at optimally-spaced intervals
- **RAG-powered AI Tutor** — a chat sidebar lets students ask questions about the unit they are studying. ChromaDB stores course notes as embeddings and retrieves relevant context for every query
- **Weak Areas tracking** — every wrong answer is logged by concept and difficulty, surfacing patterns like "100% wrong rate on complexity questions"
- **ATS Resume Analyser** — students can paste their resume and a job description to get an ATS compatibility score and gap analysis

---

## Curriculum

14 units across 4 domains with prerequisite chains enforced by a knowledge graph. A unit unlocks only when all prerequisite skills have mastery ≥ 0.70.

| Domain | Units |
|---|---|
| 🐍 Python Fundamentals | Python Basics → Functions & Scope |
| 🔷 Object-Oriented Programming | OOP Concepts → Advanced OOP |
| 🌲 Data Structures | Arrays & Lists → Linked Lists → Stacks & Queues → Trees & BST → Hash Tables |
| ⚙️ Algorithms | Sorting → Searching → Recursion & Backtracking → Dynamic Programming → Graph Algorithms |

---

## Tech stack

### Backend (`ai-ml/`)
| Technology | Purpose |
|---|---|
| FastAPI + Uvicorn | REST API — all learning, quiz, and AI endpoints |
| Groq API (`llama-3.1-8b-instant`) | On-demand question generation and AI Tutor responses |
| ChromaDB | Vector database for RAG-based AI Tutor |
| sentence-transformers | Text embeddings for ChromaDB indexing |
| Custom MCTS | Unit recommendation engine |
| Custom BKT + IRT | Adaptive quiz scoring |
| Custom SM-2 | Spaced repetition for flashcards |
| Python 3.11 | |

### Frontend (`frontend/`)
| Technology | Purpose |
|---|---|
| React 18 + React Router v6 | SPA with client-side routing |
| Vite | Dev server and bundler |
| Vanilla CSS | No UI framework |

---

## Project structure

```
Dynamic-Design-Education/
├── ai-ml/
│   ├── main.py                          # FastAPI app — all 35+ endpoints
│   ├── .env                             # API keys and config (not committed)
│   ├── requirements.txt
│   └── python_source/
│       ├── content/
│       │   ├── curriculum.py            # 14-unit knowledge graph definition
│       │   ├── quiz_bank.py             # Handcrafted MCQ question bank (90 questions)
│       │   ├── diagnostic_quiz.py       # Placement test questions and scoring
│       │   ├── notes_data.py            # Course notes for RAG indexing
│       │   └── dataset_loader.py        # python_course_dataset.json loader
│       ├── core/
│       │   ├── mcts_algorithm.py        # Monte Carlo Tree Search (150 iterations)
│       │   ├── learner_session.py       # Per-student state — BKT, SM-2, history
│       │   ├── irt_scoring.py           # 2PL Item Response Theory scoring
│       │   ├── adaptive_systems.py      # IRT-based question selection
│       │   ├── knowledge_graph.py       # Prerequisite dependency graph
│       │   ├── mistake_tracker.py       # Per-concept wrong-answer tracking
│       │   └── analytics_logger.py      # Learning event logging
│       ├── engines/
│       │   ├── question_generator.py    # On-demand Groq generation + 24hr lock cache
│       │   ├── rag_engine.py            # ChromaDB RAG engine for AI Tutor
│       │   └── ats_engine.py            # ATS resume analysis engine
│       ├── state/
│       │   └── state_manager.py         # Per-user JSON session file management
│       └── data/
│           ├── notes.json               # Rich unit notes (definitions, examples, code)
│           ├── learner_states/          # Per-user session files (gitignored)
│           └── quiz_cache/              # Per-user generated question cache (gitignored)
└── frontend/
    └── src/
        ├── pages/
        │   ├── Onboarding.jsx           # Landing — student ID entry
        │   ├── Diagnostic.jsx           # Placement test
        │   ├── Dashboard.jsx            # Progress overview and skill mastery
        │   ├── Learn.jsx                # Main study flow — notes, quiz, results
        │   ├── SkillTree.jsx            # Visual curriculum map with unit cards
        │   ├── Flashcards.jsx           # SM-2 spaced review
        │   ├── Mistakes.jsx             # Weak areas, concepts, history
        │   └── ATS.jsx                  # Resume ATS analyser
        ├── services/
        │   └── api.js                   # All API calls in one place
        └── context/
            └── AppContext.jsx           # Global user state (userId, profile)
```

---

## Getting started

### Prerequisites
- Python 3.11
- Node.js 18+
- A free Groq API key — [console.groq.com](https://console.groq.com) (no credit card needed)

### 1. Clone

```bash
git clone https://github.com/your-username/Dynamic-Design-Education.git
cd Dynamic-Design-Education
```

### 2. Backend

```bash
cd ai-ml

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create `ai-ml/.env`:

```env
# Required
GROQ_API_KEY=gsk_your_key_here

# Optional — defaults shown
GROQ_MODEL=llama-3.1-8b-instant
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
MCTS_ITERATIONS=150
STATE_DIR=data/learner_states
QUIZ_QUESTION_CAP=10
LOG_LEVEL=INFO
```

Start the backend:

```bash
# Windows
python.exe -m uvicorn main:app --reload

# macOS / Linux
uvicorn main:app --reload
```

Backend runs at `http://localhost:8000`. Keep this terminal open.

### 3. Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

### 4. First run

Go to `http://localhost:3000`. Enter any student ID (e.g. `testuser_01`) and click Continue. You will be taken to the Placement Test — complete it to create your learner profile and get placed at the right point in the curriculum.

---

## How the quiz system works

```
Student clicks "Start Quiz"
    ↓
GET /curriculum/{unit_id}/questions?user_id={id}
    ↓
question_generator.py checks quiz_cache/{user_id}_{unit_id}.json
    ↓
Cache miss → Groq generates 15 questions (5 easy + 5 medium + 5 hard)
             Questions cached, locked_until = None (no lock yet)
    ↓
Student answers all questions and clicks Submit
    ↓
POST /quiz/submit-irt
    ↓
IRT scores the quiz (2PL MLE ability estimation)
BKT updates skill mastery (0.7 × IRT + 0.3 × BKT prior on pass)
24-hour lock written to cache
    ↓
Unit passed?  → SM-2 flashcard created, MCTS picks next unit
Unit failed?  → Lock active for 24hrs, student reviews notes and retries tomorrow
```

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/curriculum` | All 14 units with metadata |
| GET | `/curriculum/{unit_id}/questions?user_id=` | Get quiz questions (AI-generated, 24hr lock) |
| GET | `/curriculum/{unit_id}/notes` | Get unit study notes |
| POST | `/recommend` | Get next unit recommendation via MCTS |
| POST | `/quiz/submit-irt` | Submit quiz answers for IRT + BKT scoring |
| GET | `/learner/{user_id}` | Get learner progress and mastery state |
| POST | `/learner/{user_id}/reset` | Reset learner to fresh state |
| DELETE | `/learner/{user_id}/quiz-lock` | Clear all quiz locks (dev/testing) |
| DELETE | `/learner/{user_id}/quiz-lock/{unit_id}` | Clear quiz lock for one unit |
| GET | `/skill-tree/{user_id}` | Skill tree with unit statuses and mastery |
| GET | `/diagnostic/topics` | Available placement test topics |
| POST | `/diagnostic/start` | Start placement test |
| POST | `/diagnostic/submit` | Submit placement test answers |
| POST | `/diagnostic/skip` | Skip placement test (start from beginning) |
| GET | `/flashcard/due/{user_id}` | Flashcards due for review today |
| GET | `/flashcard/gate/{user_id}` | Check if reviews must be done before continuing |
| POST | `/flashcard/review` | Submit flashcard review quality (SM-2 update) |
| POST | `/chat` | AI Tutor message (RAG over course notes) |
| POST | `/ats/analyze` | Analyse resume against job description |
| POST | `/ats/improve` | Get improvement suggestions for resume |
| GET | `/mistakes/insights/{user_id}` | Weak areas and mistake pattern analysis |
| GET | `/mistakes/log/{user_id}` | Full mistake history |

---

## Key algorithms

**MCTS — Monte Carlo Tree Search**
Selects the next learning unit by simulating future study sessions. Each iteration: select a node using UCB1 (exploration vs exploitation), expand by adding an untried unit, simulate a random rollout using BKT + IRT to estimate expected mastery gain, backpropagate the reward. Runs 150 iterations by default. Configurable via `MCTS_ITERATIONS` in `.env`.

**BKT — Bayesian Knowledge Tracing**
Tracks skill mastery as a probability between 0 and 1. Default parameters: `p_transit = 0.15`, `p_guess = 0.20`, `p_slip = 0.10`. On quiz pass, blends with IRT estimate: `new_mastery = 0.7 × IRT + 0.3 × BKT_prior`. Stuck threshold: 3 consecutive failures on a unit surfaces prerequisite review suggestions.

**IRT — Item Response Theory (2PL model)**
Estimates student ability θ using Maximum Likelihood Estimation over quiz responses. Each question has a difficulty parameter `b` (easy: 0.30, medium: 0.60, hard: 0.90) and discrimination `a` (easy: 1.20, medium: 1.00, hard: 0.80). Pass threshold: θ ≥ 0.619 (mastery probability ≥ 65%). Edge cases: all correct → θ = 3.2, all wrong → θ = −3.2.

**SM-2 — Spaced Repetition**
Flashcards are created when a unit is passed with interval = 1 day. Review intervals grow exponentially based on recall quality (0–5 scale). Quality < 3 resets interval to 1. The system gates access to the next unit if flashcard reviews are overdue, enforcing spaced review before new content.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** Get free at console.groq.com |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | LLM for question generation and chat |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `MCTS_ITERATIONS` | `150` | Higher = better recommendations, slower |
| `QUIZ_QUESTION_CAP` | `10` | Questions served per quiz attempt |
| `STATE_DIR` | `data/learner_states` | Directory for per-user session JSON files |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Notes for contributors

- `data/learner_states/` is gitignored — per-user sessions are local only
- `data/quiz_cache/` is gitignored — generated questions are ephemeral
- `data/chroma_db/` is gitignored — the vector store rebuilds automatically on first run
- `python_course_dataset.json` is not in the repo due to size — it is required for the RAG notes index and dataset-derived quiz questions
- To add a new curriculum unit: add it to `curriculum.py`, add its topics to `_UNIT_META` in `question_generator.py`, and optionally add handcrafted seed questions to `quiz_bank.py`

---

## License

MIT
