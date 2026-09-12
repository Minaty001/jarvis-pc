"""Unit tests for MemoryConsolidator episodic turn distillation and graph synchronization."""

import pytest
from jarvis.brain.consolidator import MemoryConsolidator
from jarvis.brain.graph import KnowledgeGraph
from jarvis.brain.memory import MemoryStore
from jarvis.tools.builtin.memory_tools import (
    add_graph_fact,
    consolidate_user_memory,
    list_known_entities,
    query_knowledge_graph,
)
from jarvis.cli.main import run_cli


@pytest.fixture
def temp_memory_and_graph(tmp_path):
    mem_db = tmp_path / "memory.db"
    graph_db = tmp_path / "graph.db"
    mem_store = MemoryStore(mem_db)
    graph = KnowledgeGraph(graph_db)
    yield mem_store, graph
    graph.close()


def test_triple_extraction_from_dialogue(temp_memory_and_graph):
    """Verify regex and heuristic triple extraction from user utterances."""
    mem_store, graph = temp_memory_and_graph
    consolidator = MemoryConsolidator(memory_store=mem_store, graph=graph)

    t1 = consolidator.extract_triples_from_text("My name is Alice")
    assert len(t1) == 1
    assert t1[0] == ("User", "has_name", "Alice", "person")

    t2 = consolidator.extract_triples_from_text("I live in San Francisco and work on project Apollo")
    assert len(t2) >= 2

    t3 = consolidator.extract_triples_from_text("I code with Neovim")
    assert len(t3) == 1
    assert t3[0] == ("User", "uses_tool", "Neovim", "tool")


def test_consolidation_pipeline_execution(temp_memory_and_graph):
    """Verify full consolidation cycle from raw chat episodes to Knowledge Graph."""
    mem_store, graph = temp_memory_and_graph
    consolidator = MemoryConsolidator(memory_store=mem_store, graph=graph)

    # Add raw episodes
    mem_store.add("My name is John", "Pleased to make your acquaintance, John.")
    mem_store.add("I live in Seattle", "Noted, sir. Seattle location updated.")
    mem_store.add("I code with VS Code", "VS Code is excellent.")

    res = consolidator.consolidate(limit=10)
    assert res["consolidated_episodes"] == 3
    assert res["new_relations"] >= 3
    assert res["total_entities"] >= 4

    # Verify Knowledge Graph nodes
    user_ent = graph.get_entity("User")
    assert user_ent is not None

    seattle = graph.get_entity("Seattle")
    assert seattle is not None

    # Verify semantic profile
    profile = mem_store.get_user_profile()
    assert profile is not None


def test_cli_memory_graph_and_consolidate(capsys):
    """Verify CLI commands for memory graph, consolidate, and entities."""
    # 1. Consolidate
    ret1 = run_cli(["memory", "consolidate"])
    assert ret1 == 0
    out1 = capsys.readouterr().out
    assert "JARVIS Memory Consolidation" in out1

    # 2. Graph query
    ret2 = run_cli(["memory", "graph", "--entity", "User"])
    assert ret2 == 0
    out2 = capsys.readouterr().out
    assert "Knowledge Graph Subgraph" in out2 or "No graph relationships" in out2

    # 3. Entities
    ret3 = run_cli(["memory", "entities"])
    assert ret3 == 0
    out3 = capsys.readouterr().out
    assert "Tracked Knowledge Graph Entities" in out3 or "No entities" in out3
