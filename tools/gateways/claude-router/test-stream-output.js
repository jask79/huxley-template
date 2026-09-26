#!/usr/bin/env node
// Test script to capture raw streaming output from router
const fetch = require('node-fetch');

async function testStream() {
  console.log('Testing router streaming output...\n');
  
  const response = await fetch('http://127.0.0.1:3456/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-5-20250929',
      max_tokens: 1024,
      stream: true,
      messages: [{
        role: 'user',
        content: 'Say "TEST123" exactly once and nothing else.'
      }]
    })
  });

  console.log('Response status:', response.status);
  console.log('Content-Type:', response.headers.get('content-type'));
  console.log('\n--- Raw Stream Output ---\n');

  let chunkCount = 0;
  let fullText = '';
  
  const reader = response.body;
  reader.on('data', chunk => {
    chunkCount++;
    const text = chunk.toString();
    fullText += text;
    process.stdout.write(text);
  });

  reader.on('end', () => {
    console.log('\n\n--- Analysis ---');
    console.log('Total chunks:', chunkCount);
    console.log('Full text length:', fullText.length);
    
    // Check for duplicates
    const test123Count = (fullText.match(/TEST123/g) || []).length;
    console.log('Occurrences of "TEST123":', test123Count);
    
    if (test123Count > 1) {
      console.log('⚠️  DUPLICATION DETECTED at router level!');
    } else {
      console.log('✅ No duplication at router level');
    }
  });
}

testStream().catch(console.error);
