# DeepSeek Harness (dsh) AI Agent Skill Specification

This document is a technical specification designed for an AI Agent to build a "consultation and query skill" for DeepSeek Harness (dsh). The goal is to equip any LLM with the capability to accurately retrieve, explain, and interact with the architecture, deployment, and operation of DeepSeek Harness based on its official repository structure and documentation.

---

## 1. Context & Core Vision
DeepSeek Harness (dsh) is an open-source agent harness developed by **DeepSeek AI**. Its core philosophy is: **"Everything is a plugin. Every run is traceable."**

*   **Harness vs. Model**: The model represents the reasoning engine ("the soul"), while the harness enables the agent to interact with its environment, execute tools, and persist in real-world environments.
*   **Kernel Core**: Powered by **Cordis**, which acts as the system kernel to manage plugin mounting, unmounting, and dependency injection. Agent capabilities are fully modularized inside plugins.
*   **Traceability**: Every input, reasoning step, tool call/result, subagent scheduling, and context injection is stored in an **append-only session log**. This event stream enables advanced trajectory views, session resuming, forking, searching, and replaying.

---

## 2. Technical Capabilities & Runtime Modes
The skill designed by the AI Agent must expose query mechanisms for the following four runtime modes:

1.  **Standard Mode**:
    *   *Definition*: A full coding agent with comprehensive local tools.
    *   *Features*: File editing, persistent shell, local file search, web search, custom skills, goal planning, subagent spawning, and structured workflows.
2.  **Code Mode**:
    *   *Definition*: Standard mode tools exposed via a custom SDK.
    *   *Features*: Exposes tools through the **Code Mode SDK**, allowing the model to compile and orchestrate multi-step tool calls natively inside a single **TypeScript** program.
3.  **Minimal Mode**:
    *   *Definition*: A lightweight, restricted benchmark environment.
    *   *Features*: Only provides a persistent shell tool (`bash`) and an editor tool (`str_replace_editor`). Designed to benchmark model capabilities in an isolated workspace.
4.  **Creator Mode**:
    *   *Definition*: Built for authoring custom presets.
    *   *Features*: Standard mode capabilities combined with runtime inspection, plugin sandboxing experiments, and authoring guidelines to create custom agent presets.

---

## 3. Official Repository Map & Structure (GitHub)
The AI Agent must use this official file mapping to guide any LLM querying files or trying to understand the repository structure:

*   **`/apps` & `/packages`**: Contains the core TypeScript application layers and modular packages.
*   **`/docs`**: General documentation, including user guides, development guides (`/docs/development.md`), and architecture references (`/docs/architecture.md`).
*   **`/native` & `/python`**: Low-level runtime components and Python SDK integration files.
*   **`/vendor`**: External dependencies, including Cordis kernel distributions (e.g., Cordis 4.0.2).
*   **`/website`**: Source code for the developer preview web interface.
*   **Key Root Files**:
    *   `README.md`: Project overview, quickstart instructions, and GitHub configuration details.
    *   `AGENTS.md`: Specific developer guidelines for designing and executing AI Agents.
    *   `BENCHMARK.md`: Procedures for testing and running evaluations on models.
    *   `CLAUDE.md`: Symlinks and context instructions for agent environments.
    *   `SAFETY.md`: Crucial security guidelines to review before running the harness locally.
    *   `LICENSE`: MIT License information.

---

## 4. Installation & Deployment Procedures
The skill must be able to provide accurate steps for running DeepSeek Harness:

### Option A: Direct Launch via npm
Designed for rapid testing without cloning. Requires Node.js.
```bash
npx @deepseek-ai/dsh web
```
*Note*: Starts the Web UI at `http://127.0.0.1:3080` by default and auto-opens in the default browser.

### Option B: Build and Run From Source
For developers modifying the core harness or building custom plugins.
```bash
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh web
```
*Note*: `pnpm run build` compiles repository assets. subsequent `pnpm dsh web` launches utilizing those built artifacts.

---

## 5. Blueprint for the LLM Consultation Skill
To enable an LLM to query this information, the AI Agent should design a skill interface (such as an MCP server, a toolset, or a system prompt extension) with the following functional capabilities:

```typescript
interface DeepSeekHarnessConsultantSkill {
  /**
   * Retrieves the architectural explanation of DSH, including the Cordis kernel plugin system.
   */
  getArchitectureOverview(): ArchitectureDetails;

  /**
   * Provides step-by-step setup assistance for npm or source builds.
   */
  getInstallationInstructions(method: 'npm' | 'source'): string;

  /**
   * Explains the capabilities, differences, and use-cases of the 4 runtime modes.
   */
  explainRuntimeMode(mode: 'standard' | 'code' | 'minimal' | 'creator'): ModeSpecs;

  /**
   * Explains how traceability is maintained via the append-only log and how to parse trajectories.
   */
  getTraceabilityGuide(): TraceabilitySpecs;

  /**
   * Maps a directory/file name to its purpose based on the repository layout.
   */
  resolveRepoFile(path: string): string;
}
```

---
*Created dynamically for DeepSeek Harness Agent Integrations. Sources: deepseek-ai/deepseek-harness GitHub and official developer preview documentation.*
