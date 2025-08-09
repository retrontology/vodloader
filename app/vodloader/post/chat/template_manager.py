"""
Template manager for chat overlay dynamic content injection.

This module provides the TemplateManager class that handles template loading,
caching, dynamic CSS variable substitution, JavaScript configuration injection,
and message data injection with proper escaping.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger('vodloader.chat_video.template_manager')


class TemplateError(Exception):
    """Base exception for template-related errors."""
    pass


class TemplateManager:
    """
    Manages template loading, caching, and dynamic content injection.
    
    Provides template loading with caching, dynamic CSS variable substitution,
    JavaScript configuration object injection, and message data JSON injection
    with proper escaping.
    """
    
    def __init__(self, template_dir: Path):
        """
        Initialize template manager with template directory.
        
        Args:
            template_dir: Path to directory containing template files
            
        Raises:
            TemplateError: If template directory doesn't exist
        """
        self.template_dir = template_dir
        self._template_cache = {}
        self._cache_timestamps = {}
        
        if not self.template_dir.exists():
            raise TemplateError(f"Template directory not found: {self.template_dir}")
        
        logger.debug(f"TemplateManager initialized with directory: {self.template_dir}")
    
    def _get_template_path(self, template_name: str) -> Path:
        """
        Get full path for a template file.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            Path to the template file
        """
        return self.template_dir / template_name
    
    def _is_cache_valid(self, template_name: str) -> bool:
        """
        Check if cached template is still valid (file hasn't been modified).
        
        Args:
            template_name: Name of the template file
            
        Returns:
            True if cache is valid, False otherwise
        """
        if template_name not in self._template_cache:
            return False
        
        template_path = self._get_template_path(template_name)
        if not template_path.exists():
            return False
        
        cached_timestamp = self._cache_timestamps.get(template_name, 0)
        current_timestamp = template_path.stat().st_mtime
        
        return cached_timestamp >= current_timestamp
    
    def load_template(self, template_name: str, use_cache: bool = True) -> str:
        """
        Load template content with optional caching.
        
        Args:
            template_name: Name of the template file to load
            use_cache: Whether to use cached version if available
            
        Returns:
            Template content as string
            
        Raises:
            TemplateError: If template file cannot be loaded
        """
        # Check cache first if enabled
        if use_cache and self._is_cache_valid(template_name):
            logger.debug(f"Using cached template: {template_name}")
            return self._template_cache[template_name]
        
        # Load template from file
        template_path = self._get_template_path(template_name)
        
        try:
            logger.debug(f"Loading template from file: {template_path}")
            content = template_path.read_text(encoding='utf-8')
            
            # Update cache
            if use_cache:
                self._template_cache[template_name] = content
                self._cache_timestamps[template_name] = template_path.stat().st_mtime
                logger.debug(f"Template cached: {template_name}")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            raise TemplateError(f"Template loading failed: {template_name}") from e
    
    def generate_css_variables(self, config: Dict[str, Any]) -> str:
        """
        Generate CSS variable declarations from configuration.
        
        Args:
            config: Configuration dictionary with CSS values
            
        Returns:
            CSS string with variable declarations
        """
        css_variables = {
            '--chat-font-family': self._format_css_font_family(config.get('font_family', 'Roboto Mono')),
            '--chat-font-size': f"{config.get('font_size', 14)}px",
            '--chat-font-style': config.get('font_style', 'normal'),
            '--chat-font-weight': config.get('font_weight', 'normal'),
            '--chat-text-color': config.get('text_color', '#ffffff'),
            '--chat-text-shadow-color': config.get('text_shadow_color', '#000000'),
            '--chat-text-shadow-size': f"{config.get('text_shadow_size', 1)}px",
            '--chat-overlay-width': f"{config.get('overlay_width', 350)}px",
            '--chat-overlay-height': f"{config.get('overlay_height', 400)}px"
        }
        
        css_rules = [":root {"]
        for var_name, var_value in css_variables.items():
            css_rules.append(f"    {var_name}: {var_value};")
        css_rules.append("}")
        
        css_content = "\n".join(css_rules)
        logger.debug(f"Generated CSS variables: {len(css_variables)} variables")
        return css_content
    
    def _format_css_font_family(self, font_family: str) -> str:
        """
        Format font family for CSS with proper quoting and fallbacks.
        
        Args:
            font_family: Font family name
            
        Returns:
            Properly formatted CSS font-family value
        """
        # Add quotes if font name contains spaces and isn't already quoted
        if ' ' in font_family and not (font_family.startswith('"') and font_family.endswith('"')):
            font_family = f'"{font_family}"'
        
        # Add fallback fonts
        return f"{font_family}, monospace"
    
    def generate_config_object(self, config: Dict[str, Any]) -> str:
        """
        Generate JavaScript configuration object.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            JavaScript code string that assigns config to window.chatConfig
        """
        try:
            # Create configuration object with proper defaults
            js_config = {
                'messageDuration': config.get('message_duration', 30.0),
                'frameRate': config.get('frame_rate', 30.0),
                'videoDuration': config.get('video_duration', 0),
                'showTimestamps': config.get('show_timestamps', False)
            }
            
            # Generate JavaScript assignment with proper JSON encoding
            js_code = f"window.chatConfig = {json.dumps(js_config, indent=2)};"
            
            logger.debug(f"Generated JavaScript config object with {len(js_config)} properties")
            return js_code
            
        except Exception as e:
            logger.error(f"Failed to generate config object: {e}")
            raise TemplateError(f"Config object generation failed: {e}") from e
    
    def generate_message_data(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate JavaScript message data with proper JSON escaping.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            JavaScript code string that assigns messages to window.chatMessages
        """
        try:
            # Sanitize and validate message data
            sanitized_messages = []
            
            for message in messages:
                sanitized_message = {
                    'id': self._sanitize_string(str(message.get('id', ''))),
                    'username': self._sanitize_string(message.get('username', '')),
                    'text': self._sanitize_string(message.get('text', '')),
                    'color': self._sanitize_color(message.get('color')),
                    'timestamp': float(message.get('timestamp', 0)),
                    'badges': message.get('badges', []),
                    'moderator': bool(message.get('moderator', False)),
                    'subscriber': bool(message.get('subscriber', False)),
                    'first_message': bool(message.get('first_message', False))
                }
                
                sanitized_messages.append(sanitized_message)
            
            # Generate JavaScript assignment with proper JSON encoding
            js_code = f"window.chatMessages = {json.dumps(sanitized_messages, indent=2, ensure_ascii=False)};"
            
            logger.debug(f"Generated message data for {len(sanitized_messages)} messages")
            return js_code
            
        except Exception as e:
            logger.error(f"Failed to generate message data: {e}")
            raise TemplateError(f"Message data generation failed: {e}") from e
    
    def _sanitize_string(self, text: str) -> str:
        """
        Sanitize string content for safe JSON injection.
        
        Args:
            text: Input string to sanitize
            
        Returns:
            Sanitized string safe for JSON encoding
        """
        if not isinstance(text, str):
            return str(text)
        
        # Remove or replace potentially problematic characters
        # JSON encoding will handle most escaping, but we can do additional sanitization
        sanitized = text.replace('\x00', '')  # Remove null bytes
        
        # Limit length to prevent extremely long messages
        if len(sanitized) > 500:
            sanitized = sanitized[:497] + '...'
        
        return sanitized
    
    def _sanitize_color(self, color: Optional[str]) -> Optional[str]:
        """
        Sanitize color value for CSS safety.
        
        Args:
            color: Color string (hex, rgb, etc.)
            
        Returns:
            Sanitized color string or None if invalid
        """
        if not color or not isinstance(color, str):
            return None
        
        # Basic validation for hex colors
        if color.startswith('#'):
            if len(color) == 7 and all(c in '0123456789abcdefABCDEF' for c in color[1:]):
                return color.lower()
            elif len(color) == 4 and all(c in '0123456789abcdefABCDEF' for c in color[1:]):
                return color.lower()
        
        # Allow some basic CSS color names
        css_colors = {
            'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'cyan',
            'white', 'black', 'gray', 'grey', 'brown', 'lime', 'navy', 'teal'
        }
        
        if color.lower() in css_colors:
            return color.lower()
        
        # If color doesn't match expected patterns, return None
        logger.debug(f"Invalid color format rejected: {color}")
        return None
    
    def substitute_template_placeholders(
        self, 
        template_content: str, 
        css_content: str,
        js_content: str,
        config_js: str,
        messages_js: str
    ) -> str:
        """
        Substitute placeholders in template with dynamic content.
        
        Args:
            template_content: Base HTML template content
            css_content: CSS content to inject
            js_content: JavaScript content to inject
            config_js: JavaScript configuration code
            messages_js: JavaScript message data code
            
        Returns:
            Complete HTML with all substitutions made
        """
        try:
            # Use a replacement function to avoid regex escape issues
            def css_replacer(match):
                return f'<style>\n{css_content}\n</style>'
            
            def js_replacer(match):
                return f'<script>\n{js_content}\n</script>'
            
            # Replace CSS link with inline styles
            html_content = re.sub(
                r'<link\s+rel=["\']stylesheet["\']\s+href=["\']chat\.css["\']>',
                css_replacer,
                template_content,
                flags=re.IGNORECASE
            )
            
            # Replace JavaScript src with inline script
            html_content = re.sub(
                r'<script\s+src=["\']chat\.js["\']></script>',
                js_replacer,
                html_content,
                flags=re.IGNORECASE
            )
            
            # Replace dynamic CSS placeholder
            html_content = html_content.replace(
                '/* Dynamic CSS variables will be injected here */',
                self._extract_css_variables_from_content(css_content)
            )
            
            # Replace viewport with dynamic dimensions
            overlay_width = config.get('overlay_width', 350)
            overlay_height = config.get('overlay_height', 400)
            dynamic_viewport = f'width={overlay_width}, height={overlay_height}, initial-scale=1.0, user-scalable=no'
            html_content = re.sub(
                r'content="width=\d+, height=\d+, initial-scale=1\.0, user-scalable=no"',
                f'content="{dynamic_viewport}"',
                html_content
            )
            
            # Replace configuration placeholder
            html_content = html_content.replace(
                '/* Dynamic configuration object will be injected here */',
                config_js
            )
            
            # Replace message data placeholder
            html_content = html_content.replace(
                '/* Message data will be injected here */',
                messages_js
            )
            
            logger.debug("Template placeholder substitution completed")
            return html_content
            
        except Exception as e:
            logger.error(f"Template substitution failed: {e}")
            raise TemplateError(f"Template substitution failed: {e}") from e
    
    def _extract_css_variables_from_content(self, css_content: str) -> str:
        """
        Extract CSS variable declarations from full CSS content.
        
        Args:
            css_content: Full CSS content
            
        Returns:
            Just the CSS variable declarations
        """
        # Look for :root { ... } block and extract variable declarations
        root_match = re.search(r':root\s*\{([^}]+)\}', css_content, re.DOTALL)
        if root_match:
            return f":root {{{root_match.group(1)}}}"
        
        # If no :root block found, return empty
        return ""
    
    def generate_complete_html(
        self,
        messages: List[Dict[str, Any]],
        config: Dict[str, Any],
        use_cache: bool = True
    ) -> str:
        """
        Generate complete HTML with all dynamic content injected.
        
        Args:
            messages: List of message dictionaries
            config: Configuration dictionary
            use_cache: Whether to use template caching
            
        Returns:
            Complete HTML string ready for browser loading
            
        Raises:
            TemplateError: If template generation fails
        """
        try:
            logger.debug(f"Generating complete HTML with {len(messages)} messages")
            
            # Load template files
            base_html = self.load_template('base.html', use_cache)
            chat_css = self.load_template('chat.css', use_cache)
            chat_js = self.load_template('chat.js', use_cache)
            
            # Generate dynamic content
            css_variables = self.generate_css_variables(config)
            config_js = self.generate_config_object(config)
            messages_js = self.generate_message_data(messages)
            
            # Combine CSS with dynamic variables
            combined_css = chat_css + '\n\n/* Dynamic CSS Variables */\n' + css_variables
            
            # Substitute all placeholders
            complete_html = self.substitute_template_placeholders(
                base_html,
                combined_css,
                chat_js,
                config_js,
                messages_js
            )
            
            logger.info("Complete HTML template generated successfully")
            return complete_html
            
        except Exception as e:
            logger.error(f"Failed to generate complete HTML: {e}")
            raise TemplateError(f"HTML generation failed: {e}") from e
    
    def clear_cache(self) -> None:
        """Clear all cached templates."""
        self._template_cache.clear()
        self._cache_timestamps.clear()
        logger.debug("Template cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about cached templates.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'cached_templates': list(self._template_cache.keys()),
            'cache_size': len(self._template_cache),
            'cache_timestamps': dict(self._cache_timestamps)
        }