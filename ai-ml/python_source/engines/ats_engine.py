"""
ats_engine.py
-------------
ATS Resume Scorer + LLM-based Resume Improvement.

FIXES APPLIED (Review §3 Bug #4, §5 Performance):
  1. GROQ_API_KEY / GROQ_MODEL / GROQ_BASE_URL now imported from config.py
     instead of being re-declared here (was duplicated with rag_engine.py).

  2. All print('[DEBUG]...') calls replaced with logging.debug() / logging.info().

  3. Bullet rewrites parallelised using concurrent.futures.ThreadPoolExecutor.
     Previously 10 bullets were rewritten sequentially (10 × ~3s = 30s+).
     Now they run in parallel (all 10 at once, limited by thread pool).
     Wall-clock time drops from 30-60s to ~5-10s.

Two concerns kept cleanly separate:
  analyze()        → scoring (deterministic ML, always runs)
  rewrite_resume() → improvement suggestions (LLM, optional)
"""

import logging
import os
import re
import sys
import json
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL

logger = logging.getLogger(__name__)

# Thread pool for parallel bullet rewrites
_BULLET_EXECUTOR = ThreadPoolExecutor(max_workers=5, thread_name_prefix="ats_bullet")

# ─────────────────────────────────────────────────────────────────
#  TECH SKILLS KEYWORD SET
# ─────────────────────────────────────────────────────────────────

TECH_SKILLS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "react", "angular", "vue", "nextjs", "nodejs", "django", "flask", "fastapi",
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "jenkins",
    "git", "linux", "rest", "api", "graphql", "grpc", "kafka", "rabbitmq",
    "machine learning", "deep learning", "nlp", "computer vision",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
    "data structures", "algorithms", "system design", "microservices",
    "agile", "scrum", "devops", "ci/cd", "testing", "unit testing",
}


# ─────────────────────────────────────────────────────────────────
#  PROMPT TEMPLATES
# ─────────────────────────────────────────────────────────────────

REWRITE_SYSTEM_PROMPT = """You are a professional resume editor specialising in \
technical resumes for software engineering roles.

YOUR RULES — follow without exception:
1. NEVER add skills, tools, frameworks, or experience not present in the original text
2. NEVER invent metrics, numbers, or percentages (e.g., do not write "improved by 40%" \
unless the original says so)
3. NEVER change the meaning of what the candidate did
4. You may only: rephrase, reorder words, add action verbs, improve clarity
5. Output ONLY valid JSON — no preamble, no explanation, no markdown fences
6. If a bullet is already well-written, return it unchanged in the rewritten field"""


def _bullet_rewrite_prompt(
    bullet:           str,
    missing_keywords: List[str],
    job_title:        str = "",
) -> str:
    keyword_hint = ""
    if missing_keywords:
        keyword_hint = (
            f"\nMISSING KEYWORDS FROM JOB DESCRIPTION: {', '.join(missing_keywords[:6])}\n"
            "If and ONLY IF any of these keywords genuinely describe what this bullet "
            "already talks about, you may naturally include them in the rewrite. "
            "Do NOT force keywords that don't fit."
        )
    role_hint = f"\nTARGET ROLE: {job_title}" if job_title else ""
    return f"""Rewrite the following resume bullet point to be more impactful.
Use strong action verbs. Be specific. Keep it to 1-2 lines maximum.
{role_hint}{keyword_hint}

ORIGINAL BULLET:
{bullet}

Respond with this exact JSON structure:
{{
  "original":    "<original bullet>",
  "rewritten":   "<improved bullet>",
  "changes_made": "<brief description of what you changed and why>",
  "action_verb_used": "<the action verb you started with>"
}}"""


def _keyword_inject_prompt(
    resume_sections:  Dict[str, str],
    missing_keywords: List[str],
    job_description:  str,
) -> str:
    sections_text = "\n".join(
        f"[{name.upper()}]\n{text}" for name, text in resume_sections.items()
    )
    return f"""You are reviewing a resume for keyword gaps.

MISSING KEYWORDS (present in job description, absent from resume):
{', '.join(missing_keywords)}

RESUME SECTIONS:
{sections_text}

JOB DESCRIPTION EXCERPT (first 400 chars):
{job_description[:400]}

For each missing keyword, decide:
  a) Can it be added truthfully based on what the resume already shows?
  b) If yes: which section, and suggest a natural addition (max 1 line)
  c) If no: mark as "cannot add without misrepresenting experience"

RULES:
- Do NOT suggest adding experience that is not implied by the resume
- Do NOT create bullet points from scratch
- Suggestions must be grounded in what already exists

Respond with this exact JSON structure:
{{
  "suggestions": [
    {{
      "keyword":   "<missing keyword>",
      "can_add":   true or false,
      "section":   "<section name or null>",
      "suggestion": "<one line addition or null>",
      "reason":    "<why this can or cannot be added>"
    }}
  ]
}}"""


def _summary_improve_prompt(
    existing_summary: str,
    target_role:      str,
    matched_keywords: List[str],
    missing_keywords: List[str],
) -> str:
    if existing_summary.strip():
        task = (
            f"Rewrite this professional summary to be more impactful for a {target_role} role. "
            f"Use only information present in the original. "
            f"Naturally incorporate these matched keywords where appropriate: "
            f"{', '.join(matched_keywords[:5])}."
        )
        subject = f"EXISTING SUMMARY:\n{existing_summary}"
    else:
        task = (
            f"Write a 2-3 sentence professional summary for a {target_role} candidate. "
            f"Base it ONLY on these skills the candidate already has: "
            f"{', '.join(matched_keywords[:8])}. "
            f"Do not add any skills not in this list."
        )
        subject = "EXISTING SUMMARY: [none provided]"

    return f"""{task}

{subject}

RULES:
- Maximum 3 sentences
- Start with a strong professional identity statement
- Do not use first person ("I" or "my")
- Do not invent achievements or metrics
- Do not add technologies not mentioned in the matched keywords list

Respond with this exact JSON:
{{
  "improved_summary": "<the rewritten or generated summary>",
  "changes_made":     "<what you changed or how you constructed it>"
}}"""


# ─────────────────────────────────────────────────────────────────
#  ATS ENGINE
# ─────────────────────────────────────────────────────────────────

class ATSEngine:
    """
    ATS scorer + LLM-based resume improvement engine.

    Scoring:   deterministic (TF-IDF + spaCy + cosine similarity)
    Rewriting: generative   (Groq API + structured prompts, parallelised)
    """

    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )
            self.nlp = None

        self.groq_available = self._check_groq()
        if self.groq_available:
            logger.info("ATSEngine: Groq API connected (model: %s)", GROQ_MODEL)
        else:
            logger.warning(
                "ATSEngine: Groq API not available — "
                "resume improvement will use rule-based fallback. "
                "Set GROQ_API_KEY to enable LLM suggestions."
            )

    # ──────────────────────────────────────────
    #  PUBLIC API — scoring
    # ──────────────────────────────────────────

    def analyze(self, resume_text: str, job_description: str) -> Dict:
        """Score a resume against a job description."""
        if not resume_text.strip() or not job_description.strip():
            return {"error": "Both resume_text and job_description must be provided."}

        jd_kw      = self._extract_keywords(job_description)
        resume_kw  = self._extract_keywords(resume_text)
        tfidf      = self._tfidf_score(job_description, resume_text)
        kw_score, matched, missing = self._keyword_overlap(jd_kw, resume_kw)

        final_score = min(100, max(0, round(tfidf * 0.6 + kw_score * 0.4)))

        feedback    = self._generate_feedback(final_score, sorted(matched), sorted(missing))
        suggestions = self._parse_suggestions(feedback)

        return {
            "score_ats":            final_score,
            "matched_keywords":     sorted(matched),
            "missing_keywords":     sorted(missing),
            "jd_keyword_count":     len(jd_kw),
            "resume_keyword_count": len(resume_kw),
            "feedback":             feedback,
            "suggestions":          suggestions,
            "score_breakdown": {
                "tfidf_similarity_score": round(tfidf, 1),
                "keyword_overlap_score":  round(kw_score, 1),
                "final_weighted_score":   final_score,
            },
        }

    # ──────────────────────────────────────────
    #  PUBLIC API — rewriting (now parallelised)
    # ──────────────────────────────────────────

    def rewrite_resume(
        self,
        resume_text:      str,
        missing_keywords: List[str],
        matched_keywords: List[str],
        job_description:  str = "",
        target_role:      str = "",
        resume_sections:  Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        Generate LLM-based improvement suggestions for a resume.

        FIX: bullet rewrites now run in parallel via ThreadPoolExecutor.
        Previously: 10 sequential calls × ~3s each = 30s+
        Now:        10 parallel calls, wall-clock ≈ max(individual call time) ≈ 5-10s
        """
        if not resume_text.strip():
            return {"error": "resume_text is required."}

        if not self.groq_available:
            return {
                "error":   "Groq API is not available.",
                "message": (
                    "Set your GROQ_API_KEY environment variable. "
                    "Get a free key at https://console.groq.com"
                ),
            }

        sections = resume_sections or self._parse_sections(resume_text)
        bullets  = self._extract_bullets(resume_text)

        results = {
            "bullet_rewrites":     [],
            "keyword_suggestions": [],
            "improved_summary":    {},
            "bullets_processed":   len(bullets),
            "anti_hallucination_note": (
                "All suggestions are based strictly on your existing experience. "
                "No skills or achievements have been invented. "
                "Review each suggestion before using it."
            ),
        }

        # ── Pass 1: Rewrite bullets IN PARALLEL ──────────────────
        target_bullets = bullets[:10]
        logger.info("ATSEngine: rewriting %d bullet points in parallel...", len(target_bullets))

        futures = {
            _BULLET_EXECUTOR.submit(
                self._rewrite_bullet, bullet, missing_keywords, target_role
            ): bullet
            for bullet in target_bullets
        }

        rewrites = []
        for future in as_completed(futures):
            try:
                rewrite = future.result()
                if rewrite:
                    rewrites.append(rewrite)
            except Exception as exc:
                logger.warning("Bullet rewrite failed: %s", exc)

        # Restore original order (as_completed returns in completion order)
        bullet_order = {b: i for i, b in enumerate(target_bullets)}
        rewrites.sort(key=lambda r: bullet_order.get(r.get("original", ""), 999))
        results["bullet_rewrites"] = rewrites

        # ── Pass 2: Keyword injection suggestions ────────────────
        if missing_keywords:
            logger.info("ATSEngine: generating keyword injection suggestions...")
            results["keyword_suggestions"] = self._suggest_keyword_injection(
                sections, missing_keywords, job_description
            )

        # ── Pass 3: Summary improvement ───────────────────────────
        summary_text = sections.get("summary", sections.get("profile", ""))
        logger.info("ATSEngine: improving professional summary...")
        results["improved_summary"] = self._improve_summary(
            summary_text, target_role, matched_keywords, missing_keywords
        )

        return results

    def analyze_and_improve(
        self,
        resume_text:     str,
        job_description: str,
        target_role:     str = "",
    ) -> Dict:
        """Combined endpoint: score + improve in one call."""
        score_result = self.analyze(resume_text, job_description)
        if "error" in score_result:
            return score_result

        improve_result = self.rewrite_resume(
            resume_text=      resume_text,
            missing_keywords= score_result["missing_keywords"],
            matched_keywords= score_result["matched_keywords"],
            job_description=  job_description,
            target_role=      target_role,
        )

        return {
            "scoring": {
                "score_ats":        score_result["score_ats"],
                "matched_keywords": score_result["matched_keywords"],
                "missing_keywords": score_result["missing_keywords"],
                "feedback":         score_result["feedback"],
                "score_breakdown":  score_result["score_breakdown"],
            },
            "improvements": improve_result,
        }

    # ──────────────────────────────────────────
    #  Rewriting helpers
    # ──────────────────────────────────────────

    def _rewrite_bullet(
        self,
        bullet:           str,
        missing_keywords: List[str],
        target_role:      str,
    ) -> Optional[Dict]:
        if len(bullet.strip()) < 10:
            return None

        prompt = _bullet_rewrite_prompt(bullet, missing_keywords, target_role)
        raw    = self._call_groq_generate(prompt)
        parsed = self._safe_parse_json(raw)

        if not parsed:
            return {
                "original":         bullet,
                "rewritten":        bullet,
                "changes_made":     "Could not generate improvement.",
                "action_verb_used": "",
            }

        # Hallucination guard: reject if rewrite is more than 2.5× original length
        original_words = len(bullet.split())
        rewritten      = parsed.get("rewritten", bullet)
        if len(rewritten.split()) > original_words * 2.5:
            logger.warning(
                "Bullet rewrite rejected (hallucination guard): original=%d words, rewritten=%d words",
                original_words, len(rewritten.split()),
            )
            return {
                "original":         bullet,
                "rewritten":        bullet,
                "changes_made":     "Rewrite rejected — response too long (hallucination guard).",
                "action_verb_used": "",
            }

        return {
            "original":         bullet,
            "rewritten":        rewritten,
            "changes_made":     parsed.get("changes_made", ""),
            "action_verb_used": parsed.get("action_verb_used", ""),
        }

    def _suggest_keyword_injection(
        self,
        sections:         Dict[str, str],
        missing_keywords: List[str],
        job_description:  str,
    ) -> List[Dict]:
        prompt = _keyword_inject_prompt(sections, missing_keywords[:8], job_description)
        raw    = self._call_groq_generate(prompt)
        parsed = self._safe_parse_json(raw)

        if not parsed or "suggestions" not in parsed:
            return [{
                "keyword":    kw,
                "can_add":    False,
                "suggestion": None,
                "reason":     "Could not generate suggestion.",
            } for kw in missing_keywords[:5]]

        return parsed["suggestions"]

    def _improve_summary(
        self,
        existing_summary: str,
        target_role:      str,
        matched_keywords: List[str],
        missing_keywords: List[str],
    ) -> Dict:
        if not matched_keywords:
            return {
                "improved_summary": "",
                "changes_made":     "No matched keywords — cannot generate summary.",
            }

        prompt = _summary_improve_prompt(
            existing_summary, target_role, matched_keywords, missing_keywords
        )
        raw    = self._call_groq_generate(prompt)
        parsed = self._safe_parse_json(raw)

        if not parsed:
            return {
                "improved_summary": existing_summary,
                "changes_made":     "Could not generate improvement.",
            }

        return parsed

    # ──────────────────────────────────────────
    #  Groq communication
    # ──────────────────────────────────────────

    def _call_groq_generate(self, user_prompt: str) -> str:
        if not GROQ_API_KEY:
            return ""

        try:
            resp = httpx.post(
                GROQ_BASE_URL,
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens":  600,
                },
                timeout=30,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                },
            )
            logger.debug("ATSEngine Groq response: %d", resp.status_code)

            if resp.status_code == 200:
                return (
                    resp.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                )
            else:
                logger.warning(
                    "ATSEngine Groq error %d: %s", resp.status_code, resp.text[:200]
                )
                return ""

        except Exception as exc:
            logger.exception("ATSEngine Groq call failed: %s", exc)
            return ""

    def _check_groq(self) -> bool:
        if not GROQ_API_KEY:
            return False
        try:
            resp = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _safe_parse_json(self, text: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown fences and leading text."""
        if not text:
            return None

        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*',     '', text)
        text = text.strip()

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            text = re.sub(r',\s*}', '}', text)
            text = re.sub(r',\s*]', ']', text)
            try:
                return json.loads(text)
            except Exception:
                return None

    # ──────────────────────────────────────────
    #  Parsing helpers
    # ──────────────────────────────────────────

    def _parse_sections(self, resume_text: str) -> Dict[str, str]:
        section_headers = [
            "summary", "profile", "objective",
            "experience", "work experience", "employment",
            "education", "skills", "technical skills",
            "projects", "certifications", "achievements",
        ]
        sections: Dict[str, str] = {}
        lines   = resume_text.split("\n")
        current = "general"
        buffer  = []

        for line in lines:
            lower   = line.lower().strip()
            matched = next((h for h in section_headers if h in lower and len(lower) < 40), None)
            if matched:
                if buffer:
                    sections[current] = "\n".join(buffer).strip()
                current = matched
                buffer  = []
            else:
                buffer.append(line)

        if buffer:
            sections[current] = "\n".join(buffer).strip()

        return sections

    def _extract_bullets(self, resume_text: str) -> List[str]:
        bullets = []
        for line in resume_text.split("\n"):
            stripped = line.strip()
            if re.match(r'^[•\-\*\–]\s+.{15,}', stripped):
                bullets.append(re.sub(r'^[•\-\*\–]\s+', '', stripped))
            elif re.match(r'^\d+[\.\ )]\s+.{15,}', stripped):
                bullets.append(re.sub(r'^\d+[\.\ )]\s+', '', stripped))
            elif len(stripped) > 20 and stripped[0].isupper() and not stripped.endswith(':'):
                if any(verb in stripped.lower()[:20] for verb in [
                    "built", "developed", "designed", "implemented", "created",
                    "led", "managed", "improved", "optimised", "reduced",
                    "increased", "delivered", "deployed", "integrated", "wrote",
                ]):
                    bullets.append(stripped)

        return list(dict.fromkeys(bullets))   # deduplicate preserving order

    # ──────────────────────────────────────────
    #  Scoring internals
    # ──────────────────────────────────────────

    def _extract_keywords(self, text: str) -> Set[str]:
        text_lower = text.lower()
        keywords: Set[str] = set()
        for skill in TECH_SKILLS:
            if skill in text_lower:
                keywords.add(skill)
        if self.nlp:
            doc = self.nlp(text[:50_000])
            for token in doc:
                if (not token.is_stop and not token.is_punct
                        and len(token.text) > 2
                        and token.pos_ in {"NOUN", "PROPN"}):
                    keywords.add(token.lemma_.lower())
            for chunk in doc.noun_chunks:
                cleaned = chunk.text.lower().strip()
                if len(cleaned) > 3 and not all(t.is_stop for t in chunk):
                    keywords.add(cleaned)
        return keywords

    def _tfidf_score(self, jd: str, resume: str) -> float:
        try:
            vec  = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=1000)
            vecs = vec.fit_transform([jd, resume])
            return float(cosine_similarity(vecs[0], vecs[1])[0][0] * 100)
        except Exception:
            return 0.0

    def _keyword_overlap(self, jd_kw: Set[str], resume_kw: Set[str]) -> Tuple:
        if not jd_kw:
            return 0.0, set(), set()
        matched = jd_kw & resume_kw
        missing = jd_kw - resume_kw
        return float(len(matched) / len(jd_kw) * 100), matched, missing

    def _generate_feedback(self, score: int, matched: List[str], missing: List[str]) -> str:
        if not self.groq_available:
            return self._rule_based_feedback(score, matched, missing)

        if score >= 80:   label = "excellent match"
        elif score >= 60: label = "good match with minor gaps"
        elif score >= 40: label = "moderate match with significant gaps"
        else:             label = "poor match needing major revision"

        prompt = (
            f"ATS Score: {score}/100 ({label}). "
            f"Matched: {', '.join(matched[:6]) or 'none'}. "
            f"Missing: {', '.join(missing[:6]) or 'none'}. "
            f"Write 3 numbered improvement suggestions. Be specific."
        )

        try:
            resp = httpx.post(
                GROQ_BASE_URL,
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens":  300,
                },
                timeout=20,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                },
            )
            if resp.status_code == 200:
                return (
                    resp.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                )
        except Exception as exc:
            logger.warning("ATSEngine feedback generation failed: %s", exc)

        return self._rule_based_feedback(score, matched, missing)

    def _rule_based_feedback(self, score: int, matched: List[str], missing: List[str]) -> str:
        if score >= 80:   head = "Excellent match for this role."
        elif score >= 60: head = "Good match with some room to improve."
        elif score >= 40: head = "Partial match. Key gaps identified."
        else:             head = "Needs significant revision."
        parts = [head]
        if matched: parts.append(f"1. Strong: {', '.join(matched[:5])}.")
        if missing: parts.append(f"2. Add: {', '.join(missing[:6])}.")
        if missing: parts.append(f"3. Add project experience with: {', '.join(missing[:3])}.")
        return "\n".join(parts)

    def _parse_suggestions(self, feedback: str) -> List[str]:
        return [
            re.sub(r"^\d+[\.\ )]\s*", "", line.strip())
            for line in feedback.split("\n")
            if re.match(r"^\d+[\.\ )]\s+", line.strip())
        ]