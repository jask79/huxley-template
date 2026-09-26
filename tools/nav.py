#!/usr/bin/env python3
"""
Huxley Capsule Navigation Engine

Provides interactive and direct navigation to capsules with lane detection,
fuzzy matching, and shell integration support.
"""

import os
import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import difflib

# Cache directory for session state integration
CACHE_DIR = Path.home() / ".cache" / "catalyst"
CONTEXT_INJECTED_FLAG = CACHE_DIR / "context_injected"


@dataclass
class Capsule:
    """Represents a Huxley capsule"""
    name: str
    path: str
    lane: str
    description: str = ""
    status: str = "unknown"
    
    @property
    def lane_indicator(self) -> str:
        """Visual indicator for lane type"""
        return "🔧"  # Using unified quality standards


class CapsuleNavigator:
    """Main navigation engine for Huxley capsules"""
    
    def __init__(self, capsules_root: str = "{{CATALYST_ROOT}}/capsules"):
        self.capsules_root = Path(capsules_root)
        self.capsules: List[Capsule] = []
        
        # Keyword-to-capsule mapping for natural language navigation.
        # Placeholder entries: replace with your own capsules and the words you
        # naturally use for them (scripts/generate-nav-skills.py regenerates nav skills).
        self.keyword_mappings = {
            # Huxley core
            'system': ['huxley-core'],
            'core': ['huxley-core'],
            'framework': ['huxley-core'],
            'tools': ['huxley-core'],
            'governance': ['huxley-core'],

            # Example: a mobile app capsule
            'mobile': ['example-mobile-capsule'],
            'ios': ['example-mobile-capsule'],
            'app': ['example-mobile-capsule'],

            # Example: a web / e-commerce capsule
            'store': ['example-web-capsule'],
            'shop': ['example-web-capsule'],
            'website': ['example-web-capsule'],

            # Example: an automation capsule
            'automation': ['example-automation-capsule'],
            'workflow': ['example-automation-capsule'],
            'script': ['example-automation-capsule'],
        }
        
        self._discover_capsules()
    
    def _discover_capsules(self) -> None:
        """Discover and validate all capsules in the system"""
        if not self.capsules_root.exists():
            return
        
        for item in self.capsules_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                capsule = self._validate_capsule(item)
                if capsule:
                    self.capsules.append(capsule)
        
        # Sort by name for consistent ordering
        self.capsules.sort(key=lambda c: c.name)
    
    def _validate_capsule(self, capsule_path: Path) -> Optional[Capsule]:
        """Validate capsule structure and extract metadata"""
        capsule_json = capsule_path / "capsule.json"
        
        if not capsule_json.exists():
            return None
        
        try:
            with open(capsule_json) as f:
                metadata = json.load(f)
            
            # Determine lane from capsule.json or fallback detection
            lane = self._detect_lane(capsule_path, metadata)
            
            return Capsule(
                name=capsule_path.name,
                path=str(capsule_path),
                lane=lane,
                description=metadata.get("description", ""),
                status=metadata.get("status", "unknown")
            )
        except (json.JSONDecodeError, KeyError, OSError):
            return None
    
    def _detect_lane(self, capsule_path: Path, metadata: Dict) -> str:
        """Detect capsule quality mode using unified Huxley approach"""
        # Using unified quality standards approach - no lane differentiation
        return "standard"
    
    def find_capsule_by_keywords(self, query: str) -> List[Tuple[str, float]]:
        """Find capsules using keyword matching with confidence scores"""
        query_words = query.lower().split()
        capsule_scores = {}
        
        for word in query_words:
            if word in self.keyword_mappings:
                for capsule_name in self.keyword_mappings[word]:
                    # Check if capsule actually exists
                    if any(c.name == capsule_name for c in self.capsules):
                        capsule_scores[capsule_name] = capsule_scores.get(capsule_name, 0) + 0.9
        
        # Also check for partial keyword matches
        for word in query_words:
            for keyword, capsule_names in self.keyword_mappings.items():
                if word in keyword or keyword in word:
                    for capsule_name in capsule_names:
                        if any(c.name == capsule_name for c in self.capsules):
                            if capsule_name not in capsule_scores:
                                capsule_scores[capsule_name] = capsule_scores.get(capsule_name, 0) + 0.6
        
        return sorted(capsule_scores.items(), key=lambda x: x[1], reverse=True)

    def find_capsule(self, query: str) -> Optional[Capsule]:
        """Enhanced capsule finding with keyword matching"""
        if not query:
            return None
        
        query_lower = query.lower().strip()
        
        # 1. Exact match (highest priority)
        for capsule in self.capsules:
            if capsule.name.lower() == query_lower:
                return capsule
        
        # 2. Prefix match (second priority)
        for capsule in self.capsules:
            if capsule.name.lower().startswith(query_lower):
                return capsule
        
        # 3. Keyword-based matching (new - third priority)
        keyword_matches = self.find_capsule_by_keywords(query)
        if keyword_matches and keyword_matches[0][1] >= 0.6:  # Minimum confidence threshold
            capsule_name = keyword_matches[0][0]
            for capsule in self.capsules:
                if capsule.name == capsule_name:
                    return capsule
        
        # 4. Fuzzy matching (fallback)
        names = [c.name.lower() for c in self.capsules]
        matches = difflib.get_close_matches(query_lower, names, n=1, cutoff=0.6)
        
        if matches:
            for capsule in self.capsules:
                if capsule.name.lower() == matches[0]:
                    return capsule
        
        # 5. Substring matching (last resort)
        for capsule in self.capsules:
            if query_lower in capsule.name.lower():
                return capsule
        
        return None
    
    def get_completions(self, prefix: str = "") -> List[str]:
        """Get capsule names for shell tab completion"""
        if not prefix:
            return [c.name for c in self.capsules]
        
        prefix_lower = prefix.lower()
        return [c.name for c in self.capsules 
                if c.name.lower().startswith(prefix_lower)]
    
    def interactive_select(self) -> Optional[Capsule]:
        """Interactive capsule selection menu"""
        if not self.capsules:
            print("No capsules found in the system.")
            return None
        
        print("\n🏗️  Huxley - Capsule Navigator")
        print("=" * 50)
        
        for i, capsule in enumerate(self.capsules, 1):
            lane_info = f"{capsule.lane_indicator} {capsule.lane}"
            status_info = f"({capsule.status})" if capsule.status != "unknown" else ""
            description = f" - {capsule.description}" if capsule.description else ""
            
            print(f"{i:2d}. {capsule.name:<25} {lane_info:<15} {status_info}{description}")
        
        print("\nOptions:")
        print("  • Enter number to select capsule")
        print("  • Type name for fuzzy search")
        print("  • 'q' to quit")
        
        while True:
            try:
                choice = input("\nSelection: ").strip()
                
                if choice.lower() in ['q', 'quit', 'exit']:
                    return None
                
                # Try numeric selection
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(self.capsules):
                        return self.capsules[index]
                    else:
                        print(f"Invalid selection. Please choose 1-{len(self.capsules)}")
                        continue
                
                # Try name search
                capsule = self.find_capsule(choice)
                if capsule:
                    return capsule
                else:
                    print(f"No capsule found matching '{choice}'. Try again.")
                    continue
                    
            except KeyboardInterrupt:
                print("\nCancelled.")
                return None
            except EOFError:
                return None
    
    def list_capsules(self, format_type: str = "table") -> None:
        """List all capsules in specified format"""
        if not self.capsules:
            print("No capsules found.")
            return
        
        if format_type == "json":
            capsules_data = [
                {
                    "name": c.name,
                    "path": c.path,
                    "description": c.description,
                    "status": c.status
                }
                for c in self.capsules
            ]
            print(json.dumps(capsules_data, indent=2))
        
        elif format_type == "names":
            for capsule in self.capsules:
                print(capsule.name)
        
        else:  # table format
            print(f"{'Name':<25} {'Lane':<12} {'Status':<12} Description")
            print("-" * 80)
            for capsule in self.capsules:
                lane_display = f"{capsule.lane_indicator} {capsule.lane}"
                print(f"{capsule.name:<25} {lane_display:<12} {capsule.status:<12} {capsule.description}")


def _clear_context_injection_flag():
    """
    Clear the context injection flag on navigation.

    This ensures the next session in a new capsule will get fresh context.
    Non-blocking - failures are silently ignored.
    """
    try:
        if CONTEXT_INJECTED_FLAG.exists():
            CONTEXT_INJECTED_FLAG.unlink()
    except Exception:
        pass  # Silent failure


def main():
    """CLI entry point for navigation system"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Huxley Capsule Navigator")
    parser.add_argument("query", nargs="?", help="Capsule name to find")
    parser.add_argument("--list", "-l", action="store_true", help="List all capsules")
    parser.add_argument("--completions", "-c", help="Get completions for prefix")
    parser.add_argument("--format", choices=["table", "json", "names"], default="table",
                       help="Output format for listing")
    parser.add_argument("--interactive", "-i", action="store_true", 
                       help="Interactive selection mode")
    
    args = parser.parse_args()
    
    navigator = CapsuleNavigator()
    
    if args.completions is not None:
        # Shell completion mode
        completions = navigator.get_completions(args.completions)
        for completion in completions:
            print(completion)
        return
    
    if args.list:
        navigator.list_capsules(args.format)
        return
    
    if args.interactive or not args.query:
        # Interactive mode
        selected = navigator.interactive_select()
        if selected:
            _clear_context_injection_flag()
            print(f"NAVIGATE_TO:{selected.path}")
        return

    # Direct navigation mode
    capsule = navigator.find_capsule(args.query)
    if capsule:
        _clear_context_injection_flag()
        print(f"NAVIGATE_TO:{capsule.path}")
    else:
        print(f"ERROR:Capsule '{args.query}' not found", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()