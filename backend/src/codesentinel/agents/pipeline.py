"""LangGraph review pipeline — the AI core.

Replaces the 2940-line reviewer.ts with a declarative graph definition.
Agents are ReAct agents with tool-calling capabilities.
"""

from __future__ import annotations

import asyncio
import json
import operator
import re
from typing import Annotated, Any, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from structlog import get_logger

from codesentinel.agents.prompts import (
    BUG_PROMPT,
    COMMENT_ACCURACY_PROMPT,
    DELTA_CAPTION_PROMPT,
    DIAGRAM_PROMPT,
    ERROR_HANDLING_PROMPT,
    ORCHESTRATOR_PROMPT,
    SECURITY_PROMPT,
    STYLE_PROMPT,
    SUMMARY_PROMPT,
    TEST_COVERAGE_PROMPT,
    VERIFIER_PROMPT,
)
from codesentinel.agents.tools import make_tools
from codesentinel.config.settings import get_settings
from codesentinel.github.client import GitHubClient

logger = get_logger()
_settings = get_settings()


# ─── State ───────────────────────────────────────────────────────────────────


class Finding(TypedDict):
    file: str
    line: int
    severity: str
    confidence: int
    title: str
    description: str
    suggestion: str
    category: str
    verification: str | None


class ReviewState(TypedDict):
    github_client: Any
    owner: str
    repo: str
    pr_number: int
    commit_sha: str
    pr_title: str
    pr_body: str
    diff: str
    pr_context: dict
    config: dict
    conventions: str
    review_mode: str
    raw_findings: Annotated[list[Finding], operator.add]
    verified_findings: list[Finding]
    disputed_keys: list[str]
    previous_findings: list[dict]
    final_findings: list[Finding]
    summary: str
    diagram: str
    delta_caption: str
    merge_score: int
    merge_score_reason: str
    tokens_used: dict
    cost_usd: float
    enabled_agent_count: Annotated[int, operator.add]
    errors: Annotated[list[str], operator.add]


# ─── LLM Factory ─────────────────────────────────────────────────────────────


REASONING_MODELS = {"gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "o1", "o3", "o4-mini"}


def _is_reasoning_model(model: str) -> bool:
    return any(model.startswith(rm) for rm in REASONING_MODELS)


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0,
    reasoning_effort: str | None = None,
    with_tools: bool = False,
) -> Any:
    provider = provider or _settings.llm_provider
    model = model or _settings.llm_model

    if provider == "openai":
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": _settings.openai_api_key,
            "max_tokens": _settings.max_tokens_per_agent,
        }

        if _is_reasoning_model(model):
            effective_effort = "none" if with_tools else (reasoning_effort or _settings.reasoning_effort)
            kwargs["reasoning_effort"] = effective_effort
        else:
            kwargs["temperature"] = temperature

        return ChatOpenAI(**kwargs)

    elif provider == "anthropic":
        return ChatAnthropic(
            model=model, temperature=temperature, api_key=_settings.anthropic_api_key
        )
    elif provider == "litellm":
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=_settings.litellm_api_key,
            base_url=_settings.litellm_base_url,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _parse_findings(text: str, category: str) -> list[Finding]:
    findings: list[Finding] = []

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [_normalize_finding(item, category) for item in data]
        if isinstance(data, dict) and "findings" in data:
            return [_normalize_finding(item, category) for item in data["findings"]]
    except (json.JSONDecodeError, TypeError):
        pass

    json_match = re.search(r'\{[\s\S]*"findings"[\s\S]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return [
                _normalize_finding(item, category)
                for item in data.get("findings", [])
            ]
        except (json.JSONDecodeError, TypeError):
            pass

    for match in re.finditer(
        r'\{[^{}]*"file"[^{}]*"line"[^{}]*\}', text
    ):
        try:
            item = json.loads(match.group())
            findings.append(_normalize_finding(item, category))
        except (json.JSONDecodeError, TypeError):
            continue

    return findings


def _normalize_finding(item: dict, default_category: str) -> Finding:
    return Finding(
        file=item.get("file", ""),
        line=item.get("line", 0),
        severity=item.get("severity", "info"),
        confidence=item.get("confidence", 100),
        title=item.get("title", ""),
        description=item.get("description", ""),
        suggestion=item.get("suggestion", ""),
        category=item.get("category", default_category),
        verification=None,
    )


def _parse_verdict(text: str) -> dict:
    try:
        data = json.loads(text)
        return {
            "valid": data.get("valid", False),
            "confidence": data.get("confidence", 0),
            "reason": data.get("reason", ""),
        }
    except (json.JSONDecodeError, TypeError):
        text_lower = text.lower()
        if "true" in text_lower and "false" not in text_lower:
            return {"valid": True, "confidence": 0.5, "reason": text[:200]}
        return {"valid": False, "confidence": 0.5, "reason": text[:200]}


def _parse_orchestrator(text: str) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass
    return {}


def _default_config() -> dict:
    return {
        "max_files": _settings.max_files,
        "max_findings": _settings.max_findings,
        "min_confidence": _settings.confidence_floor,
        "max_tokens_per_agent": _settings.max_tokens_per_agent,
    }


# ─── Pipeline Nodes ──────────────────────────────────────────────────────────


async def load_context_node(state: ReviewState) -> dict:
    """Fetch PR diff, files, conventions, and previous findings."""
    gc = state["github_client"]
    owner = state["owner"]
    repo = state["repo"]
    pr_number = state["pr_number"]
    commit_sha = state["commit_sha"]

    diff = await gc.get_pr_diff(owner, repo, pr_number)
    pr_context = await gc.get_pr(owner, repo, pr_number)
    conventions = await gc.get_conventions(owner, repo, commit_sha) or ""

    repo_config = await gc.get_repo_config(owner, repo, commit_sha) or {}
    config = {**_default_config(), **repo_config}

    try:
        from codesentinel.rag.indexer import index_codebase

        await index_codebase(owner, repo, commit_sha, gc)
    except Exception as e:
        logger.warning("rag_index_failed", error=str(e))

    return {
        "diff": diff[: _settings.max_context_kb * 1024],
        "pr_context": pr_context,
        "conventions": conventions,
        "config": config,
        "raw_findings": [],
        "tokens_used": {"input": 0, "output": 0},
        "cost_usd": 0.0,
        "errors": [],
    }


async def _run_agent(
    agent_name: str,
    prompt_template: str,
    state: ReviewState,
    tools: list[BaseTool],
) -> list[Finding]:
    """Run a single ReAct agent with tools."""
    llm = create_llm(temperature=0, with_tools=True)

    prompt = prompt_template.format(
        pr_title=state.get("pr_title") or "",
        pr_body=(state.get("pr_body") or "")[:2000],
        diff=(state.get("diff") or "")[: _settings.max_context_kb * 1024],
        conventions=(state.get("conventions") or "")[:4000] or "No conventions file found.",
    )

    agent = create_react_agent(llm, tools)

    try:
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        last_message = result["messages"][-1].content
        findings = _parse_findings(last_message, agent_name)
        logger.info(
            "agent_completed",
            agent=agent_name,
            findings=len(findings),
        )
        return findings
    except Exception as e:
        logger.error("agent_failed", agent=agent_name, error=str(e))
        return []


async def security_agent_node(state: ReviewState) -> dict:
    gc = state["github_client"]
    tools = make_tools(gc, state["owner"], state["repo"], state["commit_sha"])
    findings = await _run_agent("security", SECURITY_PROMPT, state, tools)
    return {
        "raw_findings": findings,
        "enabled_agent_count": 1,
    }


async def bug_agent_node(state: ReviewState) -> dict:
    gc = state["github_client"]
    tools = make_tools(gc, state["owner"], state["repo"], state["commit_sha"])
    findings = await _run_agent("bugs", BUG_PROMPT, state, tools)
    return {
        "raw_findings": findings,
        "enabled_agent_count": 1,
    }


async def style_agent_node(state: ReviewState) -> dict:
    gc = state["github_client"]
    tools = make_tools(gc, state["owner"], state["repo"], state["commit_sha"])
    findings = await _run_agent("style", STYLE_PROMPT, state, tools)
    return {
        "raw_findings": findings,
        "enabled_agent_count": 1,
    }


async def error_handling_agent_node(state: ReviewState) -> dict:
    gc = state["github_client"]
    tools = make_tools(gc, state["owner"], state["repo"], state["commit_sha"])
    findings = await _run_agent("error_handling", ERROR_HANDLING_PROMPT, state, tools)
    return {
        "raw_findings": findings,
        "enabled_agent_count": 1,
    }


async def test_coverage_agent_node(state: ReviewState) -> dict:
    gc = state["github_client"]
    tools = make_tools(gc, state["owner"], state["repo"], state["commit_sha"])
    findings = await _run_agent("test_coverage", TEST_COVERAGE_PROMPT, state, tools)
    return {
        "raw_findings": findings,
        "enabled_agent_count": 1,
    }


async def comment_accuracy_agent_node(state: ReviewState) -> dict:
    gc = state["github_client"]
    tools = make_tools(gc, state["owner"], state["repo"], state["commit_sha"])
    findings = await _run_agent("comment_accuracy", COMMENT_ACCURACY_PROMPT, state, tools)
    return {
        "raw_findings": findings,
        "enabled_agent_count": 1,
    }


async def verification_node(state: ReviewState) -> dict:
    """Cross-model verification — use a DIFFERENT model to verify findings."""
    verifier_llm = create_llm(
        provider=_settings.verifier_provider,
        model=_settings.verifier_model,
        reasoning_effort=_settings.verifier_reasoning_effort,
    )

    gc = state["github_client"]
    verified = []

    for finding in state["raw_findings"]:
        if finding["severity"] not in ("critical", "warning"):
            verified.append(finding)
            continue

        try:
            file_content = await gc.get_file_contents(
                state["owner"], state["repo"], finding["file"], state["commit_sha"]
            )
        except Exception:
            file_content = "(could not fetch file)"

        prompt = VERIFIER_PROMPT.format(
            finding=json.dumps(finding, indent=2),
            file_path=finding["file"],
            file_content=file_content[:10_000],
        )

        try:
            result = await verifier_llm.ainvoke([HumanMessage(content=prompt)])
            verdict = _parse_verdict(result.content)
            finding["verification"] = (
                "verified" if verdict["valid"] else "unverified"
            )
        except Exception as e:
            logger.warning("verification_failed", finding=finding["title"], error=str(e))
            finding["verification"] = "unverified"

        verified.append(finding)

    return {"verified_findings": verified}


async def orchestration_node(state: ReviewState) -> dict:
    """Dedup, filter, rank findings and assign merge score."""
    findings = state["verified_findings"]

    floor = state["config"].get("min_confidence", _settings.confidence_floor)
    findings = [f for f in findings if f.get("confidence", 100) >= floor]

    seen = set()
    deduped = []
    for f in findings:
        key = (f["file"], f["line"], f["title"].lower()[:50])
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    deduped.sort(
        key=lambda f: (severity_order.get(f["severity"], 3), -f.get("confidence", 100))
    )

    max_findings = state["config"].get("max_findings", _settings.max_findings)
    deduped = deduped[:max_findings]

    criticals = [f for f in deduped if f["severity"] == "critical"]
    all_unverified = criticals and all(
        f.get("verification") == "unverified" for f in criticals
    )

    llm = create_llm(temperature=0)
    changed_files = set(f["file"] for f in deduped)
    changed_lines = sum(
        1
        for line in state["diff"].split("\n")
        if line.startswith("+") or line.startswith("-")
    )

    prompt = ORCHESTRATOR_PROMPT.format(
        findings_json=json.dumps(deduped[:20], indent=2),
        pr_title=state.get("pr_title", ""),
        changed_files=len(changed_files),
        changed_lines=changed_lines,
    )

    try:
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        orch_data = _parse_orchestrator(result.content)
        merge_score = orch_data.get("merge_score", 3)
        merge_score_reason = orch_data.get("merge_score_reason", "")
        if orch_data.get("findings"):
            deduped = [
                _normalize_finding(f, f.get("category", "general"))
                for f in orch_data["findings"]
            ]
    except Exception as e:
        logger.warning("orchestrator_failed", error=str(e))
        critical_count = sum(1 for f in deduped if f["severity"] == "critical")
        merge_score = max(1, 5 - critical_count) if deduped else 5
        merge_score_reason = f"{critical_count} critical, {len(deduped)} total findings"

    if all_unverified and merge_score < 3:
        merge_score = 3
        merge_score_reason += " (clamped: all criticals unverified)"

    return {
        "final_findings": deduped,
        "merge_score": merge_score,
        "merge_score_reason": merge_score_reason,
    }


async def generative_node(state: ReviewState) -> dict:
    """Generate summary, diagram, and delta caption in parallel."""
    llm = create_llm()

    findings_summary = "; ".join(
        f"{f['severity']}: {f['title']} ({f['file']}:{f['line']})"
        for f in state["final_findings"][:10]
    ) or "No findings"

    changed_files = list(set(f["file"] for f in state["final_findings"]))[:10]

    summary_prompt = SUMMARY_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        pr_body=(state.get("pr_body") or "")[:1000],
        changed_files=len(changed_files),
        findings_summary=findings_summary,
    )

    diagram_prompt = DIAGRAM_PROMPT.format(
        pr_title=state.get("pr_title", ""),
        changed_files=", ".join(changed_files),
        findings_summary=findings_summary,
    )

    summary_task = llm.ainvoke([HumanMessage(content=summary_prompt)])
    diagram_task = llm.ainvoke([HumanMessage(content=diagram_prompt)])

    delta_caption = ""
    if state.get("previous_findings"):
        delta_prompt = DELTA_CAPTION_PROMPT.format(
            previous_findings=json.dumps(state["previous_findings"][:10], indent=2),
            current_findings=json.dumps(state["final_findings"][:10], indent=2),
        )
        delta_task = llm.ainvoke([HumanMessage(content=delta_prompt)])
        summary_result, diagram_result, delta_result = await asyncio.gather(
            summary_task, diagram_task, delta_task
        )
        delta_caption = delta_result.content
    else:
        summary_result, diagram_result = await asyncio.gather(
            summary_task, diagram_task
        )

    return {
        "summary": summary_result.content,
        "diagram": diagram_result.content.strip(),
        "delta_caption": delta_caption,
    }


# ─── Graph Definition ────────────────────────────────────────────────────────


def build_review_graph() -> Any:
    """Build and compile the LangGraph review pipeline."""
    workflow = StateGraph(ReviewState)

    workflow.add_node("load_context", load_context_node)
    workflow.add_node("security", security_agent_node)
    workflow.add_node("bugs", bug_agent_node)
    workflow.add_node("style", style_agent_node)
    workflow.add_node("error_handling", error_handling_agent_node)
    workflow.add_node("test_coverage", test_coverage_agent_node)
    workflow.add_node("comment_accuracy", comment_accuracy_agent_node)
    workflow.add_node("verify", verification_node)
    workflow.add_node("orchestrate", orchestration_node)
    workflow.add_node("generate", generative_node)

    workflow.set_entry_point("load_context")

    workflow.add_edge("load_context", "security")
    workflow.add_edge("load_context", "bugs")
    workflow.add_edge("load_context", "style")
    workflow.add_edge("load_context", "error_handling")
    workflow.add_edge("load_context", "test_coverage")
    workflow.add_edge("load_context", "comment_accuracy")

    workflow.add_edge("security", "verify")
    workflow.add_edge("bugs", "verify")
    workflow.add_edge("style", "verify")
    workflow.add_edge("error_handling", "verify")
    workflow.add_edge("test_coverage", "verify")
    workflow.add_edge("comment_accuracy", "verify")

    workflow.add_edge("verify", "orchestrate")
    workflow.add_edge("orchestrate", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


# ─── Entry Point ─────────────────────────────────────────────────────────────


async def run_review(
    github_client: GitHubClient,
    owner: str,
    repo: str,
    pr_number: int,
    commit_sha: str,
    pr_title: str = "",
    pr_body: str = "",
    review_mode: str = "review",
    on_node_complete: Any | None = None,
) -> dict[str, Any]:
    """Run the full review pipeline and return results.

    on_node_complete: optional async callable(node_name: str, output: dict)
    called after each graph node finishes — used for live progress updates.
    """
    graph = build_review_graph()

    initial_state: ReviewState = {
        "github_client": github_client,
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "commit_sha": commit_sha,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "diff": "",
        "pr_context": {},
        "config": {},
        "conventions": "",
        "review_mode": review_mode,
        "raw_findings": [],
        "verified_findings": [],
        "disputed_keys": [],
        "previous_findings": [],
        "final_findings": [],
        "summary": "",
        "diagram": "",
        "delta_caption": "",
        "merge_score": 5,
        "merge_score_reason": "",
        "tokens_used": {"input": 0, "output": 0},
        "cost_usd": 0.0,
        "enabled_agent_count": 0,
        "errors": [],
    }

    # Fields reduced with operator.add — must be accumulated, not overwritten.
    _additive_lists = {"raw_findings", "errors"}
    _additive_ints = {"enabled_agent_count"}

    final_state: dict[str, Any] = dict(initial_state)

    async for event in graph.astream(initial_state, stream_mode="updates"):
        for node_name, node_output in event.items():
            for key, value in node_output.items():
                if key in _additive_lists:
                    final_state[key] = final_state.get(key, []) + value
                elif key in _additive_ints:
                    final_state[key] = final_state.get(key, 0) + value
                else:
                    final_state[key] = value
            if on_node_complete is not None:
                try:
                    await on_node_complete(node_name, node_output)
                except Exception:
                    pass

    return final_state
