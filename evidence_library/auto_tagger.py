"""
Auto-tag extraction for Evidence Library records.
Extracts drug names, conditions, study types, mechanisms without API calls.
"""

import re
from typing import set

# Common clinical terms — add to these as your library grows
DRUG_NAMES = {
    "naltrexone", "ldn", "low-dose naltrexone",
    "aspirin", "ibuprofen", "acetaminophen",
    "metformin", "lisinopril", "atorvastatin",
}

CONDITIONS = {
    "fibromyalgia", "chronic pain", "crohn's disease", "crohns disease",
    "multiple sclerosis", "ms", "rms", "rrms",
    "complex regional pain syndrome", "crps",
    "diabetes", "arthritis", "lupus", "psoriasis",
    "depression", "anxiety", "ptsd", "ocd",
}

STUDY_TYPES = {
    "randomized controlled trial", "rct",
    "randomized trial", "meta-analysis", "systematic review",
    "case study", "case series", "cohort study",
    "cross-sectional study", "observational study",
    "pilot study", "phase i", "phase ii", "phase iii", "phase iv",
}

MECHANISMS = {
    "microglia", "glial", "toll-like receptor", "tlr4",
    "opioid receptor", "endogenous opioid",
    "anti-inflammatory", "inflammatory",
    "neuropathic", "neuropathy",
    "cytokine", "neuroinflammation",
    "dopamine", "serotonin", "glutamate",
}

METRICS = {
    "efficacy", "safety", "tolerability", "adverse event",
    "side effect", "dropout rate", "remission",
    "pain reduction", "clinical improvement",
}

POPULATIONS = {
    "pediatric", "children", "adult", "elderly", "geriatric",
    "women", "men", "pregnant", "lactating",
}


def extract_auto_tags(text: str, filename: str = "") -> list[str]:
    """
    Extract relevant tags from document text without using an API.
    Returns a list of tags to add to the record.
    """
    tags = set()
    text_lower = text.lower()

    # Search for drug names
    for drug in DRUG_NAMES:
        if drug in text_lower:
            tags.add(drug.replace(" ", "-"))

    # Search for conditions
    for condition in CONDITIONS:
        if condition in text_lower:
            tags.add(condition.replace(" ", "-"))

    # Search for study types
    for stype in STUDY_TYPES:
        if stype in text_lower:
            tags.add(stype.replace(" ", "-"))

    # Search for mechanisms
    for mech in MECHANISMS:
        if mech in text_lower:
            tags.add(mech.replace(" ", "-"))

    # Search for metrics
    for metric in METRICS:
        if metric in text_lower:
            tags.add(metric.replace(" ", "-"))

    # Search for populations
    for pop in POPULATIONS:
        if pop in text_lower:
            tags.add(pop.replace(" ", "-"))

    # Extract 4-digit years (likely publication years)
    years = re.findall(r'\b(20\d{2})\b', text)
    if years:
        tags.add(f"year-{years[0]}")

    # Extract DOI or PubMed ID from filename or text
    doi_match = re.search(r'10\.\d{4,}/[\w\./-]+', text)
    if doi_match:
        tags.add("has-doi")

    pubmed_match = re.search(r'PMID:\s*(\d+)', text, re.IGNORECASE)
    if pubmed_match:
        tags.add(f"pmid-{pubmed_match.group(1)}")

    return sorted(list(tags))


def extract_citations(text: str) -> list[str]:
    """
    Extract author citations and references from text.
    Returns list of citation patterns found (e.g., "Author Year", "doi:...").
    """
    citations = []

    # Pattern: Author et al. (Year)
    author_year = re.findall(
        r'([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?)\s+(?:et\s+al\.?|&\s+colleagues)?\s*\(?(20\d{2})',
        text
    )
    for author, year in author_year:
        citations.append(f"{author} {year}")

    # Pattern: DOI
    dois = re.findall(r'(?:doi|DOI)[\s:]*([^\s,;]+)', text)
    for doi in dois:
        citations.append(f"doi:{doi}")

    # Pattern: PMID
    pmids = re.findall(r'(?:PMID|PubMed ID)[\s:]*(\d+)', text)
    for pmid in pmids:
        citations.append(f"pmid:{pmid}")

    return citations
