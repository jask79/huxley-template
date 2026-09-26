#!/usr/bin/env python3
"""
Test script - Generate .cherri files only (no compilation)
"""

import yaml
from pathlib import Path
from datetime import datetime

def generate_test_cherri():
    """Generate a simple test shortcut"""
    
    # Simple test spec
    test_spec = {
        'name': 'Huxley Test Shortcut',
        'icon': 'hammer',
        'color': 'blue',
        'actions': [
            {'type': 'get_text', 'parameters': {'text': 'Hello from Huxley!'}},
            {'type': 'show_alert', 'parameters': {'title': 'Test', 'message': 'Shortcut generated successfully!'}},
            {'type': 'show_result'}
        ]
    }
    
    # Generate Cherri source
    clean_name = 'BuilderTestShortcut'
    
    cherri_source = f'''// Generated shortcut: {test_spec['name']}
// Generated on: {datetime.now().isoformat()}

@Icon("{test_spec['icon']}")
@Color("{test_spec['color']}")
Shortcut {clean_name} {{
    // Test actions
    GetText("Hello from Huxley!")
    ShowAlert("Test", "Shortcut generated successfully!")
    ShowResult()
    
    // Huxley integration
    ShowAlert("Complete", "Huxley shortcut test complete!")
}}
'''
    
    # Write to file
    output_path = Path("{{CATALYST_ROOT}}/testing/test_shortcut.cherri")
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(cherri_source)
    
    print(f"✅ Generated test shortcut: {output_path}")
    print(f"📄 Content:")
    print(cherri_source)
    
    return output_path

if __name__ == "__main__":
    generate_test_cherri()