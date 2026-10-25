"""Local DistilBERT inference; loading never downloads or substitutes a model."""

import logging
import os
from functools import lru_cache

from decisioniq.config import configured_path
from decisioniq.errors import ModelUnavailable

logger = logging.getLogger(__name__)
MAX_TOKENS = 256


@lru_cache(maxsize=1)
def _load_bundle():
    path = configured_path("PHISHING_MODEL_PATH", "services/phishing/models/phishing_distilbert")
    if not path.is_dir():
        raise ModelUnavailable(
            "Phishing model is missing. Supply the trained model and tokenizer at "
            "PHISHING_MODEL_PATH; see README.md."
        )
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        # Bound native CPU parallelism inside FastAPI's worker pool.
        threads = int(os.getenv("PHISHING_TORCH_THREADS", "1"))
        if threads < 1:
            raise ValueError("PHISHING_TORCH_THREADS must be positive")
        torch.set_num_threads(threads)

        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        # DistilBERT's small CPU requests use eager attention consistently across
        # platforms, avoiding the fused SDPA backend's worker-thread restrictions.
        model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True, attn_implementation="eager"
        )
        if model.config.num_labels != 2:
            raise ValueError("Expected labels 0=legitimate, 1=phishing")
        model.eval()
        return tokenizer, model
    except ImportError as exc:
        raise ModelUnavailable(
            "Install phishing dependencies with: uv sync --extra phishing"
        ) from exc
    except Exception as exc:
        logger.exception("Cannot load phishing model")
        raise ModelUnavailable("Phishing model or tokenizer could not be loaded.") from exc


def detect_phishing(text: str) -> dict:
    tokenizer, model = _load_bundle()
    import torch

    token_count = len(tokenizer(text, truncation=False)["input_ids"])
    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=MAX_TOKENS
    )
    with torch.inference_mode():
        probability = float(torch.softmax(model(**inputs).logits, dim=-1)[0][1].item())
    is_phishing = probability >= 0.5
    return {
        "is_phishing": is_phishing,
        "confidence": round(probability if is_phishing else 1 - probability, 6),
        "phishing_probability": round(probability, 6),
        "risk_score": round(probability * 100),
        "truncated": token_count > MAX_TOKENS,
    }
