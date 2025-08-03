"""
Simple chat video generation module.

This is a basic skeleton for chat video generation functionality.
Use the Spec feature to implement a better, cleaner solution.
"""

from .generator import ChatVideoGenerator, generate_chat_video
from .browser_manager import BrowserManager, BrowserManagerError, BrowserTimeoutError, BrowserResourceError, browser_context

__all__ = [
    'ChatVideoGenerator',
    'generate_chat_video',
    'BrowserManager',
    'BrowserManagerError', 
    'BrowserTimeoutError',
    'BrowserResourceError',
    'browser_context'
]