"""
rag_engine.py  — DDE Tutor (Hybrid RAG + Free LLM mode)
"""

import logging
import sys
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Tuple

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import chromadb
import httpx
from sentence_transformers import SentenceTransformer

import os
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL    = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

logger = logging.getLogger(__name__)

EMBEDDING_MODEL      = "all-MiniLM-L6-v2"
CHROMA_PATH          = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME      = "dde_notes"
DATASET_PATH         = Path(__file__).parent.parent / "data" / "python_course_dataset.json"
TOP_K_RETRIEVE       = 6
SIMILARITY_THRESHOLD = 0.65

SYSTEM_PROMPT = """You are DDE Tutor, an expert AI teaching assistant inside the DDE adaptive learning platform.

YOUR ROLE:
- You are a knowledgeable, patient computer science tutor for BTech/engineering students
- You give complete, accurate, genuinely useful answers to CS questions
- You use the CONTEXT NOTES to understand what topic and unit the student is studying
- You draw on your full CS knowledge to give thorough answers — don't be limited by notes quality

HOW TO ANSWER:
- Use context notes to understand the topic level and provide relevant examples
- If notes contain good code examples, reference them; otherwise write your own clear example
- Always relate your answer to the student's current unit (shown above the notes)
- Give complete answers — never refuse to answer a standard CS question

FORMAT RULES:
- 2-4 paragraphs maximum (clear and concise)
- Include a short code snippet when it genuinely helps
- Use bullet points only when listing multiple items
- Do not start with "Certainly!", "Great question!", or filler phrases

STRICT RULES:
- Do not invent false facts (wrong syntax, wrong algorithm names, made-up APIs)
- Do not say "I cannot answer" or "I don't have information" for standard CS topics
- Do not add irrelevant information outside the CS domain
- Do not refer to yourself as an AI or mention training data"""


def _build_question_prompt(question, notes, unit_title=None, unit_domain=None):
    parts = []
    if unit_title:
        header = f"STUDENT'S CURRENT UNIT: {unit_title}"
        if unit_domain:
            header += f"  |  Domain: {unit_domain}"
        parts.append(header)
        parts.append("-" * 50)
    if notes.strip():
        parts.append("CONTEXT NOTES (use to understand topic level):")
        parts.append(notes.strip())
        parts.append("-" * 50)
    else:
        parts.append("CONTEXT NOTES: [Not available — answer from your CS knowledge]")
        parts.append("-" * 50)
    parts.append(f"STUDENT QUESTION: {question}")
    parts.append("")
    parts.append("Answer clearly and completely. Use context notes for topic grounding but answer from your full CS knowledge.")
    return "\n".join(parts)


def _build_hint_prompt(question_text, unit_title=None, notes=""):
    parts = []
    if unit_title:
        parts.append(f"CURRENT UNIT: {unit_title}")
        parts.append("-" * 50)
    if notes.strip():
        parts.append("RELEVANT NOTES:")
        parts.append(notes.strip())
        parts.append("-" * 50)
    parts.append(f"QUIZ QUESTION: {question_text}")
    parts.append("")
    parts.append("Give ONE Socratic hint — a guiding question pointing toward the answer without revealing it. Maximum 2 sentences.")
    return "\n".join(parts)


def _build_simplify_prompt(note_content, unit_title=None):
    parts = []
    if unit_title:
        parts.append(f"UNIT: {unit_title}")
        parts.append("-" * 50)
    parts.append("ORIGINAL NOTE:")
    parts.append(note_content.strip())
    parts.append("-" * 50)
    parts.append("Rewrite this for a complete beginner using simple analogies. Remove jargon. 2-3 short paragraphs. Add a simple code example if relevant.")
    return "\n".join(parts)


def _load_notes_from_dataset():
    if not DATASET_PATH.exists():
        logger.error("Dataset not found at %s", DATASET_PATH)
        return []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    notes = []
    for item in raw:
        parts = []
        if item.get("concept"):   parts.append(item["concept"])
        if item.get("code"):      parts.append(f"Code:\n{item['code']}")
        if item.get("explanation"): parts.append(f"Explanation:\n{item['explanation']}")
        if not parts or "id" not in item:
            continue
        notes.append({"id": item["id"], "unit_id": item.get("unit",""), "topic": item.get("topic",""), "content": "\n\n".join(parts)})
    logger.info("Loaded %d notes from dataset.", len(notes))
    return notes


SAMPLE_NOTES: List[Dict] = []
try:
    from content.notes_data import ALL_NOTES as SAMPLE_NOTES
except ImportError:
    try:
        from notes_data import ALL_NOTES as SAMPLE_NOTES
    except ImportError:
        pass
if not SAMPLE_NOTES:
    SAMPLE_NOTES = _load_notes_from_dataset()


class RAGEngine:
    def __init__(self):
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set. Get a free key at https://console.groq.com")
        else:
            logger.info("RAGEngine ready (model: %s)", GROQ_MODEL)

        logger.info("Loading sentence transformer...")
        self.embed_model = SentenceTransformer(EMBEDDING_MODEL)
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.chroma_client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        if self.collection.count() == 0:
            count = self._index_notes(SAMPLE_NOTES)
            logger.info("Indexed %d notes.", count)
        else:
            logger.info("%d notes ready.", self.collection.count())
        self.groq_available = bool(GROQ_API_KEY)

    def query(self, user_question, unit_id=None, unit_title=None, unit_domain=None, unit_notes=None, mode="question"):
        if not user_question.strip() and mode != "simplify":
            return {"answer": "Please type a question.", "sources": [], "mode": mode, "context_used": False}
        if mode == "simplify":
            return self._handle_simplify(unit_notes, unit_title)
        context_notes, sources = self._get_context(query=user_question, unit_id=unit_id, unit_notes=unit_notes)
        if mode == "hint":
            return self._handle_hint(user_question, unit_title, context_notes, sources)
        return self._handle_question(user_question, context_notes, unit_title, unit_domain, sources)

    def add_notes(self, notes): return self._index_notes(notes)

    def reindex(self, notes=None):
        try: self.chroma_client.delete_collection(COLLECTION_NAME)
        except: pass
        self.collection = self.chroma_client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        count = self._index_notes(notes if notes is not None else SAMPLE_NOTES)
        logger.info("Re-indexed %d notes.", count)
        return count

    def _handle_question(self, question, notes, unit_title, unit_domain, sources):
        answer = self._generate(_build_question_prompt(question, notes, unit_title, unit_domain))
        return {"answer": answer, "sources": sources, "mode": "question", "context_used": bool(notes.strip())}

    def _handle_simplify(self, note_content, unit_title):
        if not note_content or not note_content.strip():
            return {"answer": "No note content provided to simplify.", "sources": [], "mode": "simplify", "context_used": False}
        answer = self._generate(_build_simplify_prompt(note_content, unit_title))
        return {"answer": answer, "sources": [], "mode": "simplify", "context_used": True}

    def _handle_hint(self, question, unit_title, notes, sources):
        answer = self._generate(_build_hint_prompt(question, unit_title, notes))
        return {"answer": answer, "sources": sources, "mode": "hint", "context_used": bool(notes.strip())}

    def _get_context(self, query, unit_id=None, unit_notes=None):
        if unit_notes and unit_notes.strip():
            return unit_notes.strip(), ["direct_unit_context"]
        return self._semantic_search(query, unit_id=unit_id)

    def _semantic_search(self, query, unit_id=None):
        n = min(TOP_K_RETRIEVE, self.collection.count())
        if n == 0:
            return "", []
        query_vec = self.embed_model.encode(query).tolist()
        where = {"unit_id": unit_id} if unit_id else None
        try:
            results = self.collection.query(query_embeddings=[query_vec], n_results=n, where=where)
        except Exception:
            results = self.collection.query(query_embeddings=[query_vec], n_results=n)
        docs      = results["documents"][0] if results.get("documents") else []
        ids       = results["ids"][0]       if results.get("ids")       else []
        distances = results.get("distances", [[]])[0]
        if not docs:
            return "", []
        # Always return at least 2 results for context even if similarity is low
        filtered_docs, filtered_ids = [], []
        for i, (doc, did) in enumerate(zip(docs, ids)):
            dist = distances[i] if i < len(distances) else 1.0
            if dist <= SIMILARITY_THRESHOLD:
                filtered_docs.append(doc)
                filtered_ids.append(did)
        if not filtered_docs:
            filtered_docs = docs[:2]
            filtered_ids  = ids[:2]
        return "\n\n---\n\n".join(filtered_docs), filtered_ids

    def _generate(self, user_prompt, _retry=0):
        if not GROQ_API_KEY:
            return (
                "The AI tutor needs a Groq API key to work.\n\n"
                "Get a FREE key (no credit card) at https://console.groq.com\n"
                "Then set it before starting the server:\n"
                "  Windows CMD:  set GROQ_API_KEY=your_key_here\n"
                "  PowerShell:   $env:GROQ_API_KEY=\"your_key_here\"\n"
                "  Linux/Mac:    export GROQ_API_KEY=your_key_here"
            )
        try:
            resp = httpx.post(
                GROQ_BASE_URL,
                json={"model": GROQ_MODEL, "messages": [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_prompt}], "temperature":0.4, "max_tokens":700},
                timeout=30,
                headers={"Content-Type":"application/json","Authorization":f"Bearer {GROQ_API_KEY}"},
            )
            logger.debug("Groq: %d", resp.status_code)
            if resp.status_code == 200:
                answer = resp.json().get("choices",[{}])[0].get("message",{}).get("content","").strip()
                return answer if answer else self._fallback(user_prompt)
            elif resp.status_code == 429:
                logger.warning("Groq rate limited")
                if _retry == 0:
                    time.sleep(5)
                    return self._generate(user_prompt, _retry=1)
                return "Rate limit reached. Please wait a moment and try again."
            elif resp.status_code == 401:
                return "Invalid API key. Please check your GROQ_API_KEY."
            else:
                logger.error("Groq error %d", resp.status_code)
                return self._fallback(user_prompt)
        except httpx.TimeoutException:
            return "Response timed out. Please try again."
        except Exception as exc:
            logger.exception("RAGEngine error: %s", exc)
            return self._fallback(user_prompt)

    def _fallback(self, prompt):
        if "CONTEXT NOTES" in prompt:
            start = prompt.find("CONTEXT NOTES") + len("CONTEXT NOTES")
            end   = prompt.find("-" * 10, start)
            notes = prompt[start:end].strip() if end > start else ""
            if notes and len(notes) > 50:
                return f"(API unavailable — showing relevant notes)\n\n{notes[:600]}"
        return "AI tutor unavailable. Check your GROQ_API_KEY and internet connection."

    def _index_notes(self, notes):
        ids, documents, metadatas = [], [], []
        for note in notes:
            content = note.get("content", "").strip()
            if not content or "id" not in note:
                continue
            ids.append(note["id"])
            documents.append(content)
            metadatas.append({"unit_id": note.get("unit_id",""), "topic": note.get("topic","")})
        if not ids:
            return 0
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            b_ids  = ids[i:i+batch_size]
            b_docs = documents[i:i+batch_size]
            b_meta = metadatas[i:i+batch_size]
            embs   = self.embed_model.encode(b_docs).tolist()
            self.collection.upsert(ids=b_ids, embeddings=embs, documents=b_docs, metadatas=b_meta)
        return len(ids)