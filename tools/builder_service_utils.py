#!/usr/bin/env python3
"""
Huxley Service Utilities - Circuit breaker integration for Huxley services
Provides safe wrappers for common Huxley service calls
"""

import requests
import subprocess
import json
import pathlib
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Import circuit breaker
try:
    from circuit_breaker import get_builder_circuit_breaker, CircuitBreakerConfig
except ImportError:
    print("Warning: Circuit breaker not available")
    # Fallback - no circuit breaking
    def get_builder_circuit_breaker(name): 
        return None

logger = logging.getLogger(__name__)

class SafeRAGClient:
    """Circuit breaker protected RAG client"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.circuit_breaker = get_builder_circuit_breaker("rag_service")
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request with circuit breaker protection"""
        url = f"{self.base_url}{endpoint}"
        
        def request_func():
            response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        
        if self.circuit_breaker:
            result = self.circuit_breaker.call(request_func)
            if result.success:
                return result.value
            else:
                raise result.exception
        else:
            return request_func()
    
    def query(self, collection: str, query: str, top_k: int = 5, 
              where: Optional[Dict] = None) -> Dict[str, Any]:
        """Query documents with circuit breaker protection"""
        payload = {
            "collection": collection,
            "query": query,
            "top_k": top_k,
            "include_metadata": True
        }
        
        if where:
            payload["where"] = where
        
        try:
            response = self._make_request("POST", "/query", json=payload)
            return response.json()
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            # Return empty results on failure
            return {
                "results": [],
                "query_time_ms": 0,
                "collection": collection,
                "error": str(e)
            }
    
    def upsert(self, collection: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert documents with circuit breaker protection"""
        payload = {
            "collection": collection,
            "documents": documents
        }
        
        try:
            response = self._make_request("POST", "/upsert", json=payload)
            return response.json()
        except Exception as e:
            logger.error(f"RAG upsert failed: {e}")
            return {
                "success": False,
                "upserted_count": 0,
                "error": str(e)
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check RAG service health"""
        try:
            response = self._make_request("GET", "/health")
            return response.json()
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

class SafeMCPClient:
    """Circuit breaker protected MCP client"""
    
    def __init__(self, server_name: str):
        self.server_name = server_name
        self.circuit_breaker = get_builder_circuit_breaker(f"mcp_{server_name}")
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any], 
                  timeout: float = 60) -> Dict[str, Any]:
        """Call MCP tool with circuit breaker protection"""
        def mcp_call():
            # This would be replaced with actual MCP call logic
            # For now, simulate with subprocess call
            cmd = [
                "python3", "-c",
                f"print('MCP call to {self.server_name}.{tool_name} with {arguments}')"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"MCP call failed: {result.stderr}")
            
            return {"result": result.stdout.strip(), "success": True}
        
        if self.circuit_breaker:
            result = self.circuit_breaker.call(mcp_call)
            if result.success:
                return result.value
            else:
                logger.error(f"MCP call failed: {result.exception}")
                return {"success": False, "error": str(result.exception)}
        else:
            try:
                return mcp_call()
            except Exception as e:
                return {"success": False, "error": str(e)}

class SafeBuilderTool:
    """Circuit breaker protected Huxley tool execution"""
    
    def __init__(self, tool_name: str, catalyst_root: pathlib.Path = None):
        self.tool_name = tool_name
        self.catalyst_root = catalyst_root or pathlib.Path("{{CATALYST_ROOT}}")
        self.circuit_breaker = get_builder_circuit_breaker(f"tool_{tool_name}")
        
    def execute(self, args: List[str] = None, timeout: float = 300) -> Dict[str, Any]:
        """Execute Huxley tool with circuit breaker protection"""
        tool_path = self.catalyst_root / "tools" / f"{self.tool_name}.py"
        
        def tool_execution():
            if not tool_path.exists():
                raise FileNotFoundError(f"Tool not found: {tool_path}")
            
            cmd = ["python3", str(tool_path)]
            if args:
                cmd.extend(args)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        
        if self.circuit_breaker:
            result = self.circuit_breaker.call(tool_execution)
            if result.success:
                return result.value
            else:
                logger.error(f"Tool execution failed: {result.exception}")
                return {
                    "success": False,
                    "error": str(result.exception),
                    "stdout": "",
                    "stderr": str(result.exception)
                }
        else:
            try:
                return tool_execution()
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "stdout": "",
                    "stderr": str(e)
                }

# Convenience functions for common operations
def safe_rag_query(query: str, collection: str = "general", top_k: int = 5) -> List[Dict[str, Any]]:
    """Safely query RAG service with circuit breaker"""
    client = SafeRAGClient()
    result = client.query(collection, query, top_k)
    return result.get("results", [])

def safe_autopsy_analysis(capsule_name: str, run_id: str = None) -> Dict[str, Any]:
    """Safely run capsule autopsy with circuit breaker"""
    tool = SafeBuilderTool("capsule_autopsy")
    args = [capsule_name]
    if run_id:
        args.extend(["--run-id", run_id])
    
    return tool.execute(args)

def safe_dependency_mapping() -> Dict[str, Any]:
    """Safely run dependency mapping with circuit breaker"""
    tool = SafeBuilderTool("dependency_mapper")
    return tool.execute(["--quiet"])

def safe_health_check() -> Dict[str, Any]:
    """Comprehensive system health check with circuit breakers"""
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "overall_healthy": True,
        "services": {}
    }
    
    # Check RAG service
    rag_client = SafeRAGClient()
    rag_health = rag_client.health_check()
    health_status["services"]["rag"] = {
        "healthy": rag_health.get("status") == "healthy",
        "details": rag_health
    }
    
    if not health_status["services"]["rag"]["healthy"]:
        health_status["overall_healthy"] = False
    
    # Check critical tools
    critical_tools = ["dependency_mapper", "system_health_rollup"]
    
    for tool_name in critical_tools:
        tool = SafeBuilderTool(tool_name)
        tool_result = tool.execute(["--help"], timeout=10)  # Quick help check
        
        health_status["services"][f"tool_{tool_name}"] = {
            "healthy": tool_result.get("success", False),
            "details": tool_result
        }
        
        if not tool_result.get("success"):
            health_status["overall_healthy"] = False
    
    # Get circuit breaker stats
    from circuit_breaker import get_all_circuit_breaker_stats
    cb_stats = get_all_circuit_breaker_stats()
    
    # Check for circuit breakers in OPEN state
    open_breakers = [name for name, stats in cb_stats.items() if stats.get("state") == "open"]
    
    health_status["circuit_breakers"] = {
        "total": len(cb_stats),
        "open": len(open_breakers),
        "open_breakers": open_breakers,
        "stats": cb_stats
    }
    
    if open_breakers:
        health_status["overall_healthy"] = False
    
    return health_status

def main():
    """CLI interface for safe Huxley service operations"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Safe Huxley Service Operations")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="System health check")
    health_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # RAG query command
    rag_parser = subparsers.add_parser("rag", help="RAG service operations")
    rag_parser.add_argument("action", choices=["query", "health"], help="RAG action")
    rag_parser.add_argument("--collection", default="general", help="Collection name")
    rag_parser.add_argument("--query", help="Query string")
    rag_parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    
    # Tool execution command
    tool_parser = subparsers.add_parser("tool", help="Execute Huxley tool safely")
    tool_parser.add_argument("tool_name", help="Tool name")
    tool_parser.add_argument("args", nargs="*", help="Tool arguments")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "health":
            health = safe_health_check()
            
            if args.json:
                print(json.dumps(health, indent=2))
            else:
                status = "✅ HEALTHY" if health["overall_healthy"] else "❌ UNHEALTHY"
                print(f"🏥 Huxley Health Check: {status}")
                print("=" * 50)
                
                for service, details in health["services"].items():
                    service_status = "✅" if details["healthy"] else "❌"
                    print(f"{service_status} {service}")
                
                cb_info = health["circuit_breakers"]
                if cb_info["open"]:
                    print(f"\n⚠️ Circuit Breakers: {cb_info['open']}/{cb_info['total']} OPEN")
                    for breaker in cb_info["open_breakers"]:
                        print(f"  ❌ {breaker}")
                else:
                    print(f"\n✅ Circuit Breakers: All {cb_info['total']} operational")
        
        elif args.command == "rag":
            client = SafeRAGClient()
            
            if args.action == "health":
                health = client.health_check()
                status = "✅ HEALTHY" if health.get("status") == "healthy" else "❌ UNHEALTHY"
                print(f"RAG Service: {status}")
                
                if health.get("metrics"):
                    metrics = health["metrics"]
                    print(f"  Queries: {metrics.get('total_queries', 0)}")
                    print(f"  Avg Time: {metrics.get('avg_query_time_ms', 0):.1f}ms")
            
            elif args.action == "query":
                if not args.query:
                    print("Error: --query required for query action")
                    return
                
                results = safe_rag_query(args.query, args.collection, args.top_k)
                print(f"Query: {args.query}")
                print(f"Results: {len(results)}")
                
                for i, result in enumerate(results):
                    print(f"{i+1}. Score: {result.get('similarity_score', 0):.3f}")
                    print(f"   {result.get('content', '')[:100]}...")
        
        elif args.command == "tool":
            tool = SafeBuilderTool(args.tool_name)
            result = tool.execute(args.args)
            
            if result["success"]:
                print("✅ Tool executed successfully")
                if result["stdout"]:
                    print(result["stdout"])
            else:
                print("❌ Tool execution failed")
                if result["stderr"]:
                    print(result["stderr"])
                return 1
    
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    main()