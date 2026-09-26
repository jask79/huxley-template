#!/usr/bin/env node
/**
 * Comprehensive test suite for agent-name-resolver transformer
 */

const transformer = require('{{HOME_DIR}}/.claude-code-router/plugins/agent-name-resolver.js');

const testCases = [
  {
    name: "No emoji shorthand",
    input: "Research Agent",
    expected: "🔍 Research Agent"
  },
  {
    name: "Case-insensitive match",
    input: "research agent",
    expected: "🔍 Research Agent"
  },
  {
    name: "Already has emoji",
    input: "🔍 Research Agent",
    expected: "🔍 Research Agent"
  },
  {
    name: "Backend Dev shorthand",
    input: "Backend Dev",
    expected: "🏛️ Backend Developer"
  },
  {
    name: "AI Nerd case-insensitive",
    input: "ai nerd",
    expected: "🤓 AI Nerd"
  },
  {
    name: "Unknown agent (should pass through)",
    input: "Unknown Agent",
    expected: "Unknown Agent"
  },
  {
    name: "Code Reviewer",
    input: "Code Reviewer",
    expected: "🧐 Code Reviewer"
  },
  {
    name: "Debugger",
    input: "Debugger",
    expected: "👾 Debugger"
  }
];

console.log("🧪 Running comprehensive agent name resolution tests\n");

let passed = 0;
let failed = 0;

async function runTests() {
  for (const testCase of testCases) {
    const request = {
      messages: [{
        role: "user",
        content: [{
          type: "tool_use",
          name: "Task",
          input: {
            subagent_type: testCase.input,
            prompt: "Test prompt"
          }
        }]
      }]
    };

    try {
      const result = await transformer.req(request, {}, {});
      const resolvedName = result.body.messages[0].content[0].input.subagent_type;

      if (resolvedName === testCase.expected) {
        console.log(`✅ ${testCase.name}`);
        console.log(`   '${testCase.input}' → '${resolvedName}'`);
        passed++;
      } else {
        console.log(`❌ ${testCase.name}`);
        console.log(`   Input: '${testCase.input}'`);
        console.log(`   Expected: '${testCase.expected}'`);
        console.log(`   Got: '${resolvedName}'`);
        failed++;
      }
    } catch (err) {
      console.log(`❌ ${testCase.name} - ERROR: ${err.message}`);
      failed++;
    }
  }

  console.log(`\n📊 Test Results: ${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

runTests();
