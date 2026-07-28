"""Bundle the Agent Skill assets into the installed package.

`SKILL.md`, `references/`, and `scripts/` are the skill itself, and they live at
the repository root so a cloned checkout works as a skill directory directly.
A wheel cannot reference files outside the package, so copy them into
`classcorpus/_skill/` while building. `classcorpus install-skill` reads them from
there, and falls back to the repository root in a source or editable checkout.

Keep the root copies canonical. Nothing here is generated into version control.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

SKILL_ASSETS = ("SKILL.md", "references", "scripts")
BUNDLE_DIRECTORY = "_skill"


class build_py(_build_py):
    def run(self) -> None:
        super().run()
        source_root = Path(__file__).parent.resolve()
        destination_root = (
            Path(self.build_lib) / "classcorpus" / BUNDLE_DIRECTORY
        )
        for name in SKILL_ASSETS:
            source = source_root / name
            if not source.exists():
                raise FileNotFoundError(
                    f"cannot bundle the Agent Skill: {source} is missing"
                )
            destination = destination_root / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    destination,
                    ignore=shutil.ignore_patterns(
                        "__pycache__", "*.pyc", ".DS_Store"
                    ),
                    dirs_exist_ok=True,
                )
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

    def get_outputs(self, include_bytecode: int = 1) -> list[str]:
        outputs = list(super().get_outputs(include_bytecode))
        bundle = Path(self.build_lib) / "classcorpus" / BUNDLE_DIRECTORY
        if bundle.exists():
            outputs.extend(
                str(path) for path in sorted(bundle.rglob("*")) if path.is_file()
            )
        return outputs


setup(cmdclass={"build_py": build_py})
