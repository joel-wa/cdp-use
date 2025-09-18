#!/usr/bin/env python3

# Read the file
with open('simple_conversational_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Process lines to fix issues
fixed_lines = []
skip_next = 0

for i, line in enumerate(lines):
    if skip_next > 0:
        skip_next -= 1
        continue
        
    # Fix the context_used variable issue
    if 'context_used or \'none\'' in line:
        line = line.replace('context_used or \'none\'', 'context_type')
        
    # Remove problematic visual_context and interactive_context references
    if 'if visual_context:' in line and i + 3 < len(lines) and 'if interactive_context:' in lines[i+2]:
        # Skip this block of 4 lines
        skip_next = 3
        continue
        
    fixed_lines.append(line)

# Write back the fixed content
with open('simple_conversational_orchestrator.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print('Fixed all issues in the file!')