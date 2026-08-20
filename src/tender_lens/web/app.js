"use strict";

const state = {
  mode: "search",
  key: document.getElementById("api-key"),
  query: document.getElementById("query"),
  submit: document.getElementById("submit"),
  notice: document.getElementById("notice"),
  results: document.getElementById("results"),
  empty: document.getElementById("empty"),
  answerCard: document.getElementById("answer-card"),
  answerText: document.getElementById("answer-text"),
  rate: document.getElementById("rate-state"),
};

const savedKey = sessionStorage.getItem("tenderLensApiKey");
if (savedKey) state.key.value = savedKey;

function showNotice(message, isError = false) {
  state.notice.textContent = message;
  state.notice.classList.toggle("error", isError);
  state.notice.hidden = !message;
}

function clearResults() {
  state.results.replaceChildren();
  state.answerCard.hidden = true;
}

function createResult(item) {
  const article = document.createElement("article");
  article.className = "result-card";

  const top = document.createElement("div");
  top.className = "result-topline";
  const badge = document.createElement("span");
  badge.className = "source-badge";
  badge.textContent = item.source;
  const score = document.createElement("span");
  score.className = "score";
  score.textContent = `${Math.round(Number(item.score) * 100)}% релевантности`;
  top.append(badge, score);

  const title = document.createElement("h3");
  title.textContent = item.title;
  const snippet = document.createElement("p");
  snippet.textContent = item.snippet;

  const footer = document.createElement("div");
  footer.className = "result-footer";
  const attachment = document.createElement("span");
  attachment.textContent = item.attachment ? item.attachment.filename : "Метаданные закупки";
  const link = document.createElement("a");
  link.href = item.source_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Открыть источник";
  footer.append(attachment, link);

  article.append(top, title, snippet, footer);
  return article;
}

function updateRate(response) {
  const limit = response.headers.get("X-RateLimit-Limit");
  const remaining = response.headers.get("X-RateLimit-Remaining");
  if (limit !== null && remaining !== null) {
    state.rate.textContent = `Осталось ${remaining} из ${limit} запросов в текущей UTC-минуте`;
  }
}

async function parseError(response) {
  try {
    const payload = await response.json();
    return payload.error?.message || `HTTP ${response.status}`;
  } catch (_) {
    return `HTTP ${response.status}`;
  }
}

async function submitQuery() {
  const query = state.query.value.trim();
  const apiKey = state.key.value.trim();
  if (query.length < 3) {
    showNotice("Введите запрос длиной не менее трёх символов.", true);
    state.query.focus();
    return;
  }
  if (!apiKey) {
    showNotice("Укажите API-ключ в заголовке формы.", true);
    state.key.focus();
    return;
  }

  clearResults();
  showNotice("Ищем релевантные фрагменты…");
  state.submit.disabled = true;
  state.submit.setAttribute("aria-busy", "true");
  const originalText = state.submit.textContent;
  state.submit.textContent = "Обрабатываем…";

  try {
    const response = await fetch(`/api/v1/${state.mode}`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-API-Key": apiKey},
      body: JSON.stringify({query, limit: 5}),
    });
    updateRate(response);
    if (!response.ok) throw new Error(await parseError(response));
    const payload = await response.json();
    const items = state.mode === "ask" ? payload.sources : payload.items;
    items.forEach((item) => state.results.append(createResult(item)));
    state.empty.hidden = items.length > 0;
    if (!items.length) state.empty.textContent = "Релевантные документы не найдены.";
    if (state.mode === "ask") {
      state.answerText.textContent = payload.answer;
      state.answerCard.hidden = false;
    }
    showNotice(items.length ? `Найдено фрагментов: ${items.length}.` : "Поиск завершён без результатов.");
  } catch (error) {
    state.empty.hidden = false;
    state.empty.textContent = "Результаты не загружены.";
    showNotice(error instanceof Error ? error.message : "Неизвестная ошибка.", true);
  } finally {
    state.submit.disabled = false;
    state.submit.removeAttribute("aria-busy");
    state.submit.textContent = originalText;
  }
}

document.getElementById("save-key").addEventListener("click", () => {
  sessionStorage.setItem("tenderLensApiKey", state.key.value.trim());
  showNotice("API-ключ сохранён для текущей вкладки.");
});

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.answerCard.hidden = true;
  });
});

state.submit.addEventListener("click", submitQuery);
state.query.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submitQuery();
});

fetch("/health/live")
  .then((response) => {
    const health = document.getElementById("health");
    health.textContent = response.ok ? "API доступен" : "API недоступен";
    health.classList.add(response.ok ? "ok" : "bad");
  })
  .catch(() => {
    const health = document.getElementById("health");
    health.textContent = "API недоступен";
    health.classList.add("bad");
  });
