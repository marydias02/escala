---
name: ltp-html
description: LTPlabs brand reference (colors, fonts, spacing, components) for styling HTML deliverables. Use when building or styling any HTML page that should carry LTP branding.
---

# LTP Brand

Read [DESIGN.md](DESIGN.md) before writing any CSS or HTML for an LTP-branded deliverable. It is the canonical reference for:

- brand and semantic color tokens
- typography (Bw Modelica) and type scale
- spacing, radius, and shadow scales
- component rules (buttons, cards, tags, nav, charts, footer)
- motion rules
- do/do-not list

If a light/dark theme toggle is explicitly requested (it's off by default — see DESIGN.md §7), also read [references/theme-toggle.md](references/theme-toggle.md) before implementing. It's kept out of DESIGN.md itself so its cost isn't paid on every invocation.

## When to use

- Building a standalone HTML report, dashboard, or microsite for LTP.
- Styling any web deliverable that needs to look on-brand.
- Another skill needs to check a color hex, spacing value, or component pattern against the LTP standard.
