"""
Chat video generation orchestrator.

This module coordinates the entire chat overlay generation process, including
message retrieval and filtering, configuration loading, browser automation,
video composition, and file path management with database integration.
"""

import asyncio
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import ffmpeg

from vodloader.models import VideoFile, Message, ChannelConfig
from .browser_manager import BrowserManager, BrowserManagerError, browser_context
from .chat_renderer import ChatRenderer, ChatRendererError, VideoMetadataError
from .video_compositor import composite_videos, VideoCompositionError, verify_composition_requirements

logger = logging.getLogger('vodloader.chat_video.generator')


class ChatOverlayError(Exception):
    """Base exception for recoverable chat overlay errors."""
    pass


class ChatDataError(Exception):
    """Exception for corrupted or invalid chat data."""
    pass


class ChatVideoGenerator:
    """Main orchestrator for chat video generation process."""
    
    def __init__(self):
        """Initialize the generator."""
        pass
    
    async def generate(self, video: VideoFile) -> Optional[Path]:
        """
        Generate a chat overlay video by coordinating the entire process.
        
        Args:
            video: The video file to process
            
        Returns:
            Path to the generated composite video, or None if no messages found
            
        Raises:
            ChatOverlayError: For recoverable errors that should be retried
            ChatDataError: For corrupted or invalid chat data
        """
        logger.info(f'Chat video generation requested for video {video.id} at {video.path}')
        
        try:
            # Step 1: Retrieve and filter messages for video time range
            messages = await self._get_messages_for_video(video)
            if not messages:
                logger.info(f'No messages found for video {video.id}')
                return None
            
            logger.info(f'Found {len(messages)} messages for video {video.id}')
            
            # Step 2: Load configuration with default value handling
            config = await self._load_configuration(video.channel)
            
            # Step 3: Extract video metadata for frame rate matching
            video_info = await self._extract_video_metadata(video)
            
            # Step 4: Generate file paths for processing
            chat_video_path, composite_video_path = self._generate_file_paths(video)
            
            # Step 5: Generate chat overlay video using browser automation
            await self._generate_chat_overlay(messages, config, video_info, chat_video_path)
            
            # Step 6: Composite original video with chat overlay
            await self._composite_videos(video, chat_video_path, composite_video_path, config)
            
            # Step 7: Update database with composite video path
            await self._update_database_record(video, composite_video_path)
            
            # Step 8: Handle file retention based on configuration
            await self._handle_file_retention(video, chat_video_path, config)
            
            logger.info(f'Successfully generated chat overlay video for {video.id} at {composite_video_path}')
            return composite_video_path
            
        except ChatDataError:
            # Re-raise data errors without wrapping
            raise
        except ChatOverlayError:
            # Re-raise overlay errors without wrapping
            raise
        except Exception as e:
            # Wrap unexpected errors as ChatOverlayError for retry handling
            logger.error(f'Unexpected error generating chat overlay for video {video.id}: {e}')
            raise ChatOverlayError(f'Unexpected error during chat overlay generation: {e}') from e
    
    async def _get_messages_for_video(self, video: VideoFile) -> List[Message]:
        """
        Retrieve and filter messages for the video time range.
        
        Args:
            video: The video file to get messages for
            
        Returns:
            List of messages within the video time range
            
        Raises:
            ChatDataError: If message data is corrupted or invalid
        """
        try:
            messages = await Message.for_video(video)
            
            # Validate message data integrity
            valid_messages = []
            for message in messages:
                if not self._validate_message_data(message):
                    logger.warning(f'Invalid message data found for message {message.id}, skipping')
                    continue
                valid_messages.append(message)
            
            # Filter messages to video time range for additional safety
            if video.started_at and video.ended_at:
                filtered_messages = [
                    msg for msg in valid_messages
                    if video.started_at <= msg.timestamp <= video.ended_at
                ]
                
                if len(filtered_messages) != len(valid_messages):
                    logger.info(f'Filtered {len(valid_messages) - len(filtered_messages)} messages outside video time range')
                
                return filtered_messages
            
            return valid_messages
            
        except Exception as e:
            logger.error(f'Error retrieving messages for video {video.id}: {e}')
            raise ChatDataError(f'Failed to retrieve valid message data: {e}') from e
    
    def _validate_message_data(self, message: Message) -> bool:
        """
        Validate that message data is complete and valid.
        
        Args:
            message: Message to validate
            
        Returns:
            True if message data is valid, False otherwise
        """
        # Check required fields
        if not message.id or not message.display_name or not message.timestamp:
            return False
        
        # Check timestamp is reasonable (not too far in past/future)
        now = datetime.now()
        if message.timestamp < (now - timedelta(days=365)) or message.timestamp > (now + timedelta(hours=1)):
            return False
        
        # Content can be None for some message types (actions, etc.)
        return True
    
    async def _load_configuration(self, channel_id: int) -> ChannelConfig:
        """
        Load channel configuration with default value handling.
        
        Args:
            channel_id: Channel ID to load configuration for
            
        Returns:
            ChannelConfig instance with defaults applied
            
        Raises:
            ChatOverlayError: If configuration cannot be loaded
        """
        try:
            config = await ChannelConfig.get(id=channel_id)
            if not config:
                logger.warning(f'No configuration found for channel {channel_id}, using defaults')
                # Create default configuration
                config = ChannelConfig(
                    id=channel_id,
                    quality='best',
                    delete_original_video=False
                )
            
            logger.debug(f'Loaded configuration for channel {channel_id}')
            return config
            
        except Exception as e:
            logger.error(f'Error loading configuration for channel {channel_id}: {e}')
            raise ChatOverlayError(f'Failed to load channel configuration: {e}') from e
    
    async def _extract_video_metadata(self, video: VideoFile) -> Dict[str, Any]:
        """
        Extract video metadata for frame rate matching and dimensions.
        
        Args:
            video: Video file to extract metadata from
            
        Returns:
            Dictionary containing video metadata
            
        Raises:
            ChatOverlayError: If metadata extraction fails
        """
        try:
            # Use the existing probe method from VideoFile
            probe_data = video.probe()
            
            # Extract video stream information
            video_stream = None
            for stream in probe_data['streams']:
                if stream['codec_type'] == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise VideoMetadataError('No video stream found in file')
            
            # Extract frame rate
            frame_rate = None
            if 'r_frame_rate' in video_stream:
                num, den = video_stream['r_frame_rate']
                if den != 0:
                    frame_rate = num / den
            
            if not frame_rate and 'avg_frame_rate' in video_stream:
                num, den = video_stream['avg_frame_rate']
                if den != 0:
                    frame_rate = num / den
            
            if not frame_rate:
                frame_rate = 30.0  # Default fallback
                logger.warning(f'Could not determine frame rate for video {video.id}, using default {frame_rate}')
            
            # Extract dimensions
            width = video_stream.get('width', 1920)
            height = video_stream.get('height', 1080)
            
            # Extract duration
            duration = video_stream.get('duration', 0.0)
            if not duration and 'format' in probe_data:
                duration = float(probe_data['format'].get('duration', 0.0))
            
            video_info = {
                'frame_rate': frame_rate,
                'width': width,
                'height': height,
                'duration': duration,
                'codec': video_stream.get('codec_name', 'unknown')
            }
            
            logger.debug(f'Extracted video metadata for {video.id}: {video_info}')
            return video_info
            
        except Exception as e:
            logger.error(f'Error extracting video metadata for {video.id}: {e}')
            raise ChatOverlayError(f'Failed to extract video metadata: {e}') from e
    
    def _generate_file_paths(self, video: VideoFile) -> tuple[Path, Path]:
        """
        Generate file paths for chat overlay and composite videos.
        
        Args:
            video: Video file to generate paths for
            
        Returns:
            Tuple of (chat_video_path, composite_video_path)
        """
        # Generate paths in same directory as original video
        base_path = video.path.parent
        stem = video.path.stem
        
        # Chat overlay video (transparent background)
        chat_video_path = base_path / f'{stem}_chat_overlay.mp4'
        
        # Final composite video
        composite_video_path = base_path / f'{stem}_with_chat.mp4'
        
        logger.debug(f'Generated file paths for video {video.id}: chat={chat_video_path}, composite={composite_video_path}')
        return chat_video_path, composite_video_path
    
    async def _generate_chat_overlay(
        self, 
        messages: List[Message], 
        config: ChannelConfig, 
        video_info: Dict[str, Any], 
        output_path: Path
    ) -> None:
        """
        Generate chat overlay video using browser automation.
        
        Args:
            messages: List of messages to render
            config: Channel configuration
            video_info: Video metadata dictionary
            output_path: Path to save chat overlay video
            
        Raises:
            ChatOverlayError: If chat overlay generation fails
        """
        try:
            logger.info(f'Generating chat overlay video with {len(messages)} messages')
            
            # Use browser context manager for resource management
            async with browser_context() as (browser, page):
                # Create chat renderer
                renderer = ChatRenderer(messages, config, video_info)
                
                # Render chat to video file
                await renderer.render_to_video(page, output_path)
                logger.info(f'Successfully generated chat overlay video at {output_path}')
                    
        except (BrowserManagerError, ChatRendererError) as e:
            logger.error(f'Error generating chat overlay: {e}')
            raise ChatOverlayError(f'Chat overlay generation failed: {e}') from e
        except Exception as e:
            logger.error(f'Unexpected error generating chat overlay: {e}')
            raise ChatOverlayError(f'Unexpected error during chat overlay generation: {e}') from e
    
    async def _composite_videos(
        self, 
        video: VideoFile, 
        chat_video_path: Path, 
        composite_video_path: Path, 
        config: ChannelConfig
    ) -> None:
        """
        Composite original video with chat overlay.
        
        Args:
            video: Original video file
            chat_video_path: Path to chat overlay video
            composite_video_path: Path to save composite video
            config: Channel configuration
            
        Raises:
            ChatOverlayError: If video composition fails
        """
        try:
            logger.info(f'Compositing videos: original={video.path}, overlay={chat_video_path}')
            
            # Verify composition requirements before attempting
            await verify_composition_requirements(
                original_path=video.path,
                overlay_path=chat_video_path,
                output_path=composite_video_path
            )
            
            # Use video compositor to combine videos
            await composite_videos(
                original_path=video.path,
                overlay_path=chat_video_path,
                output_path=composite_video_path,
                config=config
            )
            
            logger.info(f'Successfully composited videos to {composite_video_path}')
            
        except VideoCompositionError as e:
            logger.error(f'Error compositing videos: {e}')
            raise ChatOverlayError(f'Video composition failed: {e}') from e
        except Exception as e:
            logger.error(f'Unexpected error compositing videos: {e}')
            raise ChatOverlayError(f'Unexpected error during video composition: {e}') from e
    
    async def _update_database_record(self, video: VideoFile, composite_video_path: Path) -> None:
        """
        Update database with composite video path.
        
        Args:
            video: Video file to update
            composite_video_path: Path to composite video
            
        Raises:
            ChatOverlayError: If database update fails
        """
        try:
            video.transcode_path = composite_video_path
            await video.save()
            logger.debug(f'Updated database record for video {video.id} with transcode_path={composite_video_path}')
            
        except Exception as e:
            logger.error(f'Error updating database record for video {video.id}: {e}')
            raise ChatOverlayError(f'Failed to update database record: {e}') from e
    
    async def _handle_file_retention(
        self, 
        video: VideoFile, 
        chat_video_path: Path, 
        config: ChannelConfig
    ) -> None:
        """
        Handle file retention based on configuration settings.
        
        Args:
            video: Original video file
            chat_video_path: Path to chat overlay video
            config: Channel configuration
            
        Note:
            This method handles cleanup but does not raise exceptions
            to avoid failing the entire process due to cleanup issues.
        """
        try:
            # Handle chat overlay file retention
            if not config.get_keep_chat_overlay():
                if chat_video_path.exists():
                    chat_video_path.unlink()
                    logger.info(f'Removed chat overlay file {chat_video_path} per configuration')
            
            # Handle original video file retention
            if config.delete_original_video:
                if video.path.exists():
                    video.path.unlink()
                    logger.info(f'Removed original video file {video.path} per configuration')
                    
                    # Update database to reflect file removal
                    video.path = None
                    await video.save()
                    logger.debug(f'Updated database to reflect original file removal for video {video.id}')
            
        except Exception as e:
            # Log error but don't raise - file retention issues shouldn't fail the entire process
            logger.error(f'Error handling file retention for video {video.id}: {e}')


async def generate_chat_video(video: VideoFile, **kwargs) -> Optional[Path]:
    """
    Generate a chat overlay video (main entry point).
    
    This function coordinates the entire chat overlay generation process,
    including message retrieval, configuration loading, browser automation,
    video composition, and database integration.
    
    Args:
        video: The video file to process
        **kwargs: Additional configuration options (currently unused)
        
    Returns:
        Path to the generated composite video, or None if no messages found
        
    Raises:
        ChatOverlayError: For recoverable errors that should be retried
        ChatDataError: For corrupted or invalid chat data
    """
    generator = ChatVideoGenerator()
    return await generator.generate(video)