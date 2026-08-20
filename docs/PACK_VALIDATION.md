# Проверка SDD pack до запуска Codex

Выполнить из корня распакованного pack:

```bash
python - <<'PY'
from pathlib import Path
import json
from jsonschema import Draft202012Validator

required = [
    "AGENTS.md", "CODEX_MASTER_PROMPT.md", "README_FIRST.md",
    "specs/00-product.md", "specs/09-test-plan.md", "specs/10-implementation-plan.md",
    "schemas/tender-record-v1.schema.json",
    "schemas/tender-changed-v1.schema.json",
    "schemas/codex-final-report.schema.json",
    "docs/diagrams/architecture.png",
    "docs/ui/search-wireframe.png",
    "examples/fixtures/sample_tender.pdf",
]
for item in required:
    assert Path(item).is_file(), item
for path in Path("schemas").glob("*.json"):
    Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
print("SDD pack validation passed")
PY
```

Также визуально открыть:

- `docs/diagrams/architecture.png`;
- `docs/diagrams/data-model.png`;
- `docs/ui/search-wireframe.png`;
- `examples/fixtures/sample_tender.pdf`.
