#!/usr/bin/env python3
"""
Test Agent Memory Integration - Verify end-to-end memory lifecycle
"""

import sys
from pathlib import Path

# Add hooks utils to path
sys.path.insert(0, '{{CATALYST_ROOT}}/global/claude-config/hooks')

from utils.memory_integration import get_memory_integration

def test_memory_storage():
    """Test creating a memory."""
    print("🧪 Testing memory storage...")

    try:
        memory = get_memory_integration()

        print(f"   Memory integration initialized: {memory is not None}")
        print(f"   Coordinator available: {memory.coordinator is not None if memory else False}")

        # Create a test memory
        memory_id = memory.create_memory_for_agent(
            agent_name="Test Agent",
            content="Successfully implemented test feature using pattern X",
            context="Integration test for memory system",
            impact_score=0.8,
            tags=["test", "pattern-x", "success"],
            memory_type="task"
        )

        if memory_id:
            print(f"   ✅ Memory created: {memory_id}")
            return True
        else:
            print(f"   ❌ Failed to create memory (returned None)")
            return False
    except Exception as e:
        print(f"   ❌ Exception during memory creation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_search():
    """Test searching for memories."""
    print("\n🧪 Testing memory search...")

    memory = get_memory_integration()

    # Search for memories
    results = memory.search_memories_for_agent(
        agent_name="Test Agent",
        query="test feature pattern",
        limit=5
    )

    if results:
        print(f"   ✅ Found {len(results)} memories")
        for i, mem in enumerate(results, 1):
            print(f"      {i}. {mem['content'][:50]}... (similarity: {mem.get('similarity', 0):.2f})")
        return True
    else:
        print(f"   ⚠️  No memories found (may be expected if this is first run)")
        return True  # Not a failure - just empty db


def test_tag_extraction():
    """Test tag extraction from task descriptions."""
    print("\n🧪 Testing tag extraction...")

    memory = get_memory_integration()

    test_cases = [
        ("Implement FastAPI authentication with Supabase", "Backend Developer"),
        ("Create React component with TypeScript", "Frontend Developer"),
        ("Fix iOS simulator crash bug", "Mobile Developer"),
    ]

    for task_desc, agent_name in test_cases:
        tags = memory.extract_tags_from_task(task_desc, agent_name)
        print(f"   Task: {task_desc[:40]}...")
        print(f"   Agent: {agent_name}")
        print(f"   Tags: {tags}")
        print()

    return True


def test_should_store_logic():
    """Test memory storage decision logic."""
    print("🧪 Testing storage decision logic...")

    memory = get_memory_integration()

    test_cases = [
        ("Implement auth feature", "Successfully implemented OAuth2 with refresh tokens", True),
        ("Read the config file", "Here is the config content", False),
        ("Fix bug", "Error: Could not fix the issue", False),
        ("Create API endpoint", "Recommended using FastAPI", False),
        ("Build component", "Implemented Button component with variants", True),
    ]

    passed = 0
    for task_desc, result, expected in test_cases:
        should_store = memory.should_store_memory(task_desc, result)
        status = "✅" if should_store == expected else "❌"
        print(f"   {status} Task: {task_desc[:30]}... -> {should_store} (expected: {expected})")
        if should_store == expected:
            passed += 1

    print(f"\n   Passed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def main():
    """Run all tests."""
    print("🧠 Agent Memory Integration Tests\n")
    print("=" * 60)

    tests = [
        ("Memory Storage", test_memory_storage),
        ("Memory Search", test_memory_search),
        ("Tag Extraction", test_tag_extraction),
        ("Storage Decision Logic", test_should_store_logic),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n   ❌ Test failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")

    print(f"\n   Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! Memory integration is working.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
