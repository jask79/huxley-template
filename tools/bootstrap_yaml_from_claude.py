#!/usr/bin/env python3
"""
Bootstrap YAML specs from existing CLAUDE.md files

Uses Claude API to intelligently extract structured data from prose markdown
and create specs/current.yaml

Usage:
    python3 tools/bootstrap_yaml_from_claude.py <capsule_path>
    python3 tools/bootstrap_yaml_from_claude.py --all
"""

import sys
import yaml
from pathlib import Path
import anthropic
import os
from datetime import datetime


class YAMLBootstrapper:
    """Bootstraps YAML specs from CLAUDE.md"""

    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def read_claude_md(self, capsule_path: Path) -> str:
        """Read existing CLAUDE.md"""
        claude_md = capsule_path / "CLAUDE.md"

        if not claude_md.exists():
            raise FileNotFoundError(f"No CLAUDE.md found in {capsule_path}")

        with open(claude_md, 'r') as f:
            return f.read()

    def load_schema(self) -> str:
        """Load YAML schema template"""
        schema_file = self.catalyst_root / "tools" / "capsule_yaml_schema.yaml"

        if schema_file.exists():
            with open(schema_file, 'r') as f:
                return f.read()

        return "# No schema found"

    def extract_yaml_from_claude_md(self, claude_md_content: str, capsule_name: str) -> dict:
        """Use Claude API to extract structured YAML from CLAUDE.md"""

        schema = self.load_schema()

        prompt = f"""You are converting a Huxley capsule's CLAUDE.md file into structured YAML format.

**Capsule name:** {capsule_name}

**YAML Schema to follow:**
```yaml
{schema}
```

**Existing CLAUDE.md content:**
```markdown
{claude_md_content}
```

**Task:**
Extract all information from the CLAUDE.md and structure it according to the YAML schema.

**Instructions:**
1. Preserve all information - don't lose any details
2. Map sections intelligently:
   - "Purpose" → purpose.what/why/for_whom
   - "Current Status" → current.phase/health
   - "Technical Overview" → technical.stack/dependencies/integrations
   - "Key Features" → capabilities
   - "Architecture Notes" → technical.architecture
   - "Development Workflow" → development.workflow/tools
   - Any quality/security mentions → quality.standards/security
   - Any vision/roadmap mentions → vision.statement/roadmap

3. Fill in reasonable defaults for missing fields:
   - name: {capsule_name}
   - version: "1.0.0" (unless specified)
   - status: infer from "Current Status" section
   - current.last_updated: today's date

4. Be comprehensive - include all details from CLAUDE.md

**Output:**
Return ONLY the YAML (no explanations, no markdown code blocks, just raw YAML).
Start directly with the YAML content.
"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text

            # Extract YAML (handle if Claude wrapped it in code blocks)
            if "```yaml" in response_text:
                yaml_start = response_text.find("```yaml") + 7
                yaml_end = response_text.find("```", yaml_start)
                yaml_text = response_text[yaml_start:yaml_end].strip()
            elif "```" in response_text:
                yaml_start = response_text.find("```") + 3
                yaml_end = response_text.find("```", yaml_start)
                yaml_text = response_text[yaml_start:yaml_end].strip()
            else:
                yaml_text = response_text.strip()

            # Parse YAML
            spec = yaml.safe_load(yaml_text)

            # Ensure required fields
            if 'name' not in spec:
                spec['name'] = capsule_name

            if 'version' not in spec:
                spec['version'] = "1.0.0"

            if 'current' not in spec:
                spec['current'] = {}

            if 'last_updated' not in spec['current']:
                spec['current']['last_updated'] = datetime.now().strftime("%Y-%m-%d")

            # Add auto metadata
            if '_auto' not in spec:
                spec['_auto'] = {}

            spec['_auto']['last_session'] = datetime.now().isoformat()
            spec['_auto']['bootstrapped_from'] = 'CLAUDE.md'
            spec['_auto']['bootstrapped_at'] = datetime.now().isoformat()

            return spec

        except Exception as e:
            print(f"Error calling Claude API: {e}", file=sys.stderr)
            raise

    def save_yaml_spec(self, capsule_path: Path, spec: dict):
        """Save generated YAML spec"""
        specs_dir = capsule_path / "specs"
        specs_dir.mkdir(exist_ok=True)

        spec_file = specs_dir / "current.yaml"

        with open(spec_file, 'w') as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"  ✅ Created specs/current.yaml")

    def bootstrap_capsule(self, capsule_path: Path) -> bool:
        """Bootstrap YAML for a single capsule"""
        try:
            print(f"\n📦 Bootstrapping {capsule_path.name}...")

            # Check if already has YAML
            yaml_file = capsule_path / "specs" / "current.yaml"
            if yaml_file.exists():
                print(f"  ⏭️  Already has specs/current.yaml, skipping")
                return True

            # Read CLAUDE.md
            claude_md_content = self.read_claude_md(capsule_path)
            print(f"  📖 Read CLAUDE.md ({len(claude_md_content)} chars)")

            # Extract to YAML
            print(f"  🤖 Extracting structure with Claude API...")
            spec = self.extract_yaml_from_claude_md(claude_md_content, capsule_path.name)

            # Save YAML
            self.save_yaml_spec(capsule_path, spec)

            # Show preview
            print(f"\n  📋 Preview of generated YAML:")
            print(f"     Name: {spec.get('name')}")
            print(f"     Status: {spec.get('status', 'N/A')}")
            if 'technical' in spec and 'stack' in spec['technical']:
                print(f"     Stack: {', '.join(spec['technical']['stack'][:3])}")
            if 'capabilities' in spec:
                print(f"     Capabilities: {len(spec['capabilities'])} features")

            return True

        except FileNotFoundError:
            print(f"  ⏭️  No CLAUDE.md found, skipping")
            return True
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def bootstrap_all(self):
        """Bootstrap YAML for all capsules"""
        capsules_dir = self.catalyst_root / "capsules"

        if not capsules_dir.exists():
            print("❌ No capsules directory found")
            return 1

        capsules = [d for d in capsules_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

        print(f"\n🚀 Bootstrapping YAML specs for {len(capsules)} capsules...")

        success_count = 0
        for capsule in sorted(capsules):
            if self.bootstrap_capsule(capsule):
                success_count += 1

        print(f"\n📊 Summary: {success_count}/{len(capsules)} capsules bootstrapped")
        return 0 if success_count == len(capsules) else 1


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/bootstrap_yaml_from_claude.py <capsule_path> or --all")
        return 1

    try:
        bootstrapper = YAMLBootstrapper()

        if sys.argv[1] == '--all':
            return bootstrapper.bootstrap_all()

        capsule_path = Path(sys.argv[1]).resolve()

        if not capsule_path.exists():
            print(f"❌ Path does not exist: {capsule_path}")
            return 1

        success = bootstrapper.bootstrap_capsule(capsule_path)
        return 0 if success else 1

    except ValueError as e:
        print(f"❌ {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
