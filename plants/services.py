import base64
import requests
from django.conf import settings

_classifier = None


def identify(path):
    """BioCLIP: top-3 species predictions."""
    global _classifier
    from bioclip import TreeOfLifeClassifier, Rank
    if _classifier is None:
        _classifier = TreeOfLifeClassifier()  # loads once; slow the first time
    preds = _classifier.predict(path, Rank.SPECIES)[:3]
    out = []
    for p in preds:
        out.append({
            "name": p.get("common_name") or p.get("species", "?"),
            "species": p.get("species", ""),
            "score": round(float(p.get("score", 0)), 3),
        })
    return out


def diagnose(path, species):
    """Local Ollama vision model: describes the plant's condition and gives advice."""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    prompt = (
        f"You are a houseplant and garden care expert. The plant in the photo looks like: {species}. "
        "Briefly describe the plant's condition (leaves, color, signs of disease or pests), "
        "then give 3-4 concrete care tips (watering, light, soil, fertilizer). "
        "Be concise. At the end, state your confidence: low, medium or high."
    )
    r = requests.post(settings.OLLAMA_URL, json={
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
    }, timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"]
