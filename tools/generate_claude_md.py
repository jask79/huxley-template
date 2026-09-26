#!/usr/bin/env python3
"""
Generate CLAUDE.md from YAML specifications
Converts machine-readable YAML into agent-readable markdown context

SAFEGUARDS:
- Will NOT overwrite manual CLAUDE.md files without --force flag
- Always creates .manual_backup before overwriting manual content
- Shows size comparison to warn about potential data loss
- Dry-run mode available to preview changes

Usage:
    python3 tools/generate_claude_md.py <capsule_path>           # Single capsule (safe - skips manual files)
    python3 tools/generate_claude_md.py <capsule_path> --force   # Force overwrite manual file
    python3 tools/generate_claude_md.py --all                    # All capsules (safe - skips manual files)
    python3 tools/generate_claude_md.py --all --force            # Force all (DANGEROUS)
    python3 tools/generate_claude_md.py --all --dry-run          # Preview what would happen
"""

import yaml
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

# ANSI colors for terminal output
RED = '\033[91m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


class ClaudeMdGenerator:
    """Generates CLAUDE.md from capsule YAML specifications"""

    def __init__(self, force: bool = False, dry_run: bool = False):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.force = force
        self.dry_run = dry_run
        self.skipped_manual = []  # Track skipped capsules for summary

    def load_capsule_yaml(self, capsule_path: Path) -> Dict[str, Any]:
        """Load specs/current.yaml from capsule"""
        yaml_path = capsule_path / "specs" / "current.yaml"

        if not yaml_path.exists():
            raise FileNotFoundError(f"No specs/current.yaml found in {capsule_path}")

        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)

    def format_list(self, items: List, indent: int = 0) -> str:
        """Format list as markdown bullets"""
        if not items:
            return "*None configured*"

        prefix = "  " * indent
        lines = []
        for item in items:
            if isinstance(item, dict):
                # Handle dict items
                for key, value in item.items():
                    if isinstance(value, (list, dict)):
                        lines.append(f"{prefix}- **{key}:**")
                        lines.append(self.format_nested(value, indent + 1))
                    else:
                        lines.append(f"{prefix}- **{key}:** {value}")
            else:
                lines.append(f"{prefix}- {item}")

        return "\n".join(lines)

    def format_nested(self, data: Any, indent: int = 0) -> str:
        """Format nested data structures"""
        if isinstance(data, list):
            return self.format_list(data, indent)
        elif isinstance(data, dict):
            prefix = "  " * indent
            lines = []
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    lines.append(f"{prefix}**{key}:**")
                    lines.append(self.format_nested(value, indent + 1))
                else:
                    lines.append(f"{prefix}**{key}:** {value}")
            return "\n".join(lines)
        else:
            return str(data)

    def generate_markdown(self, spec: Dict[str, Any]) -> str:
        """Generate CLAUDE.md content from spec"""

        md = []

        # Header with auto-generation notice
        md.append(f"# {spec.get('name', 'Unknown Capsule')}")
        md.append("")
        md.append("<!--")
        md.append("AUTO-GENERATED FROM YAML SPECIFICATIONS")
        md.append(f"Generated: {datetime.now().isoformat()}")
        md.append("Do not edit directly. Update specs/current.yaml instead.")
        md.append("Regenerate with: python3 tools/generate_claude_md.py <capsule>")
        md.append("-->")
        md.append("")

        # Purpose
        if 'purpose' in spec:
            md.append("## Purpose")
            purpose = spec['purpose']
            if isinstance(purpose, dict):
                if 'what' in purpose:
                    md.append(f"{purpose['what']}")
                if 'why' in purpose:
                    md.append(f"\n**Why:** {purpose['why']}")
                if 'for_whom' in purpose:
                    md.append(f"\n**For:** {purpose['for_whom']}")
            else:
                md.append(f"{purpose}")
            md.append("")
        elif 'description' in spec:
            md.append("## Purpose")
            md.append(spec['description'])
            md.append("")

        # Current Status
        if 'current' in spec or 'status' in spec:
            md.append("## Current Status")
            current = spec.get('current', {})
            md.append(f"- **Phase:** {current.get('phase', spec.get('status', 'unknown'))}")
            md.append(f"- **Version:** {spec.get('version', 'unversioned')}")
            if 'last_updated' in current:
                md.append(f"- **Last Updated:** {current['last_updated']}")
            if 'health' in current:
                md.append(f"- **Health:** {current['health']}")
            md.append("")

        # Technical Overview
        if 'technical' in spec:
            tech = spec['technical']

            md.append("## Technical Overview")

            if 'stack' in tech:
                md.append("**Stack:**")
                md.append(self.format_list(tech['stack']))
                md.append("")

            if 'dependencies' in tech:
                md.append("**Dependencies:**")
                deps = tech['dependencies']
                if 'external' in deps and deps['external']:
                    md.append("\n*External:*")
                    md.append(self.format_list(deps['external']))
                if 'internal' in deps and deps['internal']:
                    md.append("\n*Internal (Huxley):*")
                    md.append(self.format_list(deps['internal']))
                if 'packages' in deps and deps['packages']:
                    md.append("\n*Packages:*")
                    md.append(self.format_nested(deps['packages'], 1))
                md.append("")

            if 'integrations' in tech:
                md.append("**Integration Points:**")
                integ = tech['integrations']
                if 'apis' in integ and integ['apis']:
                    md.append(self.format_list(integ['apis']))
                if 'mcps' in integ and integ['mcps']:
                    md.append("\n*Required MCPs:*")
                    md.append(self.format_list(integ['mcps']))
                md.append("")

        # Key Features / Capabilities
        if 'capabilities' in spec and spec['capabilities']:
            md.append("## Key Features")
            for i, cap in enumerate(spec['capabilities'], 1):
                md.append(f"{i}. {cap}")
            md.append("")

        # Architecture
        if 'technical' in spec and 'architecture' in spec['technical']:
            arch = spec['technical']['architecture']
            md.append("## Architecture Notes")

            if isinstance(arch, dict):
                if 'pattern' in arch:
                    md.append(f"**Pattern:** {arch['pattern']}")
                    md.append("")

                if 'components' in arch and arch['components']:
                    md.append("**Components:**")
                    for comp in arch['components']:
                        if isinstance(comp, dict):
                            name = comp.get('name', 'Unknown')
                            purpose = comp.get('purpose', '')
                            tech = comp.get('tech', '')
                            md.append(f"- **{name}:** {purpose}")
                            if tech:
                                md.append(f"  - *Tech:* {tech}")
                        else:
                            md.append(f"- {comp}")
                    md.append("")

                if 'data_flow' in arch:
                    md.append("**Data Flow:**")
                    md.append(arch['data_flow'])
                    md.append("")
            else:
                md.append(arch)
                md.append("")

        # Development Workflow
        if 'development' in spec:
            dev = spec['development']
            md.append("## Development Workflow")

            if 'workflow' in dev:
                md.append(dev['workflow'])
                md.append("")

            if 'tools' in dev and dev['tools']:
                md.append("**Tools:**")
                md.append(self.format_list(dev['tools']))
                md.append("")

            if 'testing' in dev:
                md.append("**Testing:**")
                md.append(dev['testing'])
                md.append("")

        # Quality & Standards
        if 'quality' in spec:
            quality = spec['quality']
            md.append("## Quality Standards")

            if 'standards' in quality and quality['standards']:
                md.append("**Standards:**")
                for std in quality['standards']:
                    if isinstance(std, dict):
                        rule = std.get('rule', 'Unknown')
                        threshold = std.get('threshold', '')
                        md.append(f"- {rule}")
                        if threshold:
                            md.append(f"  - *Threshold:* {threshold}")
                    else:
                        md.append(f"- {std}")
                md.append("")

            if 'security' in quality and quality['security']:
                md.append("**Security Requirements:**")
                md.append(self.format_list(quality['security']))
                md.append("")

            if 'performance' in quality and quality['performance']:
                md.append("**Performance Targets:**")
                for perf in quality['performance']:
                    if isinstance(perf, dict):
                        metric = perf.get('metric', 'Unknown')
                        target = perf.get('target', '')
                        md.append(f"- {metric}: {target}")
                    else:
                        md.append(f"- {perf}")
                md.append("")

        # Guardrails
        if 'guardrails' in spec and spec['guardrails']:
            md.append("## Guardrails")
            for guard in spec['guardrails']:
                if isinstance(guard, dict):
                    rule = guard.get('rule', 'Unknown')
                    rationale = guard.get('rationale', '')
                    md.append(f"- **{rule}**")
                    if rationale:
                        md.append(f"  - *Why:* {rationale}")
                else:
                    md.append(f"- {guard}")
            md.append("")

        # Vision & Roadmap
        if 'vision' in spec:
            vision = spec['vision']
            md.append("## Vision & Roadmap")

            if isinstance(vision, dict):
                if 'statement' in vision:
                    md.append(f"**Vision:** {vision['statement']}")
                    md.append("")

                if 'roadmap' in vision and vision['roadmap']:
                    md.append("**Roadmap:**")
                    for item in vision['roadmap']:
                        if isinstance(item, dict):
                            phase = item.get('name', item.get('phase', 'Unknown'))
                            target = item.get('target', '')
                            items = item.get('items', [])
                            md.append(f"\n**{phase}**")
                            if target:
                                md.append(f"*Target: {target}*")
                            if items:
                                md.append(self.format_list(items))
                        else:
                            md.append(f"- {item}")
                    md.append("")

                if 'open_bets' in vision and vision['open_bets']:
                    md.append("**Open Bets / Ideas:**")
                    for bet in vision['open_bets']:
                        if isinstance(bet, dict):
                            idea = bet.get('idea', 'Unknown')
                            rationale = bet.get('rationale', '')
                            md.append(f"- {idea}")
                            if rationale:
                                md.append(f"  - *Rationale:* {rationale}")
                        else:
                            md.append(f"- {bet}")
                    md.append("")

        # Relationships
        if 'relationships' in spec:
            rel = spec['relationships']
            if any(rel.get(k) for k in ['feeds_into', 'consumes_from', 'shared_with']):
                md.append("## Relationships")

                if 'feeds_into' in rel and rel['feeds_into']:
                    md.append("**Feeds Into:**")
                    md.append(self.format_list(rel['feeds_into']))

                if 'consumes_from' in rel and rel['consumes_from']:
                    md.append("**Consumes From:**")
                    md.append(self.format_list(rel['consumes_from']))

                if 'shared_with' in rel and rel['shared_with']:
                    md.append("**Shared Resources:**")
                    md.append(self.format_list(rel['shared_with']))

                md.append("")

        # Data & Storage
        if 'data' in spec:
            data = spec['data']
            if any(data.get(k) for k in ['storage', 'retention']):
                md.append("## Data & Storage")

                if 'storage' in data and data['storage']:
                    md.append("**Storage:**")
                    md.append(self.format_list(data['storage']))

                if 'retention' in data and data['retention']:
                    md.append("\n**Retention Policies:**")
                    md.append(self.format_nested(data['retention'], 1))

                md.append("")

        # Maintenance
        if 'maintenance' in spec:
            maint = spec['maintenance']
            md.append("## Maintenance")

            if 'schedule' in maint:
                md.append(f"**Schedule:** {maint['schedule']}")
                md.append("")

            if 'monitoring' in maint and maint['monitoring']:
                md.append("**Monitoring:**")
                md.append(self.format_list(maint['monitoring']))
                md.append("")

            if 'automation' in maint and maint['automation']:
                md.append("**Automated Tasks:**")
                md.append(self.format_list(maint['automation']))
                md.append("")

        # Footer
        md.append("---")
        md.append("*This file is auto-generated from `specs/current.yaml`*")
        md.append("*Last generated:* " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        return "\n".join(md)

    def check_manual_content(self, capsule_path: Path) -> Tuple[bool, int, int]:
        """
        Check if CLAUDE.md contains manual (non-auto-generated) content.
        Returns: (is_manual, existing_size, generated_size)
        """
        claude_md = capsule_path / "CLAUDE.md"

        if not claude_md.exists():
            return False, 0, 0

        with open(claude_md, 'r') as f:
            existing = f.read()

        is_manual = "AUTO-GENERATED" not in existing
        existing_size = len(existing)

        # Generate what we would create to compare sizes
        try:
            spec = self.load_capsule_yaml(capsule_path)
            generated = self.generate_markdown(spec)
            generated_size = len(generated)
        except Exception:
            generated_size = 0

        return is_manual, existing_size, generated_size

    def generate_for_capsule(self, capsule_path: Path) -> bool:
        """Generate CLAUDE.md for a single capsule"""
        try:
            capsule_name = capsule_path.name

            # Check for manual content BEFORE loading YAML
            is_manual, existing_size, generated_size = self.check_manual_content(capsule_path)

            if is_manual:
                size_diff = existing_size - generated_size

                if not self.force:
                    # SKIP - don't overwrite manual content without --force
                    print(f"{YELLOW}⚠️  {capsule_name}{RESET} - SKIPPED (manual CLAUDE.md detected)")
                    print(f"    Existing: {existing_size:,} bytes | Generated would be: {generated_size:,} bytes")
                    if size_diff > 1000:
                        print(f"    {RED}Would lose ~{size_diff:,} bytes of content!{RESET}")
                    print(f"    Use --force to overwrite (backup will be created)")
                    self.skipped_manual.append(capsule_name)
                    return False

                # Force mode - warn but proceed
                print(f"{CYAN}Processing {capsule_name}...{RESET}")
                print(f"    {YELLOW}⚠️  Manual content detected - will backup and overwrite{RESET}")
                if size_diff > 1000:
                    print(f"    {RED}WARNING: Losing ~{size_diff:,} bytes of content!{RESET}")
            else:
                print(f"Processing {capsule_name}...")

            # Load YAML
            spec = self.load_capsule_yaml(capsule_path)

            # Generate markdown
            md_content = self.generate_markdown(spec)

            if self.dry_run:
                print(f"  {CYAN}[DRY RUN]{RESET} Would generate CLAUDE.md ({len(md_content):,} bytes)")
                return True

            # Write CLAUDE.md
            claude_md = capsule_path / "CLAUDE.md"

            # Backup existing if manual (even in force mode)
            if is_manual:
                backup = capsule_path / "CLAUDE.md.manual_backup"
                with open(claude_md, 'r') as f:
                    existing = f.read()
                with open(backup, 'w') as bf:
                    bf.write(existing)
                print(f"  📦 Backed up manual CLAUDE.md to {backup.name}")

            with open(claude_md, 'w') as f:
                f.write(md_content)

            print(f"  {GREEN}✅ Generated CLAUDE.md{RESET}")
            return True

        except FileNotFoundError as e:
            print(f"  {YELLOW}⏭️  Skipped (no specs/current.yaml){RESET}")
            return False
        except Exception as e:
            print(f"  {RED}❌ Error: {e}{RESET}")
            return False

    def generate_all(self):
        """Generate CLAUDE.md for all capsules"""
        capsules_dir = self.catalyst_root / "capsules"

        if not capsules_dir.exists():
            print(f"{RED}❌ No capsules directory found{RESET}")
            return 1

        capsules = [d for d in capsules_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

        # Warning banner for --all
        print("")
        print(f"{BOLD}{'='*60}{RESET}")
        if self.force:
            print(f"{RED}{BOLD}⚠️  FORCE MODE - Will overwrite ALL manual CLAUDE.md files!{RESET}")
            print(f"{YELLOW}   Backups will be created as .manual_backup{RESET}")
        else:
            print(f"{GREEN}✅ SAFE MODE - Will skip capsules with manual CLAUDE.md{RESET}")
            print(f"   Use --force to overwrite manual files (creates backups)")
        if self.dry_run:
            print(f"{CYAN}📋 DRY RUN - No files will be modified{RESET}")
        print(f"{BOLD}{'='*60}{RESET}")
        print("")

        print(f"📚 Processing {len(capsules)} capsules...\n")

        success_count = 0
        for capsule in sorted(capsules):
            if self.generate_for_capsule(capsule):
                success_count += 1

        # Summary
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}📊 Summary{RESET}")
        print(f"   Generated: {success_count}")
        print(f"   Skipped (manual): {len(self.skipped_manual)}")
        print(f"   Total: {len(capsules)}")

        if self.skipped_manual and not self.force:
            print(f"\n{YELLOW}Skipped capsules with manual CLAUDE.md:{RESET}")
            for name in self.skipped_manual:
                print(f"   - {name}")
            print(f"\n{CYAN}To regenerate these, use: --force{RESET}")

        print(f"{BOLD}{'='*60}{RESET}")

        return 0


def main():
    # Parse arguments
    args = sys.argv[1:]

    force = '--force' in args
    dry_run = '--dry-run' in args

    # Remove flags from args
    args = [a for a in args if a not in ('--force', '--dry-run')]

    if not args:
        print(f"""
{BOLD}Generate CLAUDE.md from YAML Specifications{RESET}

{BOLD}Usage:{RESET}
    python3 tools/generate_claude_md.py <capsule_path>           # Single capsule
    python3 tools/generate_claude_md.py <capsule_path> --force   # Force overwrite manual
    python3 tools/generate_claude_md.py --all                    # All capsules (safe)
    python3 tools/generate_claude_md.py --all --force            # Force all
    python3 tools/generate_claude_md.py --all --dry-run          # Preview changes

{BOLD}Options:{RESET}
    --force     Overwrite manual CLAUDE.md files (creates .manual_backup)
    --dry-run   Show what would happen without making changes

{BOLD}Safety:{RESET}
    By default, capsules with manual (non-auto-generated) CLAUDE.md files
    are SKIPPED to prevent data loss. Use --force to override.
""")
        return 1

    generator = ClaudeMdGenerator(force=force, dry_run=dry_run)

    if args[0] == '--all':
        return generator.generate_all()

    capsule_path = Path(args[0]).resolve()

    if not capsule_path.exists():
        print(f"{RED}❌ Path does not exist: {capsule_path}{RESET}")
        return 1

    success = generator.generate_for_capsule(capsule_path)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
