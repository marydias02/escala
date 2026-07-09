# Dash Template DS

This is the Dash design system template repository.

## Skills

### DS Guide - developer tool

Answers questions about the design system: structure, rules, workflows, components.

Install:
```bash
mkdir -p .claude/skills/ds-guide && cp docs/skills/ds-guide/SKILL.md .claude/skills/ds-guide/SKILL.md
```
Invoke: `/ds-guide "your question"`

### Update DS Guide - UI/UX team tool

Audits the documentation against the current repo state. Run after components,
pages, or conventions have changed.

Install:
```bash
mkdir -p .claude/skills/update-ds-guide && cp docs/skills/update-ds-guide/SKILL.md .claude/skills/update-ds-guide/SKILL.md
```
Invoke: `/update-ds-guide`

Restart Claude Code after installing. To update a skill after repo changes, re-run its install command.
