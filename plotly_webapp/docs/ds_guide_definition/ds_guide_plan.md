# DS Guide — Implementation Plan

> Before implementing, read `docs/ds_guide_architecture.md` for full context on why decisions were made.
> This plan covers the developer-facing system: documentation files, INDEX maps, and the `ds-guide` skill.
> The `update-ds-guide` skill and integration files (AGENTS.md, CLAUDE.md, README.md) are in `docs/update_ds_guide_plan.md`.

---

## Mandatory Pre-Implementation Research

Before writing any file, the implementing agent MUST read the following. Content must be derived from the actual codebase — not from assumptions or this plan alone.

- [ ] Read `README.md` (understand current structure and tone)
- [ ] Read every file in `assets/css/base/` (`colors.css`, `typography.css`, `spacing-borders-shadows.css`, `layout.css`, `grid-system.css`, `reset.css`)
- [ ] Run `ls assets/css/components/` — note every component CSS file
- [ ] Run `ls components/` — note every component folder
- [ ] Read every `README.md` inside `components/*/` — understand what each component does, its props, usage
- [ ] Read `app.py` — understand the application entry point and layout wiring
- [ ] Run `ls pages/` — note all pages (ignore `documentation/`)
- [ ] Run `ls callbacks/` — note all callback files (ignore `documentation/`)
- [ ] Run `ls utils/` — note all utility files
- [ ] Run `ls assets/css/custom/` — note any existing custom styles
- [ ] Run `ls assets/css/pages/` — note any existing page styles
- [ ] Read `assets/css/base/colors.css` — locate the `--custom-theme` variable inside `:root {}` and confirm it is the only project-customizable value in this file

**Component inventory cross-check:**
- Confirm that `ls components/` and `ls assets/css/components/` correspond one-to-one
- Note any component that has a Python folder but no CSS file, or vice versa
- `components/components_extra_design_system` is an intentional exception — note what it contains

**`documentation/` folders — skip entirely:**
The following folders exist in the repo but are being phased out. Do not read, reference, describe, or include them in any file you create:
- `assets/css/documentation/`
- `assets/scripts/documentation/`
- `callbacks/documentation/`
- `pages/documentation/`

**Pattern analysis — read enough to confidently understand implementation standards:**
- Read component Python files across `components/` until the structure is clearly repeatable and predictable
- Read CSS files across `assets/css/components/` and `assets/css/base/` until naming conventions and variable usage are fully clear
- Read page files in `pages/` until the page structure pattern is unambiguous
- Read callback files in `callbacks/` until the organization pattern is understood
- The bar is: could you describe the standard confidently to a new developer without re-reading? If not, read more.

Best practices in `docs/best_practices.md` must be grounded in these observed patterns — not assumed from this plan. The rules listed here are a starting point; the agent must identify additional practices from the actual code.

**The implementing agent must go beyond what is listed in this plan.** Identify additional questions a first-time developer would realistically ask. Derive content from the actual codebase.

---

## Files to Create

### 1. `INDEX.md` (root)

**Purpose:** Agent-facing repo navigation map. Terse, structured, no prose.

**Content requirements:**
- List every top-level item: `app.py`, `assets/`, `callbacks/`, `components/`, `pages/`, `utils/`, `pyproject.toml`, `README.md`, `docs/`
- For each: one-line description of what it contains/does
- For folders: note whether frozen (do not edit) or dynamic (grows per project)
- For `assets/`: note to read `assets/css/INDEX.md` for CSS navigation
- For `components/`: note it is dynamic, use `ls`. Note `components_extra_design_system` explicitly: it holds supplementary DS components that do not map to a single concept and does not follow the standard naming convention
- For `docs/`: note it contains the AI guide knowledge base and both skills (`ds-guide`, `update-ds-guide`)
- **Do not list or mention any `documentation/` subfolder** in `pages/`, `callbacks/`, or `assets/`

---

### 2. `assets/css/INDEX.md`

**Purpose:** Describes every subfolder inside `assets/css/`.

**Content requirements:**

- **`base/`** — FROZEN. Core DS design tokens. Never edit except `--custom-theme` in `:root {}` inside `colors.css`. Read `assets/css/base/INDEX.md` to navigate files inside.
- **`components/`** — FROZEN. One CSS file per DS component. Do not edit. Use `ls assets/css/components/` to see the component inventory.
- **`custom/`** — YOUR ZONE. All project-specific styles go here. Grows per project. One file per concern, descriptive names.
- **`pages/`** — Page-level style overrides. Grows per project.
- A clear note that `base/` and `components/` are frozen and must never be edited
- A clear note that `custom/` is the only place for new project styles
- **Do not include or mention `assets/css/documentation/`**

---

### 3. `assets/css/base/INDEX.md`

**Purpose:** Describes every file in `assets/css/base/`. Read by `ds-guide` for color/typography/spacing questions. Read by `update-ds-guide` when auditing token documentation.

**Content requirements** (derived from actually reading the files):

- **`colors.css`** — All DS color tokens as CSS variables. The `--custom-theme` variable inside `:root {}` is the ONLY value in this folder that a project may customize. Its HSL value is provided by the design team — never define it yourself.
- **`typography.css`** — Typography tokens: font families, sizes, weights, line heights.
- **`spacing-borders-shadows.css`** — Spacing scale, border radius, box shadow tokens.
- **`layout.css`** — Layout tokens: max widths, container sizes, etc.
- **`grid-system.css`** — Grid configuration variables.
- **`reset.css`** — CSS reset/normalize. Do not reference or override.

Add a prominent header: **ALL FILES IN THIS FOLDER ARE FROZEN EXCEPT THE `--custom-theme` VARIABLE IN `colors.css`**.

Do not guess variable names or token values — read the files.

---

### 4. `docs/overview.md`

**Purpose:** Answers conceptual first-contact questions.

**Content requirements:**

- **What is a design system?** — Fetch and draw from: `https://www.figma.com/blog/design-systems-101-what-is-a-design-system/#components-of-a-design-system` at writing time. This URL is used here only — it does not appear in `resources.md` or in any skill.
- **Why use a design system?** — Consistency, speed, scalability, shared language.
- **Components of a design system** — Tokens, components, patterns, documentation.
- **What are design tokens?** — Relate to `assets/css/base/`.
- **What are reusable components?** — Relate to `components/`.
- **This design system specifically** — What is the Dash Template DS, who maintains it, the plug-and-play model.
- **The Figma** — Introduce the Figma as visual reference: `https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP-%E2%80%93-Design-System-by-Significa`. Mention the "Detail Page" template.
- **FAQs inline at the bottom.**

Go beyond what is listed here. Think about every conceptual question a developer new to design systems would ask.

---

### 5. `docs/navigation.md`

**Purpose:** Human-readable explanation of how the repo is organized.

**Content requirements:**

- **Top-level structure** — Every top-level item with its role
- **`components/`** — One folder per component, each with a README. Call out `components_extra_design_system`: holds supplementary DS components that do not map to a single concept. Its naming is intentional — do not treat it as a mistake.
- **`assets/`** — Full CSS structure in prose: `base/` (frozen tokens), `components/` (frozen styles), `custom/` (your zone), `pages/` (overrides)
- **`pages/`** — What Dash pages are, how they are registered
- **`callbacks/`** — What callbacks are, how they relate to components and pages
- **`utils/`** — Shared utilities
- **`app.py`** — The application entry point, when to touch it
- **`docs/`** — The AI guide knowledge base and skills
- **Where to look first** — Short decision guide: "if you want to do X, start at Y"
- **FAQs inline at the bottom.**
- **Do not mention any `documentation/` subfolder** anywhere in this file

---

### 6. `docs/best_practices.md`

**Purpose:** The complete rulebook. Source of truth the skill summarizes into hard constraints.

**Content requirements:**

**Styling rules:**
- No inline styles — ever. All styles go in CSS files.
- Never edit `assets/css/base/` or `assets/css/components/`
- All new project-specific styles go in `assets/css/custom/` — one file per concern, descriptive filenames
- Always use CSS variables: `var(--variable-name)`. Never hardcode colors, sizes, or spacing.
- Small files — one concern per CSS file.

**Component rules:**
- Reuse before creating — always check `ls assets/css/components/` and `ls components/` first
- All new components must be reusable — no page-specific one-offs
- Component priority: (1) native Dash, (2) Dash Mantine, (3) custom
- New custom components go in `components/`, their styles in `assets/css/custom/`

**Theming rules:**
- The only allowed color customization is `--custom-theme` in the `:root {}` block of `assets/css/base/colors.css`
- The HSL value is provided by the design team — never define it yourself
- Typography exceptions must be deliberate and justified

**Structural rules:**
- Place this repo at `plotly_webapp/frontend/` inside the project root
- Keep callbacks, pages, components, and utilities separated

**When deviating is justified:**
- Deviations only acceptable with a documented business/client reason
- Deviations must be minimal, justified, and confined to `custom/`

Include rationale for every rule. Identify additional conventions from the actual codebase — if the code shows a consistent pattern, document it.

**FAQs inline at the bottom.**

---

### 7. `docs/workflows.md`

**Purpose:** Step-by-step task guides. Each workflow is self-contained.

**Required workflows:**

**Project bootstrapping:** clone → `uv sync` → `uv run app.py`. Place repo at `plotly_webapp/frontend/`.

**Adding a new page:** derive exact steps from reading existing pages in `pages/`.

**Adding a new component:** create folder in `components/`, Python file, CSS in `assets/css/custom/` (NOT `assets/css/components/`). Derive from existing component patterns.

**Changing the theme color:** open `assets/css/base/colors.css`, locate `--custom-theme` in `:root {}`, replace HSL value with one provided by the design team. This is the ONLY change allowed in `assets/css/base/`.

**Adding custom styles:** new file in `assets/css/custom/`, descriptive name, CSS variables only.

**Using icons:** DashIconify + look up names at `https://lucide.dev/icons/`.

**Using charts:** Dash built-in components only. No third-party charting libraries.

**Consulting the Figma:** open `https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP-%E2%80%93-Design-System-by-Significa`. "Detail Page" template is the target layout.

Identify additional workflows by reading the codebase. **FAQs inline at the bottom.**

---

### 8. `docs/resources.md`

**Purpose:** Single source of truth for all external links a developer needs at runtime.

**Content requirements:**

| Resource | URL | When to use |
|---|---|---|
| Figma Design System | `https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP-%E2%80%93-Design-System-by-Significa` | Visual reference. "Detail Page" template is the target layout. |
| Dash Core Components | `https://dash.plotly.com/dash-core-components` | First place to look when a component does not exist in the DS |
| Dash Mantine Components | `https://www.dash-mantine-components.com/` | Last resort UI framework |
| Lucide Icons | `https://lucide.dev/icons/` | Find icon names to use with DashIconify |

Include a brief paragraph explaining priority order: DS first, then Dash Core, then Mantine, never arbitrary third-party libraries.

**Do not include the Figma blog URL.** It was used during implementation only.

---

### 9. `docs/skills/ds-guide/SKILL.md`

**Purpose:** Developer-facing guide skill. Routing logic + hard constraints. No DS content.

**Content requirements:**

**Role definition:**
```
You are the design system guide for the Dash Template repository.
Your job is to help developers understand and correctly use this design system.
Answer only based on the documentation in this repo. Never guess DS-specific facts.
```

**Hard constraints (always enforced):**
- No inline styles — all styles go in CSS files
- Never suggest editing `assets/css/base/` or `assets/css/components/` (frozen)
- All new project-specific styles go in `assets/css/custom/`
- Always use CSS variables: `var(--variable-name)` — never hardcode values
- The `--custom-theme` variable in the `:root {}` block of `assets/css/base/colors.css` is the ONLY allowed color customization — value is provided by the design team, never self-defined
- New components must always be reusable
- Reuse before creating — check existing components first

**Routing table:**

| Question type | Primary doc | Fallback |
|---|---|---|
| What is a DS / conceptual / tokens / why DS | `docs/overview.md` | `docs/best_practices.md` |
| Repo structure / where is X / how is it organized | `docs/navigation.md` | root `INDEX.md` |
| Rules / what to avoid / best practices | `docs/best_practices.md` | `docs/overview.md` |
| How to do X / task / workflow | `docs/workflows.md` | `docs/best_practices.md` |
| External tools / Figma / icons / libraries | `docs/resources.md` | `docs/workflows.md` |
| Does component X exist / what components are available | `ls components/` then `ls assets/css/components/` | If not found: route to `docs/workflows.md` for how to create one |
| How does component X work / how do I use it | `ls components/` → `components/<name>/README.md` | If README insufficient: read the component Python file directly |
| CSS tokens / variables / colors / typography | `assets/css/base/INDEX.md` → specific file | `docs/best_practices.md` |

**Composite question handling:**
Identify the primary intent (task, concept, or rule), route to that doc first, then check the cascade for secondary intent. Never answer only half of a composite question. Examples:
- "How do I add a component that uses DS colors?" → `workflows.md` → `best_practices.md` → `assets/css/base/INDEX.md`
- "What components exist and how do I use them?" → `ls components/` → `components/<name>/README.md`
- "Am I allowed to change the typography?" → `best_practices.md` → `overview.md`

**Last resort rule:**
After exhausting the routing table and repo exploration: "I don't have enough information to answer this. Please contact the design team directly." Never hallucinate DS-specific facts.

---

## Implementation Order

1. Complete all mandatory pre-implementation research (read codebase, cross-check component inventory)
2. Create `assets/css/base/INDEX.md` (depends on reading base/ files)
3. Create `assets/css/INDEX.md` (depends on knowing base/ contents)
4. Create `INDEX.md` at root (depends on full repo understanding)
5. Create `docs/overview.md` (fetch and read the Figma blog post URL at writing time)
6. Create `docs/navigation.md` (depends on full repo understanding)
7. Create `docs/best_practices.md` (depends on understanding existing patterns)
8. Create `docs/workflows.md` (depends on reading pages/, components/, app.py)
9. Create `docs/resources.md` (use URLs from this plan; do not include the Figma blog URL)
10. Create `docs/skills/ds-guide/SKILL.md` (depends on all docs being written — routing table must reference real files)

Continue in `docs/update_ds_guide_plan.md`.

---

## Quality Checks

Before considering this plan complete (ds-guide only):

- [ ] Every INDEX.md accurately reflects actual files/folders (verified against `ls`)
- [ ] `assets/css/INDEX.md` does not mention `documentation/`
- [ ] Root `INDEX.md` does not mention `pages/documentation/` or `callbacks/documentation/`
- [ ] `docs/navigation.md` does not mention any `documentation/` folder
- [ ] `assets/css/base/INDEX.md` accurately describes every token file (verified by reading the files)
- [ ] All `--custom-theme` references use variable name + `:root {}` location — never a line number
- [ ] `docs/skills/ds-guide/SKILL.md` routing table references only files that actually exist
- [ ] Routing table has a fallback for every row, including component existence and usage rows
- [ ] All external URLs in `docs/resources.md` are copied exactly from this plan
- [ ] `docs/resources.md` does NOT contain the Figma blog URL
- [ ] `docs/workflows.md` derives page and component steps from actual repo patterns, not assumptions
- [ ] No doc file contains placeholder text or "TBD"
- [ ] Hard constraints in `ds-guide` SKILL.md match rules in `docs/best_practices.md`
- [ ] `components_extra_design_system` is explained in both `INDEX.md` and `docs/navigation.md`
- [ ] Component inventory cross-check completed — divergence between `ls components/` and `ls assets/css/components/` noted in `assets/css/INDEX.md`
