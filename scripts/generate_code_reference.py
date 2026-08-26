"""Generate searchable repository, symbol, frontend, and test reference pages."""

from __future__ import annotations

import argparse
import ast
import html
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
GITHUB_BLOB = "https://github.com/komaroffsergei/tender-lens/blob/main"
GENERATED_PATHS = (
    Path("docs/reference/repository-tree.md"),
    Path("docs/reference/python-api.md"),
    Path("docs/reference/frontend-api.md"),
    Path("docs/reference/test-catalog.md"),
)

FILE_DESCRIPTIONS = {
    ".dockerignore": "Исключает local/secret/build artifacts из Docker build context.",
    ".env.example": "Безопасный шаблон всех environment settings для Compose.",
    ".flake8": "Настраивает Flake8 и согласует длину строки с Black.",
    ".gitignore": "Исключает secrets, caches, local data, build output и IDE state.",
    ".github/PULL_REQUEST_TEMPLATE.md": "Checklist содержательного PR, тестов, безопасности и документации.",
    "alembic.ini": "Конфигурация Alembic CLI и logging migration environment.",
    "CHANGELOG.md": "Хронология пользовательски значимых изменений release.",
    "docker-compose.test.yml": "Изолированные PostgreSQL/pgvector и NATS для integration/E2E.",
    "docker-compose.yml": "Runtime topology: БД, broker, roles и optional Ollama profile.",
    "Dockerfile": "Один non-root Python image для API, crawler, indexer и migrations.",
    "LICENSE": "MIT license, обязательная часть публичной поставки.",
    "Makefile": "Короткие команды install, quality, tests, migrations и demos.",
    "mkdocs.yml": "Структура, тема, поиск, extensions и navigation документационного сайта.",
    "pyproject.toml": "Package metadata, entrypoint и конфигурация Black/Pytest/MyPy.",
    "README.md": "Краткая публичная входная страница repository.",
    "requirements.lock": "Pinned runtime dependencies Docker image.",
    "requirements-dev.lock": "Pinned quality, typing и test dependencies.",
    "requirements-docs.lock": "Pinned generator/theme stack документации.",
    "SECURITY.md": "Security policy, threat boundaries и disclosure instructions.",
    "docs/javascripts/docs.js": "Добавляет Ctrl+K и управление раскрытием code tree.",
    "docs/javascripts/mermaid.mjs": "Инициализирует безопасный Mermaid rendering и instant navigation.",
    "docs/overrides/partials/source.html": "Рисует GitHub link без фонового GitHub API запроса.",
    "docs/stylesheets/extra.css": "Design tokens, layout и responsive стили документационного портала.",
    "docs/ui/search-wireframe-mobile.png": "Исходный мобильный wireframe пользовательского Search UI.",
    "docs/ui/search-wireframe.png": "Исходный desktop wireframe пользовательского Search UI.",
    "examples/demo-requests.sh": "Короткий shell-сценарий Search/Ask/rate-limit демонстрации.",
    "examples/fixture-server-contract.md": "HTTP contract локального fixture server, используемого E2E.",
    "migrations/env.py": "Подключает async SQLAlchemy engine и metadata к Alembic runtime.",
    "migrations/script.py.mako": "Шаблон новых Alembic revision files.",
    "src/tender_lens/web/app.js": "Browser state, безопасный DOM rendering и Search/Ask fetch flow.",
    "src/tender_lens/web/index.html": "Семантическая разметка статического TenderLens UI.",
    "src/tender_lens/web/styles.css": "Design tokens, desktop/mobile layout и UI component styles.",
    "tests/conftest.py": "Общие pytest fixtures project root и example fixture directory.",
}

SYMBOL_DESCRIPTIONS = {
    "Settings": "Валидирует единый набор runtime-настроек всех трёх ролей.",
    "get_settings": "Возвращает кэшированный Settings для текущего процесса.",
    "ResilientHttpClient": "Ограничивает concurrency и безопасно выполняет retry/redirect HTTP requests.",
    "SourceAdapter": "Protocol одинакового получения страницы для любого внешнего источника.",
    "SourcePage": "Порция нормализованных records и следующий opaque cursor.",
    "CrawlerService": "Оркестрирует cursor, UPSERT, attachments и публикацию события.",
    "IndexerService": "Идемпотентно превращает конкретную версию tender в vector chunks.",
    "SearchService": "Выполняет pgvector retrieval и grounded generation.",
    "FakeAIProvider": "Детерминированный hashing provider для тестов и offline demo.",
    "OllamaAIProvider": "Проверяемый async client Ollama embed/generate/health API.",
    "NatsBroker": "Создаёт JetStream stream, публикует events и читает durable consumer.",
    "NatsMessage": "Изолирует indexer от SDK типов и оставляет ACK/NAK/TERM.",
    "InMemoryBroker": "Запоминает events без внешнего NATS для unit/E2E.",
    "create_app": "Собирает FastAPI, lifecycle dependencies, middleware и handlers.",
    "consume_rate_limit": "Атомарно расходует слот fixed UTC-minute под row lock.",
    "authenticate_api_key": "Проверяет X-API-Key по hash и состоянию enabled.",
    "download_attachment": "Потоково и атомарно сохраняет ограниченное по размеру вложение.",
    "tender_content_hash": "Вычисляет SHA-256 canonical значимых полей закупки.",
    "chunk_units": "Режет TextUnit по абзацам с детерминированным overlap.",
    "build_rag_prompt": "Формирует prompt, маркирующий документы недоверенным контекстом.",
}


@dataclass(frozen=True)
class Symbol:
    qualname: str
    kind: str
    signature: str
    description: str
    start: int
    end: int


def run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")


def repository_files() -> list[Path]:
    tracked = set(run_git("ls-files").splitlines())
    untracked = set(run_git("ls-files", "--others", "--exclude-standard").splitlines())
    paths = {Path(item) for item in tracked | untracked if item}
    paths.update(GENERATED_PATHS)
    return sorted(
        path
        for path in paths
        if not any(part in {".venv", "site", "__pycache__"} for part in path.parts)
    )


def source_url(path: Path, start: int | None = None, end: int | None = None) -> str:
    url = f"{GITHUB_BLOB}/{path.as_posix()}"
    if start is not None:
        url += f"#L{start}"
        if end is not None and end != start:
            url += f"-L{end}"
    return url


def text_info(path: Path) -> tuple[int | None, int]:
    absolute = ROOT / path
    if not absolute.exists():
        return 0, 0
    size = absolute.stat().st_size
    try:
        content = absolute.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None, size
    return len(content.splitlines()), size


def first_heading(content: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def module_docstring(path: Path) -> str | None:
    try:
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None
    value = ast.get_docstring(tree, clean=True)
    return first_sentence(value) if value else None


def first_sentence(value: str) -> str:
    compact = " ".join(value.split())
    match = re.match(r"(.+?[.!?])(?:\s|$)", compact)
    return match.group(1) if match else compact


def file_description(path: Path) -> str:
    key = path.as_posix()
    if key in FILE_DESCRIPTIONS:
        return FILE_DESCRIPTIONS[key]
    if path.suffix == ".py":
        doc = module_docstring(path)
        if doc:
            return doc
    if key.startswith("tests/unit/"):
        return "Unit tests изолированной логики без real infrastructure."
    if key.startswith("tests/api/"):
        return "In-process FastAPI contract tests с dependency injection."
    if key.startswith("tests/integration/"):
        return "Integration tests с настоящими PostgreSQL/pgvector или NATS."
    if key.startswith("tests/e2e/"):
        return "Полный fixture pipeline от crawler до Search/Ask."
    if key.startswith("docs/assets/design/"):
        return "Согласованный desktop/mobile визуальный концепт документационного портала."
    if key.startswith("docs/assets/images/"):
        return "Локальный brand asset документационного сайта."
    if key.startswith("docs/diagrams/"):
        if path.suffix in {".png", ".svg"}:
            return "Отрендеренная архитектурная иллюстрация для Markdown/README."
        return "Редактируемый исходник архитектурной диаграммы."
    if key.startswith("docs/") and path.suffix == ".md" and (ROOT / path).exists():
        heading = first_heading((ROOT / path).read_text(encoding="utf-8"))
        return (
            f"Статья документации: {heading}." if heading else "Страница инженерной документации."
        )
    if key.startswith("examples/fixtures/"):
        if path.name == "README.md":
            return "Описание происхождения и роли offline fixtures."
        return f"Контролируемый fixture `{path.name}` для adapters/extraction/E2E."
    if key.startswith("examples/prompts/"):
        return "Reference prompt для сравнения grounded RAG поведения."
    if key.startswith("examples/api/"):
        return "Версионированный пример JSON HTTP-контракта."
    if key.startswith("examples/sql/"):
        return "Поясняющий SQL-пример ключевого алгоритма."
    if key.startswith("schemas/"):
        return "Checked-in JSON Schema, генерируемая из Pydantic contract."
    if key.startswith(".github/workflows/"):
        return "GitHub Actions workflow для автоматической проверки или deployment."
    if key.startswith("scripts/"):
        return "Служебный automation script для demo, schema, docs или live smoke."
    if path.name == "__init__.py":
        return "Обозначает Python package и хранит его публичные metadata/exports."
    return f"Project artifact типа `{path.suffix or 'без расширения'}`."


def file_kind(path: Path) -> str:
    key = path.as_posix()
    if key.startswith("src/"):
        return "application"
    if key.startswith("tests/"):
        return "test"
    if key.startswith("docs/"):
        return "documentation"
    if key.startswith("migrations/"):
        return "database"
    if key.startswith(".github/"):
        return "automation"
    if key.startswith("examples/") or key.startswith("schemas/"):
        return "contract/example"
    if key.startswith("scripts/"):
        return "automation"
    return "project"


def tree_node(paths: Iterable[Path]) -> dict[str, object]:
    root: dict[str, object] = {}
    for path in paths:
        node = root
        for part in path.parts[:-1]:
            node = node.setdefault(part, {})  # type: ignore[assignment]
        node.setdefault("__files__", []).append(path)  # type: ignore[union-attr]
    return root


def render_tree(node: dict[str, object], depth: int = 0) -> list[str]:
    lines: list[str] = []
    files = sorted(node.get("__files__", []), key=lambda value: value.name)  # type: ignore[arg-type]
    for path in files:
        lines.append(
            f'<a class="file" href="{source_url(path)}" title="{html.escape(file_description(path))}">{html.escape(path.name)}</a>'
        )
    for name in sorted(key for key in node if key != "__files__"):
        child = node[name]
        open_attr = " open" if depth < 1 else ""
        lines.append(f"<details{open_attr}><summary>{html.escape(name)}/</summary>")
        lines.extend(render_tree(child, depth + 1))  # type: ignore[arg-type]
        lines.append("</details>")
    return lines


def generate_repository_tree(paths: list[Path]) -> str:
    rows: list[str] = []
    for path in paths:
        # Generated pages include this table, so their own byte/line count would
        # create a self-referential diff on every run. Their content is covered
        # by the separate drift check instead.
        lines, size = (None, 0) if path in GENERATED_PATHS else text_info(path)
        line_text = "—" if lines is None else str(lines)
        rows.append(
            "| [{path}]({url}) | {kind} | {description} | {lines} | {size} |".format(
                path=path.as_posix(),
                url=source_url(path),
                kind=file_kind(path),
                description=escape_table(file_description(path)),
                lines=line_text,
                size=size,
            )
        )
    tree = "\n".join(render_tree(tree_node(paths)))
    return f"""<!-- AUTO-GENERATED by scripts/generate_code_reference.py; DO NOT EDIT. -->
# Дерево репозитория

Страница описывает каждый version-controlled файл. Наведите на файл в дереве, чтобы увидеть назначение; ссылка открывает его в GitHub. Нажмите кнопку, чтобы развернуть вложенные каталоги.

<button class="md-button" data-expand-code-tree>Развернуть дерево</button>

<div class="code-tree">
{tree}
</div>

## Все файлы

| Файл | Слой | Назначение | Строк | Байт |
|---|---|---|---:|---:|
{chr(10).join(rows)}

_Сгенерировано из `git ls-files` и локального source tree. Binary assets показывают «—» вместо числа строк._
"""


def signature(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(item) for item in node.bases)
        return f"class {node.name}({bases})" if bases else f"class {node.name}"
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"


def describe_symbol(node: ast.AST, qualname: str) -> str:
    doc = (
        ast.get_docstring(node, clean=True)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        else None
    )
    if doc:
        return first_sentence(doc)
    short = qualname.rsplit(".", 1)[-1]
    if short in SYMBOL_DESCRIPTIONS:
        return SYMBOL_DESCRIPTIONS[short]
    plain = short.strip("_").replace("_", " ")
    if short.startswith("normalize_") or short.startswith("validate_"):
        return f"Нормализует или валидирует `{plain}` по contract rules."
    if short.startswith("extract_"):
        return f"Безопасно извлекает текст: `{plain}`."
    if short.startswith("map_"):
        return f"Преобразует внешний payload: `{plain}`."
    if short.startswith("create_") or short.startswith("build_"):
        return f"Создаёт объект/значение для операции `{plain}`."
    if short.startswith("get_") or short.startswith("list_"):
        return f"Читает данные без изменения основной сущности: `{plain}`."
    if short.startswith("_is_") or short.startswith("is_"):
        return f"Проверяет условие `{plain}`."
    if short.startswith("_mark_"):
        return f"Атомарно меняет состояние: `{plain}`."
    if short in {"main", "run"}:
        return "Запускает lifecycle соответствующей CLI/worker роли."
    if short == "__init__":
        parent = qualname.rsplit(".", 1)[0]
        return f"Сохраняет dependencies и начальное состояние `{parent}`."
    if short.startswith("__a"):
        return "Реализует async context manager lifecycle."
    return f"Реализует внутреннюю операцию `{plain}`; точный contract виден в сигнатуре."


def symbols_in(tree: ast.Module) -> list[Symbol]:
    result: list[Symbol] = []
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        kind = (
            "class"
            if isinstance(node, ast.ClassDef)
            else ("async function" if isinstance(node, ast.AsyncFunctionDef) else "function")
        )
        result.append(
            Symbol(
                node.name,
                kind,
                signature(node),
                describe_symbol(node, node.name),
                node.lineno,
                node.end_lineno or node.lineno,
            )
        )
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                qualname = f"{node.name}.{child.name}"
                kind = "async method" if isinstance(child, ast.AsyncFunctionDef) else "method"
                result.append(
                    Symbol(
                        qualname,
                        kind,
                        signature(child),
                        describe_symbol(child, qualname),
                        child.lineno,
                        child.end_lineno or child.lineno,
                    )
                )
    return result


def imports_in(tree: ast.Module) -> list[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return sorted(names)


def generate_python_api(paths: list[Path]) -> str:
    python_paths = sorted(
        [
            path
            for path in paths
            if path.suffix == ".py"
            and not path.as_posix().startswith("tests/")
            and path.name != "script.py.mako"
        ],
        key=lambda path: (
            (
                0
                if path.as_posix().startswith("src/")
                else 1 if path.as_posix().startswith("migrations/") else 2
            ),
            path.as_posix(),
        ),
    )
    sections: list[str] = []
    total = 0
    for path in python_paths:
        content = (ROOT / path).read_text(encoding="utf-8")
        tree = ast.parse(content)
        symbols = symbols_in(tree)
        total += len(symbols)
        doc = ast.get_docstring(tree, clean=True) or file_description(path)
        imports = imports_in(tree)
        rows = []
        for item in symbols:
            rows.append(
                f'| `{escape_table(item.qualname)}` | {item.kind} | <span class="symbol-signature">`{escape_table(item.signature)}`</span> | {escape_table(item.description)} | [L{item.start}–L{item.end}]({source_url(path, item.start, item.end)}) |'
            )
        if not rows:
            rows.append(
                "| — | module | — | Модуль не объявляет classes/functions. | [файл](%s) |"
                % source_url(path)
            )
        dependency_text = ", ".join(f"`{item}`" for item in imports) if imports else "—"
        sections.append(
            f"""## `{path.as_posix()}`

{first_sentence(doc)}

**Imports:** {dependency_text}

| Символ | Вид | Сигнатура | Ответственность | Исходник |
|---|---|---|---|---|
{chr(10).join(rows)}
"""
        )
    return f"""<!-- AUTO-GENERATED by scripts/generate_code_reference.py; DO NOT EDIT. -->
# Python: классы и функции

AST-каталог содержит **{len(python_paths)} modules** и **{total} top-level/class symbols**. Private helpers включены: они важны для чтения реального execution path.

{chr(10).join(sections)}
"""


def line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def generate_frontend_api() -> str:
    html_path = Path("src/tender_lens/web/index.html")
    js_path = Path("src/tender_lens/web/app.js")
    css_path = Path("src/tender_lens/web/styles.css")
    html_text = (ROOT / html_path).read_text(encoding="utf-8")
    js_text = (ROOT / js_path).read_text(encoding="utf-8")
    css_text = (ROOT / css_path).read_text(encoding="utf-8")

    dom_rows: list[str] = []
    for match in re.finditer(
        r"<(?P<tag>[a-zA-Z][\w-]*)(?P<attrs>[^>]*?\bid=\"(?P<id>[^\"]+)\"[^>]*)>", html_text
    ):
        line = line_number(html_text, match.start())
        attrs = match.group("attrs")
        label = re.search(r"aria-label=\"([^\"]+)\"", attrs)
        purpose = label.group(1) if label else f"DOM anchor/control `{match.group('id')}`."
        dom_rows.append(
            f"| `#{match.group('id')}` | `{match.group('tag')}` | {escape_table(purpose)} | [L{line}]({source_url(html_path, line)}) |"
        )

    js_rows: list[str] = []
    for match in re.finditer(
        r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", js_text, re.MULTILINE
    ):
        line = line_number(js_text, match.start())
        name, args = match.groups()
        purpose = {
            "showNotice": "Показывает status/error без небезопасного HTML.",
            "clearResults": "Удаляет предыдущие DOM results и answer.",
            "createResult": "Строит одну безопасную карточку результата.",
            "updateRate": "Читает rate headers успешного/ошибочного response.",
            "parseError": "Переводит HTTP/error envelope в сообщение пользователю.",
            "submitQuery": "Валидирует, вызывает Search/Ask и обновляет UI state.",
        }.get(name, f"Frontend operation `{name}`.")
        js_rows.append(
            f"| `{name}({escape_table(args)})` | {purpose} | [L{line}]({source_url(js_path, line)}) |"
        )

    selectors: list[tuple[str, int]] = []
    for match in re.finditer(r"(?:^|\})([^@{}][^{}]*)\{", css_text, re.MULTILINE):
        raw = " ".join(match.group(1).split())
        line = line_number(css_text, match.start(1))
        for selector in raw.split(","):
            selector = selector.strip()
            if selector and len(selector) <= 120:
                selectors.append((selector, line))
    seen: set[tuple[str, int]] = set()
    css_rows = []
    for selector, line in selectors:
        if (selector, line) in seen:
            continue
        seen.add((selector, line))
        css_rows.append(
            f"| `{escape_table(selector)}` | Визуальное правило UI selector. | [L{line}]({source_url(css_path, line)}) |"
        )

    return f"""<!-- AUTO-GENERATED by scripts/generate_code_reference.py; DO NOT EDIT. -->
# Frontend: DOM, JS и CSS

Статический UI не имеет build step. Этот каталог связывает видимые controls с JavaScript behavior и CSS selectors.

## DOM anchors

| ID | Element | Назначение | Исходник |
|---|---|---|---|
{chr(10).join(dom_rows)}

## JavaScript functions

| Функция | Назначение | Исходник |
|---|---|---|
{chr(10).join(js_rows)}

## CSS selectors

| Selector | Назначение | Исходник |
|---|---|---|
{chr(10).join(css_rows)}
"""


TOKEN_TRANSLATIONS = {
    "rejects": "отклоняется",
    "invalid": "невалидный",
    "returns": "возвращается",
    "creates": "создаётся",
    "without": "без",
    "after": "после",
    "before": "до",
    "same": "одинаковый",
    "different": "разный",
    "does": "выполняет",
    "not": "не",
    "when": "когда",
    "source": "источник",
    "event": "событие",
    "attachment": "вложение",
    "query": "запрос",
}


def describe_test(name: str) -> str:
    words = [TOKEN_TRANSLATIONS.get(item, item) for item in name.removeprefix("test_").split("_")]
    return "Проверяет: " + " ".join(words) + "."


def generate_test_catalog(paths: list[Path]) -> str:
    test_paths = [
        path for path in paths if path.suffix == ".py" and path.as_posix().startswith("tests/")
    ]
    sections: list[str] = []
    total = 0
    for path in test_paths:
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        tests = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        if not tests:
            continue
        total += len(tests)
        level = path.parts[1]
        rows = []
        for node in tests:
            decorators = ", ".join(ast.unparse(item) for item in node.decorator_list) or "—"
            rows.append(
                f"| `{node.name}` | {escape_table(describe_test(node.name))} | `{escape_table(decorators)}` | [L{node.lineno}–L{node.end_lineno or node.lineno}]({source_url(path, node.lineno, node.end_lineno or node.lineno)}) |"
            )
        sections.append(
            f"""## `{path.as_posix()}`

**Уровень:** `{level}` · **cases:** {len(tests)}

| Test | Проверяемое поведение | Mark/decorator | Исходник |
|---|---|---|---|
{chr(10).join(rows)}
"""
        )
    return f"""<!-- AUTO-GENERATED by scripts/generate_code_reference.py; DO NOT EDIT. -->
# Каталог тестов

Каталог содержит **{total} test functions**. Parametrization может превращать одну функцию в несколько pytest cases, поэтому число runtime tests обычно больше.

{chr(10).join(sections)}
"""


def escape_table(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())


def outputs() -> dict[Path, str]:
    paths = repository_files()
    return {
        GENERATED_PATHS[0]: generate_repository_tree(paths),
        GENERATED_PATHS[1]: generate_python_api(paths),
        GENERATED_PATHS[2]: generate_frontend_api(),
        GENERATED_PATHS[3]: generate_test_catalog(paths),
    }


def generate(*, check: bool) -> int:
    drift: list[Path] = []
    for relative, content in outputs().items():
        absolute = ROOT / relative
        current = absolute.read_text(encoding="utf-8") if absolute.exists() else None
        if current == content:
            continue
        drift.append(relative)
        if not check:
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        action = "out of date" if check else "generated"
        print(f"Documentation reference {action}: " + ", ".join(map(str, drift)))
        return 1 if check else 0
    print("Documentation reference is current.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail instead of writing on drift")
    raise SystemExit(generate(check=parser.parse_args().check))


if __name__ == "__main__":
    main()
