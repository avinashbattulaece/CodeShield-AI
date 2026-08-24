from difflib import SequenceMatcher
import ast
import re

from utils.preprocess import normalize_python, normalize_generic

def _is_python(code):
    try:
        ast.parse(code)
        return True
    except Exception:
        return False

def _structural_tokens(code):
    if _is_python(code):
        try:
            tree = ast.parse(code)
            tokens = []

            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp):
                    tokens.append(type(node.op).__name__)
                elif isinstance(node, ast.BoolOp):
                    tokens.append(type(node.op).__name__)
                elif isinstance(node, ast.Compare):
                    tokens.extend(type(op).__name__ for op in node.ops)
                elif isinstance(node, ast.Call):
                    tokens.append("CALL")
                elif isinstance(node, (ast.For, ast.While)):
                    tokens.append(type(node).__name__)
                elif isinstance(node, ast.If):
                    tokens.append("IF")
                elif isinstance(node, ast.Return):
                    tokens.append("RETURN")
                elif isinstance(node, ast.FunctionDef):
                    tokens.append("FUNCTION")
            return tokens
        except Exception:
            pass

    return re.findall(r"[+\-*/%]|==|!=|<=|>=|&&|\|\||\b(?:if|for|while|return|function|class)\b", code)

def _sequence_score(a, b):
    return SequenceMatcher(None, a, b).ratio() * 100

def _jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 100.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb) * 100

def get_similar_lines(code1, code2, minimum=0.88):
    lines1 = [line.rstrip() for line in code1.splitlines() if line.strip()]
    lines2 = [line.rstrip() for line in code2.splitlines() if line.strip()]
    pairs = []

    for line1 in lines1:
        best = None
        best_score = 0
        for line2 in lines2:
            score = SequenceMatcher(None, line1.strip(), line2.strip()).ratio()
            if score > best_score:
                best_score = score
                best = line2

        if best is not None and best_score >= minimum:
            pairs.append({
                "student1": line1,
                "student2": best,
                "similarity": round(best_score * 100, 2)
            })

    return pairs

def analyze_pair(code1, code2):
    norm1 = normalize_python(code1) if _is_python(code1) else normalize_generic(code1)
    norm2 = normalize_python(code2) if _is_python(code2) else normalize_generic(code2)

    structural1 = _structural_tokens(code1)
    structural2 = _structural_tokens(code2)

    raw_score = _sequence_score(code1, code2)
    normalized_score = _sequence_score(norm1, norm2)
    structural_score = _jaccard(structural1, structural2)

    # Structure matters most. This prevents addition and multiplication
    # from becoming a high-risk match merely because their layout is similar.
    if structural_score < 45:
        similarity = min(45.0, 0.30 * raw_score + 0.35 * normalized_score + 0.35 * structural_score)
    else:
        similarity = 0.15 * raw_score + 0.55 * normalized_score + 0.30 * structural_score

    similarity = round(max(0.0, min(100.0, similarity)), 2)

    matched_blocks = get_similar_lines(code1, code2, minimum=0.90)

    if similarity >= 80:
        explanation = "Very strong structural and normalized-code similarity detected."
    elif similarity >= 60:
        explanation = "Meaningful structural similarity detected. Manual review is recommended."
    elif similarity >= 40:
        explanation = "Some common programming structure is present, but evidence is moderate."
    else:
        explanation = "Low similarity. No strong plagiarism pattern was detected."

    return {
        "similarity": similarity,
        "matched_blocks": matched_blocks,
        "explanation": explanation,
        "code1": code1,
        "code2": code2,
        "raw_score": round(raw_score, 2),
        "normalized_score": round(normalized_score, 2),
        "structural_score": round(structural_score, 2),
    }

def calculate_similarity(code1, code2):
    return analyze_pair(code1, code2)["similarity"]

def get_status(similarity, high_threshold=60):
    if similarity >= high_threshold:
        return "HIGH RISK"
    if similarity >= max(1, high_threshold - 20):
        return "MEDIUM RISK"
    return "LOW RISK"
