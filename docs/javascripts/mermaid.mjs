import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.esm.min.mjs";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "base",
  themeVariables: {
    primaryColor: "#eef2ff",
    primaryTextColor: "#172033",
    primaryBorderColor: "#3157d5",
    lineColor: "#5272df",
    secondaryColor: "#f5f7fb",
    tertiaryColor: "#ffffff",
    fontFamily: "Inter, system-ui, sans-serif",
  },
});

window.mermaid = mermaid;

document$.subscribe(async () => {
  const nodes = [...document.querySelectorAll("pre.mermaid:not([data-processed])")];
  if (nodes.length) await mermaid.run({ nodes });
});
