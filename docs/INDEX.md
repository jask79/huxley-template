# Huxley Documentation Index

## Getting Started

- [Setup Guide](SETUP.md) — Prerequisites and initial configuration for Huxley (Claude Code, Python, Node.js, Docker)
- [Environment Setup](ENVIRONMENT_SETUP.md) — Quick guide for configuring Huxley environment variables
- [FAQ](FAQ.md) — Common questions about the framework, how it works, and how to use it
- [Examples](EXAMPLES.md) — Concrete usage scenarios showing how Huxley orchestrates work across specialist agents

## Agents & AI

- [Agent System Guide](AGENTS.md) — How agents work, how to define them, and orchestration fundamentals
- [Agent MCP Integration](AGENT_MCP_INTEGRATION.md) — How agents are equipped with MCP servers for domain-specific tools
- [Handoff Manifest Spec](HANDOFF_MANIFEST_SPEC.md) — Standardized data format for multi-agent handoffs in iOS workflows
- [Skills System Guide](SKILLS.md) — How skills bundle domain expertise for agents and when they activate
- [Hook System Guide](HOOKS.md) — Extension points (memory, task logging, quality gates) at Claude Code lifecycle events

## iOS & Mobile

- [iOS Simulator Testing Guide](SIMULATOR_TESTING_GUIDE.md) — Two-tier testing system using xcodebuildmcp and simulator_control.rb
- [Technical Implementation Guide](technical-implementation.md) — Complete technical reference for iOS development automation in Huxley

## Apple Shortcuts & Cherri

- [Apple Shortcuts Context](apple-shortcuts-context.md) — Apple Shortcuts fundamentals for Huxley agents (iOS/macOS triggers, Siri, widgets)
- [Cherri Language Reference](cherri-language-reference.md) — Language reference for Cherri, the iOS Shortcut compiler language

## Design & UI

- [Wireframing Guide](wireframing-guide.md) — First-step wireframing workflow in Huxley for iOS native applications
- [Design Validation Tools](DESIGN_VALIDATION_TOOLS.md) — Five CLI tools for autonomous pixel-perfect design verification in agent loops

## Automation & Integrations


## Development Loops

- [Frontend Dev Loop](FRONTEND_DEV_LOOP.md) — Autonomous frontend development with feedback iteration and agentic loop architecture
- [Backend Dev Loop](BACKEND_DEV_LOOP.md) — Autonomous backend development loop for APIs, databases, and backend testing

## Capsule System

- [Creating New Capsules](CREATING_NEW_CAPSULES.md) — How to scaffold new capsules using YAML specs and `tools/capsule_creator.py`
- [Capsule Lifecycle Maintenance](capsule-lifecycle-maintenance.md) — Build-and-sustain architecture for ongoing capsule maintenance states

## Infrastructure & DevOps

- [JWT Security Guide](JWT_Security_Guide.md) — JWT authentication patterns with macOS Keychain-backed signing keys
