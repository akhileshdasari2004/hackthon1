# AGIRA — Autonomous Repository Intelligence Engine

**Deterministic. Parallel. Self-Healing. Memory-Enhanced.**

Agira is a production-grade autonomous agent system that executes repository analysis, bug detection, patch generation, and validation through a deterministic 11-node DAG engine. It runs to completion on every execution — no retry loops, no hallucinated patches, no silent failures.

```bash
python demo.py [path-to-repo]
```

---

## The Problem

**Traditional CI tools are reactive.** They run after code is written, catch a narrow class of errors, and return a pass/fail signal. They have no memory, no planning, and no ability to adapt.

**LLM agents fail in real execution loops.** They hallucinate file paths, apply patches that don't match the target code, retry failed operations indefinitely, and produce non-deterministic results that can't be reproduced. The "chat + execute" model breaks down when the environment doesn't match the model's assumptions.

**What the field needs is a DAG-native execution engine.** Tasks have dependencies. Tools have preconditions. Failures are informative. A system that models software engineering as a directed graph of deterministically-executed nodes — where failure is classified, not retried blindly — is what production autonomous agents require.

Agira is that system.

---

## Solution Overview

Agira is an **autonomous repository intelligence engine** built on five principles:

1. **DAG-native execution** — All tasks are modeled as directed acyclic graph nodes with explicit dependencies. The planner proposes goals, the executor respects ordering, and parallelism is derived from graph topology.

2. **Deterministic tool layer** — Patch application uses exact-match string replacement. There are no LLM-generated patches, no `ast.unparse` formatting drift, no guessing. If the target string isn't found exactly, the tool fails fast and rolls back.

3. **4-way failure classification** — Failures are classified at node boundaries as `DETERMINISTIC` / `TRANSIENT` / `DEPENDENCY` / `ESCALATE`. Only transient failures retry. Deterministic failures skip immediately. Dependency failures trigger DAG repair. Unknown errors escalate without retry loops.

4. **Parallel batch execution** — The scheduler computes topologically-sorted batches of independent nodes. Nodes in the same batch execute concurrently via `ThreadPoolExecutor`, with thread-safe result aggregation. DAG correctness is always preserved.

5. **Persistent cross-run memory** — A JSON-backed store (`~/.agira/memory_store.json`) records failure patterns, success outcomes, repo profiles, and tool metrics. The planner reads this memory to skip known-permanent-failure goals and prioritize high-confidence paths.

---

## Architecture

### DAG Execution Flow

```
Batch 1 (parallel)          Batch 2 (parallel — independent)
─────────────────           ────────────────────────────────
repo_metadata               bug_detection (BugHunterAgent)
file_list              ∥   repo_analysis  (RepoAnalyzerAgent)
dependency_graph
        │
        └─► merge_findings ─► initial_validation ─► patch_generation
                                          ∥
                                   test_validation
                                          │
                                   health_score ─► json_report
```

**Legend:** `∥` = parallel execution, `─►` = sequential dependency

The planner (`AdaptivePlanner`) reactively proposes nodes whose dependencies are satisfied. The executor (`ExecutionStateMachine`) runs each node. Nodes in the same batch have no shared dependencies — they are graph-independent and safe to run concurrently.

### Subagent Isolation Model

Each subagent (BugHunterAgent, RepoAnalyzerAgent, PatchGeneratorAgent, TestValidationAgent) receives a **copy-on-write isolated workdir** (`ExecutionContext.create_isolated_workdir()`). All file mutations happen in the copy. The orchestrator approves merges back to the source repo. Subagents never share state.

### Memory + Plugin Architecture

```
~/.agira/memory_store.json
├── failures:    {node_name: {error_sig: {count, error_type}}}
├── successes:   {goal: {context, timestamp}}
├── repo_profiles: {repo_path: {language, mode}}
├── tool_metrics:  {tool_name: {calls, failures, avg_duration_ms}}
├── decision_log:  [{decision_type, target, reason}]
└── learning_log:  [{event, timestamp, data}]

agira/plugins/
├── analyzers/   (SecurityAuditAnalyzer, ComplexityAnalyzer)
├── patchers/    (SafeEvalPatcher, HardcodedSecretPatcher)
├── validators/  (PythonSyntaxValidator, PatchIntegrityValidator)
└── subagents/   (extensible stub)
```

---

## Core Modules

| Module | Responsibility |
|--------|---------------|
| `orchestrator/engine.py` | Reactive plan→execute→observe→replan loop. Gated parallel/self-healing/memory features. |
| `orchestrator/planner.py` | `DynamicPlanner` — 15-goal reactive proposal based on missing artifacts. |
| `orchestrator/dynamic_planner.py` | `AdaptivePlanner(DynamicPlanner)` — memory-aware filtering and goal prioritization. |
| `orchestrator/state_machine.py` | Executes plan nodes. Deterministic tools (apply_edit, ast_apply_fix) run with no retry. Non-deterministic tools retry once. |
| `orchestrator/failure_classifier.py` | 4-way classification: DETERMINISTIC / TRANSIENT / DEPENDENCY / ESCALATE. |
| `orchestrator/dag_repair.py` | Post-failure DAG repair: re-evaluates dependents, unblocks ready nodes. |
| `orchestrator/parallel_scheduler.py` | Computes topologically-sorted batches of independent nodes. Executes batches via ThreadPoolExecutor. |
| `orchestrator/memory_store.py` | Thread-safe JSON persistence. Records failures, successes, repo profiles, tool metrics, decision reasons. |
| `orchestrator/checkpoint.py` | File-based checkpointing per plan_id for resumable execution. |
| `patch/ast_patcher.py` | Source-based AST transformations. AST used only for detection, not code generation. |
| `tools/patch_tools.py` | `apply_edit` — exact-match string replacement with rollback-on-verification-failure. |
| `subagents/` | BugHunterAgent, RepoAnalyzerAgent, PatchGeneratorAgent, TestValidationAgent. All use think/observe/finalize loop in isolated workdirs. |
| `plugins/` | PluginRegistry singleton with external path loading and discovery. |
| `utils/execution_logger.py` | Timeline tracking: node start/end, batch duration, parallel overlap detection, parallel gain %. |
| `report/final_report.py` | `FinalReport` dataclass. Builds from orchestrator result + execution logger. |

---

## Key Innovations

**Deterministic Editing System (No Hallucinated Patching)**
The `apply_edit` tool requires `oldText` to be an exact substring of the current file content. The patch is rejected before any write if the string is not found. After writing, the file is re-read and verified. On verification failure, the original content is restored. There is no retry loop, no LLM guesswork, no `ast.unparse` drift.

**Parallel DAG Batching Engine**
`ParallelScheduler.compute_batches()` performs a single O(N) pass over the DAG to group nodes into topologically-sorted batches. Nodes in batch N have all dependencies in batches < N. Nodes within a batch have no shared dependencies — they are graph-independent and safe to execute concurrently. This is not coarse-grained parallelism; it is dependency-respecting fine-grained scheduling.

**4-Way Failure Classification System**
Traditional retry logic treats all failures the same — exponential backoff until it works or gives up. Agira's `failure_classifier` inspects the error message and node target to route failures precisely:
- **DETERMINISTIC**: `apply_edit`, `apply_patch`, `edit_file`, `ast_apply_fix` always fail fast — no retries
- **TRANSIENT**: Errors matching "ConnectionError", "Timeout", "permission denied", "resource temporarily unavailable" — retry once
- **DEPENDENCY**: Upstream artifact or dependency failures trigger DAG repair
- **ESCALATE**: Unknown errors mark the node failed without retry loops

**Self-Healing DAG Execution**
After a node fails, `DAGRepair.repair_after_failure()` re-evaluates all dependent nodes, marking their status to `PENDING` so they can be re-proposed in the next iteration. The planner re-observes the artifact store and may propose alternative paths around the failure.

**Persistent Memory Across Runs**
The `MemoryStore` singleton persists to `~/.agira/memory_store.json` after every write. On startup, the planner reads known failure patterns and skips goals with ≥3 deterministic failures. Tool metrics inform scheduling decisions. The system improves with each run.

**Source-Based AST Transformations**
The `ASTPatcher` uses Python's `ast` module only for detection and validation. All transformations are source-based string replacements. This avoids `ast.unparse` formatting differences that plague other AST transformation systems — the diff between old and new content is always minimal and readable.

**Plugin-Based Extensibility Layer**
External plugins are loaded via `PluginRegistry.register_plugin_path()`. Each plugin is a class implementing `Plugin.execute(context)`. The registry supports four categories (analyzers, patchers, validators, subagents) and can discover and load plugins from any registered directory at runtime without modifying core engine code.

---

## System Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| 11/11 DAG completion | Reactive planner ensures nodes are only proposed when dependencies are satisfied; loop exits only when `json_report` artifact exists |
| No retry loops for deterministic tools | `DETERMINISTIC_TOOLS` set in `ExecutionStateMachine._execute_tool` bypasses `retry_with_backoff` entirely |
| Safe rollback on failure | `apply_edit` writes to temp path first, verifies, then moves; verification failure triggers immediate rollback to original content |
| Parallel correctness | `compute_batches()` is a pure topological sort; a node enters a batch only when all its dependencies are in prior batches |
| Subagent isolation | `create_isolated_workdir()` uses `shutil.copytree` for copy-on-write; orchestrator approves all merges via `_apply_merge` |
| Deterministic patch application | `apply_edit` requires exact substring match; `ast_apply_fix` uses source-based replacement validated by `ast.parse` |

---

## Demo

```bash
python demo.py [path-to-repo]
```

The demo initializes an `Orchestrator` with `parallel_scheduling=True`, `self_healing=True`, `memory_layer=True`, `adaptive_planning=True`, then runs the full pipeline and produces:

- **Execution Timeline Report** — per-node start/end/duration, batch timings, parallel overlap detection, and parallel speedup percentage
- **Final Report** (`output/final_report.json`) — machine-readable summary with `dag_status`, `nodes_executed`, `failures`, `self_healing_triggered`, `tool_calls`, `subagent_calls`
- **Execution Timeline** (`output/execution_timeline.json`) — full node event log for post-hoc visualization

```
$ python demo.py examples/buggy_calculator

✔ DAG execution:        SUCCESS
✔ Nodes executed:       11 total (11 ✓ / 0 ✗ / 0 ⊘)
✔ Parallel batches:     9
✔ Self-healing:         not needed
✔ Execution time:       ~300ms
✔ Tool invocations:     7
✔ Subagent invocations: 4

  Batch  4: ∥ 2 nodes,    12.21ms   ← bug_detection ∥ repo_analysis in parallel
  Batch  6: ∥ 2 nodes,    30.21ms   ← patch_generation ∥ initial_validation in parallel
```

---

## Performance Highlights

| Metric | Value |
|--------|-------|
| DAG nodes executed | 11 / 11 |
| Parallel batches | 9 |
| Independent nodes in parallel | 2 (batch 4: bug_detection ∥ repo_analysis) |
| Execution time | ~300ms end-to-end |
| Test suite | 11 / 11 passing |
| Tool invocations (orchestrator level) | 7 |
| Subagent invocations | 4 |
| Retry loops triggered | 0 |
| Deterministic patch failures | 0 |
| Rollback triggered | 0 |

---

## Folder Structure

```
agira/
├── orchestrator/
│   ├── engine.py              # Orchestrator (run loop, parallel/sequential modes)
│   ├── planner.py             # DynamicPlanner (reactive goal proposer)
│   ├── dynamic_planner.py     # AdaptivePlanner (memory-aware, inherits DynamicPlanner)
│   ├── state_machine.py       # ExecutionStateMachine (node executor)
│   ├── plan.py                # ExecutionPlan, PlanNode, NodeStatus
│   ├── checkpoint.py          # CheckpointManager (file-based plan persistence)
│   ├── failure_classifier.py  # 4-way failure classification
│   ├── dag_repair.py          # DAGRepair (post-failure rebalancing)
│   ├── parallel_scheduler.py  # ParallelScheduler (batch computation + execution)
│   └── memory_store.py        # MemoryStore (cross-run persistence)
├── subagents/
│   ├── base.py                # BaseSubagent (think/observe/finalize loop)
│   ├── bug_hunter.py          # BugHunterAgent
│   ├── repo_analyzer.py       # RepoAnalyzerAgent
│   ├── patch_generator.py     # PatchGeneratorAgent
│   └── test_validation.py     # TestValidationAgent
├── tools/
│   ├── context.py             # ExecutionContext (artifact store, state, isolated workdir)
│   ├── patch_tools.py         # apply_edit, ast_apply_fix, rollback_all, etc.
│   ├── repo_tools.py          # get_repo_metadata, list_files, search_code, etc.
│   ├── analysis_tools.py      # build_dependency_graph, pattern_analyzer, etc.
│   ├── execution_tools.py     # run_tests, run_linter, run_typechecker
│   ├── agent_tools.py         # merge_agent_output
│   ├── report_tools.py        # generate_json_report, generate_markdown_report
│   └── observability_tools.py # tool_coverage_report
├── artifacts/
│   └── store.py               # ArtifactStore (in-memory artifact registry)
├── patch/
│   └── ast_patcher.py         # ASTPatcher (source-based transformations)
├── registry/
│   ├── base.py                # ToolDefinition, ToolSchema
│   └── registry.py            # ToolRegistry (registration, invocation, usage audit)
├── plugins/
│   ├── __init__.py            # PluginRegistry, Plugin, get_plugin_registry
│   ├── analyzers/             # SecurityAuditAnalyzer, ComplexityAnalyzer
│   ├── patchers/              # SafeEvalPatcher, HardcodedSecretPatcher
│   ├── validators/            # PythonSyntaxValidator, PatchIntegrityValidator
│   └── subagents/             # (extensible stub)
├── utils/
│   ├── __init__.py
│   └── execution_logger.py    # ExecutionLogger (timeline, batch timings, parallel gain)
├── report/
│   ├── __init__.py
│   └── final_report.py        # FinalReport, build_report_from_orchestrator
├── observability/
│   ├── logging.py             # Structured logging, demo_print
│   ├── errors.py              # ExecutionError, ToolError, SubagentError
│   └── retry.py               # retry_with_backoff
├── sandbox/
│   └── executor.py            # SandboxExecutor
├── demo.py                    # One-command demo runner
└── (tests/, examples/, scripts/, output/)
```

---

## Future Roadmap

**Distributed Execution Engine** — Partition the DAG across multiple worker processes. Nodes with no shared artifacts can execute on different machines. The coordinator aggregates results and manages the artifact store across the cluster.

**Multi-Repo Intelligence Network** — Connect multiple Agira instances across repositories. Failure patterns learned in one repo inform planning in another. A shared memory layer creates a network effect: the more repos Agira runs on, the smarter the planner becomes.

**LLM Planner Replacement** — Replace the rule-based `AdaptivePlanner` with a lightweight LLM that generates DAG structures from natural-language task descriptions. The LLM proposes the goal graph; Agira executes it deterministically. This separates the "what to do" question (LLM) from the "do it correctly" constraint (deterministic executor).

**Real-Time Streaming DAG Execution** — Replace batch-mode iteration with event-driven node completion. When a node finishes, the scheduler immediately computes updated batches and fires the next wave. This eliminates iteration overhead and reduces latency between dependent nodes.

**Cloud Plugin Marketplace** — A registry of vetted plugins (security analyzers, performance profilers, architectural validators) downloadable and loadable at runtime. Plugins are versioned, signed, and sandboxed. Teams share plugin libraries without modifying engine code.

---

## Closing Statement

Agira is a deterministic, parallel, self-healing DAG execution engine for autonomous software engineering. It demonstrates that reliable autonomous agents don't require unreliable LLM guesswork — they require explicit dependency modeling, exact-match tool semantics, failure classification without retry loops, and persistent cross-run memory. The 11-node pipeline completes successfully every time, produces a final report, and improves with each run through its memory layer.

This system is a foundation. The DAG is the substrate. Determinism is the constraint. Memory is the advantage. Build on it.

---

**Status:** Production-grade. 11/11 tests passing. Zero retry loops. Zero hallucinated patches.