# Learning Guide: Multi-Agent Code Review System

This document explains the architecture, design patterns, and flow of the multi-agent code review system. By the end, you'll understand how to build agentic AI systems with parallel execution, provider abstraction, and synthesis patterns.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Architecture Overview](#architecture-overview)
3. [End-to-End Flow](#end-to-end-flow)
4. [Provider Abstraction Pattern](#provider-abstraction-pattern)
5. [Agent Design Pattern](#agent-design-pattern)
6. [Parallel Execution with asyncio](#parallel-execution-with-asyncio)
7. [The Reviewer Agent: Synthesis Pattern](#the-reviewer-agent-synthesis-pattern)
8. [Prompt Engineering Patterns](#prompt-engineering-patterns)
9. [Error Handling Strategies](#error-handling-strategies)
10. [Key Takeaways](#key-takeaways)

---

## Core Concepts

### What is an Agentic System?

An **agentic system** is one where AI models act autonomously to accomplish tasks. Instead of a single prompt-response, agents:
- Have specialized roles and expertise
- Can be composed together (multi-agent)
- Make decisions based on context
- Produce structured outputs

### Multi-Agent vs Single-Agent

```mermaid
flowchart LR
    subgraph Single["Single Agent Approach"]
        A[User Input] --> B[One Large Prompt]
        B --> C[Single Response]
    end

    subgraph Multi["Multi-Agent Approach"]
        D[User Input] --> E[Security Agent]
        D --> F[Bug Agent]
        D --> G[Style Agent]
        E & F & G --> H[Reviewer Agent]
        H --> I[Final Response]
    end
```

**Why Multi-Agent?**
| Aspect | Single Agent | Multi-Agent |
|--------|--------------|-------------|
| Specialization | Generic knowledge | Deep expertise per domain |
| Parallelism | Sequential | Concurrent execution |
| Cost | One expensive call | Multiple cheap calls + one synthesis |
| Reliability | Single point of failure | Graceful degradation |
| Maintainability | Monolithic prompt | Modular, testable prompts |

---

## Architecture Overview

### High-Level Components

```mermaid
flowchart TB
    subgraph Input["Input Layer"]
        CLI[CLI - click]
        GIT[Git Utils]
        GH[GitHub CLI]
    end

    subgraph Orchestration["Orchestration Layer"]
        ORCH[Orchestrator]
    end

    subgraph Agents["Agent Layer"]
        SEC[Security Agent]
        BUG[Bug Agent]
        STY[Style Agent]
        REV[Reviewer Agent]
    end

    subgraph Provider["Provider Layer"]
        PROT[LLMProvider Protocol]
        BED[Bedrock Provider]
        SDK[Agent SDK Provider]
    end

    subgraph Output["Output Layer"]
        MD[Markdown Formatter]
        JSON[JSON Output]
        RICH[Rich Console]
    end

    CLI --> GIT & GH
    GIT & GH --> ORCH
    ORCH --> SEC & BUG & STY
    SEC & BUG & STY --> REV
    ORCH --> REV
    SEC & BUG & STY & REV --> PROT
    PROT --> BED & SDK
    ORCH --> MD & JSON
    MD --> RICH

    style SEC fill:#ff6b6b,color:#fff
    style BUG fill:#ffd93d,color:#000
    style STY fill:#6bcb77,color:#fff
    style REV fill:#4d96ff,color:#fff
```

### Layer Responsibilities

| Layer | Responsibility | Key Files |
|-------|---------------|-----------|
| **Input** | Parse CLI args, fetch git diffs | `cli.py`, `git_utils.py` |
| **Orchestration** | Coordinate agents, manage flow | `orchestrator.py` |
| **Agent** | Specialized code analysis | `agents/*.py` |
| **Provider** | Abstract LLM calls | `providers/*.py` |
| **Output** | Format results | `output/markdown.py` |

---

## End-to-End Flow

### Complete Request Flow

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant CLI
    participant GitUtils
    participant Orchestrator
    participant SecurityAgent
    participant BugAgent
    participant StyleAgent
    participant ReviewerAgent
    participant BedrockProvider
    participant Output

    User->>CLI: code-review https://github.com/org/repo/pull/123
    CLI->>GitUtils: parse_github_pr_url()
    GitUtils-->>CLI: GitHubPR(owner, repo, number)
    CLI->>GitUtils: get_github_pr_diff(pr)
    GitUtils-->>CLI: diff string

    CLI->>Orchestrator: review_diff(diff, languages)
    Orchestrator->>GitUtils: parse_diff(diff)
    GitUtils-->>Orchestrator: List[FileChange]
    Orchestrator->>GitUtils: filter_by_language(files)
    GitUtils-->>Orchestrator: filtered files

    Note over Orchestrator,StyleAgent: Phase 1: Parallel Agent Execution

    par Security Analysis
        Orchestrator->>SecurityAgent: review(files_data)
        SecurityAgent->>BedrockProvider: invoke(messages, system_prompt, "fast")
        BedrockProvider-->>SecurityAgent: ModelResponse
        SecurityAgent-->>Orchestrator: ReviewResult
    and Bug Detection
        Orchestrator->>BugAgent: review(files_data)
        BugAgent->>BedrockProvider: invoke(messages, system_prompt, "fast")
        BedrockProvider-->>BugAgent: ModelResponse
        BugAgent-->>Orchestrator: ReviewResult
    and Style Review
        Orchestrator->>StyleAgent: review(files_data)
        StyleAgent->>BedrockProvider: invoke(messages, system_prompt, "fast")
        BedrockProvider-->>StyleAgent: ModelResponse
        StyleAgent-->>Orchestrator: ReviewResult
    end

    Note over Orchestrator,ReviewerAgent: Phase 2: Synthesis

    Orchestrator->>ReviewerAgent: synthesize(agent_results, files_context)
    ReviewerAgent->>BedrockProvider: invoke(findings_summary, system_prompt, "smart")
    BedrockProvider-->>ReviewerAgent: ModelResponse (JSON verdict)
    ReviewerAgent-->>Orchestrator: FinalVerdict

    Orchestrator->>Orchestrator: ReviewReport.from_agent_results(results, verdict)
    Orchestrator-->>CLI: ReviewReport

    CLI->>Output: format_report(report)
    Output-->>CLI: markdown string
    CLI-->>User: Rich console output
```

### Data Flow Through the System

```mermaid
flowchart LR
    subgraph Input
        DIFF[Git Diff String]
    end

    subgraph Parsing
        FC[FileChange Objects]
    end

    subgraph AgentInput
        FD[files_data: List of Dict]
    end

    subgraph AgentOutput
        F1[Security Findings]
        F2[Bug Findings]
        F3[Style Findings]
    end

    subgraph ReviewerInput
        RR[List of ReviewResult]
    end

    subgraph FinalOutput
        V[FinalVerdict]
        REP[ReviewReport]
    end

    DIFF --> FC --> FD
    FD --> F1 & F2 & F3
    F1 & F2 & F3 --> RR
    RR --> V
    RR --> REP
    V --> REP
```

---

## Provider Abstraction Pattern

### Why Abstract the Provider?

The system is designed to work with multiple LLM backends:
- **AWS Bedrock** (current) - Production ready
- **Claude Agent SDK** (future) - Enhanced capabilities
- **Other providers** - OpenAI, local models, etc.

### The Protocol Pattern

```mermaid
classDiagram
    class LLMProvider {
        <<Protocol>>
        +invoke(messages, system_prompt, model_tier) ModelResponse
        +stream(messages, system_prompt, model_tier) AsyncIterator
    }

    class BedrockProvider {
        -client: boto3.Client
        -MODEL_MAP: dict
        +invoke() ModelResponse
        +stream() AsyncIterator
    }

    class AgentSDKProvider {
        -agent: Agent
        +invoke() ModelResponse
        +stream() AsyncIterator
    }

    class BaseAgent {
        -provider: LLMProvider
        -model_tier: str
        +review(files) ReviewResult
    }

    LLMProvider <|.. BedrockProvider : implements
    LLMProvider <|.. AgentSDKProvider : implements
    BaseAgent --> LLMProvider : uses
```

### Code Pattern

```python
# providers/base.py - The Protocol
from typing import Protocol

class LLMProvider(Protocol):
    """Protocol for LLM providers - any class with these methods works."""

    async def invoke(
        self,
        messages: list[Message],
        system_prompt: str,
        model_tier: str = "fast",
    ) -> ModelResponse:
        ...

# providers/bedrock.py - Implementation
class BedrockProvider:
    """Implements LLMProvider without explicit inheritance."""

    MODEL_MAP = {
        "fast": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "smart": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }

    async def invoke(self, messages, system_prompt, model_tier="fast"):
        model_id = self.MODEL_MAP[model_tier]
        # ... boto3 call
        return ModelResponse(content=response)
```

### Model Tiers: Cost vs Quality Tradeoff

```mermaid
flowchart LR
    subgraph FastTier["Fast Tier (Haiku 4.5)"]
        direction TB
        F1[Lower cost]
        F2[Faster response]
        F3[Good for focused tasks]
    end

    subgraph SmartTier["Smart Tier (Sonnet 4.5)"]
        direction TB
        S1[Higher capability]
        S2[Better reasoning]
        S3[Good for synthesis]
    end

    subgraph Usage
        SEC[Security Agent] --> FastTier
        BUG[Bug Agent] --> FastTier
        STY[Style Agent] --> FastTier
        REV[Reviewer Agent] --> SmartTier
    end
```

---

## Agent Design Pattern

### Base Agent Architecture

```mermaid
classDiagram
    class BaseAgent {
        <<abstract>>
        #provider: LLMProvider
        #model_tier: str
        +AGENT_NAME: str
        +FINDING_CATEGORY: FindingCategory
        +get_system_prompt()* str
        +review(files, context) ReviewResult
        #_invoke(user_message) str
        #_build_review_message(files) str
        #_parse_findings(response) List~Finding~
    }

    class SecurityAgent {
        +AGENT_NAME = "security"
        +FINDING_CATEGORY = SECURITY
        +get_system_prompt() str
    }

    class BugAgent {
        +AGENT_NAME = "bugs"
        +FINDING_CATEGORY = BUG
        +get_system_prompt() str
    }

    class StyleAgent {
        +AGENT_NAME = "style"
        +FINDING_CATEGORY = STYLE
        +get_system_prompt() str
    }

    class ReviewerAgent {
        +AGENT_NAME = "reviewer"
        +synthesize(results, context) FinalVerdict
        #_format_findings(results) str
        #_parse_verdict(content) FinalVerdict
    }

    BaseAgent <|-- SecurityAgent
    BaseAgent <|-- BugAgent
    BaseAgent <|-- StyleAgent
    BaseAgent <.. ReviewerAgent : similar pattern
```

### Agent Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Initialized: __init__(provider, model_tier)
    Initialized --> BuildingPrompt: review(files) called
    BuildingPrompt --> InvokingLLM: _build_review_message()
    InvokingLLM --> ParsingResponse: provider.invoke()
    ParsingResponse --> ReturningResult: _parse_findings()
    ReturningResult --> [*]: ReviewResult

    ParsingResponse --> ErrorHandling: JSON parse error
    ErrorHandling --> ReturningResult: Return empty findings
```

### Template Method Pattern

The `BaseAgent` uses the **Template Method** pattern:

```python
class BaseAgent(ABC):
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Subclasses provide their specialized prompt."""
        raise NotImplementedError

    async def review(self, files, context=None) -> ReviewResult:
        """Template method - same flow for all agents."""
        # 1. Build the message (common)
        user_message = self._build_review_message(files, context)

        # 2. Invoke LLM (common)
        response = await self._invoke(user_message)

        # 3. Parse findings (common)
        findings = self._parse_findings(response)

        return ReviewResult(
            agent_name=self.AGENT_NAME,
            findings=findings,
            files_reviewed=[f["path"] for f in files],
        )
```

---

## Parallel Execution with asyncio

### Why Parallel?

```mermaid
gantt
    title Sequential vs Parallel Execution
    dateFormat X
    axisFormat %s

    section Sequential
    Security Agent    :0, 3
    Bug Agent         :3, 6
    Style Agent       :6, 9
    Reviewer Agent    :9, 11
    Total: 11 seconds :milestone, 11, 0

    section Parallel
    Security Agent    :0, 3
    Bug Agent         :0, 3
    Style Agent       :0, 3
    Reviewer Agent    :3, 5
    Total: 5 seconds  :milestone, 5, 0
```

### asyncio.gather Pattern

```python
# orchestrator.py
async def _review_diff(self, diff, ...):
    # Parse and prepare files
    files_data = [...]

    # Run all agents in PARALLEL using asyncio.gather
    results = await asyncio.gather(
        self.security_agent.review(files_data),  # Coroutine 1
        self.bug_agent.review(files_data),        # Coroutine 2
        self.style_agent.review(files_data),      # Coroutine 3
        return_exceptions=True,  # Don't fail if one agent errors
    )

    # All three complete before this line executes
    # results = [SecurityResult, BugResult, StyleResult]

    # Now run reviewer (must be sequential - needs agent results)
    verdict = await self.reviewer_agent.synthesize(results, context)
```

### Async Flow Visualization

```mermaid
flowchart TB
    subgraph Orchestrator
        START[Start _review_diff]
        GATHER[asyncio.gather]
        WAIT[Await all results]
        SYNTH[Call Reviewer]
        END[Return Report]
    end

    subgraph EventLoop["Python Event Loop"]
        SEC_TASK[Security Task]
        BUG_TASK[Bug Task]
        STY_TASK[Style Task]
        REV_TASK[Reviewer Task]
    end

    subgraph Bedrock["AWS Bedrock (External)"]
        API1[API Call 1]
        API2[API Call 2]
        API3[API Call 3]
        API4[API Call 4]
    end

    START --> GATHER
    GATHER --> SEC_TASK & BUG_TASK & STY_TASK
    SEC_TASK --> API1
    BUG_TASK --> API2
    STY_TASK --> API3
    API1 & API2 & API3 --> WAIT
    WAIT --> SYNTH
    SYNTH --> REV_TASK --> API4 --> END
```

### Key asyncio Concepts

| Concept | Description | Usage in Project |
|---------|-------------|------------------|
| `async def` | Defines a coroutine function | All agent methods |
| `await` | Pauses until coroutine completes | `await provider.invoke()` |
| `asyncio.gather()` | Run multiple coroutines concurrently | Parallel agent execution |
| `return_exceptions=True` | Return exceptions instead of raising | Graceful error handling |
| `asyncio.run()` | Entry point for async code | `asyncio.run(orchestrator.review())` |

---

## The Reviewer Agent: Synthesis Pattern

### What Makes the Reviewer Different?

```mermaid
flowchart TB
    subgraph AnalysisAgents["Analysis Agents (Parallel)"]
        SEC[Security Agent]
        BUG[Bug Agent]
        STY[Style Agent]
    end

    subgraph SynthesisAgent["Synthesis Agent (Sequential)"]
        REV[Reviewer Agent]
    end

    subgraph Differences
        D1["Receives: Raw code diffs"]
        D2["Produces: List of findings"]
        D3["Model: Fast tier (Haiku)"]
        D4["Receives: Agent findings"]
        D5["Produces: Final verdict"]
        D6["Model: Smart tier (Sonnet)"]
    end

    SEC & BUG & STY --> D1 & D2 & D3
    REV --> D4 & D5 & D6

    D1 & D2 & D3 -.->|"Different from"| D4 & D5 & D6
```

### Synthesis Flow

```mermaid
flowchart LR
    subgraph Input
        R1[Security: 6 findings]
        R2[Bug: 9 findings]
        R3[Style: 6 findings]
    end

    subgraph Processing
        FMT[Format for LLM]
        CNT[Count severities]
        INV[Invoke Sonnet]
    end

    subgraph Output
        DEC[Decision: REQUEST_CHANGES]
        SUM[Summary: Critical issues found]
        RSN[Reasoning: 2-3 sentences]
        CON[Key Concerns: Top 3]
    end

    R1 & R2 & R3 --> FMT --> CNT --> INV
    INV --> DEC & SUM & RSN & CON
```

### Decision Logic

```mermaid
flowchart TD
    START[Analyze Findings] --> CRIT{Critical > 0?}
    CRIT -->|Yes| RC[REQUEST_CHANGES]
    CRIT -->|No| HIGH{High >= 2?}
    HIGH -->|Yes| RC
    HIGH -->|No| HIGH1{High == 1?}
    HIGH1 -->|Yes| COM[COMMENT]
    HIGH1 -->|No| MED{Medium > 0?}
    MED -->|Yes| COM
    MED -->|No| APP[APPROVE]

    RC --> DONE[Return FinalVerdict]
    COM --> DONE
    APP --> DONE

    style RC fill:#ff6b6b,color:#fff
    style COM fill:#ffd93d,color:#000
    style APP fill:#6bcb77,color:#fff
```

### Structured Output Pattern

The Reviewer expects JSON output from the LLM:

```python
# prompts/reviewer.py
REVIEWER_SYSTEM_PROMPT = """
...
## Response Format

You MUST respond with ONLY a valid JSON object:

{
    "decision": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
    "summary": "One-line summary of your decision",
    "reasoning": "2-3 sentences explaining your decision",
    "key_concerns": ["concern1", "concern2", "concern3"]
}
"""

# agents/reviewer.py
def _parse_verdict(self, content: str) -> FinalVerdict:
    try:
        # Try to parse JSON
        data = json.loads(content)
        return FinalVerdict(
            decision=ReviewDecision(data["decision"]),
            summary=data.get("summary", ""),
            reasoning=data.get("reasoning", ""),
            key_concerns=data.get("key_concerns", []),
        )
    except (json.JSONDecodeError, KeyError):
        # Fallback: determine from severity counts
        return self._fallback_verdict(content, severity_counts)
```

---

## Prompt Engineering Patterns

### Structured Output Prompts

Each agent's prompt follows a pattern:

```mermaid
flowchart TB
    subgraph PromptStructure["Prompt Structure"]
        ROLE[Role Definition]
        FOCUS[Focus Areas]
        FORMAT[Output Format]
        GUIDE[Guidelines]
    end

    ROLE --> FOCUS --> FORMAT --> GUIDE

    subgraph Example["Security Agent Example"]
        E1["You are an expert security reviewer..."]
        E2["OWASP Top 10, Python-specific, Go-specific..."]
        E3["Return JSON array with severity, title, description..."]
        E4["Be specific, include line numbers, focus on changed code..."]
    end

    ROLE -.-> E1
    FOCUS -.-> E2
    FORMAT -.-> E3
    GUIDE -.-> E4
```

### JSON Output Pattern

```python
# All agents use this JSON structure for findings
OUTPUT_FORMAT = """
Return your findings as a JSON array:
```json
[
  {
    "severity": "critical|high|medium|low",
    "title": "Brief title",
    "description": "Detailed explanation",
    "file_path": "path/to/file.py",
    "line_number": 42,
    "code_snippet": "The problematic code",
    "suggested_fix": "How to fix it"
  }
]
```
If no issues found, return: []
"""
```

### Prompt Specialization

| Agent | Focus | Severity Emphasis |
|-------|-------|-------------------|
| Security | OWASP, injection, secrets | Critical for exploitable vulns |
| Bug | Logic errors, null refs, leaks | High for production crashes |
| Style | Naming, structure, practices | Low/Medium only |
| Reviewer | Synthesis, decision making | Weighs all severities |

---

## Error Handling Strategies

### Graceful Degradation

```mermaid
flowchart TB
    subgraph AgentError["Agent Error Handling"]
        A1[Agent throws exception]
        A2[Caught by gather]
        A3[Converted to ReviewResult with error]
        A4[Other agents continue]
    end

    subgraph ReviewerError["Reviewer Error Handling"]
        R1[JSON parse fails]
        R2[Fallback to severity counting]
        R3[Still produces verdict]
    end

    subgraph ProviderError["Provider Error Handling"]
        P1[Bedrock API error]
        P2[Retry with backoff]
        P3[Return error after retries]
    end

    A1 --> A2 --> A3 --> A4
    R1 --> R2 --> R3
    P1 --> P2 --> P3
```

### Error Handling Code Patterns

```python
# Orchestrator: Handle agent exceptions
results = await asyncio.gather(
    self.security_agent.review(files_data),
    self.bug_agent.review(files_data),
    self.style_agent.review(files_data),
    return_exceptions=True,  # Key: don't fail on one error
)

for result in results:
    if isinstance(result, Exception):
        valid_results.append(ReviewResult(
            agent_name="unknown",
            error=str(result),
        ))
    else:
        valid_results.append(result)

# Reviewer: Fallback verdict
def _parse_verdict(self, content, severity_counts):
    try:
        return FinalVerdict(**json.loads(content))
    except:
        # Fallback: use severity counts to decide
        if severity_counts["critical"] > 0:
            return FinalVerdict(decision=REQUEST_CHANGES, ...)
        # ... more logic
```

---

## Data Models

### Complete Model Hierarchy

```mermaid
classDiagram
    class Severity {
        <<enumeration>>
        CRITICAL
        HIGH
        MEDIUM
        LOW
    }

    class FindingCategory {
        <<enumeration>>
        SECURITY
        BUG
        STYLE
    }

    class ReviewDecision {
        <<enumeration>>
        APPROVE
        REQUEST_CHANGES
        COMMENT
    }

    class Message {
        +role: str
        +content: str
    }

    class FileChange {
        +path: str
        +language: str
        +diff: str
        +content: str?
    }

    class Finding {
        +category: FindingCategory
        +severity: Severity
        +title: str
        +description: str
        +file_path: str
        +line_number: int?
        +code_snippet: str?
        +suggested_fix: str?
    }

    class ReviewResult {
        +agent_name: str
        +findings: List~Finding~
        +files_reviewed: List~str~
        +error: str?
    }

    class FinalVerdict {
        +decision: ReviewDecision
        +summary: str
        +reasoning: str
        +key_concerns: List~str~
    }

    class ReviewReport {
        +files_reviewed: int
        +total_findings: int
        +critical_count: int
        +high_count: int
        +medium_count: int
        +low_count: int
        +findings: List~Finding~
        +agent_results: List~ReviewResult~
        +verdict: FinalVerdict?
        +to_markdown() str
        +from_agent_results() ReviewReport
    }

    Finding --> Severity
    Finding --> FindingCategory
    ReviewResult --> Finding
    FinalVerdict --> ReviewDecision
    ReviewReport --> Finding
    ReviewReport --> ReviewResult
    ReviewReport --> FinalVerdict
```

---

## Key Takeaways

### 1. Multi-Agent Architecture Benefits

```mermaid
mindmap
  root((Multi-Agent))
    Specialization
      Deep domain expertise
      Focused prompts
      Better accuracy
    Parallelism
      Faster execution
      Efficient resource use
      Scalable
    Modularity
      Easy to test
      Easy to extend
      Easy to maintain
    Reliability
      Graceful degradation
      No single point of failure
      Error isolation
```

### 2. Key Design Patterns Used

| Pattern | Where Used | Why |
|---------|------------|-----|
| **Protocol** | LLMProvider | Decouple agents from providers |
| **Template Method** | BaseAgent | Common flow, specialized behavior |
| **Factory** | get_provider() | Create providers by type |
| **Strategy** | Model tiers | Switch cost/quality tradeoff |
| **Facade** | Orchestrator | Hide complexity from CLI |

### 3. When to Use This Architecture

**Good for:**
- Tasks with distinct sub-problems (security, style, bugs)
- When specialization improves quality
- When parallel execution saves time
- When you need a final synthesis/decision

**Not ideal for:**
- Simple, single-step tasks
- Tasks requiring deep context sharing between steps
- Very low latency requirements (network overhead)

### 4. Extension Points

```mermaid
flowchart LR
    subgraph AddProvider["Add New Provider"]
        P1[Implement LLMProvider protocol]
        P2[Add to get_provider factory]
        P3[Add CLI option]
    end

    subgraph AddAgent["Add New Agent"]
        A1[Extend BaseAgent]
        A2[Create prompt file]
        A3[Add to Orchestrator]
    end

    subgraph AddOutput["Add Output Format"]
        O1[Create formatter in output/]
        O2[Add CLI option]
        O3[Call from report]
    end
```

---

## Quick Reference

### File Locations

```
code_reviewer/
├── cli.py              # Entry point, argument parsing
├── orchestrator.py     # Coordinates agents
├── models.py           # Pydantic data models
├── git_utils.py        # Git and GitHub operations
├── agents/
│   ├── base.py         # BaseAgent abstract class
│   ├── security.py     # Security analysis
│   ├── bugs.py         # Bug detection
│   ├── style.py        # Style review
│   └── reviewer.py     # Final synthesis
├── prompts/
│   ├── security.py     # Security prompt
│   ├── bugs.py         # Bug prompt
│   ├── style.py        # Style prompt
│   └── reviewer.py     # Reviewer prompt
├── providers/
│   ├── base.py         # LLMProvider protocol
│   ├── bedrock.py      # AWS Bedrock
│   └── agent_sdk.py    # Future SDK
└── output/
    └── markdown.py     # Report formatting
```

### Command Quick Reference

```bash
# Review a commit
code-review HEAD

# Review a GitHub PR
code-review https://github.com/owner/repo/pull/123

# Review with options
code-review HEAD --verbose --languages python
```

---

## Next Steps

1. **Try it yourself**: Run `code-review` on your own PRs
2. **Add an agent**: Create a `PerformanceAgent` that looks for N+1 queries
3. **Add a provider**: Implement `OpenAIProvider` using the same protocol
4. **Customize prompts**: Adjust prompts for your codebase's patterns
5. **Add tests**: Write unit tests for agents using mocked providers
