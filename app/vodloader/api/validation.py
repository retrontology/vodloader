"""
Validation functions for API request data.
"""

from .constants import VALID_QUALITIES, STATUS_ERROR, HTTP_BAD_REQUEST


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