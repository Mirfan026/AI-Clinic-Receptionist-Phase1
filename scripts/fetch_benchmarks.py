"""Download third-party benchmark datasets used for external evaluation.

    python scripts/fetch_benchmarks.py

Datasets land in data/benchmarks/, which is gitignored. They are deliberately
NOT vendored into this repository:

* they carry their own licences, some of them copyleft, and mixing those into
  the project tree creates obligations the project should not inherit silently;
* they are evaluation inputs, not project data. Nothing here may ever be added
  to data/production/knowledge/documents/ - enlarging the knowledge base with
  benchmark text would destroy the abstention behaviour the benchmarks exist to
  measure.

Every download records its licence in data/benchmarks/MANIFEST.json.
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "benchmarks"

SOURCES = {
    "clinc150": {
        "url": "https://codeload.github.com/clinc/oos-eval/tar.gz/refs/heads/master",
        "kind": "tar.gz",
        "keep": ["data/data_full.json", "data/domains.json", "LICENSE", "README.md"],
        "licence": "CC BY 3.0 Unported",
        "citation": "Larson et al. 2019, An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction (EMNLP)",
        "used_for": "Out-of-scope abstention stress test (1,000 OOS queries).",
    },
    "roman_urdu": {
        "url": "https://codeload.github.com/Smat26/Roman-Urdu-Dataset/tar.gz/refs/heads/master",
        "kind": "tar.gz",
        "keep": [
            "Conversions/English-Urdu-Roman.txt",
            "Dictionary/Roman-Urdu-Dictionary.txt",
            "LICENSE",
            "README.md",
        ],
        "licence": "GPL-3.0  ***COPYLEFT - see BENCHMARKS.md before redistributing***",
        "citation": "Sharf, Z. Roman Urdu Data Set (compiled by Smat26).",
        "used_for": "Auditing app/rag/lexicon.py against attested Roman Urdu spellings.",
    },
    "sgd_schema": {
        "url": "https://raw.githubusercontent.com/google-research-datasets/"
               "dstc8-schema-guided-dialogue/master/train/schema.json",
        "kind": "file",
        "filename": "sgd_train_schema.json",
        "licence": "CC BY-SA 4.0",
        "citation": "Rastogi et al. 2019, Towards Scalable Multi-domain Conversational Agents: The Schema-Guided Dialogue Dataset",
        "used_for": "Architectural comparison of the booking contract (Services_3 = doctor appointments).",
    },
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "clinic-receptionist-benchmarks"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def extract(payload: bytes, keep: list[str], destination: Path) -> list[str]:
    written = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            # Archive paths are prefixed with "<repo>-<branch>/".
            relative = member.name.split("/", 1)[1] if "/" in member.name else member.name
            if relative not in keep:
                continue
            data = archive.extractfile(member)
            if data is None:
                continue
            out = destination / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data.read())
            written.append(relative)
    return written


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    manifest = {}
    failures = []

    for name, spec in SOURCES.items():
        destination = TARGET / name
        destination.mkdir(parents=True, exist_ok=True)
        print(f"\n{name}")
        print(f"  licence: {spec['licence']}")
        try:
            payload = fetch(spec["url"])
        except Exception as exc:                      # network, proxy, 404...
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            failures.append(name)
            continue

        if spec["kind"] == "tar.gz":
            written = extract(payload, spec["keep"], destination)
        else:
            out = destination / spec["filename"]
            out.write_bytes(payload)
            written = [spec["filename"]]

        if not written:
            print("  FAILED: archive contained none of the expected files")
            failures.append(name)
            continue

        for item in written:
            print(f"  + {item}")
        manifest[name] = {
            "source": spec["url"],
            "licence": spec["licence"],
            "citation": spec["citation"],
            "used_for": spec["used_for"],
            "files": written,
        }

    (TARGET / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"\nManifest: {TARGET / 'MANIFEST.json'}")

    if failures:
        print(f"\nUnavailable: {', '.join(failures)}")
        print("Evaluation scripts skip missing datasets rather than failing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
