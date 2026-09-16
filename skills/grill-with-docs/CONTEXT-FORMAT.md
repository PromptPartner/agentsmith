# Project language format

Use `CONTEXT.md` as a glossary of canonical project language, not as a specification or an
implementation guide.

```markdown
# <Context name>

<One or two sentences defining the context boundary.>

## Language

**<Canonical term>**: <One or two sentences defining what it is.>
_Avoid_: <ambiguous or rejected synonyms>
```

Define what it is, not how it is implemented. Include only concepts specific to this project.
Choose one canonical term, keep definitions tight, and group terms only when a natural cluster
exists.

For multiple bounded contexts, keep a root `CONTEXT-MAP.md` that links each context's glossary and
states the relationships between contexts. Follow an existing map and glossary structure before
creating a new convention.

---
*Adapted from Matt Pocock's
[`CONTEXT-FORMAT.md`](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/CONTEXT-FORMAT.md)
([MIT](https://github.com/mattpocock/skills/blob/main/LICENSE), 2026).*
