# Tips Writing & Review Guidelines

## Content Requirements

### Accuracy
- Every tip must be verified online against its source before inclusion
- Do not fabricate features or embellish — wording should closely match the original documentation
- Minor rewording for brevity is acceptable, but do not change the meaning or add information not present in the source

### Value
- Every tip must provide real insight — something users wouldn't easily discover on their own
- Do not include obvious or low-information tips (e.g., "MCP is supported by multiple tools but each has its own config" — not actionable)
- Be specific and actionable: include concrete file paths, command names, setting keys, etc.

### Actionable, Not Descriptive
- Tips must be usage tricks that users can immediately apply, not descriptions of how internals work
- Bad: "Codex concatenates instruction files from root to your working directory" — this just describes a mechanism
- Good: "Override any config key at runtime with -c key=value" — this tells users what to DO
- Avoid tips that merely describe: storage locations, loading order, file precedence rules, or what files a tool reads
- If a mechanism is worth mentioning, frame it as a trick: "Put API-specific rules in subdirectory CLAUDE.md files — they load on demand only when Claude works in that directory, saving context tokens"
- Prefer high-leverage interaction tips over config trivia when possible: slash commands, mention syntax, prompt prefixes, pickers, and workflow shortcuts usually make better Tip of the Day content than one-off config keys

### No Self-Promotion
- Do not include tips about HarnessKit — it is our own product
- Self-promotion in tips will annoy users and undermine trust

## Source Requirements

### Accepted Sources
- Official documentation (e.g., code.claude.com/docs, developers.openai.com, docs.cursor.com)
- Official blogs (e.g., github.blog, developers.googleblog.com)
- Official repository docs (e.g., github.com/google-gemini/gemini-cli/docs)

### Rejected Sources
- Product promotion websites (e.g., agents.md — promotes its own standard)
- SEO blogs or content farms (e.g., thepromptshelf.dev, antigravity.codes)
- Personal blogs, including DevRel blogs on personal domains
- Unverified community posts

### Source Field
- Every tip must include a `source` field pointing to the page where the information was verified
- The tip text should be consistent with what the source page actually says

## Format

### JSON Structure
```json
{
  "agent": "claude",
  "tip": "Tip content — one to two sentences, concise and accurate.",
  "source": "https://official-docs-url"
}
```

### Agent Field Values
- `claude` — Claude Code
- `codex` — OpenAI Codex CLI
- `gemini` — Gemini CLI
- `cursor` — Cursor Editor
- `antigravity` — Google Antigravity IDE
- `copilot` — GitHub Copilot
- `general` — Cross-tool (use sparingly; prefer assigning to a specific agent)

## Review Process

1. **Write** — Find a valuable insight from official documentation and condense it into one to two sentences
2. **Verify** — Visit the source URL and confirm the tip content matches the original text
3. **Cross-check** — Compare tip wording against the source to catch any embellishment or added claims not in the original
4. **Deduplicate** — Ensure no overlap with existing tips
