"""
Validation functions for API request data.
"""

from .constants import VALID_QUALITIES, STATUS_ERROR, HTTP_BAD_REQUEST

# Valid chat position options
VALID_CHAT_POSITIONS = [
    'top-left', 'top-right', 'bottom-left', 'bottom-right', 'left', 'right'
]

# Valid font styles
VALID_FONT_STYLES = ['normal', 'italic', 'oblique']

# Valid font weights
VALID_FONT_WEIGHTS = ['normal', 'bold', '100', '200', '300', '400', '500', '600', '700', '800', '900']


def validate_quality(quality):
    """Validate quality parameter"""
    if quality not in VALID_QUALITIES:
        return {
            "status": STATUS_ERROR, 
            "message": f"Invalid quality. Must be one of: {', '.join(VALID_QUALITIES)}"
        }, HTTP_BAD_REQUEST
    return None, None


def validate_delete_original_video(value):
    """Validate delete_original_video parameter"""
    if not isinstance(value, bool):
        return {
            "status": STATUS_ERROR, 
            "message": "delete_original_video must be a boolean"
        }, HTTP_BAD_REQUEST
    return None, None


def validate_channel_config(data):
    """Validate channel configuration data"""
    errors = []
    
    if 'quality' in data:
        error_response, status_code = validate_quality(data['quality'])
        if error_response:
            return error_response, status_code
    
    if 'delete_original_video' in data:
        error_response, status_code = validate_delete_original_video(data['delete_original_video'])
        if error_response:
            return error_response, status_code
    
    return None, None


def validate_chat_font_family(font_family):
    """Validate chat font family parameter"""
    if not isinstance(font_family, str):
        return {
            "status": STATUS_ERROR,
            "message": "font_family must be a string"
        }, HTTP_BAD_REQUEST
    
    if len(font_family.strip()) == 0:
        return {
            "status": STATUS_ERROR,
            "message": "font_family cannot be empty"
        }, HTTP_BAD_REQUEST
    
    if len(font_family) > 100:
        return {
            "status": STATUS_ERROR,
            "message": "font_family cannot exceed 100 characters"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_font_size(font_size):
    """Validate chat font size parameter"""
    if not isinstance(font_size, int):
        return {
            "status": STATUS_ERROR,
            "message": "font_size must be an integer"
        }, HTTP_BAD_REQUEST
    
    if font_size < 8 or font_size > 72:
        return {
            "status": STATUS_ERROR,
            "message": "font_size must be between 8 and 72"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_font_style(font_style):
    """Validate chat font style parameter"""
    if font_style not in VALID_FONT_STYLES:
        return {
            "status": STATUS_ERROR,
            "message": f"Invalid font_style. Must be one of: {', '.join(VALID_FONT_STYLES)}"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_font_weight(font_weight):
    """Validate chat font weight parameter"""
    if font_weight not in VALID_FONT_WEIGHTS:
        return {
            "status": STATUS_ERROR,
            "message": f"Invalid font_weight. Must be one of: {', '.join(VALID_FONT_WEIGHTS)}"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_color(color, field_name):
    """Validate chat color parameter (hex color format)"""
    if not isinstance(color, str):
        return {
            "status": STATUS_ERROR,
            "message": f"{field_name} must be a string"
        }, HTTP_BAD_REQUEST
    
    if not color.startswith('#') or len(color) != 7:
        return {
            "status": STATUS_ERROR,
            "message": f"{field_name} must be a valid hex color (e.g., #ffffff)"
        }, HTTP_BAD_REQUEST
    
    try:
        int(color[1:], 16)
    except ValueError:
        return {
            "status": STATUS_ERROR,
            "message": f"{field_name} must be a valid hex color (e.g., #ffffff)"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_text_shadow_size(shadow_size):
    """Validate chat text shadow size parameter"""
    if not isinstance(shadow_size, int):
        return {
            "status": STATUS_ERROR,
            "message": "text_shadow_size must be an integer"
        }, HTTP_BAD_REQUEST
    
    if shadow_size < 0 or shadow_size > 10:
        return {
            "status": STATUS_ERROR,
            "message": "text_shadow_size must be between 0 and 10"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_overlay_dimension(dimension, field_name):
    """Validate chat overlay width or height parameter"""
    if not isinstance(dimension, int):
        return {
            "status": STATUS_ERROR,
            "message": f"{field_name} must be an integer"
        }, HTTP_BAD_REQUEST
    
    if dimension < 100 or dimension > 3840:
        return {
            "status": STATUS_ERROR,
            "message": f"{field_name} must be between 100 and 3840"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_position(position):
    """Validate chat position parameter"""
    if position not in VALID_CHAT_POSITIONS:
        return {
            "status": STATUS_ERROR,
            "message": f"Invalid position. Must be one of: {', '.join(VALID_CHAT_POSITIONS)}"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_padding(padding):
    """Validate chat padding parameter"""
    if not isinstance(padding, int):
        return {
            "status": STATUS_ERROR,
            "message": "padding must be an integer"
        }, HTTP_BAD_REQUEST
    
    if padding < 0 or padding > 200:
        return {
            "status": STATUS_ERROR,
            "message": "padding must be between 0 and 200"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_message_duration(duration):
    """Validate chat message duration parameter"""
    if not isinstance(duration, (int, float)):
        return {
            "status": STATUS_ERROR,
            "message": "message_duration must be a number"
        }, HTTP_BAD_REQUEST
    
    if duration < 5.0 or duration > 300.0:
        return {
            "status": STATUS_ERROR,
            "message": "message_duration must be between 5.0 and 300.0 seconds"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_keep_chat_overlay(value):
    """Validate keep_chat_overlay parameter"""
    if not isinstance(value, bool):
        return {
            "status": STATUS_ERROR,
            "message": "keep_chat_overlay must be a boolean"
        }, HTTP_BAD_REQUEST
    
    return None, None


def validate_chat_config(data):
    """Validate chat configuration data"""
    validation_map = {
        'font_family': validate_chat_font_family,
        'font_size': validate_chat_font_size,
        'font_style': validate_chat_font_style,
        'font_weight': validate_chat_font_weight,
        'text_color': lambda x: validate_chat_color(x, 'text_color'),
        'text_shadow_color': lambda x: validate_chat_color(x, 'text_shadow_color'),
        'text_shadow_size': validate_chat_text_shadow_size,
        'overlay_width': lambda x: validate_chat_overlay_dimension(x, 'overlay_width'),
        'overlay_height': lambda x: validate_chat_overlay_dimension(x, 'overlay_height'),
        'position': validate_chat_position,
        'padding': validate_chat_padding,
        'message_duration': validate_chat_message_duration,
        'keep_chat_overlay': validate_keep_chat_overlay
    }
    
    for field, value in data.items():
        if field in validation_map:
            error_response, status_code = validation_map[field](value)
            if error_response:
                return error_response, status_code
        else:
            return {
                "status": STATUS_ERROR,
                "message": f"Unknown configuration field: {field}"
            }, HTTP_BAD_REQUEST
    
    return None, None