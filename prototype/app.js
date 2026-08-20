const state = {
  mode: "ask",
  results: document.getElementById("results"),
  answer: document.getElementById("answer"),
  submit: document.getElementById("submit"),
  query: document.getElementById("query"),
  apiKey: document.getElementById("api-key")
};

const savedKey = sessionStorage.getItem("tenderLensApiKey");
if (savedKey) state.apiKey.value = savedKey;

document.getElementById("save-key").addEventListener("click", () => {
  sessionStorage.setItem("tenderLensApiKey", state.apiKey.value.trim());
});

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.answer.hidden = state.mode !== "ask";
  });
});

state.submit.addEventListener("click", async () => {
  const query = state.query.value.trim();
  if (query.length < 3) {
    state.query.focus();
    return;
  }

  state.submit.classList.add("is-loading");
  state.submit.disabled = true;
  state.submit.querySelector("span").textContent = "Обрабатываем…";
  await new Promise((resolve) => setTimeout(resolve, 550));
  state.submit.classList.remove("is-loading");
  state.submit.disabled = false;
  state.submit.querySelector("span").textContent = "Выполнить запрос";
  state.answer.hidden = state.mode !== "ask";
  state.answer.scrollIntoView({ behavior: "smooth", block: "center" });
});
