# DS Guide — Architecture

## What We Are Building

An AI-guide system layered on top of the Dash design system repository. The goal is to allow a developer who has just cloned this repo to ask questions to an AI agent (Codex or Claude Code) and receive accurate, well-routed answers about the design system — without needing a human to onboard them.

The system has two skills:

- **`ds-guide`** — developer-facing. Answers questions about the design system on demand.
- **`update-ds-guide`** — UI/UX team-facing. Audits the documentation against the current repo state and proposes updates when things have changed.

Neither skill is a chatbot. Both are structured operation systems backed by a curated documentation layer and deterministic routing logic.

---

## Why We Are Doing This

This design system is intended to be plug-and-play: clone the repo, install dependencies, start building. In practice, first-time users consistently face the same friction points:

- They do not know what a design system is or why it matters
- They do not know how the repo is organized or where to find things
- They do not know what components already exist and reach for custom solutions unnecessarily
- They deviate from the design system (inline styles, editing frozen files, ignoring CSS variables) because no one told them the rules
- They do not know about external resources (Figma, Dash docs, Mantine, icon libraries)
- They ask the same questions repeatedly to the UI/UX team

The `ds-guide` skill reduces all of this to a single entry point. The `update-ds-guide` skill ensures that entry point stays accurate as the repo evolves.

**Primary objectives:**
- Reduce learning time for someone using the DS repo for the first time
- Teach how to consult the Figma design system
- Answer conceptual questions ("what are tokens?", "what is a design system?", "what are reusable components?")
- Answer structural questions ("how is the repo organized?", "where is the sidebar component?")
- Answer task-based questions ("how do I add a new page?", "how do I bootstrap a new project?")
- Enforce best practices passively — the agent knows the rules and applies them in every answer
- Keep the documentation accurate over time without manual trawling

---

## Target Audience

**`ds-guide`:** Engineers starting a new project using this design system for the first time. They may be familiar with Python and Dash but unfamiliar with the concept of a design system, this repo's structure, or its conventions.

**`update-ds-guide`:** The UI/UX cell team. Invoked when they need to verify the documentation is still accurate after components, pages, or conventions have changed.

Primary AI tool: **Codex** (OpenAI Enterprise). Secondary: **Claude Code**.

---

## Architecture Overview

The system has four layers:

```
User question / maintenance trigger
    → Layer 0: Project config (AGENTS.md / CLAUDE.md) — discovery + install instructions for both skills
        → Layer 1: Skills (routing + audit logic)
            ds-guide/SKILL.md     → Layer 2: docs/ (knowledge base)
            update-ds-guide/SKILL.md → scans docs/ + repo → proposes updates
                → Layer 3: INDEX.md files + ls (repo navigation)
```

### Layer 0 — Project Configuration (`AGENTS.md` / `CLAUDE.md`)

Two minimal files at the repo root. Read automatically by their respective AI tools at session start — no discovery required.

**Purpose:**
- Tell the developer both skills exist and what each does
- Provide exact install commands for both
- Tell the agent how to invoke each

**`AGENTS.md`** (Codex — installs to `.agents/skills/`):

```markdown
# Dash Template DS

This is the Dash design system template repository.

## Skills

### DS Guide — developer tool

Answers questions about the design system: structure, rules, workflows, components.

Install:
```bash
mkdir -p .agents/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .agents/skills/ds-guide/SKILL.md
```
Invoke: `$ds-guide "your question"`

### Update DS Guide — UI/UX team tool

Audits the documentation against the current repo state. Run this when components,
pages, or conventions have changed and the docs may need updating.

Install:
```bash
mkdir -p .agents/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .agents/skills/update-ds-guide/SKILL.md
```
Invoke: `$update-ds-guide`

Restart Codex after installing. To update a skill after repo changes, re-run its install command.
```

**`CLAUDE.md`** (Claude Code — installs to `.claude/skills/`):

```markdown
# Dash Template DS

This is the Dash design system template repository.

## Skills

### DS Guide — developer tool

Answers questions about the design system: structure, rules, workflows, components.

Install:
```bash
mkdir -p .claude/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .claude/skills/ds-guide/SKILL.md
```
Invoke: `/ds-guide "your question"`

### Update DS Guide — UI/UX team tool

Audits the documentation against the current repo state. Run this when components,
pages, or conventions have changed and the docs may need updating.

Install:
```bash
mkdir -p .claude/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .claude/skills/update-ds-guide/SKILL.md
```
Invoke: `/update-ds-guide`

Restart Claude Code after installing. To update a skill after repo changes, re-run its install command.
```

**Why not auto-sync on every session?** Running a diff + copy on every session costs tokens every time, even when nothing has changed. The install command is cheap to run once manually; re-running it when the skill changes is sufficient.

**Why `.agents/` instead of `.codex/`:** Codex recognizes `.agents/skills/` as the skill directory.

#### Why not put everything in AGENTS.md and skip skills entirely?

AGENTS.md is loaded on every session regardless of what the developer is doing. A developer editing a Python callback has no use for a full routing table and DS knowledge in their context. Skills are loaded on-demand — the right content at the right moment, zero cost otherwise.

**Rule:** AGENTS.md and CLAUDE.md are pointers, not the guides. Keep them minimal. All logic and content lives in the skills and docs.

---

### Layer 1 — Skills (`docs/skills/`)

Two skill files, each serving a different purpose and audience.

#### `ds-guide/SKILL.md` — Developer guidance

The entry point for the guide. When invoked, the agent reads this file first. Contains:

1. **Role definition** — who the agent is and what it does
2. **Hard constraints** — rules always enforced, regardless of what is asked
3. **Routing table** — topic-based map from question type to the doc file that answers it
4. **Composite question guidance** — how to handle questions that span multiple topics
5. **Cascade fallback** — if the primary doc does not answer, which doc to check next
6. **Last resort rule** — if no doc answers, say so and point to the design team. Never hallucinate DS-specific facts.

Routing logic only — no DS content. All substance lives in the docs.

#### `update-ds-guide/SKILL.md` — Documentation maintenance

Invoked by the UI/UX team when the repo has changed and the docs may be stale. Contains:

1. **Role definition** — documentation auditor, not a developer guide
2. **Scan targets** — which dynamic folders to inspect (see below)
3. **Documentation targets** — which files to read as the current documented state
4. **Cross-reference logic** — how to map what was found in the repo to what should be documented where
5. **Audit report format** — structured output: one section per doc file, gaps categorized by severity
6. **Update process** — present report first, confirm before applying, update one file at a time

**What `update-ds-guide` scans (dynamic, may have changed):**

| Scan target | Ignore | Maps to |
|---|---|---|
| `ls components/` | — | `docs/navigation.md`, root `INDEX.md` |
| `ls assets/css/components/` | — | `assets/css/INDEX.md` |
| Component `README.md` files for any new/undocumented component | — | `docs/navigation.md`, `docs/workflows.md` |
| `ls pages/` | `documentation/` | `docs/navigation.md` |
| `ls callbacks/` | `documentation/` | `docs/navigation.md` |
| `ls assets/css/custom/` | — | `docs/best_practices.md`, `docs/workflows.md` |
| Code patterns in new components/pages | — | `docs/best_practices.md` |

**What `update-ds-guide` reads as current documented state:**

- `docs/overview.md`
- `docs/navigation.md`
- `docs/best_practices.md`
- `docs/workflows.md`
- `docs/resources.md`
- `INDEX.md` (root)
- `assets/css/INDEX.md`
- `assets/css/base/INDEX.md`

**Audit report structure:**

For each documentation file:
- **Current** — what is documented
- **Missing** — entities or patterns in the repo not yet documented
- **Outdated** — documented things that no longer exist or have changed
- **Proposed change** — specific text to add, modify, or remove
- **Severity** — `breaking` (doc actively misleads), `gap` (missing info), `minor` (cosmetic)

**Update process:** report first → confirm → apply file by file → remind team to re-run skill install commands if `SKILL.md` files were changed.

---

### Layer 2 — Knowledge base (`docs/`)

Five curated markdown files. Each answers a specific category of question. The `ds-guide` skill routes to exactly one file per question type. The `update-ds-guide` skill reads all five to understand current documented state.

| File | Answers |
|---|---|
| `overview.md` | What is a design system, why use one, what are tokens, what are reusable components |
| `navigation.md` | How the repo is organized, what each folder does, where to find things |
| `best_practices.md` | All rules: what to do, what never to do, and why |
| `workflows.md` | Task-based: add a page, add a component, bootstrap a project, change the theme color |
| `resources.md` | All external links: Figma, Dash docs, Mantine, DashIconify, Lucide icons |

**No `faq.md`** — FAQs are inline at the bottom of the most relevant doc.

**No `docs/INDEX.md`** — the skill is the index for docs/. An extra hop with no gain.

---

### Layer 3 — Navigation maps (INDEX.md files + `ls`)

Used by both skills — `ds-guide` to locate things, `update-ds-guide` to detect what has changed.

**Navigation strategy:**
- **Stable folder + content needs context** → `INDEX.md` (one file, name + purpose for every entry)
- **Dynamic folder or self-explanatory filenames** → `ls` (always fresh, no maintenance burden)

**Three INDEX.md files:**

| File | Covers |
|---|---|
| `INDEX.md` (root) | All top-level folders and files, agent-facing, terse, structured |
| `assets/css/INDEX.md` | All subfolders of `assets/css/`: rules per subfolder, frozen vs. editable |
| `assets/css/base/INDEX.md` | One-liner per token file; `--custom-theme` in `:root {}` flagged as the only editable variable |

**`ls` is used for:**
- `components/` — dynamic, new components are added over time
- `assets/css/components/` — frozen but filenames are self-explanatory
- `assets/css/custom/` — dynamic by design
- `assets/css/pages/` — grows per project
- `pages/`, `callbacks/`, `utils/` — grow per project

**`documentation/` folders — treat as invisible everywhere:** The following folders exist in the current repo and are being phased out. Neither skill, no INDEX.md, and no doc file should reference, list, or route to them:

- `assets/css/documentation/`
- `assets/scripts/documentation/`
- `callbacks/documentation/`
- `pages/documentation/`

The `update-ds-guide` skill must also skip these when scanning.

**Component inventory:** `ls components/` lists Python component folders. `ls assets/css/components/` lists CSS component files. These correspond one-to-one. If they diverge, the gap must be noted in `assets/css/INDEX.md`.

**`components/components_extra_design_system`:** Does not follow the standard single-concept naming convention. Contains supplementary DS components that do not fit the main categories. Both `docs/navigation.md` and root `INDEX.md` must explain this explicitly. The `update-ds-guide` skill must not flag it as a gap or anomaly.

---

## Key Design Decisions and Rationale

### Why two separate skills instead of one?
`ds-guide` and `update-ds-guide` have different audiences, different triggers, and different workflows. Merging them into one skill would mean the developer's guide carries maintenance logic that is never used during normal development, and the maintenance tool carries routing logic that is irrelevant during audits. Separation keeps each skill focused and cheap to invoke.

### Why not a vector database / semantic search?
This is manual, deterministic routing — not RAG with embeddings. The DS is small and stable. A routing table is transparent, maintainable, zero-infrastructure, and works inside any AI coding tool without API dependencies.

### Why topic-based routing instead of pattern matching?
Pattern matching (~20+ entries mapping specific question phrasings) becomes unmaintainable as questions evolve. Topic-based routing (~8 entries) is durable and lets the agent handle paraphrasing naturally.

### Why keep hard constraints in the skill AND in best_practices.md?
The skill carries a short hard-constraint list so the agent never violates the rules even on an ambiguous question — without reading `best_practices.md` first. `best_practices.md` provides the full rationale for when someone explicitly asks.

### Why does update-ds-guide confirm before applying changes?
Documentation changes affect every developer using the system. A silent auto-update could introduce incorrect content or remove something intentional. The audit report + confirmation model ensures a human reviews proposed changes before they land.

### Why does update-ds-guide produce a severity rating?
Not all gaps are equal. A `breaking` gap (doc says "X does not exist" but X now exists) needs immediate attention. A `minor` gap (a new utility file not mentioned in navigation) can wait. Severity lets the team prioritize.

### Why separate INDEX.md from docs/navigation.md?
`INDEX.md` is a routing table — short, structured, no prose, for agent orientation. `docs/navigation.md` is human-readable explanation with rationale. They serve different audiences.

### Why is `docs/` not indexed?
The skill already maps every question type to a specific doc file. An extra `docs/INDEX.md` would just be an intermediate hop with no routing value.

### One INDEX.md per decision point, not per folder
An INDEX.md is created only where the agent faces a routing choice it cannot resolve from the parent alone.

### Why AGENTS.md/CLAUDE.md instead of just README install instructions?
README is read by humans, not automatically by AI tools. AGENTS.md and CLAUDE.md are read at session start — the skills are discoverable the moment the developer opens their AI tool.

### Why reference `--custom-theme` by variable name, not line number?
Line numbers change when files are edited. The variable name is stable. All documentation references it as `--custom-theme` in the `:root {}` block of `assets/css/base/colors.css`. A line number is only relevant during the one-time initial implementation of `assets/css/base/INDEX.md`.

### Why is the Figma blog URL not in resources.md?
It is used once, when the implementing agent writes `docs/overview.md`. After that, the conceptual content lives in `overview.md` and the URL serves no runtime purpose.

---

## Composite Question Routing (ds-guide)

Some developer questions span multiple topics. The skill must handle these without silently omitting part of the answer.

**Examples and preferred read order:**

| Question | Read order |
|---|---|
| "How do I add a component that uses DS colors?" | `workflows.md` → `best_practices.md` → `assets/css/base/INDEX.md` |
| "What components exist and how do I use them?" | `ls components/` → `components/<name>/README.md` |
| "Am I allowed to change the typography for this project?" | `best_practices.md` → `docs/overview.md` |

**General rule:** identify the primary intent (task, concept, or rule), route to that doc first, then check the cascade for the secondary intent. Never answer only half of a composite question.

---

## Hard Constraints (always enforced by ds-guide)

1. **No inline styles** — styling must always be in a CSS file
2. **Never touch `assets/css/base/` or `assets/css/components/`** — these are frozen DS files
3. **All new project-specific styles go in `assets/css/custom/`**
4. **Always use CSS variables** — `var(--variable-name)`, never hardcoded values
5. **The `--custom-theme` variable in the `:root {}` block of `assets/css/base/colors.css` is the ONLY allowed color customization — its value is provided by the design team, never self-defined**
6. **Small files, one concern per file** — do not create large monolithic CSS or Python files
7. **Reuse before creating** — check if a component or style already exists before building new
8. **New components must be reusable** — no one-off components tied to a single page

---

## Component Priority Order

When a required component does not exist in the DS:

1. **Native Dash components** — `dash.plotly.com/dash-core-components`
2. **Dash Mantine Components** — `dash-mantine-components.com` (last resort)
3. **Custom component** — must be reusable, placed in `components/`, styled in `assets/css/custom/`

---

## Maintenance Model

**Owner:** The UI/UX cell team owns all files in `docs/` and `docs/skills/`.

**Trigger for a doc update:** run `$update-ds-guide` / `/update-ds-guide`. The skill scans the repo, cross-references against current docs, and produces a prioritized audit report with proposed changes.

**When to run `update-ds-guide`:**
- After adding or removing a component
- After adding or renaming a page
- After establishing or changing a convention
- After any structural change to `assets/css/`
- Periodically as a health check

**INDEX.md files** are maintained by whoever adds or removes files/folders in those directories. They are short and fast to update. `update-ds-guide` will also flag INDEX.md gaps.

**Skill file updates:** when `docs/skills/ds-guide/SKILL.md` or `docs/skills/update-ds-guide/SKILL.md` change, developers and the team re-run the relevant install commands to pick up the new version.

---

## External Resources Referenced

| Resource | Purpose |
|---|---|
| Figma DS | `https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP-%E2%80%93-Design-System-by-Significa` — visual reference for all DS components, includes "Detail Page" template |
| Dash Core Components | `https://dash.plotly.com/dash-core-components` — native components, first priority |
| Dash Mantine Components | `https://www.dash-mantine-components.com/` — UI framework, last resort |
| Lucide Icons | `https://lucide.dev/icons/` — icon name reference for DashIconify |
| Figma Blog (DS 101) | `https://www.figma.com/blog/design-systems-101-what-is-a-design-system/#components-of-a-design-system` — used by the implementing agent when writing `overview.md` only; not a runtime resource, not in `resources.md` |

---

## Project Bootstrap Convention

When starting a new project from this template, the repo should be placed at:

```
your-project/
└── plotly_webapp/
    └── frontend/   ← this repo goes here
```

This separates the Dash frontend from backend modules in the broader project structure. Documented in `docs/workflows.md`.
