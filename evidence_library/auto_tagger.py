"""
Universal auto-tag extraction for Evidence Library.
Works across any content domain — no API calls, all local keyword matching.

Domains supported:
  clinical      Medical studies, trials, drugs, conditions
  tech          AI/ML, programming, software engineering
  fitness       Workouts, exercise, nutrition, training
  recipe        Food, cooking, ingredients, meal types
  tutorial      How-to guides, step-by-step instructions
  quote         Life quotes, inspiration, philosophy
  academic      Research papers, studies, methodology
  business      Finance, strategy, productivity, work
  science       Physics, chemistry, biology, earth science
"""

import re
from pathlib import Path


# ── Domain keyword dictionaries ───────────────────────────────────────────────

_CLINICAL_DRUGS = {
    "naltrexone", "ldn", "aspirin", "ibuprofen", "acetaminophen", "metformin",
    "lisinopril", "atorvastatin", "sertraline", "fluoxetine", "amoxicillin",
    "prednisone", "gabapentin", "hydrocodone", "oxycodone", "insulin",
    "warfarin", "levothyroxine", "omeprazole", "metoprolol", "amlodipine",
    "hydroxychloroquine", "naloxone", "buprenorphine", "semaglutide", "ozempic",
    "wegovy", "tirzepatide", "mounjaro",
}

_CLINICAL_CONDITIONS = {
    "fibromyalgia", "chronic pain", "crohn's disease", "multiple sclerosis",
    "complex regional pain syndrome", "crps", "diabetes", "arthritis",
    "lupus", "psoriasis", "depression", "anxiety", "ptsd", "ocd",
    "hypertension", "cancer", "alzheimer", "parkinson", "autism",
    "adhd", "bipolar", "schizophrenia", "epilepsy", "obesity",
    "cardiovascular", "stroke", "dementia", "neuropathy", "inflammation",
    "autoimmune", "rheumatoid", "osteoporosis", "asthma", "copd",
}

_CLINICAL_STUDY_TYPES = {
    "randomized controlled trial", "rct", "meta-analysis", "systematic review",
    "case study", "case series", "cohort study", "cross-sectional",
    "observational study", "pilot study", "phase i", "phase ii",
    "phase iii", "phase iv", "double blind", "placebo-controlled",
    "open label", "prospective", "retrospective", "clinical trial",
}

_CLINICAL_MECHANISMS = {
    "microglia", "glial", "toll-like receptor", "tlr4", "opioid receptor",
    "anti-inflammatory", "cytokine", "neuroinflammation", "dopamine",
    "serotonin", "glutamate", "endocannabinoid", "neuropathic",
    "biomarker", "receptor", "enzyme", "protein", "antibody",
    "immunology", "pharmacokinetics", "pharmacodynamics",
}

_CLINICAL_METRICS = {
    "efficacy", "safety", "tolerability", "adverse event", "side effect",
    "remission", "pain reduction", "clinical improvement", "dropout rate",
    "p-value", "confidence interval", "hazard ratio", "odds ratio",
    "sensitivity", "specificity", "bioavailability",
}

_CLINICAL_POPULATIONS = {
    "pediatric", "children", "adult", "elderly", "geriatric",
    "women", "men", "pregnant", "postmenopausal",
}

# ── Tech / AI / Software ──────────────────────────────────────────────────────

_TECH_AI = {
    "machine learning", "deep learning", "neural network", "transformer",
    "llm", "large language model", "gpt", "claude", "gemini", "llama",
    "embedding", "fine-tuning", "rag", "retrieval augmented",
    "diffusion model", "stable diffusion", "generative ai",
    "natural language processing", "nlp", "computer vision",
    "reinforcement learning", "supervised learning", "unsupervised learning",
    "classification", "regression", "clustering", "inference",
    "gradient descent", "backpropagation", "attention mechanism",
    "prompt engineering", "few-shot", "zero-shot", "chain of thought",
    "multimodal", "vector database", "semantic search",
}

_TECH_PROGRAMMING = {
    "python", "javascript", "typescript", "rust", "go", "java", "swift",
    "kotlin", "c++", "c#", "ruby", "php", "bash", "sql", "graphql",
    "react", "vue", "angular", "nextjs", "fastapi", "django", "flask",
    "docker", "kubernetes", "aws", "azure", "gcp", "terraform",
    "git", "github", "api", "rest", "microservice", "serverless",
    "database", "postgresql", "mongodb", "redis", "elasticsearch",
    "algorithm", "data structure", "debugging", "refactoring",
}

_TECH_TOPICS = {
    "artificial intelligence", "robotics", "blockchain", "cryptocurrency",
    "cybersecurity", "cloud computing", "devops", "agile", "scrum",
    "software architecture", "system design", "open source",
    "internet of things", "iot", "augmented reality", "virtual reality",
    "quantum computing", "edge computing", "5g", "web3",
}

_TECH_ORGS = {
    "openai", "anthropic", "google", "meta", "microsoft", "apple",
    "mit", "stanford", "berkeley", "carnegie mellon", "harvard",
    "deepmind", "hugging face", "nvidia", "tesla", "spacex",
}

# ── Fitness / Workout ─────────────────────────────────────────────────────────

_FITNESS_WORKOUTS = {
    "hiit", "cardio", "strength training", "weight lifting", "powerlifting",
    "crossfit", "yoga", "pilates", "stretching", "flexibility",
    "running", "cycling", "swimming", "rowing", "boxing", "martial arts",
    "bodyweight", "calisthenics", "resistance band", "kettlebell", "dumbbell",
    "barbell", "squat", "deadlift", "bench press", "pull up", "push up",
    "lunge", "plank", "burpee", "sprint", "interval training",
}

_FITNESS_BODY = {
    "chest", "back", "shoulders", "biceps", "triceps", "legs",
    "glutes", "hamstrings", "quadriceps", "calves", "core", "abs",
    "upper body", "lower body", "full body",
}

_FITNESS_NUTRITION = {
    "protein", "carbohydrates", "carbs", "fat", "calories", "macros",
    "meal prep", "pre-workout", "post-workout", "creatine", "whey",
    "bcaa", "supplement", "hydration", "intermittent fasting",
    "keto diet", "paleo", "vegan diet", "bulking", "cutting",
    "body fat", "muscle mass", "bmi", "metabolism",
}

_FITNESS_METRICS = {
    "reps", "sets", "rest period", "one rep max", "1rm", "volume",
    "progressive overload", "heart rate", "vo2 max", "rpe",
    "recovery", "deload", "periodization",
}

# ── Recipes / Food ────────────────────────────────────────────────────────────

_RECIPE_TYPES = {
    "breakfast", "lunch", "dinner", "snack", "dessert", "appetizer",
    "soup", "salad", "sandwich", "pasta", "pizza", "burger",
    "smoothie", "juice", "cocktail", "mocktail", "baking", "grilling",
    "slow cooker", "instant pot", "air fryer",
}

_RECIPE_CUISINE = {
    "italian", "mexican", "chinese", "japanese", "indian", "thai",
    "french", "mediterranean", "greek", "american", "korean",
    "vietnamese", "middle eastern", "spanish", "bbq",
}

_RECIPE_DIETARY = {
    "vegan", "vegetarian", "gluten-free", "dairy-free", "keto",
    "paleo", "whole30", "low-carb", "low-fat", "sugar-free",
    "nut-free", "halal", "kosher",
}

_RECIPE_COOKING = {
    "ingredient", "recipe", "tablespoon", "teaspoon", "cup", "ounce",
    "preheat", "oven", "bake", "roast", "sauté", "boil", "simmer",
    "chop", "dice", "mince", "whisk", "marinate", "season",
    "serves", "yield", "prep time", "cook time",
}

# ── Tutorials / How-To ────────────────────────────────────────────────────────

_TUTORIAL_KEYWORDS = {
    "how to", "step by step", "tutorial", "guide", "instructions",
    "walkthrough", "setup", "install", "configure", "deploy",
    "getting started", "beginner", "advanced", "tips", "tricks",
    "best practices", "quick start", "cheat sheet", "reference",
    "example", "demo", "learn", "course", "lesson",
}

# ── Life / Quotes / Inspiration ───────────────────────────────────────────────

_QUOTE_KEYWORDS = {
    "quote", "said", "wisdom", "motivation", "inspiration",
    "mindset", "success", "failure", "leadership", "courage",
    "gratitude", "happiness", "purpose", "growth", "resilience",
    "stoic", "stoicism", "philosophy", "meditation", "mindfulness",
    "habit", "discipline", "focus", "goals", "vision",
}

# ── Academic / Research ───────────────────────────────────────────────────────

_ACADEMIC_KEYWORDS = {
    "abstract", "introduction", "methodology", "results", "discussion",
    "conclusion", "references", "bibliography", "doi", "journal",
    "peer-reviewed", "hypothesis", "experiment", "data analysis",
    "statistical significance", "sample size", "literature review",
    "theoretical framework", "qualitative", "quantitative",
    "university", "institute", "laboratory", "research",
}

# ── Business / Productivity ───────────────────────────────────────────────────

_BUSINESS_KEYWORDS = {
    "strategy", "revenue", "profit", "roi", "kpi", "okr",
    "startup", "entrepreneur", "venture capital", "funding",
    "product management", "project management", "agile", "scrum",
    "marketing", "sales", "customer", "retention", "churn",
    "productivity", "workflow", "automation", "delegation",
    "leadership", "management", "team", "hiring", "culture",
    "finance", "budget", "investment", "portfolio",
}

# ── Science (non-clinical) ────────────────────────────────────────────────────

_SCIENCE_KEYWORDS = {
    "physics", "chemistry", "biology", "astronomy", "geology",
    "climate", "environment", "ecology", "evolution", "genetics",
    "neuroscience", "quantum", "particle", "thermodynamics",
    "hypothesis", "experiment", "peer review", "observation",
    "satellite", "telescope", "microscope", "laboratory",
    "atmosphere", "oceanography", "seismic", "tectonic",
}

# ── Domain detection ──────────────────────────────────────────────────────────

_DOMAIN_SIGNALS = {
    "clinical":    _CLINICAL_CONDITIONS | _CLINICAL_STUDY_TYPES | _CLINICAL_DRUGS,
    "tech":        _TECH_AI | _TECH_PROGRAMMING | _TECH_TOPICS,
    "fitness":     _FITNESS_WORKOUTS | _FITNESS_NUTRITION | _FITNESS_METRICS,
    "recipe":      _RECIPE_COOKING | _RECIPE_TYPES,
    "tutorial":    _TUTORIAL_KEYWORDS,
    "quote":       _QUOTE_KEYWORDS,
    "academic":    _ACADEMIC_KEYWORDS,
    "business":    _BUSINESS_KEYWORDS,
    "science":     _SCIENCE_KEYWORDS,
}


def detect_domain(text_lower: str) -> str:
    """Detect primary content domain by keyword density in first 1500 chars."""
    head = text_lower[:1500]
    scores = {}
    for domain, keywords in _DOMAIN_SIGNALS.items():
        scores[domain] = sum(1 for kw in keywords if kw in head)
    top = max(scores, key=scores.get)
    return top if scores[top] > 0 else "general"


def extract_auto_tags(text: str, filename: str = "") -> list[str]:
    """
    Extract relevant tags from document text without using an API.
    Works across clinical, tech, fitness, recipe, tutorial, quote, and academic content.
    Returns a sorted list of tags to merge into the record.
    """
    tags = set()
    text_lower = text.lower()
    head = text_lower[:2000]

    # ── Detect and tag domain ──────────────────────────────────────────────
    domain = detect_domain(text_lower)
    tags.add(f"domain-{domain}")

    # ── Clinical tags ──────────────────────────────────────────────────────
    if domain in ("clinical", "academic", "science"):
        for kw_set, prefix in [
            (_CLINICAL_DRUGS,        None),
            (_CLINICAL_CONDITIONS,   None),
            (_CLINICAL_STUDY_TYPES,  None),
            (_CLINICAL_MECHANISMS,   None),
            (_CLINICAL_METRICS,      None),
            (_CLINICAL_POPULATIONS,  None),
        ]:
            for kw in kw_set:
                if kw in text_lower:
                    tags.add(kw.replace(" ", "-"))

    # ── Tech tags ──────────────────────────────────────────────────────────
    if domain in ("tech", "academic", "tutorial"):
        for kw_set in (_TECH_AI, _TECH_PROGRAMMING, _TECH_TOPICS, _TECH_ORGS):
            for kw in kw_set:
                if kw in head:
                    tags.add(kw.replace(" ", "-"))

    # ── Fitness tags ───────────────────────────────────────────────────────
    if domain == "fitness":
        for kw_set in (_FITNESS_WORKOUTS, _FITNESS_BODY, _FITNESS_NUTRITION, _FITNESS_METRICS):
            for kw in kw_set:
                if kw in text_lower:
                    tags.add(kw.replace(" ", "-"))

    # ── Recipe tags ────────────────────────────────────────────────────────
    if domain == "recipe":
        for kw_set in (_RECIPE_TYPES, _RECIPE_CUISINE, _RECIPE_DIETARY, _RECIPE_COOKING):
            for kw in kw_set:
                if kw in text_lower:
                    tags.add(kw.replace(" ", "-"))

    # ── Tutorial tags ──────────────────────────────────────────────────────
    if domain == "tutorial":
        for kw in _TUTORIAL_KEYWORDS:
            if kw in head:
                tags.add(kw.replace(" ", "-"))

    # ── Quote / life tags ──────────────────────────────────────────────────
    if domain == "quote":
        for kw in _QUOTE_KEYWORDS:
            if kw in text_lower:
                tags.add(kw.replace(" ", "-"))

    # ── Business tags ──────────────────────────────────────────────────────
    if domain == "business":
        for kw in _BUSINESS_KEYWORDS:
            if kw in head:
                tags.add(kw.replace(" ", "-"))

    # ── Science tags ───────────────────────────────────────────────────────
    if domain == "science":
        for kw in _SCIENCE_KEYWORDS:
            if kw in head:
                tags.add(kw.replace(" ", "-"))

    # ── Universal tags (apply to all domains) ─────────────────────────────

    # Publication year
    years = re.findall(r'\b(20\d{2}|19\d{2})\b', text)
    if years:
        tags.add(f"year-{years[0]}")

    # DOI present
    if re.search(r'10\.\d{4,}/[\w\./-]+', text):
        tags.add("has-doi")

    # PubMed ID
    pmid = re.search(r'PMID[\s:]+(\d+)', text, re.IGNORECASE)
    if pmid:
        tags.add(f"pmid-{pmid.group(1)}")

    # arXiv ID
    arxiv = re.search(r'arXiv[\s:]+(\d{4}\.\d{4,5})', text, re.IGNORECASE)
    if arxiv:
        tags.add("arxiv")
        tags.add(f"year-{arxiv.group(1)[:4]}")

    # File type tag from filename
    if filename:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix in {"pdf", "docx", "xlsx", "pptx", "csv", "html"}:
            tags.add(f"format-{suffix}")

    # Clean up: remove very short tags and normalize
    tags = {t.strip("-").replace("'", "").replace(" ", "-") for t in tags if len(t.strip()) > 1}

    return sorted(list(tags))


def extract_citations(text: str) -> list[str]:
    """Extract author citations and DOIs/PMIDs from text."""
    citations = []

    author_year = re.findall(
        r'([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?)\s*(?:et\s+al\.?)?\s*\(?(20\d{2}|19\d{2})',
        text
    )
    for author, year in author_year[:10]:
        citations.append(f"{author.strip()} {year}")

    for doi in re.findall(r'(?:doi|DOI)[\s:]*([^\s,;]+)', text):
        citations.append(f"doi:{doi}")

    for pmid in re.findall(r'(?:PMID|PubMed ID)[\s:]*(\d+)', text):
        citations.append(f"pmid:{pmid}")

    return citations
