"""
Main chat video generation orchestrator.
"""

import cv2
import ffmpeg
import numpy as np
import asyncio
import concurrent.futures
import logging
import subprocess
from pathlib import Path
from datetime import timedelta, timezone
from typing import List, Optional

from vodloader.models import VideoFile, Message
from .config import ChatVideoConfig
from .video_processor import VideoProcessor
from .renderer import ChatRenderer

logger = logging.getLogger('vodloader.chat_video.generator')


class ChatVideoGenerator:
    """Main class for generating chat overlay videos."""
    
    def __init__(self, config: Optional[ChatVideoConfig] = None):
        self.config = config or ChatVideoConfig()
        self.video_processor = VideoProcessor(self.config)
        self.chat_renderer = ChatRenderer(self.config)
        self._check_gpu_support()
    
    async def generate(self, video: VideoFile) -> Optional[Path]:
        """
        Generate a chat overlay video.
        
        Args:
            video: The video file to process
            
        Returns:
            Path to the generated video, or None if no messages found
        """
        logger.info(f'Generating chat video for {video.path}')
        
        # Track temporary files for cleanup
        temp_files = []
        
        try:
            # Get messages for this video
            messages = await Message.for_video(video)
            if len(messages) == 0:
                logger.info('No messages found for this video')
                return None
            
            logger.info(f'Found {len(messages)} messages')
            
            # Check for cancellation before starting heavy processing
            await asyncio.sleep(0)
            
            # Preprocess video (ad removal)
            processed_path, main_stream_properties = await self.video_processor.preprocess_video(video)
            
            # Track processed file for cleanup if different from original
            if processed_path != video.path:
                temp_files.append(processed_path)
            
            # Check for cancellation after preprocessing
            await asyncio.sleep(0)
            
            # Process the video
            return await self._process_video(
                video, processed_path, messages, main_stream_properties, temp_files
            )
            
        except asyncio.CancelledError:
            logger.info(f"Chat video generation cancelled for {video.path}")
            # Cleanup will happen in finally block
            raise
        except Exception as e:
            logger.error(f"Error generating chat video for {video.path}: {e}")
            raise
        finally:
            # Clean up all temporary files
            await self._cleanup_temp_files(temp_files)
    
    def _check_gpu_support(self):
        """Check if GPU acceleration is available."""
        if not self.config.use_gpu:
            logger.info("GPU acceleration disabled in config")
            return
            
        try:
            # Check for CUDA support
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                logger.info(f"Found {cv2.cuda.getCudaEnabledDeviceCount()} CUDA devices")
                self.gpu_available = True
            else:
                logger.warning("CUDA devices not found, falling back to CPU")
                self.gpu_available = False
        except AttributeError:
            logger.warning("OpenCV not compiled with CUDA support, falling back to CPU")
            self.gpu_available = False
    
    async def _process_video(
        self,
        video: VideoFile,
        processed_path: Path,
        messages: List[Message],
        main_stream_properties: Optional[object],
        temp_files: List[Path]
    ) -> Path:
        """Process the video with chat overlay using batch processing."""
        # Open input video with GPU support if available
        api_preference = cv2.CAP_FFMPEG
        if self.config.use_gpu and hasattr(cv2, 'CAP_CUDA'):
            api_preference = cv2.CAP_CUDA
            
        video_in = cv2.VideoCapture(str(processed_path), apiPreference=api_preference)
        
        # Get video properties
        video_width = int(video_in.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = int(video_in.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = video_in.get(cv2.CAP_PROP_FPS)
        total_frames = int(video_in.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Use main stream properties if available
        if main_stream_properties:
            logger.info(f'Using main stream properties: {main_stream_properties.width}x{main_stream_properties.height} @ {main_stream_properties.fps}fps')
            video_width = main_stream_properties.width
            video_height = main_stream_properties.height
            fps = main_stream_properties.fps
        
        # Setup chat area
        chat_area = self.chat_renderer.setup_chat_area(video_width, video_height)
        
        # Open output video with GPU encoding if available
        chat_video_path = video.path.parent.joinpath(f'{video.path.stem}.chat.mp4')
        temp_files.append(chat_video_path)  # Track for cleanup
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        if self.config.use_gpu and hasattr(cv2, 'VideoWriter_fourcc'):
            # Try H.264 hardware encoding
            try:
                fourcc = cv2.VideoWriter_fourcc(*'H264')
            except:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                
        video_out = cv2.VideoWriter(
            str(chat_video_path),
            fourcc,
            fps,
            (video_width, video_height)
        )
        
        logger.info(f"Processing {total_frames} frames in batches of {self.config.batch_size}")
        
        try:
            # Process frames in batches
            frame_count = 0
            message_index = 0
            
            while frame_count < total_frames:
                # Check for cancellation at the start of each batch
                await asyncio.sleep(0)
                
                # Read batch of frames
                batch_frames = []
                batch_times = []
                batch_indices = []
                
                for _ in range(self.config.batch_size):
                    ret, frame = video_in.read()
                    if not ret:
                        break
                    
                    # Calculate current time
                    time_offset = timedelta(milliseconds=video_in.get(cv2.CAP_PROP_POS_MSEC))
                    current_time = video.started_at + time_offset
                    
                    # Ensure timezone consistency
                    if current_time.tzinfo is None:
                        current_time = current_time.replace(tzinfo=timezone.utc)
                    
                    # Update message index
                    message_index = self._update_message_index(
                        messages, message_index, current_time
                    )
                    
                    batch_frames.append(frame)
                    batch_times.append(current_time)
                    batch_indices.append(message_index)
                    frame_count += 1
                
                if not batch_frames:
                    break
                
                # Process batch in parallel with cancellation support
                processed_frames = await self._process_frame_batch(
                    batch_frames, batch_times, batch_indices, messages
                )
                
                # Write processed frames
                for processed_frame in processed_frames:
                    video_out.write(processed_frame)
                
                if frame_count % (self.config.batch_size * 10) == 0:
                    logger.info(f"Processed {frame_count}/{total_frames} frames ({frame_count/total_frames*100:.1f}%)")
        
        except asyncio.CancelledError:
            logger.info("Frame processing cancelled")
            raise
        finally:
            video_in.release()
            video_out.release()
        
        # Mux with audio
        return await self._mux_audio(video, processed_path, chat_video_path)
    
    async def _process_frame_batch(
        self,
        frames: List[np.ndarray],
        times: List,
        message_indices: List[int],
        messages: List[Message]
    ) -> List[np.ndarray]:
        """Process a batch of frames in parallel with cancellation support."""
        loop = asyncio.get_event_loop()
        
        # Create tasks for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.num_workers) as executor:
            tasks = []
            for frame, current_time, message_index in zip(frames, times, message_indices):
                task = loop.run_in_executor(
                    executor,
                    self._process_single_frame,
                    frame, messages, current_time, message_index
                )
                tasks.append(task)
            
            try:
                # Wait for all frames to be processed with cancellation support
                processed_frames = await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("Frame batch processing cancelled")
                # Cancel all running tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                # Wait briefly for tasks to complete cancellation
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Some frame processing tasks did not complete cancellation within timeout")
                raise
        
        return processed_frames
    
    def _process_single_frame(
        self,
        frame: np.ndarray,
        messages: List[Message],
        current_time,
        message_index: int
    ) -> np.ndarray:
        """Process a single frame (thread-safe)."""
        return self.chat_renderer.render_messages_on_frame(
            frame, messages, current_time, message_index
        )
    
    def _update_message_index(
        self,
        messages: List[Message],
        current_index: int,
        current_time
    ) -> int:
        """Update message index to point to the newest message for current time."""
        while current_index < len(messages) - 1:
            message_time = messages[current_index].timestamp
            next_message_time = messages[current_index + 1].timestamp
            
            # Ensure timezone consistency
            if message_time.tzinfo is None:
                message_time = message_time.replace(tzinfo=timezone.utc)
            if next_message_time.tzinfo is None:
                next_message_time = next_message_time.replace(tzinfo=timezone.utc)
            
            if message_time <= current_time:
                if next_message_time > current_time:
                    break
                current_index += 1
            else:
                break
        return current_index
    
    async def _mux_audio(
        self,
        video: VideoFile,
        processed_path: Path,
        chat_video_path: Path
    ) -> Path:
        """Mux the chat video with audio from original with cancellation support."""
        logger.debug('Muxing chat video with audio...')
        
        transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
        
        # Build ffmpeg command
        chat_stream = ffmpeg.input(str(chat_video_path))
        original_stream = ffmpeg.input(str(processed_path))
        
        output_stream = ffmpeg.output(
            chat_stream['v:0'],
            original_stream['a:0'],
            str(transcode_path),
            vcodec='copy',
            acodec='aac'
        )
        output_stream = ffmpeg.overwrite_output(output_stream)
        
        # Run ffmpeg with cancellation support
        loop = asyncio.get_event_loop()
        
        def run_ffmpeg_mux():
            # Use subprocess for better control
            cmd = ffmpeg.compile(output_stream)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return process
        
        try:
            # Start ffmpeg process
            process = await loop.run_in_executor(None, run_ffmpeg_mux)
            
            # Wait for completion with cancellation support
            await loop.run_in_executor(None, process.wait)
            
            if process.returncode != 0:
                stderr = process.stderr.read().decode() if process.stderr else "Unknown error"
                raise subprocess.CalledProcessError(process.returncode, "ffmpeg", stderr)
            
        except asyncio.CancelledError:
            logger.info("Audio muxing cancelled")
            if 'process' in locals():
                process.terminate()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, process.wait),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    process.kill()
            
            # Clean up partial output file
            if transcode_path.exists():
                transcode_path.unlink()
            raise
        
        # Update video model
        video.transcode_path = transcode_path
        await video.save()
        
        # Clean up chat video (will be handled by cleanup function)
        # chat_video_path.unlink()
        
        # Keep original video file as requested
        
        return transcode_path
    
    async def _cleanup_temp_files(self, temp_files: List[Path]):
        """Clean up temporary files created during processing."""
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")


# Convenience function for backward compatibility
async def generate_chat_video(
    video: VideoFile,
    width: int = 320,
    height: Optional[int] = None,
    x_offset: int = 20,
    y_offset: int = 20,
    padding: int = 20,
    font_family: str = "FreeSans",
    font_style: str = "Regular",
    font_size: int = 24,
    font_color: tuple = (255, 255, 255, 255),
    background_color: tuple = (0, 0, 0, 127),
    message_duration: int = 10,
    remove_ads: bool = True,
    use_gpu: bool = True,
    batch_size: int = 30,
    num_workers: Optional[int] = None
) -> Optional[Path]:
    """
    Generate a chat overlay video (backward compatibility function).
    """
    config = ChatVideoConfig(
        width=width,
        height=height,
        x_offset=x_offset,
        y_offset=y_offset,
        padding=padding,
        font_family=font_family,
        font_style=font_style,
        font_size=font_size,
        font_color=font_color,
        background_color=background_color,
        message_duration=message_duration,
        remove_ads=remove_ads,
        use_gpu=use_gpu,
        batch_size=batch_size,
        num_workers=num_workers
    )
    
    generator = ChatVideoGenerator(config)
    return await generator.generate(video)