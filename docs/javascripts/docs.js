"use strict";

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    document.querySelector("[data-md-toggle='search']")?.click();
    window.setTimeout(() => document.querySelector(".md-search__input")?.focus(), 50);
  }
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-expand-code-tree]");
  if (!button) return;
  const details = document.querySelectorAll(".code-tree details");
  const shouldOpen = button.dataset.expanded !== "true";
  details.forEach((item) => {
    item.open = shouldOpen;
  });
  button.dataset.expanded = String(shouldOpen);
  button.textContent = shouldOpen ? "Свернуть дерево" : "Развернуть дерево";
});
