# Chat Video Generation Module

This module provides functionality to overlay chat messages on video streams with proper timing and formatting. It has been split into focused submodules for better maintainability and testability.

## Module Structure

```
chat/
├── __init__.py          # Package exports and imports
├── config.py            # Configuration class
├── font_manager.py      # Font loading and caching
├── video_processor.py   # Video preprocessing (ad removal)
├── area.py             # Chat area positioning and sizing
├── renderer.py         # Message rendering on frames
├── generator.py        # Main orchestrator class
└── README.md           # This file
```

## Classes Overview

### `ChatVideoConfig` (config.py)
Configuration container for all chat video generation settings including:
- Layout (width, height, positioning, padding)
- Appearance (fonts, colors)
- Performance (GPU usage, batch size, worker count)
- Features (ad removal, message duration)

### `FontManager` (font_manager.py)
Handles system font discovery, loading, and caching:
- Discovers available system fonts
- Caches font instances to avoid reloading
- Provides thread-safe font access

### `VideoProcessor` (video_processor.py)
Handles video preprocessing tasks:
- Ad detection and removal
- Video format validation
- Stream property extraction

### `ChatArea` (area.py)
Manages chat overlay positioning and sizing:
- Auto-sizing to fit video bounds
- Content area calculations with padding
- Boundary validation

### `ChatRenderer` (renderer.py)
Core message rendering functionality:
- Text wrapping and layout
- Message caching for performance
- Frame-by-frame rendering
- Thread-safe operations

### `ChatVideoGenerator` (generator.py)
Main orchestrator that coordinates all components:
- GPU acceleration detection
- Batch processing for performance
- Parallel frame processing
- Audio muxing

## Usage Examples

### Basic Usage
```python
from vodloader.post.chat import ChatVideoGenerator, ChatVideoConfig

# Use default configuration
generator = ChatVideoGenerator()
result = await generator.generate(video_file)
```

### Custom Configuration
```python
config = ChatVideoConfig(
    width=400,
    height=600,
    font_size=28,
    use_gpu=True,
    batch_size=60,
    num_workers=8
)

generator = ChatVideoGenerator(config)
result = await generator.generate(video_file)
```

### Backward Compatibility
```python
# The old function still works
from vodloader.post.chat import generate_chat_video

result = await generate_chat_video(
    video=video_file,
    width=320,
    use_gpu=True
)
```

## Performance Features

- **Batch Processing**: Processes multiple frames simultaneously
- **Parallel Rendering**: Uses ThreadPoolExecutor for concurrent frame rendering
- **Message Caching**: Pre-computes and caches message layouts
- **GPU Acceleration**: Automatic CUDA detection and usage
- **Memory Optimization**: Efficient frame handling and cleanup

## Benefits of Modular Structure

1. **Maintainability**: Each class has a single responsibility
2. **Testability**: Individual components can be unit tested
3. **Extensibility**: Easy to add new features or modify existing ones
4. **Readability**: Smaller, focused files are easier to understand
5. **Reusability**: Components can be used independently
6. **Performance**: Optimizations can be applied to specific components

## Migration Guide

Existing code using the old `chat_video.py` module will continue to work without changes due to the compatibility layer. However, for new code, consider using the modular imports:

```python
# Old way (still works)
from vodloader.post.chat_video import ChatVideoGenerator

# New way (recommended)
from vodloader.post.chat import ChatVideoGenerator
```

## Testing

Each module can be tested independently:

```python
# Test configuration
from vodloader.post.chat.config import ChatVideoConfig
config = ChatVideoConfig(width=320)
assert config.width == 320

# Test font manager
from vodloader.post.chat.font_manager import FontManager
font = FontManager.get_font("Arial", "Regular", 24)

# Test chat area
from vodloader.post.chat.area import ChatArea
area = ChatArea(config, 1920, 1080)
assert area.fits_in_video()
```