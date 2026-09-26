#!/usr/bin/env python3
"""
Agent Name Router for Huxley

Translates plain agent names to emoji-prefixed names required by Claude Code.
Usage: tools/route_agent.py "macOS Specialist" -> outputs "💻 macOS Specialist"
"""

import sys
import argparse

# Agent name translation table
AGENT_MAP = {
    # Utility agents (no emoji)
    "general-purpose": "general-purpose",
    "statusline-setup": "statusline-setup",
    "output-style-setup": "output-style-setup",

    # Specialist agents (with emojis)
    "DevOps Troubleshooter": "🚨 DevOps Troubleshooter",
    "Python Pro": "🐍 Python Pro",
    "JavaScript Pro": "⚡ JavaScript Pro",
    "iOS Dev": "📱 iOS Dev",
    "Boss": "👔 BOSS",
    "BOSS": "👔 BOSS",
    "System Architect": "🏗️ System Architect",
    "Deployment Engineer": "🚀 Deployment Engineer",
    "Security Analyst": "🛡️ Security Analyst",
    "Performance Optimizer": "⚡ Performance Optimizer",
    "Frontend Specialist": "🎨 Frontend Specialist",
    "Research Agent": "🔍 Research Agent",
    "Shopify Specialist": "🛒 Shopify Specialist",
    "Automation Specialist": "🤖 Automation Specialist",
    "macOS Specialist": "💻 macOS Specialist",
    "Test Automator": "🧪 Test Automator",
    "Data Analyst": "📊 Data Analyst",
    "Code Reviewer": "👨‍💻 Code Reviewer",
    "Backend Architect": "🏛️ Backend Architect",
    "Playwright Agent": "🎭 Playwright Agent",
}

# Create case-insensitive lookup
AGENT_MAP_LOWER = {k.lower(): v for k, v in AGENT_MAP.items()}


def route_agent(agent_name: str) -> str:
    """
    Translate plain agent name to emoji-prefixed name.

    Args:
        agent_name: Plain agent name (e.g., "macOS Specialist")

    Returns:
        Emoji-prefixed agent name (e.g., "💻 macOS Specialist")

    Raises:
        ValueError: If agent name not found
    """
    # Try exact match first
    if agent_name in AGENT_MAP:
        return AGENT_MAP[agent_name]

    # Try case-insensitive match
    agent_lower = agent_name.lower()
    if agent_lower in AGENT_MAP_LOWER:
        return AGENT_MAP_LOWER[agent_lower]

    # Agent not found
    available = sorted(AGENT_MAP.keys())
    raise ValueError(
        f"Agent '{agent_name}' not found.\n\n"
        f"Available agents:\n" + "\n".join(f"  - {a}" for a in available)
    )


def main():
    parser = argparse.ArgumentParser(
        description="Translate plain agent names to emoji-prefixed names for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "macOS Specialist"     -> 💻 macOS Specialist
  %(prog)s "Python Pro"           -> 🐍 Python Pro
  %(prog)s --list                 -> List all available agents
        """
    )

    parser.add_argument(
        "agent_name",
        nargs="?",
        help="Plain agent name to translate"
    )

    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all available agents"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only output the translated name (no labels)"
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        print("Available agents:")
        for plain, emoji in sorted(AGENT_MAP.items()):
            print(f"  {plain:<30} -> {emoji}")
        return 0

    # Require agent name
    if not args.agent_name:
        parser.print_help()
        return 1

    # Translate
    try:
        translated = route_agent(args.agent_name)
        if args.quiet:
            print(translated)
        else:
            print(f"{translated}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
