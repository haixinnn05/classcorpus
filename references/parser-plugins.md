# Parser Plugins

ClassCorpus dispatches source formats through `ParserPlugin` registrations.
The indexer asks the registry for supported suffixes on every synchronization,
so adding a registered plugin does not require changing discovery logic.

## Contract

```python
from classcorpus.parser_registry import ParserPlugin
from classcorpus.parsers import register_parser

register_parser(
    ParserPlugin(
        name="example",
        suffixes=(".example",),
        parse=parse_example,
    )
)
```

The parse callable accepts `(source_path, generated_data_directory)` and
returns `list[SlideRecord]`. It must:

- Return one-based, contiguous ordinals.
- Preserve native source text in `raw_text` without intentional truncation.
- Use `slide` only for presentation slides and `page` for other ordered units.
- Keep generated files under the supplied generated-data directory.
- Mark uncertain extraction with `review-needed` and stable reason codes.
- Never modify the source file.
- Raise on source-level failure so atomic replacement preserves prior records.

Plugin names and suffixes must be unique. Suffix matching is case-insensitive.
Register programmatic plugins before calling `sync_course`; agent-facing CLI
support requires importing the plugin from the ClassCorpus package.

## Built-In Text Plugin

The isolated `text-documents` plugin handles UTF-8 `.md` and `.txt` files. Each
file becomes one page record. The first nonblank line is the title; a Markdown
ATX heading has its leading `#` markers removed from the normalized title.
`raw_text` remains byte-decoded text exactly as read. Blank documents are
indexed as `review-needed` with `no-native-text`.

Text files have no render. Visual review and OCR therefore require a separate
rendered source such as PDF.

