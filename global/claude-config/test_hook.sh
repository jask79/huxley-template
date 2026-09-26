#!/bin/bash
echo "Hook triggered at $(date)" >> /tmp/claude_hook_test.txt
echo "Environment vars:" >> /tmp/claude_hook_test.txt
env | grep -i claude >> /tmp/claude_hook_test.txt
echo "---" >> /tmp/claude_hook_test.txt