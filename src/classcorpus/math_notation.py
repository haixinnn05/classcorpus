from __future__ import annotations

import re

_MATRIX_ENVIRONMENT = re.compile(
    r"\\begin\{(?P<kind>matrix|bmatrix|Bmatrix|pmatrix|vmatrix|Vmatrix)\}"
    r"(?P<body>.*?)"
    r"\\end\{(?P=kind)\}",
    re.DOTALL,
)
_BRACKET_MATRIX = re.compile(
    r"\[\s*"
    r"(?P<rows>\[[^\[\]]*\](?:\s*,\s*\[[^\[\]]*\])*)"
    r"\s*\]"
)
_TRANSPOSED_VECTOR = re.compile(
    r"\[([^\[\]]+)\]\s*(?:\^\{T\}|\^T)"
)
_CITATION = re.compile(
    r"^\[[^,\]]+,\s*[^,\]]+,\s*(?:Page|Pages|Slide|Slides)\b"
)
_DISPLAY_COMMAND = re.compile(
    r"\\(?:frac|sum|int|sqrt|lim|prod|vec|begin\{[bBpPvV]?matrix\})"
)
_RELATION = re.compile(r"(?<![<>=!])=(?!=)|!=|<=|>=|\\(?:le|ge|ne)\b")
_FUNCTION_NAMES = (
    "det",
    "diag",
    "span",
    "rank",
    "nullity",
    "Null",
    "Col",
    "sin",
    "cos",
    "tan",
    "log",
    "ln",
    "exp",
    "dim",
)
_GREEK_NAMES = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "theta",
    "lambda",
    "mu",
    "pi",
    "rho",
    "sigma",
    "tau",
    "phi",
    "omega",
    "Delta",
    "Gamma",
    "Lambda",
    "Sigma",
    "Phi",
    "Omega",
)
_INLINE_GREEK_SYMBOLS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "phi": "φ",
    "omega": "ω",
    "Delta": "Δ",
    "Gamma": "Γ",
    "Lambda": "Λ",
    "Sigma": "Σ",
    "Phi": "Φ",
    "Omega": "Ω",
}


def group_math_lines(lines: list[str]) -> list[str]:
    """Keep multiline LaTeX matrix environments in one rendered expression."""
    grouped: list[str] = []
    pending: list[str] = []
    environment_depth = 0

    for raw_line in lines:
        line = raw_line.strip()
        begins = len(re.findall(r"\\begin\{[bBpPvV]?matrix\}", line))
        ends = len(re.findall(r"\\end\{[bBpPvV]?matrix\}", line))

        if environment_depth or begins:
            pending.append(line)
            environment_depth += begins - ends
            if environment_depth <= 0:
                grouped.append(" ".join(pending))
                pending.clear()
                environment_depth = 0
            continue

        grouped.append(line)

    if pending:
        grouped.append(" ".join(pending))
    return grouped


def normalize_math_expression(text: str) -> str:
    """Convert common agent-written math into Matplotlib MathText notation."""
    value = text.strip().replace("−", "-").replace("…", r"\cdots")
    value = _MATRIX_ENVIRONMENT.sub(_replace_latex_matrix, value)
    value = _BRACKET_MATRIX.sub(_replace_bracket_matrix, value)
    value = _TRANSPOSED_VECTOR.sub(_replace_transposed_vector, value)

    value = value.replace("!=", r"\ne ")
    value = value.replace("<=", r"\le ")
    value = value.replace(">=", r"\ge ")
    value = re.sub(r"sqrt\(([^()]*)\)", r"\\sqrt{\1}", value)
    value = re.sub(
        r"\(([^()]+)\)\s*/\s*\(([^()]+)\)",
        r"\\frac{\1}{\2}",
        value,
    )
    for name in _FUNCTION_NAMES:
        value = re.sub(
            rf"(?<![\\A-Za-z]){name}(?![A-Za-z])",
            rf"\\mathrm{{{name}}}",
            value,
        )
    for name in _GREEK_NAMES:
        value = re.sub(
            rf"(?<![\\A-Za-z]){name}(?![A-Za-z])",
            rf"\\{name}",
            value,
        )
    return value


def normalize_inline_math(text: str) -> str:
    """Convert common inline LaTeX into compact Unicode-friendly notation."""
    value = text
    for name, symbol in _INLINE_GREEK_SYMBOLS.items():
        value = re.sub(
            rf"\\{name}(?![A-Za-z])|(?<![A-Za-z\\]){name}(?![A-Za-z])",
            symbol,
            value,
        )
    value = (
        value.replace("!=", "≠")
        .replace("&lt;=", "≤")
        .replace("&gt;=", "≥")
        .replace(r"\le", "≤")
        .replace(r"\ge", "≥")
        .replace(r"\ne", "≠")
    )
    value = value.replace(" degrees", "°")
    value = re.sub(
        r"\\frac\{([^{}]+)\}\{([^{}]+)\}",
        r"\1/\2",
        value,
    )
    value = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", value)
    value = re.sub(r"sqrt\(([^)]+)\)", r"√(\1)", value)
    return value


def looks_like_display_math(text: str) -> bool:
    """Conservatively identify standalone equations without catching prose."""
    value = strip_display_math_delimiters(text)
    if not value or _CITATION.match(value):
        return False
    if _DISPLAY_COMMAND.search(value):
        return True
    if _BRACKET_MATRIX.search(value) or _TRANSPOSED_VECTOR.search(value):
        return True
    if not _RELATION.search(value):
        return False

    prose_check = value
    for name in (*_FUNCTION_NAMES, *_GREEK_NAMES, "sqrt"):
        prose_check = re.sub(
            rf"(?<![A-Za-z]){name}(?![A-Za-z])",
            "",
            prose_check,
        )
    return not re.search(r"[A-Za-z]{4,}", prose_check)


def strip_display_math_delimiters(text: str) -> str:
    value = text.strip()
    if value.startswith("$$") and value.endswith("$$") and len(value) > 4:
        return value[2:-2].strip()
    if value.startswith(r"\[") and value.endswith(r"\]") and len(value) > 4:
        return value[2:-2].strip()
    return value


def _replace_latex_matrix(match: re.Match[str]) -> str:
    body = match.group("body").strip()
    raw_rows = re.split(r"\\\\(?:\[[^\]]*\])?", body)
    rows = [
        [cell.strip() for cell in row.split("&")]
        for row in raw_rows
        if row.strip()
    ]
    return _matrix_markup(rows, kind=match.group("kind"))


def _replace_bracket_matrix(match: re.Match[str]) -> str:
    rows = [
        _split_top_level(row, ",")
        for row in re.findall(r"\[([^\[\]]*)\]", match.group("rows"))
    ]
    return _matrix_markup(rows, kind="bmatrix")


def _replace_transposed_vector(match: re.Match[str]) -> str:
    entries = _split_top_level(match.group(1), ",")
    return _matrix_markup([[entry] for entry in entries], kind="bmatrix")


def _split_top_level(text: str, delimiter: str) -> list[str]:
    values: list[str] = []
    current: list[str] = []
    depth = 0

    for character in text:
        if character in "({[":
            depth += 1
        elif character in ")}]":
            depth = max(0, depth - 1)
        if character == delimiter and depth == 0:
            values.append("".join(current).strip())
            current.clear()
        else:
            current.append(character)
    values.append("".join(current).strip())
    return values


def _matrix_markup(rows: list[list[str]], *, kind: str) -> str:
    if not rows or not all(rows):
        raise ValueError("matrix must contain at least one value per row")
    column_count = len(rows[0])
    if any(len(row) != column_count for row in rows):
        raise ValueError("matrix rows must have the same number of columns")

    body = r"\\".join(
        r"\quad".join(_matrix_cell(cell) for cell in row)
        for row in rows
    )
    contents = rf"\substack{{{body}}}"
    delimiters = {
        "matrix": ("", ""),
        "bmatrix": (r"\left[", r"\right]"),
        "Bmatrix": (r"\left\{", r"\right\}"),
        "pmatrix": (r"\left(", r"\right)"),
        "vmatrix": (r"\left|", r"\right|"),
        "Vmatrix": (r"\left|", r"\right|"),
    }
    left, right = delimiters[kind]
    return f"{left}{contents}{right}"


def _matrix_cell(value: str) -> str:
    cell = value.strip()
    fraction = re.fullmatch(
        r"(?P<sign>[+-]?)(?P<numerator>[A-Za-z0-9.]+)"
        r"\s*/\s*"
        r"(?P<denominator>[A-Za-z0-9.]+)",
        cell,
    )
    if fraction:
        return (
            fraction.group("sign")
            + rf"\frac{{{fraction.group('numerator')}}}"
            + rf"{{{fraction.group('denominator')}}}"
        )
    return cell


__all__ = [
    "group_math_lines",
    "looks_like_display_math",
    "normalize_inline_math",
    "normalize_math_expression",
    "strip_display_math_delimiters",
]
