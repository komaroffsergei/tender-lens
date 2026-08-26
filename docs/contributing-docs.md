# Поддержка документации

Документация является частью поставки: source links, search index и generated reference проверяются так же, как код.

## Где что менять

| Изменение | Файл |
|---|---|
| порядок/названия страниц | `mkdocs.yml` → `nav` |
| архитектурное объяснение | `docs/architecture/` или `docs/modules/` |
| новый термин | `docs/glossary.md` |
| внешний вид | `docs/stylesheets/extra.css` |
| keyboard/UI docs behavior | `docs/javascripts/docs.js` |
| file/symbol descriptions | `scripts/generate_code_reference.py` |
| generated reference | не редактировать; запустить generator |
| Pages pipeline | `.github/workflows/docs.yml` |

## Локальная сборка

```powershell
python -m pip install -r requirements-docs.lock
python scripts/generate_code_reference.py
python -m mkdocs serve --dev-addr 127.0.0.1:8001
```

Откройте `http://127.0.0.1:8001`. Port 8001 выбран, потому что application API обычно занимает 8000.

## Definition of done статьи

- заголовок отвечает одному вопросу;
- первый абзац даёт краткий ответ без необходимости читать всё;
- новый technical term определён или связан с глоссарием;
- diagram используется только для связи/последовательности/состояния;
- code claim имеет прямую source-link;
- command копируется и выполняется из repository root;
- известное ограничение не скрыто;
- desktop/mobile navigation остаётся usable;
- `mkdocs build --strict` и `check_docs.py` проходят.

## Source links

Формат:

```text
https://github.com/OWNER/REPOSITORY/blob/main/path/to/file.py#L10-L25
```

Статья может ссылаться на диапазон, если обсуждает одну логическую функцию. Generated reference получает номера из AST и обновляет их автоматически. `check_docs.py` проверяет существование local path и границы строк.

## Generated pages

В начале generated file стоит HTML comment `AUTO-GENERATED`. Генератор сначала строит полный text в памяти; без `--check` записывает файл только если content изменился. Это даёт чистый Git diff и воспроизводимость.

Добавили/переименовали Python symbol, test или tracked file — перезапустите generator и commit-ните code + reference вместе.

## Search QA

После build `site/search/search_index.json` должен находить как минимум:

- `CrawlerService`;
- `tender.changed.v1`;
- `идемпотентность`;
- `Retry-After`;
- `Contracts Finder`.

Автоматическая проверка подтверждает наличие ключевых terms; browser QA подтверждает открытие overlay по ++ctrl+k++, переход к результату и подсветку.

## Design source

Принятые визуальные концепты сохранены в `docs/assets/design/`. Реальный сайт следует их принципам — три уровня навигации, светлая инженерная палитра, компактная typography — но использует responsive primitives Material for MkDocs, а не literal pixel-copy mockup.
