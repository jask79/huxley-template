#!/usr/bin/env python3
"""
Capsule Dependency Mapper - Build and maintain global dependency graph
Tracks capsules, MCP servers, APIs, models, tools, and their interconnections
"""

import os
import sys
import json
import yaml
import pathlib
import logging
import hashlib
from typing import Dict, List, Any, Set, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import defaultdict
import re

# Add Huxley tools to path
CATALYST_ROOT = pathlib.Path("{{CATALYST_ROOT}}")
sys.path.append(str(CATALYST_ROOT / "tools"))

try:
    from events_logger import log_event
except ImportError as e:
    print(f"Warning: Could not import Huxley tools: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class DependencyNode:
    """Represents a node in the dependency graph"""
    id: str
    name: str
    type: str  # 'capsule', 'mcp', 'api', 'tool', 'model', 'file', 'service'
    version: Optional[str] = None
    source: Optional[str] = None  # Path or URL where this dependency is defined
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class DependencyEdge:
    """Represents an edge (relationship) in the dependency graph"""
    from_node: str
    to_node: str
    relationship: str  # 'requires', 'uses', 'imports', 'calls', 'extends'
    optional: bool = False
    version_constraint: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class DependencyGraph:
    """Complete dependency graph"""
    nodes: Dict[str, DependencyNode]
    edges: List[DependencyEdge]
    generated_at: str
    graph_hash: str
    
    def __post_init__(self):
        if not hasattr(self, 'generated_at') or not self.generated_at:
            self.generated_at = datetime.now().isoformat()

class DependencyMapper:
    """Builds and maintains global dependency graph"""
    
    def __init__(self):
        self.catalyst_root = CATALYST_ROOT
        self.output_dir = self.catalyst_root / "global"
        self.docs_dir = self.catalyst_root / "docs"
        
        # Ensure output directories exist
        self.output_dir.mkdir(exist_ok=True)
        self.docs_dir.mkdir(exist_ok=True)
        
        self.nodes: Dict[str, DependencyNode] = {}
        self.edges: List[DependencyEdge] = []
        
        # Previous graph for change detection
        self.previous_graph: Optional[DependencyGraph] = None
    
    def build_complete_graph(self) -> DependencyGraph:
        """Build complete dependency graph from all sources"""
        logger.info("Building complete dependency graph...")
        
        # Load previous graph for change detection
        self._load_previous_graph()
        
        # Clear current state
        self.nodes.clear()
        self.edges.clear()
        
        # Scan all sources
        self._scan_capsules()
        self._scan_mcp_configs()
        self._scan_global_configs()
        self._scan_tools()
        self._scan_imports()
        
        # Create graph
        graph_hash = self._calculate_graph_hash()
        graph = DependencyGraph(
            nodes=self.nodes.copy(),
            edges=self.edges.copy(),
            generated_at=datetime.now().isoformat(),
            graph_hash=graph_hash
        )
        
        # Detect and log changes
        changes = self._detect_changes(graph)
        if changes:
            self._log_changes(changes)
        
        # Save outputs
        self._save_graph_json(graph)
        self._generate_mermaid_diagram(graph)
        self._generate_reports(graph)
        
        logger.info(f"Dependency graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        return graph
    
    def _load_previous_graph(self):
        """Load previous graph for change detection"""
        graph_file = self.output_dir / "dependency-graph.json"
        if graph_file.exists():
            try:
                with open(graph_file, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct nodes
                nodes = {}
                for node_id, node_data in data.get("nodes", {}).items():
                    nodes[node_id] = DependencyNode(**node_data)
                
                # Reconstruct edges
                edges = []
                for edge_data in data.get("edges", []):
                    edges.append(DependencyEdge(**edge_data))
                
                self.previous_graph = DependencyGraph(
                    nodes=nodes,
                    edges=edges,
                    generated_at=data.get("generated_at", ""),
                    graph_hash=data.get("graph_hash", "")
                )
                
            except Exception as e:
                logger.warning(f"Could not load previous graph: {e}")
    
    def _scan_capsules(self):
        """Scan all capsules for dependencies"""
        capsules_dir = self.catalyst_root / "capsules"
        if not capsules_dir.exists():
            return
        
        for capsule_dir in capsules_dir.iterdir():
            if capsule_dir.is_dir() and not capsule_dir.name.startswith('.'):
                self._scan_capsule(capsule_dir)
    
    def _scan_capsule(self, capsule_dir: pathlib.Path):
        """Scan individual capsule for dependencies"""
        capsule_name = capsule_dir.name
        
        # Add capsule as node
        capsule_node = DependencyNode(
            id=f"capsule:{capsule_name}",
            name=capsule_name,
            type="capsule",
            source=str(capsule_dir),
            metadata={"path": str(capsule_dir)}
        )
        self.nodes[capsule_node.id] = capsule_node
        
        # Scan requirements.yaml
        req_file = capsule_dir / "spec" / "requirements.yaml"
        if req_file.exists():
            self._scan_requirements_yaml(capsule_name, req_file)
        
        # Scan capsule.json
        capsule_json = capsule_dir / "capsule.json"
        if capsule_json.exists():
            self._scan_capsule_json(capsule_name, capsule_json)
        
        # Scan source files for imports
        src_dir = capsule_dir / "src"
        if src_dir.exists():
            self._scan_source_directory(capsule_name, src_dir)
    
    def _scan_requirements_yaml(self, capsule_name: str, req_file: pathlib.Path):
        """Scan capsule requirements.yaml for dependencies"""
        try:
            with open(req_file, 'r') as f:
                requirements = yaml.safe_load(f)
            
            if not requirements:
                return
            
            # Dependencies section
            deps = requirements.get("dependencies", {})
            
            # MCP dependencies
            mcp_deps = deps.get("mcp", [])
            for mcp_dep in mcp_deps:
                mcp_name = mcp_dep if isinstance(mcp_dep, str) else mcp_dep.get("name", "unknown")
                mcp_node_id = f"mcp:{mcp_name}"
                
                # Add MCP node if not exists
                if mcp_node_id not in self.nodes:
                    self.nodes[mcp_node_id] = DependencyNode(
                        id=mcp_node_id,
                        name=mcp_name,
                        type="mcp",
                        source=str(req_file)
                    )
                
                # Add edge
                self.edges.append(DependencyEdge(
                    from_node=f"capsule:{capsule_name}",
                    to_node=mcp_node_id,
                    relationship="requires"
                ))
            
            # API dependencies
            api_deps = deps.get("apis", [])
            for api_dep in api_deps:
                api_name = api_dep if isinstance(api_dep, str) else api_dep.get("name", "unknown")
                api_node_id = f"api:{api_name}"
                
                # Add API node if not exists
                if api_node_id not in self.nodes:
                    self.nodes[api_node_id] = DependencyNode(
                        id=api_node_id,
                        name=api_name,
                        type="api",
                        source=str(req_file),
                        metadata={
                            "endpoint": api_dep.get("endpoint") if isinstance(api_dep, dict) else None
                        }
                    )
                
                # Add edge
                optional = api_dep.get("optional", False) if isinstance(api_dep, dict) else False
                self.edges.append(DependencyEdge(
                    from_node=f"capsule:{capsule_name}",
                    to_node=api_node_id,
                    relationship="uses",
                    optional=optional
                ))
            
            # Tool dependencies
            tool_deps = deps.get("tools", [])
            for tool_dep in tool_deps:
                tool_name = tool_dep if isinstance(tool_dep, str) else tool_dep.get("name", "unknown")
                tool_node_id = f"tool:{tool_name}"
                
                # Add tool node if not exists
                if tool_node_id not in self.nodes:
                    self.nodes[tool_node_id] = DependencyNode(
                        id=tool_node_id,
                        name=tool_name,
                        type="tool",
                        source=str(req_file)
                    )
                
                # Add edge
                self.edges.append(DependencyEdge(
                    from_node=f"capsule:{capsule_name}",
                    to_node=tool_node_id,
                    relationship="uses"
                ))
                
        except Exception as e:
            logger.warning(f"Could not parse {req_file}: {e}")
    
    def _scan_capsule_json(self, capsule_name: str, capsule_json: pathlib.Path):
        """Scan capsule.json for metadata and dependencies"""
        try:
            with open(capsule_json, 'r') as f:
                capsule_data = json.load(f)
            
            # Update capsule node with metadata
            capsule_node_id = f"capsule:{capsule_name}"
            if capsule_node_id in self.nodes:
                self.nodes[capsule_node_id].version = capsule_data.get("version")
                self.nodes[capsule_node_id].metadata.update({
                    "type": capsule_data.get("type"),
                    "description": capsule_data.get("description"),
                })
                
        except Exception as e:
            logger.warning(f"Could not parse {capsule_json}: {e}")
    
    def _scan_mcp_configs(self):
        """Scan MCP configuration files"""
        # Global MCP config
        mcp_config = self.catalyst_root / ".mcp.json"
        if mcp_config.exists():
            self._scan_mcp_json(mcp_config)
        
        # Project-specific MCP configs
        for mcp_file in self.catalyst_root.rglob(".mcp.json"):
            if mcp_file != mcp_config:
                self._scan_mcp_json(mcp_file)
    
    def _scan_mcp_json(self, mcp_file: pathlib.Path):
        """Scan individual .mcp.json file"""
        try:
            with open(mcp_file, 'r') as f:
                mcp_data = json.load(f)
            
            # Process MCP server definitions
            servers = mcp_data.get("servers", {})
            for server_name, server_config in servers.items():
                mcp_node_id = f"mcp:{server_name}"
                
                # Add or update MCP node
                if mcp_node_id not in self.nodes:
                    self.nodes[mcp_node_id] = DependencyNode(
                        id=mcp_node_id,
                        name=server_name,
                        type="mcp",
                        source=str(mcp_file)
                    )
                
                # Update metadata
                self.nodes[mcp_node_id].metadata.update({
                    "command": server_config.get("command"),
                    "args": server_config.get("args"),
                    "env": server_config.get("env"),
                    "config_source": str(mcp_file)
                })
                
        except Exception as e:
            logger.warning(f"Could not parse {mcp_file}: {e}")
    
    def _scan_global_configs(self):
        """Scan global configuration files"""
        # Huxley tools
        tools_dir = self.catalyst_root / "tools"
        if tools_dir.exists():
            for tool_file in tools_dir.glob("*.py"):
                if tool_file.stem not in ["__init__", "__pycache__"]:
                    tool_node_id = f"tool:{tool_file.stem}"
                    
                    if tool_node_id not in self.nodes:
                        self.nodes[tool_node_id] = DependencyNode(
                            id=tool_node_id,
                            name=tool_file.stem,
                            type="tool",
                            source=str(tool_file),
                            metadata={"path": str(tool_file)}
                        )
    
    def _scan_tools(self):
        """Scan for tool-to-tool dependencies"""
        tools_dir = self.catalyst_root / "tools"
        if not tools_dir.exists():
            return
        
        for tool_file in tools_dir.glob("*.py"):
            self._scan_tool_imports(tool_file.stem, tool_file)
    
    def _scan_tool_imports(self, tool_name: str, tool_file: pathlib.Path):
        """Scan tool file for imports and dependencies"""
        try:
            with open(tool_file, 'r') as f:
                content = f.read()
            
            # Find local imports (Huxley tools)
            import_pattern = r'from\s+(\w+)\s+import|import\s+(\w+)'
            matches = re.findall(import_pattern, content)
            
            for match in matches:
                imported_module = match[0] or match[1]
                
                # Check if it's a Huxley tool
                imported_tool_file = tools_dir / f"{imported_module}.py"
                if imported_tool_file.exists():
                    self.edges.append(DependencyEdge(
                        from_node=f"tool:{tool_name}",
                        to_node=f"tool:{imported_module}",
                        relationship="imports"
                    ))
                
        except Exception as e:
            logger.warning(f"Could not scan tool imports for {tool_file}: {e}")
    
    def _scan_source_directory(self, capsule_name: str, src_dir: pathlib.Path):
        """Scan capsule source directory for imports"""
        for py_file in src_dir.rglob("*.py"):
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Look for Huxley tool imports
                if "from rag_client import" in content or "import rag_client" in content:
                    self.edges.append(DependencyEdge(
                        from_node=f"capsule:{capsule_name}",
                        to_node="tool:rag_client",
                        relationship="imports"
                    ))
                
                # Look for specific API calls or services
                if "requests." in content or "import requests" in content:
                    api_node_id = "service:http_requests"
                    if api_node_id not in self.nodes:
                        self.nodes[api_node_id] = DependencyNode(
                            id=api_node_id,
                            name="HTTP Requests",
                            type="service",
                            source="inferred"
                        )
                    
                    self.edges.append(DependencyEdge(
                        from_node=f"capsule:{capsule_name}",
                        to_node=api_node_id,
                        relationship="uses"
                    ))
                    
            except Exception as e:
                logger.warning(f"Could not scan {py_file}: {e}")
    
    def _scan_imports(self):
        """Additional import scanning for system-wide dependencies"""
        # This could be expanded to scan for more sophisticated dependency patterns
        pass
    
    def _calculate_graph_hash(self) -> str:
        """Calculate hash of current graph for change detection"""
        # Create deterministic representation
        nodes_repr = json.dumps({k: asdict(v) for k, v in sorted(self.nodes.items())}, sort_keys=True)
        edges_repr = json.dumps([asdict(e) for e in sorted(self.edges, key=lambda x: (x.from_node, x.to_node))], sort_keys=True)
        
        combined = nodes_repr + edges_repr
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _detect_changes(self, current_graph: DependencyGraph) -> Dict[str, Any]:
        """Detect changes from previous graph"""
        if not self.previous_graph:
            return {"type": "initial", "message": "Initial dependency graph generated"}
        
        changes = {
            "added_nodes": [],
            "removed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "modified_nodes": []
        }
        
        # Node changes
        prev_node_ids = set(self.previous_graph.nodes.keys())
        curr_node_ids = set(current_graph.nodes.keys())
        
        changes["added_nodes"] = list(curr_node_ids - prev_node_ids)
        changes["removed_nodes"] = list(prev_node_ids - curr_node_ids)
        
        # Edge changes (simplified comparison)
        prev_edges = {(e.from_node, e.to_node, e.relationship) for e in self.previous_graph.edges}
        curr_edges = {(e.from_node, e.to_node, e.relationship) for e in current_graph.edges}
        
        added_edges = curr_edges - prev_edges
        removed_edges = prev_edges - curr_edges
        
        changes["added_edges"] = [{"from": e[0], "to": e[1], "type": e[2]} for e in added_edges]
        changes["removed_edges"] = [{"from": e[0], "to": e[1], "type": e[2]} for e in removed_edges]
        
        # Check if any significant changes
        has_changes = any(changes[key] for key in ["added_nodes", "removed_nodes", "added_edges", "removed_edges"])
        
        if not has_changes:
            return {}
        
        return changes
    
    def _log_changes(self, changes: Dict[str, Any]):
        """Log dependency graph changes"""
        if not changes:
            return
        
        change_summary = []
        if changes.get("added_nodes"):
            change_summary.append(f"+{len(changes['added_nodes'])} nodes")
        if changes.get("removed_nodes"):
            change_summary.append(f"-{len(changes['removed_nodes'])} nodes")
        if changes.get("added_edges"):
            change_summary.append(f"+{len(changes['added_edges'])} edges")
        if changes.get("removed_edges"):
            change_summary.append(f"-{len(changes['removed_edges'])} edges")
        
        summary = ", ".join(change_summary) if change_summary else "No significant changes"
        
        try:
            log_event(
                stage="dependency_mapping",
                level="INFO" if not changes.get("removed_nodes") else "WARNING",
                message=f"Dependency graph updated: {summary}",
                capsule="system",
                data=changes
            )
        except Exception as e:
            logger.warning(f"Failed to log dependency changes: {e}")
    
    def _save_graph_json(self, graph: DependencyGraph):
        """Save dependency graph as JSON"""
        graph_file = self.output_dir / "dependency-graph.json"
        
        # Convert to serializable format
        graph_data = {
            "nodes": {k: asdict(v) for k, v in graph.nodes.items()},
            "edges": [asdict(e) for e in graph.edges],
            "generated_at": graph.generated_at,
            "graph_hash": graph.graph_hash,
            "statistics": {
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "node_types": self._count_node_types(graph),
                "edge_types": self._count_edge_types(graph)
            }
        }
        
        with open(graph_file, 'w') as f:
            json.dump(graph_data, f, indent=2, default=str)
        
        logger.info(f"Dependency graph saved to {graph_file}")
    
    def _generate_mermaid_diagram(self, graph: DependencyGraph):
        """Generate Mermaid diagram of dependency graph"""
        mermaid_file = self.docs_dir / "dependency-graph.md"
        
        # Group nodes by type for better visualization
        nodes_by_type = defaultdict(list)
        for node in graph.nodes.values():
            nodes_by_type[node.type].append(node)
        
        mermaid_content = "# Huxley Dependency Graph\n\n"
        mermaid_content += f"Generated: {graph.generated_at}\n\n"
        mermaid_content += "```mermaid\ngraph TD\n"
        
        # Add nodes with styling
        for node_type, nodes in nodes_by_type.items():
            for node in nodes:
                node_label = node.name.replace("-", "_").replace(":", "_")
                display_name = node.name
                
                if node_type == "capsule":
                    mermaid_content += f"    {node_label}[{display_name}]:::capsule\n"
                elif node_type == "mcp":
                    mermaid_content += f"    {node_label}{{{display_name}}}:::mcp\n"
                elif node_type == "api":
                    mermaid_content += f"    {node_label}({display_name}):::api\n"
                elif node_type == "tool":
                    mermaid_content += f"    {node_label}[{display_name}]:::tool\n"
                else:
                    mermaid_content += f"    {node_label}[{display_name}]\n"
        
        # Add edges
        for edge in graph.edges:
            from_label = edge.from_node.split(":")[-1].replace("-", "_")
            to_label = edge.to_node.split(":")[-1].replace("-", "_")
            
            if edge.relationship == "requires":
                arrow = "-->"
            elif edge.relationship == "uses":
                arrow = "-.->"
            elif edge.relationship == "imports":
                arrow = "==>"
            else:
                arrow = "-->"
            
            optional_marker = " |optional|" if edge.optional else ""
            mermaid_content += f"    {from_label} {arrow}{optional_marker} {to_label}\n"
        
        # Add styling
        mermaid_content += "\n"
        mermaid_content += "    classDef capsule fill:#e1f5fe,stroke:#01579b\n"
        mermaid_content += "    classDef mcp fill:#f3e5f5,stroke:#4a148c\n"
        mermaid_content += "    classDef api fill:#fff3e0,stroke:#e65100\n"
        mermaid_content += "    classDef tool fill:#e8f5e8,stroke:#2e7d32\n"
        mermaid_content += "```\n\n"
        
        # Add statistics
        mermaid_content += "## Statistics\n\n"
        mermaid_content += f"- **Total Nodes**: {len(graph.nodes)}\n"
        mermaid_content += f"- **Total Edges**: {len(graph.edges)}\n"
        mermaid_content += f"- **Graph Hash**: `{graph.graph_hash}`\n\n"
        
        # Node breakdown
        node_counts = self._count_node_types(graph)
        mermaid_content += "### Node Types\n\n"
        for node_type, count in sorted(node_counts.items()):
            mermaid_content += f"- **{node_type.title()}**: {count}\n"
        
        with open(mermaid_file, 'w') as f:
            f.write(mermaid_content)
        
        logger.info(f"Mermaid diagram saved to {mermaid_file}")
    
    def _generate_reports(self, graph: DependencyGraph):
        """Generate dependency reports"""
        # Per-capsule dependency report
        self._generate_capsule_reports(graph)
        
        # Risk analysis report
        self._generate_risk_report(graph)
    
    def _generate_capsule_reports(self, graph: DependencyGraph):
        """Generate per-capsule dependency reports"""
        reports_dir = self.docs_dir / "dependency-reports"
        reports_dir.mkdir(exist_ok=True)
        
        capsule_nodes = [node for node in graph.nodes.values() if node.type == "capsule"]
        
        for capsule_node in capsule_nodes:
            capsule_name = capsule_node.name
            
            # Find all dependencies of this capsule
            dependencies = []
            for edge in graph.edges:
                if edge.from_node == capsule_node.id:
                    dep_node = graph.nodes.get(edge.to_node)
                    if dep_node:
                        dependencies.append({
                            "name": dep_node.name,
                            "type": dep_node.type,
                            "relationship": edge.relationship,
                            "optional": edge.optional
                        })
            
            # Generate report
            report_content = f"# Dependency Report: {capsule_name}\n\n"
            report_content += f"Generated: {graph.generated_at}\n\n"
            report_content += f"## Dependencies ({len(dependencies)})\n\n"
            
            if dependencies:
                for dep in sorted(dependencies, key=lambda x: (x["type"], x["name"])):
                    optional_marker = " (optional)" if dep["optional"] else ""
                    report_content += f"- **{dep['name']}** ({dep['type']}) - {dep['relationship']}{optional_marker}\n"
            else:
                report_content += "No dependencies found.\n"
            
            # Find what depends on this capsule
            dependents = []
            for edge in graph.edges:
                if edge.to_node == capsule_node.id:
                    dep_node = graph.nodes.get(edge.from_node)
                    if dep_node:
                        dependents.append({
                            "name": dep_node.name,
                            "type": dep_node.type,
                            "relationship": edge.relationship
                        })
            
            if dependents:
                report_content += f"\n## Dependents ({len(dependents)})\n\n"
                for dep in sorted(dependents, key=lambda x: (x["type"], x["name"])):
                    report_content += f"- **{dep['name']}** ({dep['type']}) - {dep['relationship']}\n"
            
            report_file = reports_dir / f"{capsule_name}-dependencies.md"
            with open(report_file, 'w') as f:
                f.write(report_content)
    
    def _generate_risk_report(self, graph: DependencyGraph):
        """Generate dependency risk analysis report"""
        risk_file = self.docs_dir / "dependency-risks.md"
        
        content = "# Dependency Risk Analysis\n\n"
        content += f"Generated: {graph.generated_at}\n\n"
        
        # Find high-risk dependencies (many dependents)
        dependency_counts = defaultdict(int)
        for edge in graph.edges:
            dependency_counts[edge.to_node] += 1
        
        high_risk = [(node_id, count) for node_id, count in dependency_counts.items() if count >= 3]
        high_risk.sort(key=lambda x: x[1], reverse=True)
        
        if high_risk:
            content += "## High-Risk Dependencies\n\n"
            content += "Dependencies with 3+ dependents (single points of failure):\n\n"
            
            for node_id, count in high_risk:
                node = graph.nodes.get(node_id)
                if node:
                    content += f"- **{node.name}** ({node.type}): {count} dependents\n"
        
        # Find orphaned nodes (no dependencies)
        orphaned = []
        for node in graph.nodes.values():
            has_incoming = any(edge.to_node == node.id for edge in graph.edges)
            has_outgoing = any(edge.from_node == node.id for edge in graph.edges)
            
            if not has_incoming and not has_outgoing:
                orphaned.append(node)
        
        if orphaned:
            content += f"\n## Orphaned Components ({len(orphaned)})\n\n"
            content += "Components with no dependencies (may be unused):\n\n"
            
            for node in sorted(orphaned, key=lambda x: (x.type, x.name)):
                content += f"- **{node.name}** ({node.type})\n"
        
        with open(risk_file, 'w') as f:
            f.write(content)
        
        logger.info(f"Risk analysis saved to {risk_file}")
    
    def _count_node_types(self, graph: DependencyGraph) -> Dict[str, int]:
        """Count nodes by type"""
        counts = defaultdict(int)
        for node in graph.nodes.values():
            counts[node.type] += 1
        return dict(counts)
    
    def _count_edge_types(self, graph: DependencyGraph) -> Dict[str, int]:
        """Count edges by relationship type"""
        counts = defaultdict(int)
        for edge in graph.edges:
            counts[edge.relationship] += 1
        return dict(counts)

def main():
    """CLI interface for dependency mapper"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Capsule Dependency Mapper")
    parser.add_argument("--output-dir", "-o", help="Output directory for results")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    parser.add_argument("--json-only", action="store_true", help="Only generate JSON output")
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        mapper = DependencyMapper()
        if args.output_dir:
            mapper.output_dir = pathlib.Path(args.output_dir)
            mapper.docs_dir = pathlib.Path(args.output_dir)
        
        graph = mapper.build_complete_graph()
        
        if not args.quiet:
            print(f"✅ Dependency graph generated:")
            print(f"   Nodes: {len(graph.nodes)}")
            print(f"   Edges: {len(graph.edges)}")
            print(f"   Hash: {graph.graph_hash}")
            
            if not args.json_only:
                print(f"   Mermaid: {mapper.docs_dir / 'dependency-graph.md'}")
                print(f"   Reports: {mapper.docs_dir / 'dependency-reports'}")
        
    except Exception as e:
        logger.error(f"Dependency mapping failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()