from typing import Any, Union
from backend.ingestion.errors import IngestionError
from backend.ingestion.models import NormalizedArticle
from backend.ingestion.text_processor import process_text_input
from backend.ingestion.url_extractor import extract_article_from_url
from backend.logging_config import logger


def ingest_input(input_type: Union[str, Any], content: str) -> NormalizedArticle:
    """Ingest user input (raw text or URL) and return a NormalizedArticle."""
    val = input_type.value if hasattr(input_type, "value") else str(input_type).lower()
    logger.info("Ingesting user input of type '%s'", val)

    if val == "text":
        return process_text_input(content)
    elif val == "url":
        return extract_article_from_url(content)
    else:
        raise IngestionError(f"Unsupported input type '{val}'.")

