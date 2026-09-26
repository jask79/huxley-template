#!/usr/bin/env python3
"""
Language-Specific Debugging Patterns for Huxley
Contains debugging patterns, error recognition, and solutions for different languages
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class DebuggingPattern:
    """Represents a debugging pattern for a specific language/framework"""
    name: str
    language: str
    framework: Optional[str]
    error_patterns: List[str]
    common_causes: List[str]
    debug_steps: List[str]
    mcp_queries: List[str]
    severity: ErrorSeverity
    builder_specific: bool = False

class LanguageDebuggingPatterns:
    """Language-specific debugging patterns and error recognition"""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
    
    def _initialize_patterns(self) -> Dict[str, List[DebuggingPattern]]:
        """Initialize all debugging patterns by language"""
        return {
            'swift': self._swift_patterns(),
            'javascript': self._javascript_patterns(),
            'typescript': self._typescript_patterns(),
            'python': self._python_patterns(),
            'web': self._web_patterns(),
            'automation': self._automation_patterns(),
            'builder': self._builder_patterns()
        }
    
    def _swift_patterns(self) -> List[DebuggingPattern]:
        """Swift/iOS debugging patterns"""
        return [
            DebuggingPattern(
                name="SwiftUI State Management",
                language="swift",
                framework="swiftui",
                error_patterns=[
                    r"Cannot find '\w+' in scope",
                    r"@State.*not found",
                    r"Publishing changes from.*main thread",
                    r"Modifying state during view update"
                ],
                common_causes=[
                    "Missing @State or @StateObject wrapper",
                    "Accessing state from wrong thread",
                    "State modification during view rendering",
                    "Incorrect binding syntax"
                ],
                debug_steps=[
                    "Check @State/@StateObject declarations",
                    "Verify state access on main thread",
                    "Review state modification timing",
                    "Test with SwiftUI preview"
                ],
                mcp_queries=[
                    "apple-doc-mcp: get_documentation 'SwiftUI/State'",
                    "apple-doc-mcp: search_symbols 'SwiftUI*State*'",
                    "apple-doc-mcp: get_documentation 'SwiftUI/Binding'"
                ],
                severity=ErrorSeverity.MEDIUM
            ),
            DebuggingPattern(
                name="Xcode Build Errors",
                language="swift",
                framework=None,
                error_patterns=[
                    r"No such module '\w+'",
                    r"Linker command failed",
                    r"Command CodeSign failed",
                    r"Provisioning profile.*doesn't match"
                ],
                common_causes=[
                    "Missing framework import",
                    "Linker configuration issues",
                    "Code signing problems",
                    "Provisioning profile mismatch"
                ],
                debug_steps=[
                    "Check framework imports and targets",
                    "Verify linker flags and libraries",
                    "Review code signing settings",
                    "Check provisioning profiles"
                ],
                mcp_queries=[
                    "apple-doc-mcp: search_symbols 'Build*Error*'",
                    "xcodebuild-mcp: analyze_build_logs",
                    "apple-doc-mcp: get_documentation 'Xcode/Build'"
                ],
                severity=ErrorSeverity.HIGH
            ),
            DebuggingPattern(
                name="Memory Management",
                language="swift",
                framework=None,
                error_patterns=[
                    r"retain cycle",
                    r"memory leak",
                    r"EXC_BAD_ACCESS",
                    r"deallocated.*while key value observers"
                ],
                common_causes=[
                    "Strong reference cycles",
                    "Observers not removed",
                    "Delegate retention issues",
                    "Closure capture problems"
                ],
                debug_steps=[
                    "Use weak/unowned references",
                    "Remove observers in deinit",
                    "Check delegate patterns",
                    "Review closure capture lists"
                ],
                mcp_queries=[
                    "apple-doc-mcp: search_symbols 'weak*reference*'",
                    "apple-doc-mcp: get_documentation 'Swift/AutomaticReferenceCounting'"
                ],
                severity=ErrorSeverity.CRITICAL
            )
        ]
    
    def _javascript_patterns(self) -> List[DebuggingPattern]:
        """JavaScript debugging patterns"""
        return [
            DebuggingPattern(
                name="React Hook Dependencies",
                language="javascript",
                framework="react",
                error_patterns=[
                    r"useEffect has a missing dependency",
                    r"Hook.*called conditionally",
                    r"Cannot read property.*of undefined",
                    r"Cannot update.*unmounted component"
                ],
                common_causes=[
                    "Missing dependencies in useEffect",
                    "Conditional hook usage",
                    "Async state updates after unmount",
                    "Stale closure problems"
                ],
                debug_steps=[
                    "Add missing dependencies to useEffect",
                    "Move hooks to component top level",
                    "Add cleanup functions",
                    "Use useCallback/useMemo appropriately"
                ],
                mcp_queries=[
                    "shadcn-ui: react-hooks troubleshooting",
                    "shadcn-ui: useEffect best practices"
                ],
                severity=ErrorSeverity.MEDIUM
            ),
            DebuggingPattern(
                name="Bundle Size Issues",
                language="javascript",
                framework=None,
                error_patterns=[
                    r"Exceeded maximum.*size",
                    r"webpack.*bundle.*large",
                    r"Module parse failed",
                    r"Can't resolve.*module"
                ],
                common_causes=[
                    "Large dependencies included",
                    "Missing code splitting",
                    "Incorrect import statements",
                    "Webpack configuration issues"
                ],
                debug_steps=[
                    "Analyze bundle with webpack-bundle-analyzer",
                    "Implement code splitting",
                    "Check import statements",
                    "Review webpack configuration"
                ],
                mcp_queries=[
                    "shadcn-ui: webpack optimization",
                    "shadcn-ui: code-splitting patterns"
                ],
                severity=ErrorSeverity.HIGH
            )
        ]
    
    def _typescript_patterns(self) -> List[DebuggingPattern]:
        """TypeScript debugging patterns"""
        return [
            DebuggingPattern(
                name="Type Inference Issues",
                language="typescript",
                framework=None,
                error_patterns=[
                    r"Type.*is not assignable to type",
                    r"Property.*does not exist on type",
                    r"Cannot find name",
                    r"TS2\d{3}:"
                ],
                common_causes=[
                    "Incorrect type annotations",
                    "Missing type definitions",
                    "Generic type issues",
                    "Strict mode violations"
                ],
                debug_steps=[
                    "Check type definitions",
                    "Add explicit type annotations",
                    "Review generic constraints",
                    "Install @types packages"
                ],
                mcp_queries=[
                    "shadcn-ui: typescript error resolution",
                    "shadcn-ui: type definition patterns"
                ],
                severity=ErrorSeverity.MEDIUM
            )
        ]
    
    def _python_patterns(self) -> List[DebuggingPattern]:
        """Python debugging patterns"""
        return [
            DebuggingPattern(
                name="Import and Module Issues",
                language="python",
                framework=None,
                error_patterns=[
                    r"ModuleNotFoundError",
                    r"ImportError",
                    r"No module named",
                    r"cannot import name"
                ],
                common_causes=[
                    "Missing package installation",
                    "Virtual environment not activated",
                    "PYTHONPATH issues",
                    "Circular imports"
                ],
                debug_steps=[
                    "Check pip list for installed packages",
                    "Verify virtual environment",
                    "Check PYTHONPATH and sys.path",
                    "Identify circular import chains"
                ],
                mcp_queries=[
                    "python-doc-mcp: import troubleshooting",
                    "python-doc-mcp: virtual environment guide"
                ],
                severity=ErrorSeverity.MEDIUM
            ),
            DebuggingPattern(
                name="Async/Await Issues",
                language="python",
                framework=None,
                error_patterns=[
                    r"RuntimeWarning.*coroutine.*never awaited",
                    r"SyntaxError.*await.*outside async function",
                    r"TypeError.*object.*not awaitable"
                ],
                common_causes=[
                    "Missing await keyword",
                    "Using await outside async function",
                    "Mixing sync and async code incorrectly"
                ],
                debug_steps=[
                    "Add await to coroutine calls",
                    "Make calling function async",
                    "Use asyncio.run() for top-level calls",
                    "Check async library usage"
                ],
                mcp_queries=[
                    "python-doc-mcp: asyncio documentation",
                    "python-doc-mcp: async best practices"
                ],
                severity=ErrorSeverity.HIGH
            )
        ]
    
    def _web_patterns(self) -> List[DebuggingPattern]:
        """Web development debugging patterns"""
        return [
            DebuggingPattern(
                name="CSS Layout Issues",
                language="web",
                framework="css",
                error_patterns=[
                    r"layout.*shift",
                    r"overflow.*scroll",
                    r"element.*not.*visible",
                    r"responsive.*breaking"
                ],
                common_causes=[
                    "Missing flexbox/grid properties",
                    "Incorrect viewport units",
                    "Z-index stacking issues",
                    "Media query problems"
                ],
                debug_steps=[
                    "Inspect element with dev tools",
                    "Check computed styles",
                    "Verify media query ranges",
                    "Test responsive design mode"
                ],
                mcp_queries=[
                    "shadcn-ui: css layout debugging",
                    "shadcn-ui: responsive design patterns"
                ],
                severity=ErrorSeverity.MEDIUM
            )
        ]
    
    def _automation_patterns(self) -> List[DebuggingPattern]:
        """Automation debugging patterns"""
        return [
            DebuggingPattern(
                name="n8n Workflow Issues",
                language="automation",
                framework="n8n",
                error_patterns=[
                    r"Workflow.*failed.*execution",
                    r"Node.*returned.*error",
                    r"HTTP.*request.*failed",
                    r"Authentication.*failed"
                ],
                common_causes=[
                    "Incorrect node configuration",
                    "API authentication issues",
                    "Data transformation errors",
                    "Workflow timing problems"
                ],
                debug_steps=[
                    "Check node execution logs",
                    "Verify API credentials",
                    "Test data transformations",
                    "Review workflow timing"
                ],
                mcp_queries=[
                    "n8n-mcp: workflow debugging",
                    "n8n-mcp: node troubleshooting"
                ],
                severity=ErrorSeverity.HIGH,
                builder_specific=True
            )
        ]
    
    def _builder_patterns(self) -> List[DebuggingPattern]:
        """Huxley-specific debugging patterns"""
        return [
            DebuggingPattern(
                name="Capsule Lane Issues",
                language="builder",
                framework="capsule",
                error_patterns=[
                    r"DoD.*validation.*failed",
                    r"Lane.*detection.*error",
                    r"Capsule.*configuration.*invalid"
                ],
                common_causes=[
                    "Invalid capsule.json structure",
                    "Missing requirements.yaml",
                    "DoD criteria not met",
                    "Lane misconfiguration"
                ],
                debug_steps=[
                    "Validate capsule.json schema",
                    "Check requirements.yaml format",
                    "Review DoD checklist",
                    "Verify lane assignment"
                ],
                mcp_queries=[
                    "builder-memory: capsule troubleshooting",
                    "git-mcp: review capsule history"
                ],
                severity=ErrorSeverity.HIGH,
                builder_specific=True
            )
        ]
    
    def get_patterns_for_language(self, language: str) -> List[DebuggingPattern]:
        """Get debugging patterns for a specific language"""
        return self.patterns.get(language, [])
    
    def analyze_error(self, error_text: str, language_context) -> List[Tuple[DebuggingPattern, float]]:
        """Analyze error text and return matching patterns with confidence scores"""
        matches = []
        
        # Get relevant patterns
        relevant_patterns = []
        relevant_patterns.extend(self.patterns.get(language_context.primary_language, []))
        
        for tech in language_context.technologies:
            relevant_patterns.extend(self.patterns.get(tech, []))
        
        for framework in language_context.frameworks:
            for patterns in self.patterns.values():
                relevant_patterns.extend([p for p in patterns if p.framework == framework])
        
        # Huxley-specific patterns are always relevant
        relevant_patterns.extend(self.patterns.get('builder', []))
        
        # Match patterns against error text
        for pattern in relevant_patterns:
            confidence = 0.0
            matches_count = 0
            
            for error_pattern in pattern.error_patterns:
                if re.search(error_pattern, error_text, re.IGNORECASE):
                    matches_count += 1
                    confidence += 1.0 / len(pattern.error_patterns)
            
            if confidence > 0:
                # Boost confidence for exact language/framework matches
                if pattern.language == language_context.primary_language:
                    confidence += 0.2
                
                if pattern.framework in language_context.frameworks:
                    confidence += 0.3
                
                matches.append((pattern, min(1.0, confidence)))
        
        # Sort by confidence score
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def get_mcp_queries_for_error(self, error_text: str, language_context) -> List[str]:
        """Get relevant MCP queries for debugging an error"""
        pattern_matches = self.analyze_error(error_text, language_context)
        
        queries = []
        for pattern, confidence in pattern_matches[:3]:  # Top 3 matches
            queries.extend(pattern.mcp_queries)
        
        # Add general language queries
        if language_context.primary_language == 'swift':
            queries.append(f"apple-doc-mcp: search_symbols '*{error_text[:20]}*'")
        elif language_context.primary_language in ['javascript', 'typescript']:
            queries.append(f"shadcn-ui: debug '{error_text[:50]}'")
        
        return list(set(queries))  # Remove duplicates

def main():
    """CLI interface for debugging pattern analysis"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python debugger_language_patterns.py <language> <error_text>")
        sys.exit(1)
    
    language = sys.argv[1]
    error_text = " ".join(sys.argv[2:])
    
    patterns = LanguageDebuggingPatterns()
    
    # Create mock language context
    from types import SimpleNamespace
    context = SimpleNamespace(
        primary_language=language,
        technologies=[language],
        frameworks=[]
    )
    
    matches = patterns.analyze_error(error_text, context)
    
    print(f"=== Debugging Analysis for: {error_text[:50]}... ===")
    print(f"Language: {language}\n")
    
    for i, (pattern, confidence) in enumerate(matches[:5]):
        print(f"{i+1}. {pattern.name} (confidence: {confidence:.2f})")
        print(f"   Severity: {pattern.severity.value}")
        print(f"   Framework: {pattern.framework or 'N/A'}")
        print(f"   Common causes: {', '.join(pattern.common_causes[:2])}")
        print(f"   Debug steps: {pattern.debug_steps[0]}")
        print(f"   MCP queries: {pattern.mcp_queries[0] if pattern.mcp_queries else 'None'}")
        print()

if __name__ == '__main__':
    main()