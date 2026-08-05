from classcorpus.math_notation import (
    group_math_lines,
    looks_like_display_math,
    normalize_inline_math,
    normalize_math_expression,
    strip_display_math_delimiters,
)


def test_compact_matrix_uses_stacked_rows_and_columns():
    normalized = normalize_math_expression("A = [[1, 2, 0], [0, 1, 1], [1, 2, 0]]")

    assert normalized == (
        r"A = \left[\substack{"
        r"1\quad2\quad0\\"
        r"0\quad1\quad1\\"
        r"1\quad2\quad0"
        r"}\right]"
    )


def test_transposed_vector_becomes_column_vector():
    normalized = normalize_math_expression("Ax = [3, 0, -1]^T")

    assert normalized == (r"Ax = \left[\substack{3\\0\\-1}\right]")


def test_matrix_fractions_and_named_functions_are_typeset():
    normalized = normalize_math_expression("P = [[-1/2, 1/2], [1, 0]]; det(P) != 0")

    assert r"-\frac{1}{2}" in normalized
    assert r"\frac{1}{2}" in normalized
    assert r"\mathrm{det}(P)" in normalized
    assert r"\ne" in normalized


def test_greek_names_and_parenthesized_fraction_are_typeset():
    normalized = normalize_math_expression("lambda = (-b + sqrt(Delta)) / (2a)")

    assert normalized == (r"\lambda = \frac{-b + \sqrt{\Delta}}{2a}")


def test_inline_greek_names_work_before_subscripts():
    assert normalize_inline_math(r"\lambda_1 = 1") == "λ_1 = 1"
    assert normalize_inline_math("lambda_2 = 2") == "λ_2 = 2"


def test_inline_latex_operators_fractions_and_roots_are_readable():
    assert normalize_inline_math(r"\frac{1}{2} \le sqrt(Delta)") == "1/2 ≤ √(Δ)"


def test_vector_set_keeps_its_closing_brace():
    normalized = normalize_math_expression("Col(A) = span{[1, 2]^T, [3, 4]^T}")

    assert normalized.startswith(r"\mathrm{Col}(A) = \mathrm{span}{")
    assert normalized.endswith(r"\right]}")
    assert normalized.count(r"\substack") == 2


def test_multiline_latex_matrix_is_grouped_and_normalized():
    grouped = group_math_lines(
        [
            r"A = \begin{bmatrix}",
            r"1 & 2 \\",
            r"3 & 4",
            r"\end{bmatrix}",
            "x = 1",
        ]
    )

    assert grouped == [
        r"A = \begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}",
        "x = 1",
    ]
    assert normalize_math_expression(grouped[0]) == (
        r"A = \left[\substack{1\quad2\\3\quad4}\right]"
    )


def test_standalone_equations_are_detected_conservatively():
    assert looks_like_display_math("A = [[1, 2], [3, 4]]") is True
    assert looks_like_display_math("x^2 + y^2 = r^2") is True
    assert looks_like_display_math(r"\sum_{i=1}^{n} a_i = b") is True
    assert (
        looks_like_display_math(
            "Average velocity = displacement divided by elapsed time."
        )
        is False
    )
    assert looks_like_display_math("[Math, lecture.pdf, Page 4]") is False
    assert looks_like_display_math("[Math, lecture.vtt, 14:32.500]") is False


def test_display_math_delimiters_are_removed():
    assert strip_display_math_delimiters("$$x^2 = 4$$") == "x^2 = 4"
    assert strip_display_math_delimiters(r"\[x^2 = 4\]") == "x^2 = 4"


def test_compound_exponent_is_grouped():
    """MathText raises only the next token, so a multi-token exponent needs braces."""
    assert normalize_math_expression("n^log_b(a)") == r"n^{\mathrm{log}_b(a)}"
    assert (
        normalize_math_expression("T(n) = Theta(n^log_b(a) * log n)")
        == r"T(n) = \Theta(n^{\mathrm{log}_b(a)} * \mathrm{log} n)"
    )


def test_capital_greek_complexity_classes_are_typeset():
    """Big-Theta is core algorithms notation and was rendering literally."""
    assert normalize_math_expression("Theta(n log n)") == r"\Theta(n \mathrm{log} n)"
    assert normalize_math_expression("Omega(n)") == r"\Omega(n)"
    assert normalize_math_expression("theta = 30") == r"\theta = 30"


def test_multi_character_and_signed_exponents_are_grouped():
    assert normalize_math_expression("n^12") == "n^{12}"
    assert normalize_math_expression("e^-x") == "e^{-x}"
    assert normalize_math_expression("x^(i+1)") == "x^{(i+1)}"


def test_single_token_exponents_are_left_alone():
    assert normalize_math_expression("n^2") == "n^2"
    assert normalize_math_expression("2^n + 1") == "2^n + 1"
    assert normalize_math_expression("a^b") == "a^b"


def test_superscript_then_subscript_keeps_its_meaning():
    """`x^2_i` is a superscript and a subscript, not an exponent of `2_i`."""
    assert normalize_math_expression("x^2_i") == "x^2_i"


def test_already_grouped_exponents_are_not_double_wrapped():
    assert normalize_math_expression("n^{log_b a}") == r"n^{\mathrm{log}_b a}"
