---
name: knowledgebase
description: "Generic RAG query skill - Retrieve any information from the local knowledge base and generate structured reports, summaries, or Q&A responses. Use for: product comparisons, technical analysis, documentation generation, competitive analysis, benchmark reports, specification queries, or any knowledge base retrieval task."
trigger: "When user needs to retrieve any information for any purpose."
user-invocable: true
allow-model-invocation: true
priority: high
---

# Knowledge Base - Generic ECRAG Information Retrieval & Report Generation

Use this skill when the user wants to retrieve information from the local knowledge base and generate structured outputs (reports, summaries, comparisons, documentation).

## 📋 QUICK START - Do This Immediately

When user asks a question, **execute the curl-based ecrag wrapper via Bash**:

```javascript
Bash({
  command: '<SKILL_DIR>/ecrag query "user\'s question here"',
  description: "Query knowledge base"
})
```

Then parse the output and present it to the user. That's it!

**Example:** User asks "What is Intel Core Ultra 358H?"

**Your immediate action:**
```javascript
Bash({
  command: '<SKILL_DIR>/ecrag query "What is Intel Core Ultra 358H?"',
  description: "Query KB for Intel Core Ultra 358H"
})
// Wait for output, then present results to user
```

## 🚨 CRITICAL EXECUTION REQUIREMENT 🚨

**YOU MUST EXECUTE COMMANDS USING THE BASH TOOL - DO NOT JUST DESCRIBE THEM!**

To query the knowledge base, you MUST:
1. Use the **Bash tool** to execute `<SKILL_DIR>/ecrag query "your question"`
2. Wait for the command to complete and get the output
3. Parse the output and present it to the user

Example Bash tool call:
```
Bash(
  command: '<SKILL_DIR>/ecrag query "What is Intel Core Ultra 358H?"',
  description: "Query knowledge base for Intel Core Ultra 358H specifications"
)
```

## Core Principles

⚠️ **ALWAYS use Bash tool to execute `<SKILL_DIR>/ecrag` commands** ⚠️
⚠️ **Primary information source is `<SKILL_DIR>/ecrag` output via Bash tool** ⚠️
⚠️ **Wait for Bash execution to complete before proceeding** ⚠️
⚠️ **Monitor long-running commands with session ID until `completed`** ⚠️

The main session can handle simple queries directly. For complex tasks, launch sub-agents.

## Core Tool

### curl-based ecrag Wrapper (Execute via Bash Tool)

Located at `<SKILL_DIR>/ecrag`, this shell script calls the ECRAG HTTP API directly with `curl`. It does not require Python, a virtual environment, the `ecrag` CLI package, or `jq`.

**CRITICAL: You MUST use the Bash tool to execute these commands!**

#### Usage via Bash Tool

```javascript
// Simple query (uses 'rag' mode by default)
Bash({
  command: '<SKILL_DIR>/ecrag query "your question here"',
  description: "Query knowledge base"
})
```

Optional query settings:

```bash
<SKILL_DIR>/ecrag query "your question" --mode rag --top-n 5 --max-tokens 512
```

Modes:
- `rag` (default): full retrieval and generation through `POST /v1/chatqna` on the mega service
- `retrieve`: context retrieval only through `POST /v1/retrieval`
- `mega`: alias for the full ChatQnA request

Connection settings are configured with environment variables:

```bash
export ECRAG_HOST="http://localhost"
export ECRAG_PORT="16010"
export ECRAG_MEGA_PORT="16011"
export ECRAG_CONNECT_TIMEOUT="10"
```

**Important**: 
- `curl` must be available in `PATH`
- ALWAYS use Bash tool to execute commands
- Script execution takes time - wait for output
- For long-running commands, check status with session ID
- Never skip execution - always run the command!
