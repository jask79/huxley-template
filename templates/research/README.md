# Research Templates

Deep Research Agent templates for structured investigation and analysis.

## Template Selection Guide

### 🔍 **Quick Lookup** (`quick-lookup.md`)
**Use when:** Need immediate answers, simple fact-checking, urgent decisions
**Timeline:** 15min - 1hour
**Lane:** standard
**Output:** Concise answer with minimal documentation

### 🔧 **Technical Analysis** (`technical-analysis.md`) 
**Use when:** Evaluating frameworks, tools, architectural decisions
**Timeline:** 2-8 hours
**Lane:** standard (usually)
**Output:** Comprehensive technical evaluation with recommendations

### 🏢 **Competitive Intelligence** (`competitive-intelligence.md`)
**Use when:** Market research, competitor analysis, strategic positioning
**Timeline:** 4-16 hours  
**Lane:** standard
**Output:** Strategic intelligence report with actionable insights

## Usage Instructions

1. **Copy Template:**
   ```bash
   cp templates/research/{template-name}.md BRIEFS/research-{date}-{topic}.md
   ```

2. **Fill Headers:**
   - Update research ID with actual date/topic
   - Set lane (standard/standard) 
   - Define priority and timeline

3. **Invoke Deep Research Agent:**
   ```
   "Have the Deep Research Agent investigate [topic] using the [template-type] template I've prepared in BRIEFS/"
   ```

## Integration with Huxley

### Lane System Alignment
- **standard:** Quick lookup template, minimal validation
- **standard:** Technical analysis or competitive intelligence, full DoD

### Decision Journal Integration
- Research findings automatically link to decision_journal.md entries
- Research artifacts tracked in capsule lifecycle
- Follow-up research scheduled based on decision outcomes

### Quality Standards
- **standard:** 2+ sources, 6-month recency, minimal conflicts
- **standard:** 5+ sources, academic rigor, comprehensive bias analysis

## Template Customization

Templates can be customized for specific domains:
- **Security Research:** Add threat modeling, compliance requirements
- **Performance Research:** Add benchmarking, load testing protocols  
- **Architecture Research:** Add scalability analysis, pattern evaluation

## Automated Features

Research templates support:
- Auto-population of timestamps and research IDs
- Integration with Huxley memory system
- Automatic source bibliography generation
- Research quality scoring and validation

---
*Research Templates v1.0 - Part of Huxley Deep Research capability*