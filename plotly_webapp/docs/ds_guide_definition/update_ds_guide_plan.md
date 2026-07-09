# Update DS Guide — Implementation Plan

> Before implementing, read `docs/ds_guide_architecture.md` for full context on why decisions were made.
> This plan covers the `update-ds-guide` maintenance skill and the integration files that wire both skills together (AGENTS.md, CLAUDE.md, README.md).
> All files from `docs/ds_guide_plan.md` must exist before starting this plan.

---

## Prerequisites

The following must already exist before implementing anything in this plan:

- [ ] All INDEX.md files (`INDEX.md`, `assets/css/INDEX.md`, `assets/css/base/INDEX.md`)
- [ ] All docs (`docs/overview.md`, `docs/navigation.md`, `docs/best_practices.md`, `docs/workflows.md`, `docs/resources.md`)
- [ ] `docs/skills/ds-guide/SKILL.md`

---

## Files to Create

### 1. `docs/skills/update-ds-guide/SKILL.md`

**Purpose:** UI/UX team maintenance skill. Audits the documentation against the current repo state, produces a structured findings report, and applies approved updates. Invoked after repo changes to keep documentation accurate.

**Audience:** UI/UX cell team. This skill is not for developer use — developers use `ds-guide`.

**Inspiration:** This skill follows the workflow and report structure of the `docs-sync` skill pattern: phased approach (read docs → scan repo → cross-reference → report → confirm → apply), four-class finding taxonomy, and "aggressive finding, conservative fixing" mindset, adapted for the specific documentation structure of this repo.

---

**Content requirements:**

#### Role definition

```
You are the documentation maintenance agent for the Dash Template DS.
Your job is to audit the current documentation against the current repo state,
identify what is missing, incorrect, outdated, or structurally misplaced,
and propose precise updates. You are run by the UI/UX cell team after repo changes.
You are not a developer guide — direct developers to ds-guide instead.
```

#### Mindset

Apply this mindset throughout:

- Treat all documentation as unverified until checked against the current repo.
- Treat the actual repo files and folder structure as the primary ground truth.
- Be aggressive in finding issues, conservative in applying fixes.
- Focus on correctness of paths, component names, rules, and workflows before wording.
- Do not invent new rules or conventions — only document patterns that are clearly and consistently present in the code.
- Do not widen the edit scope just because adjacent content could be improved.

#### Workflow

**Step 1 — Read current documented state first**

Read all of these before scanning the repo. Build an explicit understanding of what is currently claimed:

- `docs/overview.md`
- `docs/navigation.md`
- `docs/best_practices.md`
- `docs/workflows.md`
- `docs/resources.md`
- `INDEX.md` (root)
- `assets/css/INDEX.md`
- `assets/css/base/INDEX.md`

**Step 2 — Scan the repo**

| Scan | Skip | Purpose |
|---|---|---|
| `ls components/` | — | Detect new/removed/renamed components |
| Read `README.md` for any component not yet documented | — | Understand what the component does |
| `ls assets/css/components/` | — | Detect new/removed component CSS |
| `ls pages/` | `documentation/` | Detect new/removed pages |
| `ls callbacks/` | `documentation/` | Detect structural changes |
| `ls assets/css/custom/` | — | Detect new project-specific styles |
| `ls assets/css/pages/` | — | Detect new page styles |
| Skim code in new components/pages | — | Detect new conventions not yet in best_practices.md |

**Never scan or mention:**
- `assets/css/documentation/`
- `assets/scripts/documentation/`
- `callbacks/documentation/`
- `pages/documentation/`

These folders are being phased out and are invisible to this system.

**Known exception:** `components/components_extra_design_system` does not follow the standard naming convention intentionally. Do not flag it as an anomaly.

**Step 3 — Cross-reference**

Map what was found in the scan against what is documented. Use this table:

| Found in scan | Check these docs |
|---|---|
| New or removed component in `components/` | `docs/navigation.md`, root `INDEX.md` |
| New or removed component CSS in `assets/css/components/` | `assets/css/INDEX.md` |
| New or removed page in `pages/` | `docs/navigation.md` |
| New pattern in code not yet in best_practices | `docs/best_practices.md` |
| New workflow implied by a new page or component | `docs/workflows.md` |
| Changed folder structure | Relevant `INDEX.md` |

For each item found: verify the specific claim in the doc. Check path names, component names, and rule descriptions precisely — do not accept summaries as correct without verifying the source.

**Step 4 — Classify findings**

Use four categories:

- **Missing** — behavior, component, or workflow exists in the repo but is not documented
- **Incorrect** — doc describes the wrong name, path, rule, or behavior
- **Outdated** — doc describes something that no longer exists or has changed
- **Structural** — information exists but is misplaced, duplicated, or hard to discover

**Step 5 — Produce the Docs Sync Report and ask for approval**

Output the full report before making any changes. Ask for confirmation before proceeding.

Report structure:

```
## Docs Sync Report

### Scope
- Documentation files reviewed: [list]
- Repo areas scanned: [list]
- Excluded: all documentation/ folders (phased out)

### Findings by doc file

#### [doc file name]
- Finding type: Missing / Incorrect / Outdated / Structural
- Evidence: [file path + specific item]
- Proposed change: [exact text to add, modify, or remove]
- Severity: breaking / gap / minor

[repeat for each doc file with findings]

### Files with no issues
[list]

### Proposed edits summary
[doc file → one-line change summary]

### Questions for the team
[anything ambiguous that needs human judgment]
```

**Severity definitions:**
- `breaking` — doc actively misleads (e.g., says a component does not exist but it does, or gives a wrong path)
- `gap` — missing information a developer would need
- `minor` — cosmetic, low-impact, or nice-to-have

**Step 6 — Apply updates if approved**

- Apply changes one file at a time
- Confirm each file before editing
- Preserve the existing doc style, naming patterns, and structure
- Make targeted fixes only — do not expand scope to adjacent improvements
- After all updates: remind the team to re-run the skill install commands if either `SKILL.md` was modified

#### What this skill does NOT do

- Does not answer developer questions — direct developers to `ds-guide`
- Does not modify `assets/css/base/` token files — those are frozen
- Does not update `assets/css/base/INDEX.md` unless a token file was actually added or removed
- Does not invent new rules — only documents patterns clearly and consistently present in the code
- Does not scan or reference any `documentation/` folder

---

## Files to Create

### 2. `AGENTS.md` (root)

**Purpose:** Read automatically by Codex at session start. Points to both skills with install commands. Minimal — this is a pointer, not the guide.

**Note:** Created here (after both skills exist) so the install commands reference real files.

**Content:**

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

Audits the documentation against the current repo state. Run after components,
pages, or conventions have changed.

Install:
```bash
mkdir -p .agents/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .agents/skills/update-ds-guide/SKILL.md
```
Invoke: `$update-ds-guide`

Restart Codex after installing. To update a skill after repo changes, re-run its install command.
```

---

### 3. `CLAUDE.md` (root)

**Purpose:** Read automatically by Claude Code at session start. Same purpose as `AGENTS.md` but for Claude Code, which uses `.claude/skills/`.

**Content:**

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

Audits the documentation against the current repo state. Run after components,
pages, or conventions have changed.

Install:
```bash
mkdir -p .claude/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .claude/skills/update-ds-guide/SKILL.md
```
Invoke: `/update-ds-guide`

Restart Claude Code after installing. To update a skill after repo changes, re-run its install command.
```

---

## Files to Modify

### 4. `README.md`

**Changes required:**

**REMOVE:** The entire `## Status` section. It references "later iterations" — those iterations are now this implementation.

**REPLACE:** The `## Documentation` section (currently says "TBD") with:

```markdown
## Documentation

The `docs/` folder contains the design system knowledge base:

- `docs/overview.md` — what is a design system, tokens, reusable components, the Figma
- `docs/navigation.md` — how the repo is organized, where to find things
- `docs/best_practices.md` — rules, conventions, and what never to do
- `docs/workflows.md` — step-by-step guides for common tasks
- `docs/resources.md` — all external links (Figma, Dash docs, icons, etc.)
```

**ADD:** A new `## AI Design System Guide` section, placed **after `## Who This Is For`** and **before `## Prerequisites`**.

```markdown
## AI Design System Guide

This repository includes two skills for Codex and Claude Code.

**`ds-guide`** — answers questions about the design system (structure, rules, components, workflows).
**`update-ds-guide`** — UI/UX team tool: audits the docs against the current repo state after changes.

### Install

**Codex:**
```bash
mkdir -p .agents/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .agents/skills/ds-guide/SKILL.md
mkdir -p .agents/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .agents/skills/update-ds-guide/SKILL.md
```

**Claude Code:**
```bash
mkdir -p .claude/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .claude/skills/ds-guide/SKILL.md
mkdir -p .claude/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .claude/skills/update-ds-guide/SKILL.md
```

Restart your AI tool after running.

### Usage

| Skill | Codex | Claude Code | Who runs it |
|---|---|---|---|
| DS Guide | `$ds-guide "question"` | `/ds-guide "question"` | Developers |
| Update DS Guide | `$update-ds-guide` | `/update-ds-guide` | UI/UX team |
```

**ADD:** A `## Theme Color` section after `## Working Model`:

```markdown
## Theme Color

The only color customization allowed in this design system is the theme hue.

Open `assets/css/base/colors.css` and locate the `--custom-theme` variable inside `:root {}`:

```css
--custom-theme: <HSL value>;
```

The HSL value is provided by the design team. Never define your own.
This is the only variable in `assets/css/base/` you are permitted to change.
```

**Also update** the `## Working Model` section if needed to reference `docs/best_practices.md`.

---

## Implementation Order

1. Verify all prerequisites from `docs/ds_guide_plan.md` are complete
2. Create `docs/skills/update-ds-guide/SKILL.md` (depends on all docs and ds-guide skill existing — cross-reference map must reference real files)
3. Create `AGENTS.md` at root (both skills now exist)
4. Create `CLAUDE.md` at root
5. Update `README.md` (final step — depends on all new sections being accurate)

---

## Quality Checks

Before considering this plan complete:

- [ ] `docs/skills/update-ds-guide/SKILL.md` cross-reference map references only files that actually exist
- [ ] `update-ds-guide` SKILL.md explicitly skips all four `documentation/` folders in its scan step
- [ ] `update-ds-guide` SKILL.md does not flag `components_extra_design_system` as an anomaly
- [ ] `update-ds-guide` SKILL.md report format section matches the structure specified in this plan
- [ ] `AGENTS.md` and `CLAUDE.md` mention both skills with correct install commands
- [ ] `AGENTS.md` and `CLAUDE.md` are minimal — install commands and invocation only, no routing logic
- [ ] README `## Status` section is fully removed
- [ ] README `## AI Design System Guide` section is present, placed above `## Prerequisites`, and documents both skills with the usage table
- [ ] README `## Theme Color` section is present with correct variable name and `:root {}` reference
- [ ] No file contains placeholder text or "TBD"
