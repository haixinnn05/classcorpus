# Security Policy

## Supported Versions

Security fixes land on the latest released version. Please reproduce an issue on
the current release, or on `main`, before reporting it.

## Reporting A Vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/haixinnn05/classcorpus/security/advisories/new).
Do not open a public issue for a vulnerability.

Please include:

- what an attacker can achieve, and what access they need to start;
- the affected version, operating system, and Python version;
- a minimal reproduction using **synthetic** files.

**Never include real course materials, personal data, or credentials in a
report.** ClassCorpus reads local coursework, so a reproduction can easily
contain someone's private files. Generate a minimal fixture instead;
`classcorpus demo` and `benchmarks/generate.py` produce redistributable files
suitable for a report.

Expect an acknowledgement within seven days. This is a volunteer-maintained
project with no paid support and no bug bounty.

## Scope

ClassCorpus is a local Agent Skill and library. It has no hosted backend, no
account system, and no telemetry, so there is no server-side attack surface.
Reports in scope include:

- **Prompt injection through course content.** Source-derived text is evidence,
  never instructions. Payloads are marked `content_trust: "untrusted"`. A path
  that lets lecture content escape that boundary, or that omits the marking, is
  in scope. See [references/security.md](references/security.md).
- **Writing outside the generated-data directory**, or any modification of a
  lecture source file. ClassCorpus must never alter the materials it reads.
- **Path traversal** through a course name, source path, or artifact path.
- **Code execution** triggered by parsing a crafted PDF, PPTX, DOCX, Markdown,
  or text file, including through a parser plugin.
- **Unexpected network access.** Baseline indexing, search, and rendering are
  offline. Only explicitly installed optional embedding backends may fetch model
  weights, and only on first use.
- **Leaking absolute local paths** into artifacts intended to be shareable, such
  as a provenance manifest.

Out of scope:

- Vulnerabilities in upstream dependencies without a ClassCorpus-specific
  exploit path. Report those upstream; tell us if a version pin is needed.
- The data-handling behaviour of whichever agent invokes ClassCorpus. Visual
  analysis is opt-in precisely because images are viewed under that agent's
  policy.
- Uncalibrated OCR confidence, or incomplete native extraction that is already
  reported as `review-needed`. These are documented limitations, not defects.
