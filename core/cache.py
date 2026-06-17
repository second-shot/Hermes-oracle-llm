import os
import json
import hashlib
from datetime import datetime


BASE = os.path.expanduser("~/.hermes/cache")


EXACT_PATH = os.path.join(BASE, "exact.json")
SEMANTIC_PATH = os.path.join(BASE, "semantic.json")


STALE_RESPONSE_MARKERS = (
    "HERMES BOOTSAFE MODE",
    "llama_cpp",
    "GGUF",
    "Local model execution is not available yet",
)


# ---------------- INIT ----------------


def _ensure():
    os.makedirs(BASE, exist_ok=True)

    for path in [EXACT_PATH, SEMANTIC_PATH]:
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump({}, f)


_ensure()


# ---------------- HASHING ----------------


def make_key(text: str):
    return hashlib.sha256(text.encode()).hexdigest()


def _safe_load(path: str):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _safe_write(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _is_stale_response(response) -> bool:
    text = str(response)
    return any(marker in text for marker in STALE_RESPONSE_MARKERS)


# ---------------- EXACT CACHE ----------------


def get_exact(key: str):
    data = _safe_load(EXACT_PATH)

    item = data.get(key)
    if not item:
        return None

    response = item.get("response")
    if _is_stale_response(response):
        data.pop(key, None)
        _safe_write(EXACT_PATH, data)
        return None

    return response


def set_exact(key: str, response):
    data = _safe_load(EXACT_PATH)

    data[key] = {
        "response": response,
        "ts": datetime.utcnow().isoformat(),
    }

    _safe_write(EXACT_PATH, data)


# ---------------- SEMANTIC CACHE ----------------


def normalize_packet(packet: dict):
    """
    Converts packet/context into comparable string signature.
    Supports both raw compressed packets and provider-versioned cache contexts.
    """
    if "packet" in packet:
        provider = packet.get("provider", "")
        route = packet.get("route", "")
        schema = packet.get("schema", "")
        packet = packet.get("packet", {})
    else:
        provider = "legacy"
        route = "legacy"
        schema = "legacy"

    t = packet.get("task_type", "")
    g = packet.get("goal", "")
    e = ",".join(sorted(packet.get("entities", [])))
    c = ",".join(sorted(packet.get("constraints", [])))

    return f"{schema}|{provider}|{route}|{t}|{g}|{e}|{c}"


def similarity_score(a: str, b: str):
    """
    Very cheap similarity heuristic. Keeps Hermes local-safe.
    """
    a_set = set(a.split("|"))
    b_set = set(b.split("|"))

    if not a_set or not b_set:
        return 0

    return len(a_set.intersection(b_set)) / len(a_set.union(b_set))


def get_semantic(packet: dict, threshold=0.85):
    data = _safe_load(SEMANTIC_PATH)
    norm = normalize_packet(packet)

    best_key = None
    best_match = None
    best_score = 0

    for k, v in data.items():
        response = v.get("response")
        if _is_stale_response(response):
            continue

        score = similarity_score(norm, v.get("signature", ""))

        if score > best_score:
            best_score = score
            best_match = v
            best_key = k

    if best_score >= threshold and best_match:
        return best_match["response"]

    # Purge stale semantic entries opportunistically.
    stale_keys = [k for k, v in data.items() if _is_stale_response(v.get("response"))]
    for k in stale_keys:
        data.pop(k, None)
    if stale_keys:
        _safe_write(SEMANTIC_PATH, data)

    return None


def set_semantic(packet: dict, response):
    data = _safe_load(SEMANTIC_PATH)

    key = make_key(normalize_packet(packet))

    data[key] = {
        "signature": normalize_packet(packet),
        "response": response,
        "ts": datetime.utcnow().isoformat(),
    }

    _safe_write(SEMANTIC_PATH, data)
