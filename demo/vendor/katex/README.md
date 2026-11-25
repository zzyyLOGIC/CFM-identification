# Local KaTeX for model-answer presentation

Pinned version: 0.19.1. `ORIGIN.json` records the official npm tarball and verified SHA-512 integrity. Only the distributed browser script and MIT license were extracted. No install scripts were run.

The page uses `output: "mathml"`, native browser MathML and the project's own stylesheet. It does not load a CDN, external fonts, HTML rendering assets or plugins at runtime. The server exposes only the exact script path, not this directory generally.

Untrusted model TeX uses `trust: false`, bounded expansion/size, fresh macros and escaped fallback on errors. A presentation formatter handles recognized bare expressions and preserves unsupported text; it does not change the saved reply, infer an answer or validate a causal claim.

Upstream references: [rendering options](https://katex.org/docs/options.html), [untrusted input controls](https://katex.org/docs/security.html). Keep `LICENSE` with the distributed script.
