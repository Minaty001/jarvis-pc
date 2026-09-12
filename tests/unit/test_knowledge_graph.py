"""Unit tests for SQLite Knowledge Graph store and graph traversal queries."""

import pytest
from jarvis.brain.graph import KnowledgeGraph, GraphEntity, GraphRelation


@pytest.fixture
def temp_graph(tmp_path):
    db_file = tmp_path / "test_graph.db"
    graph = KnowledgeGraph(path=db_file)
    yield graph
    graph.close()


def test_entity_creation_and_retrieval(temp_graph):
    """Verify creating, querying, and updating nodes in the knowledge graph."""
    graph = temp_graph

    # 1. Add entity
    ent1 = graph.add_entity(name="Linux", entity_type="os", aliases=["GNU/Linux"])
    assert ent1.id is not None
    assert ent1.name == "Linux"
    assert "GNU/Linux" in ent1.aliases

    # 2. Query by name
    found = graph.get_entity("Linux")
    assert found is not None
    assert found.id == ent1.id

    # 3. Query case-insensitive
    found_lower = graph.get_entity("linux")
    assert found_lower is not None
    assert found_lower.id == ent1.id

    # 4. Find or create
    same_ent = graph.find_or_create_entity("Linux")
    assert same_ent.id == ent1.id


def test_relation_linking_and_subgraph(temp_graph):
    """Verify directed relationships, neighborhood expansion, and format output."""
    graph = temp_graph

    u = graph.add_entity("User", entity_type="person")
    py = graph.add_entity("Python", entity_type="language")
    vs = graph.add_entity("VSCode", entity_type="editor")
    jarvis = graph.add_entity("JARVIS", entity_type="assistant")

    # Add edges
    r1 = graph.add_relation(source=u, relation_type="codes_in", target=py, confidence=0.98)
    r2 = graph.add_relation(source=u, relation_type="uses_editor", target=vs, confidence=0.95)
    r3 = graph.add_relation(source=jarvis, relation_type="assists", target=u, confidence=1.0)

    assert r1.id is not None
    assert r2.id is not None
    assert r3.id is not None

    # Test get_relations_for_entity
    u_rels = graph.get_relations_for_entity("User")
    assert len(u_rels) == 3

    # Test get_subgraph (depth=1)
    sg1 = graph.get_subgraph("User", depth=1)
    assert len(sg1["entities"]) >= 3
    assert len(sg1["relations"]) >= 3

    # Test formatted context
    fmt = graph.format_subgraph_context("User", depth=1)
    assert "Relational Knowledge for 'User':" in fmt
    assert "codes in" in fmt
    assert "uses editor" in fmt


def test_graph_stats(temp_graph):
    graph = temp_graph
    assert graph.stats()["total_entities"] == 0
    graph.add_entity("NodeA")
    graph.add_entity("NodeB")
    graph.add_relation("NodeA", "connects_to", "NodeB")
    st = graph.stats()
    assert st["total_entities"] == 2
    assert st["total_relations"] == 1
