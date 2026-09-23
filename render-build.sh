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
