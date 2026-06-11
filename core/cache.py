import os
import json
import hashlib
from datetime import datetime, timedelta


BASE = os.path.expanduser("~/.hermes/cache")


EXACT_PATH = os.path.join(BASE, "exact.json")
SEMANTIC_PATH = os.path.join(BASE, "semantic.json")


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




# ---------------- EXACT CACHE ----------------


def get_exact(key: str):
    with open(EXACT_PATH, "r") as f:
        data = json.load(f)


    item = data.get(key)
    if not item:
        return None


    return item["response"]




def set_exact(key: str, response):
    with open(EXACT_PATH, "r") as f:
        data = json.load(f)


    data[key] = {
        "response": response,
        "ts": datetime.utcnow().isoformat()
    }


    with open(EXACT_PATH, "w") as f:
        json.dump(data, f, indent=2)




# ---------------- SEMANTIC CACHE ----------------


def normalize_packet(packet: dict):
    """
    Converts T/G/E/C into comparable string signature
    """
    t = packet.get("task_type", "")
    g = packet.get("goal", "")
    e = ",".join(sorted(packet.get("entities", [])))
    c = ",".join(sorted(packet.get("constraints", [])))


    return f"{t}|{g}|{e}|{c}"




def similarity_score(a: str, b: str):
    """
    Very cheap similarity heuristic (no embeddings for M1 safety)
    """
    a_set = set(a.split("|"))
    b_set = set(b.split("|"))


    if not a_set or not b_set:
        return 0


    return len(a_set.intersection(b_set)) / len(a_set.union(b_set))




def get_semantic(packet: dict, threshold=0.85):
    with open(SEMANTIC_PATH, "r") as f:
        data = json.load(f)


    norm = normalize_packet(packet)


    best_match = None
    best_score = 0


    for k, v in data.items():
        score = similarity_score(norm, v["signature"])


        if score > best_score:
            best_score = score
            best_match = v


    if best_score >= threshold:
        return best_match["response"]


    return None




def set_semantic(packet: dict, response):
    with open(SEMANTIC_PATH, "r") as f:
        data = json.load(f)


    key = make_key(normalize_packet(packet))


    data[key] = {
        "signature": normalize_packet(packet),
        "response": response,
        "ts": datetime.utcnow().isoformat()
    }


    with open(SEMANTIC_PATH, "w") as f:
        json.dump(data, f, indent=2)