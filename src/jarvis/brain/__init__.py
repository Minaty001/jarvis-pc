"""JARVIS brain: persona, agent loop, LLM client, and long-term memory."""

from jarvis.brain.agent import JarvisAgent, build_agent
from jarvis.brain.client import LLMClient, LocalBrain
from jarvis.brain.consolidator import MemoryConsolidator
from jarvis.brain.graph import GraphEntity, GraphRelation, KnowledgeGraph
from jarvis.brain.memory import MemoryStore
from jarvis.brain.persona import PERSONA, build_system_prompt

__all__ = [
    "JarvisAgent",
    "build_agent",
    "LLMClient",
    "LocalBrain",
    "MemoryStore",
    "KnowledgeGraph",
    "GraphEntity",
    "GraphRelation",
    "MemoryConsolidator",
    "PERSONA",
    "build_system_prompt",
]