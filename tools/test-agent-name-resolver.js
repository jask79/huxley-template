#!/usr/bin/env node
/**
 * Test script for agent-name-resolver transformer
 * Simulates a Task tool call with shorthand agent name
 */

const fs = require('fs');
const path = require('path');

// Load the transformer
const transformer = require('{{HOME_DIR}}/.claude-code-router/plugins/agent-name-resolver.js');

// Test request body with Task tool invocation using shorthand name
const testRequest = {
  model: "claude-sonnet-4-5-20250929",
  messages: [
    {
      role: "user",
      content: [
        {
          type: "tool_use",
          id: "toolu_test123",
          name: "Task",
          input: {
            subagent_type: "Research Agent",  // NO EMOJI - should be resolved
            prompt: "Research XYZ topic"
          }
        }
      ]
    }
  ]
};

console.log("🧪 Testing agent-name-resolver transformer\n");

console.log("📝 Before transformation:");
console.log(JSON.stringify(testRequest.messages[0].content[0].input, null, 2));

// Run transformer
transformer.req(testRequest, {}, {})
  .then(result => {
    console.log("\n✅ After transformation:");
    console.log(JSON.stringify(result.body.messages[0].content[0].input, null, 2));

    const resolvedName = result.body.messages[0].content[0].input.subagent_type;
    if (resolvedName === "🔍 Research Agent") {
      console.log("\n✅ SUCCESS: Agent name correctly resolved!");
      console.log(`   'Research Agent' → '${resolvedName}'`);
      process.exit(0);
    } else {
      console.log("\n❌ FAILURE: Agent name not resolved correctly");
      console.log(`   Expected: '🔍 Research Agent'`);
      console.log(`   Got: '${resolvedName}'`);
      process.exit(1);
    }
  })
  .catch(err => {
    console.error("\n❌ ERROR:", err);
    process.exit(1);
  });
