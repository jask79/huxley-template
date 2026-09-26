#!/usr/bin/env python3
"""
Research Quality Engine
Calculates quality scores for research sessions and gates publication
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import math
from pathlib import Path

class ResearchQualityEngine:
    def __init__(self, thresholds: Optional[Dict] = None):
        self.thresholds = thresholds or {
            "standard_minimum": 0.7,
            "standard_minimum": 0.85,
            "publication_threshold": 0.9
        }
        
        # Authority rankings for common sources
        self.source_authority = {
            # Academic/Research
            "arxiv.org": 0.9,
            "scholar.google.com": 0.85,
            "semanticscholar.org": 0.85,
            "pubmed.ncbi.nlm.nih.gov": 0.95,
            
            # Official Documentation
            "docs.python.org": 1.0,
            "developer.mozilla.org": 1.0,
            "nodejs.org": 1.0,
            "reactjs.org": 1.0,
            "docs.github.com": 1.0,
            
            # Tech Companies
            "engineering.fb.com": 0.9,
            "ai.googleblog.com": 0.9,
            "openai.com": 0.9,
            "anthropic.com": 0.95,
            
            # Community/Forums
            "stackoverflow.com": 0.7,
            "reddit.com": 0.5,
            "medium.com": 0.6,
            "dev.to": 0.6,
            "hackernews": 0.65,
            
            # News/Blogs
            "techcrunch.com": 0.6,
            "theverge.com": 0.55,
            "wired.com": 0.6,
            
            # Default for unknown
            "_default": 0.5
        }
    
    def calculate_overall_score(self, session_data: Dict) -> Tuple[float, Dict]:
        """Calculate overall quality score for a research session"""
        
        # Load artifacts
        artifacts = self._load_session_artifacts(session_data)
        
        # Calculate individual metrics
        authority_score = self._calculate_authority_score(artifacts["citations"])
        recency_score = self._calculate_recency_score(artifacts["citations"])
        conflict_score = self._calculate_conflict_resolution_score(artifacts["claims"])
        completeness_score = self._calculate_citation_completeness(
            artifacts["claims"], 
            artifacts["citations"]
        )
        
        # Weighted average
        weights = {
            "authority": 0.3,
            "recency": 0.2,
            "conflict": 0.2,
            "completeness": 0.3
        }
        
        overall_score = (
            authority_score * weights["authority"] +
            recency_score * weights["recency"] +
            conflict_score * weights["conflict"] +
            completeness_score * weights["completeness"]
        )
        
        metrics = {
            "source_authority": authority_score,
            "recency": recency_score,
            "conflict_resolution": conflict_score,
            "citation_completeness": completeness_score,
            "overall": overall_score,
            "timestamp": datetime.now().isoformat()
        }
        
        return overall_score, metrics
    
    def _calculate_authority_score(self, citations: List[Dict]) -> float:
        """Calculate weighted average of source authority"""
        if not citations:
            return 0.0
        
        scores = []
        for citation in citations:
            url = citation.get("source_url", "")
            domain = self._extract_domain(url)
            
            # Get authority score for domain
            authority = self.source_authority.get(
                domain, 
                self.source_authority["_default"]
            )
            
            # Boost for peer-reviewed or official docs
            if "peer_reviewed" in citation and citation["peer_reviewed"]:
                authority = min(1.0, authority * 1.1)
            
            if "official_documentation" in citation and citation["official_documentation"]:
                authority = 1.0
            
            scores.append(authority)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _calculate_recency_score(self, citations: List[Dict]) -> float:
        """Calculate time-decay score for source recency"""
        if not citations:
            return 0.0
        
        scores = []
        now = datetime.now()
        
        for citation in citations:
            pub_date_str = citation.get("publication_date")
            if not pub_date_str:
                # No date = assume older, lower score
                scores.append(0.3)
                continue
            
            try:
                pub_date = datetime.fromisoformat(pub_date_str)
                days_old = (now - pub_date).days
                
                # Time decay function: exponential decay over 2 years
                # Score = e^(-days/365)
                decay_rate = 365  # Half-life of 1 year
                score = math.exp(-days_old / decay_rate)
                
                # Floor at 0.1 for very old but potentially still relevant
                score = max(0.1, score)
                
                scores.append(score)
            except:
                scores.append(0.3)  # Parse error = low confidence
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _calculate_conflict_resolution_score(self, claims: List[Dict]) -> float:
        """Calculate how well conflicting information is handled"""
        if not claims:
            return 1.0  # No claims = no conflicts
        
        # Look for claims with multiple sources
        multi_source_claims = [c for c in claims if len(c.get("source_ids", [])) > 1]
        
        if not multi_source_claims:
            # Single sources only = no conflict resolution needed
            return 0.8
        
        # Check confidence scores for multi-source claims
        confidence_scores = [c.get("confidence_score", 0.5) for c in multi_source_claims]
        
        # Higher average confidence = better conflict resolution
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Check for explicit conflict markers
        conflict_handled = 0
        for claim in multi_source_claims:
            if "conflict_noted" in claim or "consensus" in claim.get("text", "").lower():
                conflict_handled += 1
        
        conflict_ratio = conflict_handled / len(multi_source_claims) if multi_source_claims else 0
        
        # Combine confidence and explicit handling
        return (avg_confidence * 0.7) + (conflict_ratio * 0.3)
    
    def _calculate_citation_completeness(self, claims: List[Dict], 
                                        citations: List[Dict]) -> float:
        """Calculate percentage of claims with proper citations"""
        if not claims:
            return 1.0  # No claims = complete
        
        cited_claims = 0
        for claim in claims:
            source_ids = claim.get("source_ids", [])
            evidence = claim.get("evidence_excerpt", "")
            
            # Check if claim has sources and evidence
            if source_ids and evidence:
                # Verify sources exist in citations
                citation_ids = [c.get("citation_id") for c in citations]
                if any(sid in citation_ids for sid in source_ids):
                    cited_claims += 1
        
        return cited_claims / len(claims) if claims else 0.0
    
    def gate_publication(self, overall_score: float, lane: str) -> Tuple[bool, str]:
        """Determine if research meets publication threshold"""
        
        threshold = self.thresholds[f"{lane}_minimum"]
        
        if overall_score >= self.thresholds["publication_threshold"]:
            return True, "Exceeds publication threshold - auto-approved"
        elif overall_score >= threshold:
            return True, f"Meets {lane} threshold - approved"
        else:
            return False, f"Below {lane} threshold ({overall_score:.2f} < {threshold}) - needs review"
    
    def should_escalate(self, overall_score: float, auto_escalation_threshold: float = 0.6) -> bool:
        """Check if human review should be triggered"""
        return overall_score < auto_escalation_threshold
    
    def generate_quality_report(self, metrics: Dict, session_data: Dict) -> str:
        """Generate human-readable quality report"""
        
        report = f"""
# Research Quality Report

**Session:** {session_data.get('session_id', 'Unknown')}
**Topic:** {session_data.get('research_topic', 'Unknown')}
**Overall Score:** {metrics['overall']:.2f}

## Metric Breakdown
- **Source Authority:** {metrics['source_authority']:.2f}
  - Evaluates credibility and expertise of sources
- **Recency:** {metrics['recency']:.2f}  
  - Time-weighted relevance of information
- **Conflict Resolution:** {metrics['conflict_resolution']:.2f}
  - Handling of contradictory information
- **Citation Completeness:** {metrics['citation_completeness']:.2f}
  - Coverage of claims with evidence

## Thresholds
- standard Minimum: {self.thresholds['standard_minimum']}
- standard Minimum: {self.thresholds['standard_minimum']}
- Publication Threshold: {self.thresholds['publication_threshold']}

## Recommendation
"""
        
        
        if approved:
            report += f"✅ **APPROVED** - {reason}"
        else:
            report += f"⚠️ **NEEDS REVIEW** - {reason}"
        
        if self.should_escalate(metrics['overall']):
            report += "\\n\\n🔴 **ESCALATION TRIGGERED** - Human review required"
        
        return report
    
    def _load_session_artifacts(self, session_data: Dict) -> Dict:
        """Load artifacts from session directory"""
        session_id = session_data.get("session_id")
        if not session_id:
            return {"claims": [], "citations": []}
        
        artifacts_path = Path(f"{{CATALYST_ROOT}}/research/sources/{session_id}")
        
        artifacts = {}
        for file_type in ["claims", "citations"]:
            file_path = artifacts_path / f"{file_type}.json"
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    artifacts[file_type] = data.get(file_type, [])
            else:
                artifacts[file_type] = []
        
        return artifacts
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return "_default"
    
    def save_quality_scores(self, session_id: str, metrics: Dict):
        """Save quality scores to session artifacts"""
        scores_file = Path(f"{{CATALYST_ROOT}}/research/sources/{session_id}/quality_scores.json")
        
        with open(scores_file, 'w') as f:
            json.dump({
                "overall_score": metrics["overall"],
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)


if __name__ == "__main__":
    # Test the quality engine
    engine = ResearchQualityEngine()
    
    # Mock session data
    test_session = {
        "session_id": "test-session",
        "research_topic": "Framework Analysis",
    }
    
    # Mock artifacts (would normally load from files)
    test_claims = [
        {
            "claim_id": "c1",
            "text": "Framework improves performance by 90%",
            "source_ids": ["s1", "s2"],
            "evidence_excerpt": "Benchmarks show...",
            "confidence_score": 0.85
        }
    ]
    
    test_citations = [
        {
            "citation_id": "s1",
            "source_url": "https://docs.python.org/3/",
            "publication_date": "2024-01-01",
            "official_documentation": True
        },
        {
            "citation_id": "s2",
            "source_url": "https://arxiv.org/paper/123",
            "publication_date": "2023-12-01",
            "peer_reviewed": True
        }
    ]
    
    # Calculate scores
    score, metrics = engine.calculate_overall_score(test_session)
    
    # Generate report
    report = engine.generate_quality_report(metrics, test_session)
    print(report)