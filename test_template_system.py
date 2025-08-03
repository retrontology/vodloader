#!/usr/bin/env python3
"""
Test script to verify the template system implementation.
"""

import sys
sys.path.append('app')

from vodloader.post.chat.template_manager import TemplateManager
from pathlib import Path

def test_template_system():
    """Test all template system functionality."""
    print("=== TEMPLATE SYSTEM VERIFICATION ===")
    
    try:
        # Initialize template manager
        template_dir = Path('app/vodloader/post/chat_templates')
        tm = TemplateManager(template_dir)
        print("✓ TemplateManager initialized successfully")
        
        # Test 1: Template loading
        print("\n1. Testing template loading...")
        base_html = tm.load_template('base.html')
        print(f"   - Loaded base.html: {len(base_html)} characters")
        
        # Test 2: CSS variable generation
        print("\n2. Testing CSS variable generation...")
        config = {
            'font_family': 'Arial',
            'font_size': 16,
            'text_color': '#ff0000',
            'overlay_width': 400,
            'overlay_height': 500
        }
        css_vars = tm.generate_css_variables(config)
        print(f"   - Generated CSS variables: {len(css_vars)} characters")
        if '--chat-font-size: 16px' in css_vars:
            print("   ✓ CSS variables contain expected values")
        
        # Test 3: JavaScript config generation
        print("\n3. Testing JavaScript config generation...")
        config_js = tm.generate_config_object(config)
        print(f"   - Generated JS config: {len(config_js)} characters")
        if 'window.chatConfig' in config_js:
            print("   ✓ Config object format is correct")
        
        # Test 4: Message data generation
        print("\n4. Testing message data generation...")
        messages = [
            {
                'id': 'msg-123',
                'username': 'TestUser',
                'text': 'Hello world with "quotes" and backslashes\\',
                'color': '#ff0000',
                'timestamp': 10.5,
                'badges': ['subscriber'],
                'moderator': False,
                'subscriber': True,
                'first_message': False
            }
        ]
        messages_js = tm.generate_message_data(messages)
        print(f"   - Generated message data: {len(messages_js)} characters")
        if 'window.chatMessages' in messages_js:
            print("   ✓ Message data format is correct")
        
        # Test 5: Complete HTML generation
        print("\n5. Testing complete HTML generation...")
        html = tm.generate_complete_html(messages, config)
        print(f"   - Generated complete HTML: {len(html)} characters")
        
        # Verify integration
        checks = [
            ('Config object injected', 'window.chatConfig' in html),
            ('Message data injected', 'window.chatMessages' in html),
            ('CSS variables injected', '--chat-font-size: 16px' in html),
            ('CSS inlined', '<style>' in html and 'chat-container' in html),
            ('JavaScript inlined', '<script>' in html and 'class ChatOverlay' in html),
            ('No external references', 'href="chat.css"' not in html)
        ]
        
        print("\n   Integration checks:")
        all_passed = True
        for check_name, result in checks:
            status = '✓' if result else '✗'
            print(f"   {status} {check_name}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n=== ALL TESTS PASSED ===")
            print("Template system is working correctly!")
            return True
        else:
            print("\n=== SOME TESTS FAILED ===")
            return False
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_template_system()
    sys.exit(0 if success else 1)