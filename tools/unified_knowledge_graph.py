#!/usr/bin/env python3
"""
Unified Knowledge Graph for Huxley
Combines MCP memory, decision journal, and pattern library into cohesive intelligence layer
"""

import json
import yaml
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import networkx as nx
import pickle
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class NodeType(Enum):
    """Types of nodes in the knowledge graph"""
    CAPSULE = "capsule"
    PATTERN = "pattern"
    DECISION = "decision"
    AGENT = "agent"
    DEPENDENCY = "dependency"
    SOLUTION = "solution"
    ERROR = "error"
    OPTIMIZATION = "optimization"
    TEMPLATE = "template"
    WORKFLOW = "workflow"

@dataclass
class KnowledgeNode:
    """Represents a node in the knowledge graph"""
    id: str
    type: NodeType
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    def update(self, data: Dict[str, Any]):
        """Update node data"""
        self.data.update(data)
        self.updated_at = datetime.now()
    
    def add_tag(self, tag: str):
        """Add a tag to the node"""
        self.tags.add(tag)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": list(self.tags)
        }

@dataclass
class KnowledgeEdge:
    """Represents an edge in the knowledge graph"""
    source: str
    target: str
    relationship: str
    weight: float = 1.0
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source": self.source,
            "target": self.target,
            "relationship": self.relationship,
            "weight": self.weight,
            "data": self.data,
            "created_at": self.created_at.isoformat()
        }

class UnifiedKnowledgeGraph:
    """Unified knowledge graph combining all Huxley intelligence"""
    
    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []
        
        # Storage paths
        self.graph_path = self.catalyst_root / "registry/knowledge_graph.pkl"
        self.mcp_memory_path = Path.home() / ".claude/mcp-data/builder-memory.json"
        self.decision_journal_path = self.catalyst_root / "logs/decision_journal.md"
        self.patterns_path = self.catalyst_root / "registry/success_patterns.json"
        self.events_path = self.catalyst_root / "registry/events.jsonl"
        
        # Load existing graph or initialize
        self._load_graph()
        
        # Sync with all data sources
        self.sync_all_sources()
    
    def _load_graph(self):
        """Load existing graph from storage"""
        if self.graph_path.exists():
            try:
                with open(self.graph_path, 'rb') as f:
                    stored_data = pickle.load(f)
                    self.graph = stored_data.get("graph", nx.DiGraph())
                    self.nodes = stored_data.get("nodes", {})
                    self.edges = stored_data.get("edges", [])
                logger.info(f"Loaded knowledge graph with {len(self.nodes)} nodes")
            except Exception as e:
                logger.error(f"Failed to load graph: {e}")
                self._initialize_graph()
        else:
            self._initialize_graph()
    
    def _initialize_graph(self):
        """Initialize a new knowledge graph"""
        self.graph = nx.DiGraph()
        self.nodes = {}
        self.edges = []
        
        # Create root nodes for major concepts
        root_nodes = [
            ("system", NodeType.CAPSULE, "Huxley"),
            ("patterns", NodeType.PATTERN, "Pattern Library"),
            ("decisions", NodeType.DECISION, "Decision History"),
            ("agents", NodeType.AGENT, "Agent Network"),
            ("workflows", NodeType.WORKFLOW, "Workflow Templates")
        ]
        
        for node_id, node_type, name in root_nodes:
            self.add_node(node_id, node_type, name, {"root": True})
    
    def save_graph(self):
        """Persist graph to storage"""
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        
        stored_data = {
            "graph": self.graph,
            "nodes": self.nodes,
            "edges": self.edges,
            "saved_at": datetime.now().isoformat()
        }
        
        with open(self.graph_path, 'wb') as f:
            pickle.dump(stored_data, f)
        
        # Also export as JSON for readability
        json_path = self.graph_path.with_suffix('.json')
        json_data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "stats": self.get_stats()
        }
        
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        logger.info(f"Saved knowledge graph with {len(self.nodes)} nodes and {len(self.edges)} edges")
    
    def add_node(self, node_id: str, node_type: NodeType, name: str, 
                 data: Optional[Dict[str, Any]] = None) -> KnowledgeNode:
        """Add a node to the graph"""
        if node_id in self.nodes:
            # Update existing node
            self.nodes[node_id].update(data or {})
            return self.nodes[node_id]
        
        node = KnowledgeNode(
            id=node_id,
            type=node_type,
            name=name,
            data=data or {}
        )
        
        self.nodes[node_id] = node
        self.graph.add_node(node_id, **node.to_dict())
        
        return node
    
    def add_edge(self, source: str, target: str, relationship: str, 
                 weight: float = 1.0, data: Optional[Dict[str, Any]] = None) -> KnowledgeEdge:
        """Add an edge to the graph"""
        edge = KnowledgeEdge(
            source=source,
            target=target,
            relationship=relationship,
            weight=weight,
            data=data or {}
        )
        
        self.edges.append(edge)
        # NetworkX stores edge attributes directly
        self.graph.add_edge(source, target, 
                           label=relationship,
                           weight=weight,
                           edge_data=edge.to_dict())
        
        return edge
    
    def sync_all_sources(self):
        """Synchronize with all data sources"""
        logger.info("Syncing knowledge graph with all sources...")
        
        # Sync each data source
        self.sync_mcp_memory()
        self.sync_decision_journal()
        self.sync_patterns()
        self.sync_events()
        self.sync_capsules()
        
        # Analyze relationships
        self._analyze_relationships()
        
        # Extract insights
        self._extract_insights()
        
        # Save updated graph
        self.save_graph()
        
        logger.info("Knowledge graph sync complete")
    
    def sync_mcp_memory(self):
        """Sync with MCP memory"""
        if not self.mcp_memory_path.exists():
            logger.warning("MCP memory not found")
            return
        
        try:
            with open(self.mcp_memory_path, 'r') as f:
                mcp_data = json.load(f)
            
            # Handle different MCP memory formats
            entities = []
            if isinstance(mcp_data, dict):
                entities = mcp_data.get("entities", [])
            elif isinstance(mcp_data, list):
                entities = mcp_data
            
            # Process entities
            for entity in entities:
                if isinstance(entity, dict) and "name" in entity:
                    node_id = f"mcp_{entity['name']}"
                    node = self.add_node(
                        node_id,
                        NodeType.CAPSULE if "capsule" in entity.get("entityType", "").lower() else NodeType.PATTERN,
                        entity["name"],
                        {
                            "observations": entity.get("observations", []),
                            "entity_type": entity.get("entityType")
                        }
                    )
                    node.add_tag("mcp_memory")
                    
                    # Connect to root
                    self.add_edge("system", node_id, "contains")
            
            # Process relations
            for relation in mcp_data.get("relations", []):
                source_id = f"mcp_{relation['from']}"
                target_id = f"mcp_{relation['to']}"
                
                if source_id in self.nodes and target_id in self.nodes:
                    self.add_edge(source_id, target_id, relation["relationType"])
            
            logger.info(f"Synced {len(mcp_data.get('entities', []))} entities from MCP memory")
            
        except Exception as e:
            logger.error(f"Failed to sync MCP memory: {e}")
    
    def sync_decision_journal(self):
        """Sync with decision journal"""
        if not self.decision_journal_path.exists():
            logger.warning("Decision journal not found")
            return
        
        try:
            with open(self.decision_journal_path, 'r') as f:
                content = f.read()
            
            # Parse decision entries (simple parsing, could be enhanced)
            decisions = []
            current_decision = {}
            
            for line in content.split('\n'):
                if line.startswith('## '):
                    if current_decision:
                        decisions.append(current_decision)
                    current_decision = {
                        "timestamp": line.replace('## ', '').split(' - ')[0],
                        "title": line.replace('## ', '').split(' - ')[-1] if ' - ' in line else "",
                        "details": []
                    }
                elif line.startswith('**') and current_decision:
                    key = line.split(':')[0].replace('**', '').strip()
                    value = ':'.join(line.split(':')[1:]).strip() if ':' in line else ""
                    current_decision[key] = value
                elif line.strip() and current_decision:
                    current_decision["details"].append(line.strip())
            
            if current_decision:
                decisions.append(current_decision)
            
            # Add decisions to graph
            for i, decision in enumerate(decisions):
                node_id = f"decision_{i}_{hashlib.md5(str(decision).encode()).hexdigest()[:8]}"
                node = self.add_node(
                    node_id,
                    NodeType.DECISION,
                    decision.get("title", f"Decision {i}"),
                    decision
                )
                node.add_tag("decision_journal")
                
                # Connect to decisions root
                self.add_edge("decisions", node_id, "includes")
                
                # Extract and link mentioned entities
                self._extract_decision_entities(node_id, decision)
            
            logger.info(f"Synced {len(decisions)} decisions from journal")
            
        except Exception as e:
            logger.error(f"Failed to sync decision journal: {e}")
    
    def sync_patterns(self):
        """Sync with pattern library"""
        if not self.patterns_path.exists():
            logger.warning("Pattern library not found")
            return
        
        try:
            with open(self.patterns_path, 'r') as f:
                patterns_data = json.load(f)
            
            # Process successful capsules
            for capsule_name, pattern in patterns_data.get("successful_capsules", {}).items():
                node_id = f"pattern_{capsule_name}"
                node = self.add_node(
                    node_id,
                    NodeType.PATTERN,
                    f"Pattern: {capsule_name}",
                    pattern
                )
                node.add_tag("success_pattern")
                
                # Connect to patterns root
                self.add_edge("patterns", node_id, "contains")
                
                # Link to agents used
                for agent in pattern.get("agents", []):
                    agent_id = f"agent_{agent}"
                    agent_node = self.add_node(agent_id, NodeType.AGENT, agent, {})
                    self.add_edge(node_id, agent_id, "uses_agent")
            
            # Process common patterns
            if "common_agents" in patterns_data:
                for agent, frequency in patterns_data["common_agents"].items():
                    agent_id = f"agent_{agent}"
                    if agent_id in self.nodes:
                        self.nodes[agent_id].data["frequency"] = frequency
            
            logger.info(f"Synced {len(patterns_data.get('successful_capsules', {}))} patterns")
            
        except Exception as e:
            logger.error(f"Failed to sync patterns: {e}")
    
    def sync_events(self):
        """Sync with event log"""
        if not self.events_path.exists():
            logger.warning("Events log not found")
            return
        
        try:
            events = []
            with open(self.events_path, 'r') as f:
                for line_num, line in enumerate(f):
                    if line.strip():
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")
            
            # Group events by capsule
            capsule_events = {}
            for event in events:
                capsule = event.get("capsule", "system")
                if capsule not in capsule_events:
                    capsule_events[capsule] = []
                capsule_events[capsule].append(event)
            
            # Add event summaries to graph
            for capsule, events_list in capsule_events.items():
                if events_list:
                    node_id = f"events_{capsule}"
                    node = self.add_node(
                        node_id,
                        NodeType.WORKFLOW,
                        f"Events: {capsule}",
                        {
                            "event_count": len(events_list),
                            "event_types": list(set(e.get("type", "") for e in events_list)),
                            "latest_event": events_list[-1] if events_list else None
                        }
                    )
                    node.add_tag("event_log")
                    
                    # Connect to system
                    self.add_edge("system", node_id, "has_events")
            
            logger.info(f"Synced {len(events)} events")
            
        except Exception as e:
            logger.error(f"Failed to sync events: {e}")
    
    def sync_capsules(self):
        """Sync with actual capsule files"""
        capsules_dir = self.catalyst_root / "capsules"
        
        for capsule_path in capsules_dir.iterdir():
            if not capsule_path.is_dir() or capsule_path.name.startswith('.'):
                continue
            
            node_id = f"capsule_{capsule_path.name}"
            
            # Load capsule metadata
            capsule_data = {}
            capsule_json = capsule_path / "capsule.json"
            if capsule_json.exists():
                with open(capsule_json, 'r') as f:
                    capsule_data = json.load(f)
            
            # Add capsule node
            node = self.add_node(
                node_id,
                NodeType.CAPSULE,
                capsule_path.name,
                {
                    "path": str(capsule_path),
                    "has_src": (capsule_path / "src").exists(),
                    "has_tests": (capsule_path / "tests").exists(),
                    "has_docs": (capsule_path / "docs").exists(),
                    **capsule_data
                }
            )
            node.add_tag("active_capsule")
            
            # Connect to system
            self.add_edge("system", node_id, "manages")
            
            # Detect dependencies
            self._detect_dependencies(node_id, capsule_path)
    
    def _detect_dependencies(self, capsule_id: str, capsule_path: Path):
        """Detect and link capsule dependencies"""
        dependency_files = [
            capsule_path / "package.json",
            capsule_path / "requirements.txt",
            capsule_path / "Pipfile",
            capsule_path / "Cargo.toml"
        ]
        
        for dep_file in dependency_files:
            if dep_file.exists():
                dep_id = f"deps_{capsule_id}_{dep_file.name}"
                node = self.add_node(
                    dep_id,
                    NodeType.DEPENDENCY,
                    f"Dependencies: {dep_file.name}",
                    {"file": str(dep_file)}
                )
                self.add_edge(capsule_id, dep_id, "has_dependencies")
    
    def _extract_decision_entities(self, decision_id: str, decision: Dict[str, Any]):
        """Extract entities mentioned in decisions"""
        text = str(decision)
        
        # Look for capsule mentions
        for capsule_name in self.nodes:
            if capsule_name.startswith("capsule_"):
                actual_name = capsule_name.replace("capsule_", "")
                if actual_name in text:
                    self.add_edge(decision_id, capsule_name, "references")
        
        # Look for agent mentions
        known_agents = [
            "code-reviewer", "debugger", "system-architect",
            "security-analyst", "performance-optimizer", "frontend-specialist"
        ]
        
        for agent in known_agents:
            if agent in text.lower():
                agent_id = f"agent_{agent}"
                self.add_node(agent_id, NodeType.AGENT, agent, {})
                self.add_edge(decision_id, agent_id, "mentions_agent")
    
    def _analyze_relationships(self):
        """Analyze and create derived relationships"""
        # Find patterns in successful capsules
        successful_patterns = [n for n in self.nodes.values() 
                              if n.type == NodeType.PATTERN and "success" in str(n.tags)]
        
        for pattern in successful_patterns:
            # Find similar patterns
            for other_pattern in successful_patterns:
                if pattern.id != other_pattern.id:
                    similarity = self._calculate_similarity(pattern, other_pattern)
                    if similarity > 0.7:
                        self.add_edge(pattern.id, other_pattern.id, "similar_to", weight=similarity)
        
        # Link errors to solutions
        error_nodes = [n for n in self.nodes.values() if n.type == NodeType.ERROR]
        solution_nodes = [n for n in self.nodes.values() if n.type == NodeType.SOLUTION]
        
        for error in error_nodes:
            for solution in solution_nodes:
                if self._is_solution_for(solution, error):
                    self.add_edge(error.id, solution.id, "solved_by")
    
    def _calculate_similarity(self, node1: KnowledgeNode, node2: KnowledgeNode) -> float:
        """Calculate similarity between two nodes"""
        # Simple similarity based on shared tags and data keys
        tags1 = set(node1.tags)
        tags2 = set(node2.tags)
        
        if not tags1 or not tags2:
            return 0.0
        
        tag_similarity = len(tags1.intersection(tags2)) / len(tags1.union(tags2))
        
        # Data key similarity
        keys1 = set(node1.data.keys())
        keys2 = set(node2.data.keys())
        
        if keys1 and keys2:
            key_similarity = len(keys1.intersection(keys2)) / len(keys1.union(keys2))
        else:
            key_similarity = 0
        
        return (tag_similarity + key_similarity) / 2
    
    def _is_solution_for(self, solution: KnowledgeNode, error: KnowledgeNode) -> bool:
        """Check if a solution node solves an error"""
        # Simple heuristic - could be enhanced with ML
        error_text = str(error.data).lower()
        solution_text = str(solution.data).lower()
        
        # Check for keyword matches
        error_keywords = set(error_text.split())
        solution_keywords = set(solution_text.split())
        
        common_keywords = error_keywords.intersection(solution_keywords)
        
        return len(common_keywords) > 3
    
    def _extract_insights(self):
        """Extract high-level insights from the graph"""
        insights = {
            "most_connected_nodes": self._find_most_connected(),
            "common_patterns": self._find_common_patterns(),
            "bottlenecks": self._find_bottlenecks(),
            "success_factors": self._analyze_success_factors()
        }
        
        # Store insights
        insights_id = "insights_current"
        self.add_node(
            insights_id,
            NodeType.OPTIMIZATION,
            "System Insights",
            insights
        )
        self.add_edge("system", insights_id, "has_insights")
        
        logger.info(f"Extracted {len(insights)} insight categories")
    
    def _find_most_connected(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Find most connected nodes (hubs)"""
        centrality = nx.degree_centrality(self.graph)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {
                "node": node_id,
                "name": self.nodes[node_id].name if node_id in self.nodes else node_id,
                "connections": centrality[node_id]
            }
            for node_id, _ in sorted_nodes[:top_n]
        ]
    
    def _find_common_patterns(self) -> Dict[str, Any]:
        """Find common patterns across the graph"""
        # Find frequent subgraphs
        patterns = {}
        
        # Agent usage patterns
        agent_nodes = [n for n in self.nodes.values() if n.type == NodeType.AGENT]
        agent_usage = {}
        
        for agent in agent_nodes:
            in_edges = self.graph.in_edges(agent.id)
            agent_usage[agent.name] = len(in_edges)
        
        patterns["frequent_agents"] = sorted(agent_usage.items(), 
                                            key=lambda x: x[1], reverse=True)[:5]
        
        # Workflow patterns
        workflow_nodes = [n for n in self.nodes.values() if n.type == NodeType.WORKFLOW]
        patterns["workflow_count"] = len(workflow_nodes)
        
        return patterns
    
    def _find_bottlenecks(self) -> List[str]:
        """Identify potential bottlenecks in the system"""
        bottlenecks = []
        
        # Nodes with high betweenness centrality are potential bottlenecks
        if len(self.graph.nodes) > 0:
            betweenness = nx.betweenness_centrality(self.graph)
            high_betweenness = sorted(betweenness.items(), 
                                     key=lambda x: x[1], reverse=True)[:5]
            
            for node_id, score in high_betweenness:
                if score > 0.1:  # Threshold for bottleneck
                    node_name = self.nodes[node_id].name if node_id in self.nodes else node_id
                    bottlenecks.append(f"{node_name} (score: {score:.2f})")
        
        return bottlenecks
    
    def _analyze_success_factors(self) -> Dict[str, Any]:
        """Analyze factors contributing to success"""
        success_factors = {}
        
        # Find successful patterns
        successful = [n for n in self.nodes.values() 
                     if "success" in str(n.tags) or "successful" in str(n.data)]
        
        if successful:
            # Common agents in successful projects
            agents_in_success = {}
            for node in successful:
                for edge in self.graph.out_edges(node.id):
                    target = edge[1]
                    if target in self.nodes and self.nodes[target].type == NodeType.AGENT:
                        agent_name = self.nodes[target].name
                        agents_in_success[agent_name] = agents_in_success.get(agent_name, 0) + 1
            
            success_factors["key_agents"] = agents_in_success
            
            # Average time to success
            durations = []
            for node in successful:
                if "duration_hours" in node.data:
                    durations.append(node.data["duration_hours"])
            
            if durations:
                success_factors["avg_duration_hours"] = sum(durations) / len(durations)
        
        return success_factors
    
    # Query methods
    def query(self, query_type: str, **kwargs) -> Any:
        """Query the knowledge graph"""
        queries = {
            "find_similar": self.find_similar_nodes,
            "get_path": self.find_path,
            "get_recommendations": self.get_recommendations,
            "get_node": self.get_node,
            "search": self.search_nodes
        }
        
        query_func = queries.get(query_type)
        if query_func:
            return query_func(**kwargs)
        
        return None
    
    def find_similar_nodes(self, node_id: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """Find nodes similar to the given node"""
        if node_id not in self.nodes:
            return []
        
        node = self.nodes[node_id]
        similarities = []
        
        for other_id, other_node in self.nodes.items():
            if other_id != node_id:
                similarity = self._calculate_similarity(node, other_node)
                if similarity > 0:
                    similarities.append((other_id, similarity))
        
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_n]
    
    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find shortest path between two nodes"""
        try:
            return nx.shortest_path(self.graph, source, target)
        except nx.NetworkXNoPath:
            return None
    
    def get_recommendations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get recommendations based on context"""
        recommendations = []
        
        # Find similar successful projects
        if "capsule_name" in context:
            capsule_id = f"capsule_{context['capsule_name']}"
            similar = self.find_similar_nodes(capsule_id)
            
            for similar_id, score in similar:
                if similar_id in self.nodes:
                    node = self.nodes[similar_id]
                    if "success" in str(node.tags):
                        recommendations.append({
                            "type": "similar_success",
                            "reference": node.name,
                            "confidence": score,
                            "data": node.data
                        })
        
        # Recommend agents based on patterns
        if "task_type" in context:
            task_type = context["task_type"]
            relevant_agents = []
            
            for node in self.nodes.values():
                if node.type == NodeType.AGENT:
                    if task_type in str(node.data).lower():
                        relevant_agents.append({
                            "type": "recommended_agent",
                            "agent": node.name,
                            "reason": f"Effective for {task_type} tasks"
                        })
            
            recommendations.extend(relevant_agents)
        
        return recommendations[:10]  # Limit recommendations
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get a specific node"""
        return self.nodes.get(node_id)
    
    def search_nodes(self, query: str, node_type: Optional[NodeType] = None) -> List[KnowledgeNode]:
        """Search nodes by text query"""
        results = []
        query_lower = query.lower()
        
        for node in self.nodes.values():
            if node_type and node.type != node_type:
                continue
            
            # Search in name, tags, and data
            if (query_lower in node.name.lower() or
                query_lower in str(node.tags).lower() or
                query_lower in str(node.data).lower()):
                results.append(node)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": {
                node_type.value: sum(1 for n in self.nodes.values() if n.type == node_type)
                for node_type in NodeType
            },
            "connected_components": nx.number_weakly_connected_components(self.graph),
            "density": nx.density(self.graph),
            "average_degree": sum(dict(self.graph.degree()).values()) / len(self.graph.nodes) if self.graph.nodes else 0
        }
    
    def export_for_visualization(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Export graph in format suitable for visualization"""
        if output_path is None:
            output_path = self.catalyst_root / "registry/knowledge_graph_viz.json"
        
        viz_data = {
            "nodes": [
                {
                    "id": node_id,
                    "label": node.name,
                    "type": node.type.value,
                    "size": len(self.graph.edges(node_id)) + 1,
                    "tags": list(node.tags),
                    "created": node.created_at.isoformat()
                }
                for node_id, node in self.nodes.items()
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.relationship,
                    "weight": edge.weight
                }
                for edge in self.edges
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(viz_data, f, indent=2)
        
        return viz_data


def main():
    """CLI interface for knowledge graph"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified Knowledge Graph")
    parser.add_argument("command", choices=["sync", "stats", "query", "export", "search"],
                       help="Command to execute")
    parser.add_argument("--query-type", help="Type of query (find_similar, get_path, etc)")
    parser.add_argument("--node-id", help="Node ID for queries")
    parser.add_argument("--search", help="Search query string")
    parser.add_argument("--output", help="Output path for export")
    
    args = parser.parse_args()
    
    graph = UnifiedKnowledgeGraph()
    
    if args.command == "sync":
        graph.sync_all_sources()
        print("Knowledge graph synchronized")
    
    elif args.command == "stats":
        stats = graph.get_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.command == "query":
        if args.query_type == "find_similar" and args.node_id:
            results = graph.find_similar_nodes(args.node_id)
            for node_id, score in results:
                node = graph.get_node(node_id)
                if node:
                    print(f"{score:.2f}: {node.name} ({node.type.value})")
        
        elif args.query_type == "get_node" and args.node_id:
            node = graph.get_node(args.node_id)
            if node:
                print(json.dumps(node.to_dict(), indent=2))
            else:
                print(f"Node {args.node_id} not found")
    
    elif args.command == "search":
        if args.search:
            results = graph.search_nodes(args.search)
            for node in results:
                print(f"{node.id}: {node.name} ({node.type.value})")
    
    elif args.command == "export":
        output_path = Path(args.output) if args.output else None
        viz_data = graph.export_for_visualization(output_path)
        print(f"Exported {len(viz_data['nodes'])} nodes and {len(viz_data['edges'])} edges")


if __name__ == "__main__":
    main()