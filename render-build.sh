#!/usr/bin/env bash
# Render build script for the VeriFact FastAPI backend.
# Configure in Render as: Build Command = ./render-build.sh
# (Start Command = uvicorn backend.main:app --host 0.0.0.0 --port $PORT)
set -euo pipefail

pip install -r requirements.txt

# en_core_web_sm is a spaCy model package, not a regular pip dependency.
# backend/claim/entity_extractor.py calls spacy.load("en_core_web_sm") and
# silently degrades to spacy.blank("en") without it, so install it explicitly.
python -m spacy download en_core_web_sm

# WordNet corpora for backend/verification/lexical_expansion.py (verb-sense
# synonym/hypernym expansion). Downloaded here at build time — never at
# request time — so first requests stay fast and network-independent.
python -m nltk.downloader -q -e wordnet omw-1.4

# The NLTK CLI exits 0 even when downloads fail (it only stops at the first
# error with -e), so verify explicitly: missing corpora would otherwise deploy
# green and silently degrade lexical expansion in production. Under set -e,
# this assertion fails the whole build loudly instead.
python -c "
from nltk.corpus import wordnet as wn
from nltk.data import find
count = len(wn.synsets('test', pos=wn.VERB))
assert count > 0, 'FATAL: wordnet corpus missing after download step'
find('corpora/omw-1.4.zip')
print(f'NLTK corpora OK: wordnet ({count} probe synsets) + omw-1.4 present')
"
