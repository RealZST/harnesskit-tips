# Tips 撰写与审核规范

## 内容要求

### 真实有效
- 每一条 tip 必须经过网上核实，确保信息真实准确
- 不能自由发挥或编造功能，措辞应尽量与原文保持一致
- 可以对原文措辞进行精简和修正，但不能改变原意或添加原文没有的信息

### 有信息量
- 每条 tip 必须有实际的 insight，能让用户学到东西
- 不要写废话或显而易见的内容（例如"MCP 各工具都支持但配置文件不同"这种没有 actionable 信息的）
- 具体、可操作：包含具体的文件路径、命令名、设置项等

### 不包含自家广告
- 不要包含 HarnessKit 相关的 tips，因为 HarnessKit 是我们自己的产品
- 给自己打广告会引起用户反感

## 来源要求

### 只使用官方或可信来源
- 官方文档（如 code.claude.com/docs、developers.openai.com、docs.cursor.com）
- 官方博客（如 github.blog、developers.googleblog.com）
- 官方仓库文档（如 github.com/google-gemini/gemini-cli/docs）
- 官方 DevRel 博客（如 atamel.dev — Google Developer Advocate）

### 不使用的来源
- 其他产品的推广网站（如 agents.md 这类推广自己标准的网站）
- SEO 博客或内容农场（如 thepromptshelf.dev、antigravity.codes）
- 个人博客（除非作者是官方 DevRel）
- 未经验证的社区帖子

### source 字段
- 每条 tip 必须附带 source 字段，指向验证该信息的原文页面
- source 是参考来源，tip 文本应与 source 页面内容一致

## 格式要求

### JSON 结构
```json
{
  "agent": "claude",
  "tip": "tip 内容，一到两句话，简洁准确",
  "source": "https://official-docs-url"
}
```

### agent 字段取值
- `claude` — Claude Code
- `codex` — OpenAI Codex CLI
- `gemini` — Gemini CLI
- `cursor` — Cursor Editor
- `antigravity` — Google Antigravity IDE
- `copilot` — GitHub Copilot
- `general` — 跨工具通用（尽量少用，优先归到具体 agent）

## 审核流程

1. **撰写**：从官方文档找到有价值的信息点，精简为一到两句话
2. **核实**：访问 source URL，确认 tip 内容与原文一致
3. **交叉检查**：对比 tip 措辞与原文，避免过度改写或添加原文没有的信息
4. **去重**：确认没有与已有 tips 重复的内容
