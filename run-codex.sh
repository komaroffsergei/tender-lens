#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

for command_name in codex git gh docker python; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Не найдена обязательная команда: $command_name" >&2
    exit 127
  fi
done

python - <<'PY_VALIDATE'
from pathlib import Path
import json

required = [
    "AGENTS.md",
    "CODEX_MASTER_PROMPT.md",
    "specs/09-test-plan.md",
    "specs/10-implementation-plan.md",
    "schemas/codex-final-report.schema.json",
]
for item in required:
    path = Path(item)
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"SDD pack повреждён или неполон: {item}")

for path in Path("schemas").glob("*.json"):
    schema = json.loads(path.read_text(encoding="utf-8"))
    if "$schema" not in schema:
        raise SystemExit(f"В JSON Schema отсутствует $schema: {path}")

print("Предварительная проверка SDD pack пройдена")
PY_VALIDATE

gh auth status

docker version >/dev/null
docker compose version >/dev/null

codex --search exec \
  --sandbox workspace-write \
  -c sandbox_workspace_write.network_access=true \
  --json \
  --output-schema schemas/codex-final-report.schema.json \
  --output-last-message codex-final-report.json \
  - < CODEX_MASTER_PROMPT.md \
  | tee codex-run.jsonl
