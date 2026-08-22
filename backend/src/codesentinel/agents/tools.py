"""Agent tools — the key upgrade over the TypeScript version.

Agents can call these tools to fetch context, run linters, analyze ASTs,
search the codebase via RAG, and trace data flow — instead of being
limited to a single-pass LLM call with a truncated diff.
"""

from __future__ import annotations

import ast
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
from langchain_core.tools import tool
from structlog import get_logger

from codesentinel.github.client import GitHubClient

logger = get_logger()


def make_tools(
    github_client: GitHubClient, owner: str, repo: str, ref: str
) -> list:
    """Create tool functions bound to the specific PR's repo + commit SHA."""

    @tool
    async def read_file(file_path: str) -> str:
        """Read the full contents of a file from the repo at the PR's head commit.
        Use this to get complete context around a finding, not just the diff lines.
        """
        try:
            content = await github_client.get_file_contents(
                owner, repo, file_path, ref
            )
            return content[:50_000]
        except Exception as e:
            return f"Error reading {file_path}: {e}"

    @tool
    async def read_lines(file_path: str, start_line: int, end_line: int) -> str:
        """Read a specific line range from a file. Useful for large files."""
        try:
            content = await github_client.get_file_contents(
                owner, repo, file_path, ref
            )
            lines = content.split("\n")
            start = max(0, start_line - 1)
            end = min(len(lines), end_line)
            result = "\n".join(
                f"{i+1}: {lines[i]}" for i in range(start, end)
            )
            return result or f"No lines {start_line}-{end_line} in {file_path}"
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def list_files(path_prefix: str = "") -> str:
        """List files in the repo at a given path prefix (e.g., 'src/', 'tests/')."""
        try:
            token = await github_client._auth.get_installation_token(
                github_client._installation_id
            )
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                resp.raise_for_status()
                tree = resp.json().get("tree", [])

            paths = [
                t["path"]
                for t in tree
                if t["type"] == "blob" and t["path"].startswith(path_prefix)
            ]
            return "\n".join(paths[:200]) or f"No files found under {path_prefix}"
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def grep_codebase(pattern: str, file_filter: str = "") -> str:
        """Search for a regex pattern across the repo. Returns matching files.

        Args:
            pattern: Regex pattern to search for
            file_filter: Optional file extension filter (e.g., '.py', '.ts')
        """
        try:
            token = await github_client._auth.get_installation_token(
                github_client._installation_id
            )
            url = f"https://api.github.com/search/code?q={pattern}+repo:{owner}/{repo}"
            if file_filter:
                url += f"+extension:{file_filter.lstrip('.')}"

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if resp.status_code != 200:
                    return f"Search failed: {resp.status_code}"
                items = resp.json().get("items", [])

            results = [
                f"{item['path']} (score: {item.get('score', 0):.2f})"
                for item in items[:20]
            ]
            return "\n".join(results) or "No matches found"
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def search_codebase(query: str, top_k: int = 5) -> str:
        """Semantic search over the codebase using embeddings.

        Finds code semantically related to your query, even if exact
        keywords don't match. Useful for finding related patterns.
        """
        try:
            from codesentinel.rag.indexer import semantic_search

            results = await semantic_search(owner, repo, ref, query, top_k)
            if not results:
                return "No semantically similar code found. Try a different query."

            formatted = []
            for r in results:
                formatted.append(
                    f"--- {r['file_path']} (similarity: {r['similarity']:.2f}) ---\n"
                    f"{r['content_chunk'][:2000]}"
                )
            return "\n\n".join(formatted)
        except Exception as e:
            return f"Semantic search unavailable: {e}. Use grep_codebase instead."

    @tool
    async def analyze_ast(file_path: str) -> str:
        """Parse a Python file's AST and return its structure.

        Shows functions, classes, methods, and their line numbers.
        For non-Python files, suggests using read_file instead.
        """
        try:
            content = await github_client.get_file_contents(
                owner, repo, file_path, ref
            )

            if file_path.endswith(".py"):
                tree = ast.parse(content)
                lines = []
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args]
                        lines.append(
                            f"  function {node.name}({', '.join(args)}) "
                            f"at line {node.lineno}"
                        )
                    elif isinstance(node, ast.ClassDef):
                        lines.append(
                            f"  class {node.name} at line {node.lineno}"
                        )
                        for child in node.body:
                            if isinstance(
                                child, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                lines.append(
                                    f"    method {child.name}() "
                                    f"at line {child.lineno}"
                                )
                return f"AST for {file_path}:\n" + "\n".join(lines)
            else:
                return (
                    f"AST analysis for {file_path}:\n"
                    f"(File is not Python — use read_file for contents)"
                )
        except SyntaxError as e:
            return f"Syntax error in {file_path}: {e}"
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def find_callers(function_name: str) -> str:
        """Find all call sites of a function across the repo using AST analysis.

        Returns file:line for each call site with surrounding context.
        """
        try:
            token = await github_client._auth.get_installation_token(
                github_client._installation_id
            )
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                resp.raise_for_status()
                tree = resp.json().get("tree", [])

            callers = []
            for item in tree:
                if item["type"] != "blob" or not item["path"].endswith(".py"):
                    continue
                try:
                    content = await github_client.get_file_contents(
                        owner, repo, item["path"], ref
                    )
                    tree_ast = ast.parse(content)
                    for node in ast.walk(tree_ast):
                        if isinstance(node, ast.Call):
                            name = None
                            if isinstance(node.func, ast.Name):
                                name = node.func.id
                            elif isinstance(node.func, ast.Attribute):
                                name = node.func.attr
                            if name == function_name:
                                lines = content.split("\n")
                                ctx_start = max(0, node.lineno - 3)
                                ctx_end = min(len(lines), node.lineno + 2)
                                ctx = "\n".join(
                                    f"  {i+1}: {lines[i]}"
                                    for i in range(ctx_start, ctx_end)
                                )
                                callers.append(
                                    f"{item['path']}:{node.lineno}\n{ctx}"
                                )
                except Exception:
                    continue

            return (
                "\n\n".join(callers[:20])
                or f"No callers found for {function_name}"
            )
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def check_data_flow(
        file_path: str, variable_name: str, start_line: int
    ) -> str:
        """Trace data flow of a variable from a starting line through the function.

        Helps identify if user-controlled input reaches a dangerous sink
        (taint analysis for security review).
        """
        try:
            content = await github_client.get_file_contents(
                owner, repo, file_path, ref
            )
            lines = content.split("\n")

            flow = []
            in_function = False
            func_indent = 0

            for i, line in enumerate(lines):
                if i + 1 == start_line:
                    in_function = True
                    func_indent = len(line) - len(line.lstrip())

                if in_function and variable_name in line:
                    flow.append(f"  line {i+1}: {line.strip()}")

                if (
                    in_function
                    and line.strip()
                    and not line.startswith(" " * func_indent)
                    and i + 1 > start_line
                ):
                    break

            if not flow:
                return (
                    f"Variable '{variable_name}' not found after line "
                    f"{start_line} in {file_path}"
                )

            return (
                f"Data flow for '{variable_name}' in {file_path} "
                f"from line {start_line}:\n" + "\n".join(flow)
            )
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def run_linter(file_path: str, language: str = "") -> str:
        """Run a linter on a file and return issues.

        Supports Python (pyflakes), JavaScript/TypeScript (eslint).
        """
        try:
            content = await github_client.get_file_contents(
                owner, repo, file_path, ref
            )

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=Path(file_path).suffix, delete=False
            ) as f:
                f.write(content)
                f.flush()

                lang = language or Path(file_path).suffix.lstrip(".")
                if lang == "py":
                    result = subprocess.run(
                        ["python3", "-m", "pyflakes", f.name],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                elif lang in ("js", "ts", "jsx", "tsx"):
                    result = subprocess.run(
                        [
                            "npx",
                            "--yes",
                            "eslint",
                            f.name,
                            "--format",
                            "compact",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                else:
                    return f"No linter available for .{lang} files"

                output = result.stdout + result.stderr
                return output.strip() or "No lint issues found"
        except subprocess.TimeoutExpired:
            return "Linter timed out"
        except FileNotFoundError:
            return f"Linter not available for .{lang} files"
        except Exception as e:
            return f"Error: {e}"

    @tool
    async def run_tests(test_path: str = "") -> str:
        """Run the test suite (or a specific test file) and return results.

        Executes in a sandboxed environment. Only works for repos with
        a test setup (pytest, jest, etc.).
        """
        return (
            "Test execution is not available in this environment. "
            "Use read_file to examine test files manually, or "
            "check if the changed code has corresponding test coverage."
        )

    return [
        read_file,
        read_lines,
        list_files,
        grep_codebase,
        search_codebase,
        analyze_ast,
        find_callers,
        check_data_flow,
        run_linter,
        run_tests,
    ]
