import re


class CompressorV2:
    """
    Deterministic semantic compressor for Hermes.
    Goal: reduce token load before LLM inference.
    """


    FILLERS = [
        "very", "really", "actually", "basically",
        "just", "quite", "simply", "please", "could you", "would you"
    ]


    def compress(self, text: str) -> dict:
        text = self._normalize(text)
        text = self._remove_fillers(text)


        task_type = self._classify(text)


        entities = self._extract_entities(text)
        constraints = self._extract_constraints(text)


        goal = self._extract_goal(text)


        return {
            "task_type": task_type,
            "goal": goal,
            "entities": entities,
            "constraints": constraints,
            "compressed_prompt": self._final_pack(task_type, goal, entities, constraints)
        }


    # ---------------- CORE PIPELINE ----------------


    def _normalize(self, text):
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text


    def _remove_fillers(self, text):
        for f in self.FILLERS:
            text = text.replace(f, "")
        return text


    def _classify(self, text):
        t = text.lower()


        if "image" in t:
            return "vision"
        if any(k in t for k in ["code", "function", "script", "bug"]):
            return "coding"
        if any(k in t for k in ["plan", "design", "build", "architecture"]):
            return "text_reasoning"
        if any(k in t for k in ["memory", "store", "remember"]):
            return "memory"
        if any(k in t for k in ["search", "find", "retrieve"]):
            return "retrieval"
        if any(k in t for k in ["auto", "automation"]):
            return "automation"


        return "text_reasoning"


    def _extract_goal(self, text):
        # aggressive compression: keep only verb-object core
        words = text.split()


        # remove weak words
        filtered = [
            w for w in words
            if w.lower() not in self.FILLERS
        ]


        return " ".join(filtered)[:200]


    def _extract_entities(self, text):
        # lightweight heuristic entity extraction
        caps = re.findall(r"\b[A-Z][a-zA-Z0-9_\-]+\b", text)
        return list(set(caps))[:10]


    def _extract_constraints(self, text):
        constraints = []


        keywords = {
            "fast": "low_latency",
            "cheap": "low_cost",
            "local": "local_only",
            "cloud": "cloud_allowed",
            "secure": "secure_execution",
            "minimal": "minimal_output"
        }


        t = text.lower()


        for k, v in keywords.items():
            if k in t:
                constraints.append(v)


        return constraints


    def _final_pack(self, task_type, goal, entities, constraints):
        """
        THIS is the real token saver:
        converts natural language → ultra-compact execution packet
        """


        return f"""
T:{task_type}
G:{goal}
E:{",".join(entities[:5])}
C:{",".join(constraints[:5])}
""".strip()




# singleton
compressor = CompressorV2()


def compress(text: str):
    return compressor.compress(text)