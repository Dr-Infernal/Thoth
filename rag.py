from multiprocessing import context
from langchain_core.prompts import ChatPromptTemplate
from documents import vector_store, embedding_model
from models import get_llm
from api_keys import apply_keys
from langchain_community.retrievers.wikipedia import WikipediaRetriever
from langchain_community.retrievers.arxiv import ArxivRetriever
from langchain_community.retrievers.tavily_search_api import TavilySearchAPIRetriever
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
import operator
from typing import Annotated, TypedDict
from langgraph.graph import START, StateGraph, END, add_messages
from threads import pick_or_create_thread, checkpointer

system_prompt = """You are a helpful assistant that answers questions based on the provided context and your internal knowledge.
For each question, you should use the retrieved context and your internal knowledge to provide a comprehensive answer. If the context does not contain relevant information, rely on your internal knowledge to answer the question.
For each piece of information you use from the context, cite the source in parentheses from the provided source Example: (Source: <document.pdf>) or (Source: <hyperlink>).
If the fact is from your internal knowledge, cite it as (Source: Internal Knowledge).
If you don't know the answer, say you don't know."""

document_retriever = vector_store.as_retriever(search_kwargs={"k": 5})
wiki_retriever = WikipediaRetriever()
arxiv_retriever = ArxivRetriever()
web_search_retriever = TavilySearchAPIRetriever()

apply_keys()

# ── Contextual compression: extract only query-relevant content per doc ──────
_compressor = LLMChainExtractor.from_llm(get_llm())

def _compressed(base_retriever):
    return ContextualCompressionRetriever(
        base_compressor=_compressor,
        base_retriever=base_retriever,
    )

compressed_document_retriever = _compressed(document_retriever)
compressed_wiki_retriever = _compressed(wiki_retriever)
compressed_arxiv_retriever = _compressed(arxiv_retriever)
compressed_web_retriever = _compressed(web_search_retriever)

# ── Character-based budget (1 token ≈ 4.5 characters) ───────────────────────
CHARS_PER_TOKEN = 4.5
MODEL_CONTEXT_WINDOW_TOKENS = 100000
ANSWER_RESERVE_TOKENS = 1500         # reserved for the generated answer

_total_char_budget = int(MODEL_CONTEXT_WINDOW_TOKENS * CHARS_PER_TOKEN)
_answer_reserve = int(ANSWER_RESERVE_TOKENS * CHARS_PER_TOKEN)
_system_prompt_chars = len(system_prompt)
_usable = _total_char_budget - _answer_reserve - _system_prompt_chars

CONTEXT_CHAR_BUDGET = int(_usable * 0.55)   # 55% for retrieved context
MESSAGE_CHAR_BUDGET = int(_usable * 0.45)   # 45% for conversation history


def trim_messages(messages: list, budget: int = MESSAGE_CHAR_BUDGET) -> list:
    """Keep the most recent messages that fit within the character budget.
    The latest message (current query) is always preserved."""
    if not messages:
        return messages
    total = 0
    kept: list = []
    for msg in reversed(messages):
        msg_len = len(msg.content) if hasattr(msg, "content") else len(str(msg))
        if total + msg_len > budget and kept:
            break
        total += msg_len
        kept.append(msg)
    return list(reversed(kept))


def trim_context(entries: list[str], budget: int = CONTEXT_CHAR_BUDGET) -> list[str]:
    """Keep the most recent context entries that fit within the character budget."""
    if not entries:
        return entries
    total = 0
    kept: list[str] = []
    for entry in reversed(entries):
        if total + len(entry) > budget and kept:
            break
        total += len(entry)
        kept.append(entry)
    return list(reversed(kept))


# ── Context deduplication ────────────────────────────────────────────────────
DEDUP_SIMILARITY_THRESHOLD = 0.85  # cosine similarity above this → duplicate


def _cosine_similarity(vec_a, vec_b) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def deduplicate_docs(docs: list, threshold: float = DEDUP_SIMILARITY_THRESHOLD) -> list:
    """Remove near-duplicate documents based on embedding cosine similarity.
    Keeps the first occurrence of each unique document."""
    if len(docs) <= 1:
        return docs
    texts = [doc.page_content for doc in docs]
    embeddings = embedding_model.embed_documents(texts)
    kept = []
    kept_embeddings = []
    for doc, emb in zip(docs, embeddings):
        is_dup = any(
            _cosine_similarity(emb, kept_emb) >= threshold
            for kept_emb in kept_embeddings
        )
        if not is_dup:
            kept.append(doc)
            kept_embeddings.append(emb)
    removed = len(docs) - len(kept)
    if removed:
        print(f"Dedup: removed {removed} duplicate doc(s) out of {len(docs)}")
    return kept


def deduplicate_new_context(
    new_entry: str,
    existing_entries: list[str],
    threshold: float = DEDUP_SIMILARITY_THRESHOLD,
) -> bool:
    """Return True if new_entry is NOT a duplicate of any existing entry."""
    if not existing_entries or not new_entry.strip():
        return True
    all_texts = existing_entries + [new_entry]
    embeddings = embedding_model.embed_documents(all_texts)
    new_emb = embeddings[-1]
    for existing_emb in embeddings[:-1]:
        if _cosine_similarity(new_emb, existing_emb) >= threshold:
            print("Dedup: new context entry is a duplicate of existing context — skipping.")
            return False
    return True


CONTEXT_RELEVANCE_THRESHOLD = 0.65  # if existing context is this similar to query → skip retrieval


def context_already_relevant(
    query: str,
    context_entries: list[str],
    threshold: float = CONTEXT_RELEVANCE_THRESHOLD,
) -> bool:
    """Return True if any existing context entry is already relevant to the query."""
    if not context_entries:
        return False
    all_texts = [query] + context_entries
    embeddings = embedding_model.embed_documents(all_texts)
    query_emb = embeddings[0]
    for i, ctx_emb in enumerate(embeddings[1:]):
        sim = _cosine_similarity(query_emb, ctx_emb)
        if sim >= threshold:
            print(f"Existing context entry {i} is relevant to query (similarity={sim:.3f}) — skipping retrieval.")
            return True
    return False


class SessionState(TypedDict):
    needs_context: bool
    context: Annotated[list[str], operator.add]
    answer: str
    messages: Annotated[list, add_messages]
    search_documents: bool
    search_wikipedia: bool
    search_arxiv: bool
    search_web: bool


def needs_context(state: SessionState):
    import re

    trimmed = trim_context(state.get("context", []))

    # No existing context at all → always retrieve
    if not trimmed:
        print("No existing context — will retrieve.")
        return {"needs_context": True}

    # Fast embedding check: is existing context already relevant to this query?
    query = state["messages"][-1].content
    if context_already_relevant(query, trimmed):
        return {"needs_context": False}

    # Fall back to LLM judgment for ambiguous cases
    existing_context = "\n\n".join(trimmed)
    prompt = f"""You are an expert context verifier. Given the existing context and a new question, determine if the question can be answered with the existing context or if additional information is needed.
    Existing Context: {existing_context}
    New Question: {query}
    Does the question require additional context to answer accurately?  
    **Respond with 'Yes' or 'No' only.**
    """
    response = get_llm().invoke(prompt)
    print(f"LLM response for needs_context: {response.content}")
    # Strip <think>…</think> tags (Qwen3 / reasoning models) before checking
    answer_text = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL).strip().lower()
    if "yes" in answer_text:
        return {"needs_context": True}
    else:
        return {"needs_context": False}

def needs_context_condition(state: SessionState):
    if state["needs_context"]:
        return "get_context"
    else:
        return "generate_answer"

def get_context(state: SessionState):
    import re as _re

    search_documents = state.get("search_documents", True)
    search_wikipedia = state.get("search_wikipedia", True)
    search_arxiv = state.get("search_arxiv", True)
    search_web = state.get("search_web", True)

    raw_query = state["messages"][-1].content

    # ── Query rewriting: resolve pronouns / references using recent history ──
    recent_msgs = trim_messages(state.get("messages", []))
    if len(recent_msgs) > 1:
        history_lines = []
        for msg in recent_msgs[:-1]:          # everything except the current message
            role = "User" if msg.type == "human" else "Assistant"
            history_lines.append(f"{role}: {msg.content}")
        history_block = "\n".join(history_lines[-10:])  # keep last 10 turns max

        rewrite_prompt = (
            "Given the following conversation history and a new user message, "
            "rewrite the user message into a single standalone search query that "
            "a search engine could understand without any prior context. "
            "Resolve all pronouns, references like 'they', 'it', 'those', 'the first one', etc. "
            "Return ONLY the rewritten query, nothing else.\n\n"
            f"Conversation history:\n{history_block}\n\n"
            f"User message: {raw_query}\n\n"
            "Standalone search query:"
        )
        rewrite_response = get_llm().invoke(rewrite_prompt)
        query = _re.sub(r"<think>.*?</think>", "", rewrite_response.content, flags=_re.DOTALL).strip()
        # Fallback: if the rewrite came back empty, use the original
        if not query:
            query = raw_query
        print(f"Rewritten query: {query}")
    else:
        query = raw_query
        print(f"Using original query (no history): {query}")

    def safe_invoke(retriever, label: str):
        try:
            print(f"Invoking {label} retriever...")
            return retriever.invoke(query)
        except Exception as exc:
            print(f"{label} retriever failed: {exc}")
            return []

    # Run all enabled retrievers in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed

    tasks = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        if search_documents:
            tasks[executor.submit(safe_invoke, compressed_document_retriever, "Documents")] = "doc"
        if search_wikipedia:
            tasks[executor.submit(safe_invoke, compressed_wiki_retriever, "Wikipedia")] = "wiki"
        if search_arxiv:
            tasks[executor.submit(safe_invoke, compressed_arxiv_retriever, "Arxiv")] = "arxiv"
        if search_web:
            tasks[executor.submit(safe_invoke, compressed_web_retriever, "Web")] = "web"

        results = {}
        for future in as_completed(tasks):
            results[tasks[future]] = future.result()

    doc_results = results.get("doc", [])
    wiki_results = results.get("wiki", [])
    arxiv_results = results.get("arxiv", [])
    web_search_results = results.get("web", [])

    for result in arxiv_results:
        if "Entry ID" in result.metadata:
            result.metadata["source"] = result.metadata["Entry ID"]

    # Format results with source attribution
    all_docs = doc_results + wiki_results + arxiv_results + web_search_results
    if not all_docs:
        return {"context": ["No relevant information found."]}

    # Deduplicate within this retrieval batch
    all_docs = deduplicate_docs(all_docs)

    formatted = []
    for doc in all_docs:
        source = doc.metadata.get("source", "Unknown")
        formatted.append(f"{doc.page_content} (Source: {source})")

    compressed_context = "\n\n".join(formatted)
    print(f"Compressed context length: {len(compressed_context)} chars")

    # Deduplicate against existing accumulated context
    existing_context = state.get("context", [])
    if not deduplicate_new_context(compressed_context, existing_context):
        return {"context": []}  # skip adding duplicate context

    return {"context": [compressed_context]}

def generate_answer(state: SessionState):
    prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("human", "Context:{context} \n\nQuestion: {question}")
    ]
    )
    trimmed_ctx = trim_context(state.get("context", []))
    context_text = "\n\n".join(trimmed_ctx) or "No context available"
    trimmed_msgs = trim_messages(state.get("messages", []))
    question = trimmed_msgs[-1].content if trimmed_msgs else state["messages"][-1].content
    input = prompt.format(context=context_text, question=question)
    print(f"Prompt for answer generation:\n{input}\n")
    answer = get_llm().invoke(input)
    return {"answer": answer, "messages": [answer]}

rag_graph = StateGraph(SessionState)
rag_graph.add_node("needs_context", needs_context)
rag_graph.add_node("get_context", get_context)
rag_graph.add_node("generate_answer", generate_answer)
rag_graph.add_edge(START, "needs_context")
rag_graph.add_conditional_edges("needs_context", needs_context_condition, ["get_context", "generate_answer"])
rag_graph.add_edge("get_context", "generate_answer")
rag_graph.add_edge("generate_answer", END)
rag_graph_compiled = rag_graph.compile(checkpointer=checkpointer)

if __name__ == "__main__":
    config = pick_or_create_thread()
    print("Type your questions below. Type 'quit' to exit, 'switch' to change threads.\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "switch":
            config = pick_or_create_thread()
            continue

        result = rag_graph_compiled.invoke(
            {"messages": [("human", user_input)]},
            config=config,
        )
        print(f"\nAssistant: {result['answer'].content}\n")

