"""
Chat video generation orchestrator.

This module coordinates the entire chat overlay generation process, including
message retrieval and filtering, configuration loading, browser automation,
video composition, and file path management with database integration.
"""

import asyncio
import logging
import tempfile
import psutil
import time
import traceback
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
    """Base exception for recoverable chat overlay errors that should be retried."""
    
    def __init__(self, message: str, video_id: Optional[int] = None, original_error: Optional[Exception] = None):
        """
        Initialize ChatOverlayError with context information.
        
        Args:
            message: Error description
            video_id: ID of the video being processed (if available)
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.video_id = video_id
        self.original_error = original_error
        self.timestamp = datetime.now()


class ChatDataError(Exception):
    """Exception for corrupted or invalid chat data that should not be retried."""
    
    def __init__(self, message: str, video_id: Optional[int] = None, data_context: Optional[Dict] = None):
        """
        Initialize ChatDataError with context information.
        
        Args:
            message: Error description
            video_id: ID of the video being processed (if available)
            data_context: Additional context about the corrupted data
        """
        super().__init__(message)
        self.video_id = video_id
        self.data_context = data_context or {}
        self.timestamp = datetime.now()


class ChatVideoGenerator:
    """Main orchestrator for chat video generation process."""
    
    def __init__(self):
        """Initialize the generator."""
        self._start_time: Optional[float] = None
        self._video_id: Optional[int] = None
        self._temp_files: List[Path] = []
        self._browser_process_id: Optional[int] = None
    
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
        self._start_time = time.time()
        self._video_id = video.id
        
        # Log process start with system information
        system_info = self._get_system_info()
        logger.info(
            f'Starting chat overlay generation for video {video.id} '
            f'(path: {video.path}, memory: {system_info["memory_mb"]:.1f}MB available)'
        )
        
        try:
            # Step 1: Retrieve and filter messages for video time range
            logger.info(f'Step 1/8: Retrieving messages for video {video.id}')
            messages = await self._get_messages_for_video(video)
            if not messages:
                logger.info(f'No messages found for video {video.id} - skipping chat overlay generation')
                return None
            
            logger.info(f'Found {len(messages)} messages for video {video.id}')
            
            # Step 2: Load configuration with default value handling
            logger.info(f'Step 2/8: Loading configuration for channel {video.channel}')
            config = await self._load_configuration(video.channel)
            
            # Step 3: Extract video metadata for frame rate matching
            logger.info(f'Step 3/8: Extracting video metadata from {video.path}')
            video_info = await self._extract_video_metadata(video)
            logger.info(
                f'Video metadata: {video_info["width"]}x{video_info["height"]} '
                f'@ {video_info["frame_rate"]}fps, duration: {video_info["duration"]:.1f}s'
            )
            
            # Step 4: Generate file paths for processing
            logger.info(f'Step 4/8: Generating output file paths')
            chat_video_path, composite_video_path = self._generate_file_paths(video)
            
            # Step 5: Generate chat overlay video using browser automation
            logger.info(f'Step 5/8: Generating chat overlay video at {chat_video_path}')
            await self._generate_chat_overlay(messages, config, video_info, chat_video_path)
            
            # Step 6: Composite original video with chat overlay
            logger.info(f'Step 6/8: Compositing videos to create {composite_video_path}')
            await self._composite_videos(video, chat_video_path, composite_video_path, config)
            
            # Step 7: Update database with composite video path
            logger.info(f'Step 7/8: Updating database record for video {video.id}')
            await self._update_database_record(video, composite_video_path)
            
            # Step 8: Handle file retention based on configuration
            logger.info(f'Step 8/8: Handling file retention for video {video.id}')
            await self._handle_file_retention(video, chat_video_path, config)
            
            # Log successful completion with timing and file size information
            elapsed_time = time.time() - self._start_time
            output_size_mb = composite_video_path.stat().st_size / (1024 * 1024)
            logger.info(
                f'Successfully completed chat overlay generation for video {video.id} '
                f'in {elapsed_time:.1f}s (output: {output_size_mb:.1f}MB at {composite_video_path})'
            )
            return composite_video_path
            
        except ChatDataError as e:
            # Log data errors with context and re-raise without wrapping
            self._log_error(f'Chat data error for video {video.id}', e, include_context=True)
            raise
        except ChatOverlayError as e:
            # Log overlay errors with context and re-raise without wrapping
            self._log_error(f'Chat overlay error for video {video.id}', e, include_context=True)
            raise
        except Exception as e:
            # Log unexpected errors with full context and wrap as ChatOverlayError
            self._log_error(f'Unexpected error generating chat overlay for video {video.id}', e, include_context=True)
            raise ChatOverlayError(
                f'Unexpected error during chat overlay generation: {e}',
                video_id=video.id,
                original_error=e
            ) from e
        finally:
            # Always perform cleanup regardless of success or failure
            await self._cleanup_resources()
    
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
            logger.debug(f'Retrieving messages for video {video.id} (started: {video.started_at}, ended: {video.ended_at})')
            messages = await Message.for_video(video)
            
            if not messages:
                logger.info(f'No messages found in database for video {video.id}')
                return []
            
            logger.debug(f'Retrieved {len(messages)} raw messages from database for video {video.id}')
            
            # Validate message data integrity
            valid_messages = []
            invalid_count = 0
            
            for message in messages:
                if not self._validate_message_data(message):
                    invalid_count += 1
                    logger.debug(f'Invalid message data for message {message.id}: missing required fields')
                    continue
                valid_messages.append(message)
            
            if invalid_count > 0:
                logger.warning(f'Found {invalid_count} invalid messages out of {len(messages)} total for video {video.id}')
            
            # Filter messages to video time range for additional safety
            if video.started_at and video.ended_at:
                filtered_messages = [
                    msg for msg in valid_messages
                    if video.started_at <= msg.timestamp <= video.ended_at
                ]
                
                out_of_range_count = len(valid_messages) - len(filtered_messages)
                if out_of_range_count > 0:
                    logger.info(f'Filtered {out_of_range_count} messages outside video time range for video {video.id}')
                
                logger.debug(f'Final message count for video {video.id}: {len(filtered_messages)}')
                return filtered_messages
            else:
                logger.warning(f'Video {video.id} missing start/end timestamps, using all valid messages')
                return valid_messages
            
        except Exception as e:
            error_context = {
                'video_id': video.id,
                'video_path': str(video.path) if video.path else None,
                'started_at': video.started_at.isoformat() if video.started_at else None,
                'ended_at': video.ended_at.isoformat() if video.ended_at else None
            }
            
            logger.error(f'Error retrieving messages for video {video.id}: {e}')
            raise ChatDataError(
                f'Failed to retrieve valid message data: {e}',
                video_id=video.id,
                data_context=error_context
            ) from e
    
    def _validate_message_data(self, message: Message) -> bool:
        """
        Validate that message data is complete and valid.
        
        Args:
            message: Message to validate
            
        Returns:
            True if message data is valid, False otherwise
        """
        # Check required fields
        if not message.id:
            logger.debug(f'Message validation failed: missing ID')
            return False
            
        if not message.display_name:
            logger.debug(f'Message {message.id} validation failed: missing display_name')
            return False
            
        if not message.timestamp:
            logger.debug(f'Message {message.id} validation failed: missing timestamp')
            return False
        
        # Check timestamp is reasonable (not too far in past/future)
        now = datetime.now()
        min_timestamp = now - timedelta(days=365)
        max_timestamp = now + timedelta(hours=1)
        
        if message.timestamp < min_timestamp:
            logger.debug(f'Message {message.id} validation failed: timestamp too old ({message.timestamp})')
            return False
            
        if message.timestamp > max_timestamp:
            logger.debug(f'Message {message.id} validation failed: timestamp in future ({message.timestamp})')
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
            logger.debug(f'Loading configuration for channel {channel_id}')
            config = await ChannelConfig.get(id=channel_id)
            
            if not config:
                logger.warning(f'No configuration found for channel {channel_id}, creating default configuration')
                # Create default configuration
                config = ChannelConfig(
                    id=channel_id,
                    quality='best',
                    delete_original_video=False
                )
                logger.info(f'Created default configuration for channel {channel_id}')
            else:
                logger.debug(f'Successfully loaded existing configuration for channel {channel_id}')
            
            # Log key configuration values for debugging
            logger.debug(
                f'Configuration for channel {channel_id}: '
                f'position={config.get_chat_position()}, '
                f'font_size={config.get_chat_font_size()}, '
                f'keep_overlay={config.get_keep_chat_overlay()}'
            )
            
            return config
            
        except Exception as e:
            logger.error(f'Error loading configuration for channel {channel_id}: {e}')
            raise ChatOverlayError(
                f'Failed to load channel configuration: {e}',
                video_id=self._video_id,
                original_error=e
            ) from e
    
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
            logger.debug(f'Extracting metadata from video file: {video.path}')
            
            # Check if file exists before probing
            if not video.path or not video.path.exists():
                raise ChatOverlayError(
                    f'Video file does not exist: {video.path}',
                    video_id=video.id
                )
            
            # Check file size
            file_size_mb = video.path.stat().st_size / (1024 * 1024)
            logger.debug(f'Video file size: {file_size_mb:.1f}MB')
            
            # Use the existing probe method from VideoFile
            probe_data = video.probe()
            
            if not probe_data or 'streams' not in probe_data:
                raise VideoMetadataError(f'Invalid probe data for video {video.id}')
            
            # Extract video stream information
            video_stream = None
            for stream in probe_data['streams']:
                if stream['codec_type'] == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise VideoMetadataError(f'No video stream found in file {video.path}')
            
            logger.debug(f'Found video stream with codec: {video_stream.get("codec_name", "unknown")}')
            
            # Extract frame rate with detailed logging
            frame_rate = None
            if 'r_frame_rate' in video_stream and video_stream['r_frame_rate']:
                try:
                    r_frame_rate = video_stream['r_frame_rate']
                    if isinstance(r_frame_rate, str) and '/' in r_frame_rate:
                        num, den = map(int, r_frame_rate.split('/'))
                        if den != 0:
                            frame_rate = num / den
                            logger.debug(f'Extracted frame rate from r_frame_rate: {frame_rate}')
                except (ValueError, ZeroDivisionError) as e:
                    logger.debug(f'Could not parse r_frame_rate "{video_stream["r_frame_rate"]}": {e}')
            
            if not frame_rate and 'avg_frame_rate' in video_stream and video_stream['avg_frame_rate']:
                try:
                    avg_frame_rate = video_stream['avg_frame_rate']
                    if isinstance(avg_frame_rate, str) and '/' in avg_frame_rate:
                        num, den = map(int, avg_frame_rate.split('/'))
                        if den != 0:
                            frame_rate = num / den
                            logger.debug(f'Extracted frame rate from avg_frame_rate: {frame_rate}')
                except (ValueError, ZeroDivisionError) as e:
                    logger.debug(f'Could not parse avg_frame_rate "{video_stream["avg_frame_rate"]}": {e}')
            
            if not frame_rate or frame_rate <= 0:
                frame_rate = 30.0  # Default fallback
                logger.warning(f'Could not determine valid frame rate for video {video.id}, using default {frame_rate}fps')
            
            # Extract dimensions
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)
            
            if width <= 0 or height <= 0:
                logger.warning(f'Invalid dimensions for video {video.id}: {width}x{height}, using defaults')
                width = width if width > 0 else 1920
                height = height if height > 0 else 1080
            
            # Extract duration
            duration = 0.0
            if 'duration' in video_stream and video_stream['duration']:
                try:
                    duration = float(video_stream['duration'])
                except (ValueError, TypeError):
                    logger.debug(f'Could not parse stream duration: {video_stream["duration"]}')
            
            if duration <= 0 and 'format' in probe_data and 'duration' in probe_data['format']:
                try:
                    duration = float(probe_data['format']['duration'])
                    logger.debug(f'Extracted duration from format info: {duration}s')
                except (ValueError, TypeError):
                    logger.debug(f'Could not parse format duration: {probe_data["format"]["duration"]}')
            
            if duration <= 0:
                logger.warning(f'Could not determine duration for video {video.id}')
            
            video_info = {
                'frame_rate': frame_rate,
                'width': width,
                'height': height,
                'duration': duration,
                'codec': video_stream.get('codec_name', 'unknown'),
                'pixel_format': video_stream.get('pix_fmt', 'unknown'),
                'file_size_mb': file_size_mb
            }
            
            logger.info(
                f'Extracted video metadata for {video.id}: '
                f'{width}x{height} @ {frame_rate}fps, '
                f'duration: {duration:.1f}s, codec: {video_info["codec"]}'
            )
            return video_info
            
        except VideoMetadataError:
            # Re-raise metadata errors as-is
            raise
        except Exception as e:
            logger.error(f'Error extracting video metadata for {video.id}: {e}')
            raise ChatOverlayError(
                f'Failed to extract video metadata: {e}',
                video_id=video.id,
                original_error=e
            ) from e
    
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
            # Register output path as temporary file for cleanup
            self._add_temp_file(output_path)
            
            # Log overlay generation start with parameters
            overlay_width = config.get_chat_overlay_width() or int(video_info['width'] * 0.2)
            overlay_height = config.get_chat_overlay_height() or int(video_info['height'] * 0.4)
            
            logger.info(
                f'Starting chat overlay generation: {len(messages)} messages, '
                f'{overlay_width}x{overlay_height} overlay, '
                f'{video_info["frame_rate"]}fps, {video_info["duration"]:.1f}s duration'
            )
            
            # Monitor memory before starting browser
            await self._monitor_memory_usage()
            
            # Use browser context manager for resource management
            browser_config = {
                'overlay_width': overlay_width,
                'overlay_height': overlay_height
            }
            
            async with browser_context(browser_config) as (browser, page):
                # Store browser process info for monitoring
                try:
                    # Attempt to get browser process ID for monitoring
                    if hasattr(browser, '_connection') and hasattr(browser._connection, '_transport'):
                        # This is browser-specific and may not always work
                        pass
                except Exception:
                    logger.debug('Could not retrieve browser process ID for monitoring')
                
                # Monitor memory during browser operations
                await self._monitor_memory_usage()
                
                # Create chat renderer
                logger.debug('Creating ChatRenderer instance')
                renderer = ChatRenderer(messages, config, video_info)
                
                # Monitor memory before video rendering
                await self._monitor_memory_usage()
                
                # Render chat to video file with progress monitoring
                logger.info(f'Starting video rendering to {output_path}')
                render_start_time = time.time()
                
                await renderer.render_to_video(page, output_path)
                
                render_duration = time.time() - render_start_time
                
                # Verify output file was created and has reasonable size
                if not output_path.exists():
                    raise ChatOverlayError(
                        f'Chat overlay video was not created at {output_path}',
                        video_id=self._video_id
                    )
                
                output_size_mb = output_path.stat().st_size / (1024 * 1024)
                if output_size_mb < 0.1:  # Less than 100KB is suspicious
                    logger.warning(f'Chat overlay video is very small: {output_size_mb:.2f}MB')
                
                logger.info(
                    f'Successfully generated chat overlay video at {output_path} '
                    f'({output_size_mb:.1f}MB) in {render_duration:.1f}s'
                )
                
                # Remove from temp files since it was successful
                if output_path in self._temp_files:
                    self._temp_files.remove(output_path)
                    
        except (BrowserManagerError, ChatRendererError) as e:
            logger.error(f'Error generating chat overlay for video {self._video_id}: {e}')
            raise ChatOverlayError(
                f'Chat overlay generation failed: {e}',
                video_id=self._video_id,
                original_error=e
            ) from e
        except Exception as e:
            logger.error(f'Unexpected error generating chat overlay for video {self._video_id}: {e}')
            raise ChatOverlayError(
                f'Unexpected error during chat overlay generation: {e}',
                video_id=self._video_id,
                original_error=e
            ) from e
    
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
            # Register composite video as temp file for cleanup on failure
            self._add_temp_file(composite_video_path)
            
            # Log composition start with file sizes
            original_size_mb = video.path.stat().st_size / (1024 * 1024)
            overlay_size_mb = chat_video_path.stat().st_size / (1024 * 1024)
            
            logger.info(
                f'Starting video composition: '
                f'original={video.path} ({original_size_mb:.1f}MB), '
                f'overlay={chat_video_path} ({overlay_size_mb:.1f}MB)'
            )
            
            # Monitor memory before composition
            await self._monitor_memory_usage()
            
            # Verify composition requirements before attempting
            logger.debug('Verifying composition requirements')
            await verify_composition_requirements(
                original_path=video.path,
                overlay_path=chat_video_path,
                output_path=composite_video_path
            )
            
            # Log composition parameters
            position = config.get_chat_position()
            padding = config.get_chat_padding()
            logger.debug(f'Composition settings: position={position}, padding={padding}px')
            
            # Use video compositor to combine videos
            composition_start_time = time.time()
            
            await composite_videos(
                original_path=video.path,
                overlay_path=chat_video_path,
                output_path=composite_video_path,
                config=config
            )
            
            composition_duration = time.time() - composition_start_time
            
            # Verify output and log results
            if not composite_video_path.exists():
                raise ChatOverlayError(
                    f'Composite video was not created at {composite_video_path}',
                    video_id=self._video_id
                )
            
            composite_size_mb = composite_video_path.stat().st_size / (1024 * 1024)
            
            # Sanity check: composite should be at least as large as original
            if composite_size_mb < original_size_mb * 0.8:
                logger.warning(
                    f'Composite video ({composite_size_mb:.1f}MB) is significantly smaller '
                    f'than original ({original_size_mb:.1f}MB)'
                )
            
            logger.info(
                f'Successfully composited videos to {composite_video_path} '
                f'({composite_size_mb:.1f}MB) in {composition_duration:.1f}s'
            )
            
            # Remove from temp files since composition was successful
            if composite_video_path in self._temp_files:
                self._temp_files.remove(composite_video_path)
            
        except VideoCompositionError as e:
            logger.error(f'Error compositing videos for video {self._video_id}: {e}')
            raise ChatOverlayError(
                f'Video composition failed: {e}',
                video_id=self._video_id,
                original_error=e
            ) from e
        except Exception as e:
            logger.error(f'Unexpected error compositing videos for video {self._video_id}: {e}')
            raise ChatOverlayError(
                f'Unexpected error during video composition: {e}',
                video_id=self._video_id,
                original_error=e
            ) from e
    
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
            logger.debug(f'Updating database record for video {video.id} with transcode_path={composite_video_path}')
            
            # Store original transcode_path in case we need to rollback
            original_transcode_path = video.transcode_path
            
            # Update the video record
            video.transcode_path = composite_video_path
            await video.save()
            
            logger.info(f'Successfully updated database record for video {video.id}')
            
            # Log the change for audit purposes
            logger.debug(
                f'Database update for video {video.id}: '
                f'transcode_path changed from {original_transcode_path} to {composite_video_path}'
            )
            
        except Exception as e:
            logger.error(f'Error updating database record for video {video.id}: {e}')
            
            # Attempt to restore original state if possible
            try:
                if 'original_transcode_path' in locals():
                    video.transcode_path = original_transcode_path
                    logger.debug(f'Restored original transcode_path for video {video.id}')
            except Exception as restore_error:
                logger.error(f'Failed to restore original database state for video {video.id}: {restore_error}')
            
            raise ChatOverlayError(
                f'Failed to update database record: {e}',
                video_id=video.id,
                original_error=e
            ) from e
    
    async def _handle_file_retention(
        self, 
        video: VideoFile, 
        chat_video_path: Path, 
        config: ChannelConfig
    ) -> None:
        """
        Handle file retention based on configuration settings.
        
        This method implements file cleanup logic based on ChannelConfig retention settings:
        - Removes chat overlay file if keep_chat_overlay is False
        - Removes original video file if delete_original_video is True
        - Updates database when original file is removed
        
        Args:
            video: Original video file
            chat_video_path: Path to chat overlay video
            config: Channel configuration
            
        Note:
            This method handles cleanup but does not raise exceptions
            to avoid failing the entire process due to cleanup issues.
        """
        retention_actions = []
        
        try:
            # Log retention configuration
            keep_overlay = config.get_keep_chat_overlay()
            delete_original = config.delete_original_video
            
            logger.info(
                f'File retention for video {video.id}: '
                f'keep_overlay={keep_overlay}, delete_original={delete_original}'
            )
            
            # Handle chat overlay file retention
            if not keep_overlay:
                if chat_video_path.exists():
                    try:
                        overlay_size_mb = chat_video_path.stat().st_size / (1024 * 1024)
                        chat_video_path.unlink()
                        retention_actions.append(f'Removed chat overlay file ({overlay_size_mb:.1f}MB)')
                        logger.info(f'Removed chat overlay file {chat_video_path} per configuration')
                    except Exception as e:
                        logger.error(f'Failed to remove chat overlay file {chat_video_path}: {e}')
                else:
                    logger.debug(f'Chat overlay file {chat_video_path} does not exist, skipping removal')
            else:
                logger.debug(f'Keeping chat overlay file {chat_video_path} per configuration')
            
            # Handle original video file retention
            if delete_original:
                if video.path and video.path.exists():
                    try:
                        original_size_mb = video.path.stat().st_size / (1024 * 1024)
                        original_path = video.path  # Store for logging
                        
                        # Remove the file
                        video.path.unlink()
                        retention_actions.append(f'Removed original video file ({original_size_mb:.1f}MB)')
                        logger.info(f'Removed original video file {original_path} per configuration')
                        
                        # Update database to reflect file removal
                        await self._update_original_file_path(video, None)
                        logger.debug(f'Updated database to reflect original file removal for video {video.id}')
                        
                    except Exception as e:
                        logger.error(f'Failed to remove original video file {video.path}: {e}')
                else:
                    logger.debug(f'Original video file does not exist or path is None, skipping removal')
            else:
                logger.debug(f'Keeping original video file {video.path} per configuration')
            
            # Log summary of retention actions
            if retention_actions:
                logger.info(f'File retention completed for video {video.id}: {"; ".join(retention_actions)}')
            else:
                logger.debug(f'No file retention actions needed for video {video.id}')
            
        except Exception as e:
            # Log error with context but don't raise - file retention issues shouldn't fail the entire process
            logger.error(
                f'Error handling file retention for video {video.id}: {e} '
                f'(keep_overlay={config.get_keep_chat_overlay()}, '
                f'delete_original={config.delete_original_video})'
            )
            
            # Log what actions were attempted
            if retention_actions:
                logger.info(f'Partial retention actions completed: {"; ".join(retention_actions)}')
            
            # Don't raise the exception to avoid failing the entire process
    
    async def _update_original_file_path(self, video: VideoFile, new_path: Optional[Path]) -> None:
        """
        Update the original file path in the database.
        
        This method directly updates the database to set the path field to NULL
        when the original file is removed, avoiding issues with the model's save method.
        
        Args:
            video: Video file to update
            new_path: New path value (None to set to NULL in database)
            
        Raises:
            Exception: If database update fails
        """
        from vodloader.database import get_db
        
        try:
            db = await get_db()
            connection = await db.connect()
            cursor = await connection.cursor()
            
            # Update the path field directly in the database
            path_value = str(new_path) if new_path else None
            
            await cursor.execute(
                f"UPDATE {video.table_name} SET path = {db.char} WHERE id = {db.char}",
                [path_value, video.id]
            )
            
            await connection.commit()
            await cursor.close()
            closer = connection.close()
            if closer:
                await closer
            
            # Update the model instance to reflect the change
            video.path = new_path
            
            logger.debug(f'Successfully updated path in database for video {video.id}: {path_value}')
            
        except Exception as e:
            logger.error(f'Failed to update original file path in database for video {video.id}: {e}')
            raise
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        Get current system resource information.
        
        Returns:
            Dictionary containing system resource information
        """
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            return {
                'memory_mb': memory.available / (1024 * 1024),
                'memory_percent': memory.percent,
                'cpu_percent': cpu_percent,
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.warning(f'Could not retrieve system information: {e}')
            return {
                'memory_mb': 0,
                'memory_percent': 0,
                'cpu_percent': 0,
                'timestamp': datetime.now()
            }
    
    def _log_error(self, message: str, error: Exception, include_context: bool = False) -> None:
        """
        Log error with comprehensive context information.
        
        Args:
            message: Base error message
            error: Exception that occurred
            include_context: Whether to include system and processing context
        """
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'video_id': self._video_id,
        }
        
        if self._start_time:
            error_info['elapsed_time'] = time.time() - self._start_time
        
        if include_context:
            error_info['system_info'] = self._get_system_info()
            error_info['stack_trace'] = traceback.format_exc()
            
            if self._browser_process_id:
                error_info['browser_process_id'] = self._browser_process_id
            
            if self._temp_files:
                error_info['temp_files'] = [str(f) for f in self._temp_files]
        
        # Log the error with structured information
        logger.error(f'{message}: {error_info}')
        
        # Also log stack trace separately for readability
        if include_context:
            logger.debug(f'Stack trace for video {self._video_id}:\n{traceback.format_exc()}')
    
    async def _monitor_memory_usage(self) -> None:
        """
        Monitor memory usage and terminate if limits are exceeded.
        
        Raises:
            ChatOverlayError: If memory usage exceeds safe limits
        """
        try:
            current_process = psutil.Process()
            memory_info = current_process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            # Memory limit: 2GB per process
            memory_limit_mb = 2048
            
            if memory_mb > memory_limit_mb:
                error_msg = (
                    f'Memory usage ({memory_mb:.1f}MB) exceeds limit ({memory_limit_mb}MB) '
                    f'for video {self._video_id}'
                )
                logger.error(error_msg)
                
                # Attempt to clean up resources before raising
                await self._cleanup_resources()
                
                raise ChatOverlayError(
                    f'Memory limit exceeded: {memory_mb:.1f}MB > {memory_limit_mb}MB',
                    video_id=self._video_id
                )
            
            # Log memory usage periodically for monitoring
            if hasattr(self, '_last_memory_log'):
                time_since_last_log = time.time() - self._last_memory_log
                if time_since_last_log > 30:  # Log every 30 seconds
                    logger.debug(f'Memory usage for video {self._video_id}: {memory_mb:.1f}MB')
                    self._last_memory_log = time.time()
            else:
                self._last_memory_log = time.time()
                
        except psutil.NoSuchProcess:
            logger.warning(f'Process no longer exists during memory monitoring for video {self._video_id}')
        except Exception as e:
            logger.warning(f'Could not monitor memory usage for video {self._video_id}: {e}')
    
    async def _cleanup_resources(self) -> None:
        """
        Clean up temporary files and browser processes.
        
        This method is designed to be safe to call multiple times and
        will not raise exceptions that could mask the original error.
        """
        cleanup_errors = []
        
        # Clean up temporary files
        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f'Cleaned up temporary file: {temp_file}')
            except Exception as e:
                cleanup_errors.append(f'Failed to remove temp file {temp_file}: {e}')
        
        # Clear the temp files list
        self._temp_files.clear()
        
        # Attempt to terminate browser processes if we have a process ID
        if self._browser_process_id:
            try:
                browser_process = psutil.Process(self._browser_process_id)
                if browser_process.is_running():
                    # Try graceful termination first
                    browser_process.terminate()
                    
                    # Wait up to 5 seconds for graceful shutdown
                    try:
                        browser_process.wait(timeout=5)
                        logger.debug(f'Browser process {self._browser_process_id} terminated gracefully')
                    except psutil.TimeoutExpired:
                        # Force kill if graceful termination fails
                        browser_process.kill()
                        logger.warning(f'Browser process {self._browser_process_id} force killed')
                        
            except psutil.NoSuchProcess:
                logger.debug(f'Browser process {self._browser_process_id} already terminated')
            except Exception as e:
                cleanup_errors.append(f'Failed to terminate browser process {self._browser_process_id}: {e}')
        
        # Log any cleanup errors (but don't raise them)
        if cleanup_errors:
            logger.warning(f'Cleanup errors for video {self._video_id}: {cleanup_errors}')
        else:
            logger.debug(f'Resource cleanup completed for video {self._video_id}')
    
    def _add_temp_file(self, file_path: Path) -> None:
        """
        Register a temporary file for cleanup.
        
        Args:
            file_path: Path to temporary file that should be cleaned up
        """
        if file_path not in self._temp_files:
            self._temp_files.append(file_path)
            logger.debug(f'Registered temporary file for cleanup: {file_path}')


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
    # Log the entry point with system context
    logger.info(f'Chat video generation requested for video {video.id} (entry point)')
    
    generator = ChatVideoGenerator()
    
    try:
        result = await generator.generate(video)
        
        if result is None:
            logger.info(f'Chat video generation completed with no output for video {video.id} (no messages)')
        else:
            logger.info(f'Chat video generation completed successfully for video {video.id}: {result}')
        
        return result
        
    except (ChatOverlayError, ChatDataError) as e:
        # These are expected error types that should be handled by the caller
        logger.error(f'Chat video generation failed for video {video.id}: {type(e).__name__}: {e}')
        raise
    except Exception as e:
        # Unexpected errors should be wrapped and logged with full context
        logger.error(
            f'Unexpected error in chat video generation entry point for video {video.id}: '
            f'{type(e).__name__}: {e}'
        )
        logger.debug(f'Stack trace for video {video.id}:\n{traceback.format_exc()}')
        
        # Wrap as ChatOverlayError for consistent error handling
        raise ChatOverlayError(
            f'Unexpected error in chat video generation: {e}',
            video_id=video.id,
            original_error=e
        ) from e