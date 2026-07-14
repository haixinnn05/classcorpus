from classcorpus.search import SearchResult


def format_citation(result: SearchResult) -> str:
    label = "Slide" if result.kind == "slide" else "Page"
    return (
        f"[{result.course}, {result.source_file}, "
        f"{label} {result.ordinal}]"
    )


__all__ = ["format_citation"]
