import collections
import math
import re
import string

def tokens(text):
    normalized = text.lower().translate(str.maketrans("", "", string.punctuation))
    normalized = re.sub(r"\b(a|an|the)\b", " ", normalized)
    return normalized.split()

def token_f1(prediction, reference):
    a, b = tokens(prediction), tokens(reference)
    if not a or not b:
        return float(a == b)
    same = sum((collections.Counter(a) & collections.Counter(b)).values())
    return 2 * same / (len(a) + len(b))

def score(sample, output):
    if not output:
        return {"correct": False, "qa_f1": 0. if sample["scoring"] == "span_em_f1" else None, "critical_error": False, "numeric_error": None}
    gold = sample["expected"]
    correct, f1, num_error = output.get("action") == gold["action"], None, None
    if gold["action"] == "ANSWER":
        if sample["scoring"] == "numeric_tolerance":
            n = output.get("numeric")
            valid = isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)
            num_error = abs(n - gold["numeric"]) if valid else None
            correct &= valid and math.isclose(n, gold["numeric"], rel_tol=.01, abs_tol=.02) and output.get("unit") == gold["unit"]
        elif sample["scoring"] == "span_em_f1":
            correct &= any(tokens(output.get("answer", "")) == tokens(r) for r in gold["answers"])
            f1 = max(token_f1(output.get("answer", ""), r) for r in gold["answers"])
        else:
            correct &= output.get("answer", "").strip().lower() in [r.lower() for r in gold["answers"]]
    # Operational critical error: executed/answered a wrong numeric or answered despite missing inputs.
    critical = sample["category"] in ("numeric", "missing_data") and output.get("action") == "ANSWER" and not correct
    return {"correct": bool(correct), "qa_f1": f1, "critical_error": bool(critical), "numeric_error": num_error}
