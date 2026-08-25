"""RAG / semantic search over codebase using pgvector."""

from pathlib import Path
from typing import Any

import httpx
from langchain.text_splitter import Language, RecursiveCharacterTextSplitter
from sqlalchemy import text
from structlog import get_logger

from codesentinel.config.settings import get_settings
from codesentinel.database.session import engine

logger = get_logger()
_settings = get_settings()

# Map file extension → LangChain Language for semantic-boundary splitting
_EXT_TO_LANGUAGE: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".jsx": Language.JS,
    ".tsx": Language.TS,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".java": Language.JAVA,
    ".rb": Language.RUBY,
    ".cs": Language.CSHARP,
}

_CHUNK_SIZE = 1500   # characters (~375 tokens) — fits well within embedding limits
_CHUNK_OVERLAP = 200  # characters of overlap to preserve cross-boundary context


def _make_splitter(ext: str) -> RecursiveCharacterTextSplitter:
    """Return a language-aware splitter, falling back to generic for unknown extensions."""
    lang = _EXT_TO_LANGUAGE.get(ext)
    if lang:
        return RecursiveCharacterTextSplitter.from_language(
            language=lang,
            chunk_size=_CHUNK_SIZE,
            chunk_overlap=_CHUNK_OVERLAP,
        )
    return RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
    )


async def semantic_search(
    owner: str,
    repo: str,
    ref: str,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search codebase embeddings for semantically similar code."""
    if not _settings.openai_api_key:
        return []

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=_settings.openai_api_key)
        response = await client.embeddings.create(
            model=_settings.embedding_model,
            input=query,
            dimensions=_settings.embedding_dimensions,
        )
        query_vector = str(response.data[0].embedding)

        repo_full_name = f"{owner}/{repo}"
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT file_path, content_chunk,
                           1 - (embedding <=> CAST(:vector AS vector)) as similarity
                    FROM codebase_embeddings
                    WHERE repo_full_name = :repo AND commit_sha = :ref
                    ORDER BY embedding <=> CAST(:vector AS vector)
                    LIMIT :top_k
                """),
                {
                    "vector": query_vector,
                    "repo": repo_full_name,
                    "ref": ref,
                    "top_k": top_k,
                },
            )
            rows = result.fetchall()

        return [
            {
                "file_path": row[0],
                "content_chunk": row[1],
                "similarity": float(row[2]),
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning("semantic_search_failed", error=str(e))
        return []


async def index_codebase(
    owner: str,
    repo: str,
    ref: str,
    github_client: Any,
) -> int:
    """Index a repo's files into the vector DB for semantic search."""
    if not _settings.openai_api_key:
        return 0

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=_settings.openai_api_key)
        repo_full_name = f"{owner}/{repo}"

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT count(*) FROM codebase_embeddings "
                    "WHERE repo_full_name = :repo AND commit_sha = :ref"
                ),
                {"repo": repo_full_name, "ref": ref},
            )
            if result.scalar() > 0:
                return result.scalar()

        token = await github_client._auth.get_installation_token(
            github_client._installation_id
        )
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            tree = resp.json().get("tree", [])

        indexed = 0

        for item in tree:
            if item["type"] != "blob":
                continue
            ext = Path(item["path"]).suffix
            if ext not in _EXT_TO_LANGUAGE:
                continue

            try:
                content = await github_client.get_file_contents(
                    owner, repo, item["path"], ref
                )
                splitter = _make_splitter(ext)
                chunks = splitter.split_text(content)

                for chunk_idx, chunk in enumerate(chunks):
                    if len(chunk.strip()) < 10:
                        continue

                    emb_response = await client.embeddings.create(
                        model=_settings.embedding_model,
                        input=chunk[:8000],
                        dimensions=_settings.embedding_dimensions,
                    )
                    vector = str(emb_response.data[0].embedding)

                    async with engine.begin() as conn:
                        await conn.execute(
                            text("""
                                INSERT INTO codebase_embeddings
                                    (repo_full_name, commit_sha, file_path,
                                     content_chunk, chunk_index, embedding)
                                VALUES (:repo, :ref, :path, :chunk, :idx, CAST(:emb AS vector))
                                ON CONFLICT DO NOTHING
                            """),
                            {
                                "repo": repo_full_name,
                                "ref": ref,
                                "path": item["path"],
                                "chunk": chunk[:8000],
                                "idx": chunk_idx,
                                "emb": vector,
                            },
                        )
                    indexed += 1
            except Exception as e:
                logger.debug("index_file_failed", path=item["path"], error=str(e))
                continue

        logger.info(
            "codebase_indexed", repo=repo_full_name, ref=ref[:8], chunks=indexed
        )
        return indexed

    except Exception as e:
        logger.warning("index_codebase_failed", error=str(e))
        return 0
