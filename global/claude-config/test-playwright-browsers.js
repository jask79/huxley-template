#!/usr/bin/env node

import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const execAsync = promisify(exec);

const tests = [
  {
    name: 'Chrome (Chromium)',
    command: `npx @playwright/mcp@latest --browser chrome --config ${__dirname}/playwright-mcp-config.json --headless`
  },
  {
    name: 'Chromium',
    command: `npx @playwright/mcp@latest --browser chromium --config ${__dirname}/playwright-mcp-config.json --headless`
  },
  {
    name: 'Brave Browser',
    command: `npx @playwright/mcp@latest --browser chromium --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --config ${__dirname}/playwright-brave-config.json --headless`
  }
];

async function testConfiguration(test) {
  console.log(`\n🧪 Testing: ${test.name}`);
  console.log(`Command: ${test.command}\n`);
  
  try {
    // Kill after 3 seconds since MCP server runs indefinitely
    const process = exec(test.command);
    
    let output = '';
    let errorOutput = '';
    
    process.stdout?.on('data', (data) => {
      output += data;
    });
    
    process.stderr?.on('data', (data) => {
      errorOutput += data;
    });
    
    // Give it 3 seconds to start up
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Kill the process
    process.kill('SIGTERM');
    
    // Wait a bit for cleanup
    await new Promise(resolve => setTimeout(resolve, 500));
    
    if (errorOutput.includes('Error') && !errorOutput.includes('SIGTERM')) {
      console.log(`❌ ${test.name}: Failed to start`);
      console.log(`Error: ${errorOutput}`);
      return false;
    } else {
      console.log(`✅ ${test.name}: Started successfully`);
      if (output) console.log(`Output: ${output.substring(0, 200)}...`);
      return true;
    }
    
  } catch (error) {
    console.log(`❌ ${test.name}: Exception occurred`);
    console.log(`Error: ${error.message}`);
    return false;
  }
}

async function runTests() {
  console.log('🚀 Testing Playwright MCP Browser Configurations\n');
  
  let passed = 0;
  const total = tests.length;
  
  for (const test of tests) {
    const success = await testConfiguration(test);
    if (success) passed++;
  }
  
  console.log(`\n📊 Test Results: ${passed}/${total} configurations working`);
  
  if (passed === total) {
    console.log('🎉 All browser configurations are working!');
  } else {
    console.log('⚠️  Some configurations need attention.');
  }
}

runTests().catch(console.error);