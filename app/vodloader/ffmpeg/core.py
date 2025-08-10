"""
Core FFmpeg functionality with unified interface.
"""

import ffmpeg
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, AsyncGenerator, Union
from dataclasses import dataclass

logger = logging.getLogger('vodloader.ffmpeg')


class FFmpegError(Exception):
    """Base exception for FFmpeg operations."""
    pass


class ProbeError(FFmpegError):
    """Raised when video probing fails."""
    pass


class TranscodeError(FFmpegError):
    """Raised when transcoding fails."""
    pass


class CompositionError(FFmpegError):
    """Raised when video composition fails."""
    pass


@dataclass
class VideoInfo:
    """Container for video metadata."""
    width: int
    height: int
    frame_rate: float
    duration: float
    codec: str
    bitrate: Optional[int] = None
    has_audio: bool = True
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height if self.height > 0 else 0
    
    @property
    def resolution_string(self) -> str:
        """Get resolution as string."""
        return f"{self.width}x{self.height}"


async def probe_video(video_path: Union[str, Path]) -> VideoInfo:
    """
    Probe video file for metadata using ffmpeg-python.
    
    Args:
        video_path: Path to video file
        
    Returns:
        VideoInfo object with metadata
        
    Raises:
        ProbeError: If probing fails
    """
    try:
        loop = asyncio.get_event_loop()
        
        def _probe():
            return ffmpeg.probe(str(video_path))
        
        probe_data = await loop.run_in_executor(None, _probe)
        
        # Find video and audio streams
        video_stream = None
        audio_stream = None
        
        for stream in probe_data['streams']:
            if stream['codec_type'] == 'video' and video_stream is None:
                video_stream = stream
            elif stream['codec_type'] == 'audio' and audio_stream is None:
                audio_stream = stream
        
        if not video_stream:
            raise ProbeError(f"No video stream found in {video_path}")
        
        # Parse frame rate
        frame_rate_str = video_stream.get('r_frame_rate', '30/1')
        if '/' in frame_rate_str:
            num, den = frame_rate_str.split('/')
            frame_rate = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            frame_rate = float(frame_rate_str)
        
        # Extract bitrate if available
        bitrate = None
        if 'bit_rate' in video_stream:
            bitrate = int(video_stream['bit_rate'])
        
        return VideoInfo(
            width=int(video_stream['width']),
            height=int(video_stream['height']),
            frame_rate=frame_rate,
            duration=float(video_stream.get('duration', 0)),
            codec=video_stream.get('codec_name', 'unknown'),
            bitrate=bitrate,
            has_audio=audio_stream is not None
        )
        
    except Exception as e:
        raise ProbeError(f"Failed to probe {video_path}: {e}") from e


async def transcode_video(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    video_codec: str = 'copy',
    audio_codec: str = 'copy',
    preset: Optional[str] = None,
    crf: Optional[int] = None,
    additional_args: Optional[List[str]] = None,
    cancellation_event: Optional[asyncio.Event] = None
) -> Path:
    """
    Transcode video using ffmpeg-python for simple operations.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        video_codec: Video codec to use
        audio_codec: Audio codec to use
        preset: Encoding preset
        crf: Constant rate factor for quality
        additional_args: Additional ffmpeg arguments
        cancellation_event: Event to signal cancellation
        
    Returns:
        Path to transcoded file
        
    Raises:
        TranscodeError: If transcoding fails
        asyncio.CancelledError: If operation is cancelled
    """
    try:
        # Check for cancellation before starting
        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Transcoding cancelled before starting")
        
        loop = asyncio.get_event_loop()
        
        def _transcode():
            # Check for cancellation in the executor
            if cancellation_event and cancellation_event.is_set():
                raise asyncio.CancelledError("Transcoding cancelled")
                
            stream = ffmpeg.input(str(input_path))
            
            # Build output arguments
            output_args = {}
            if video_codec:
                output_args['vcodec'] = video_codec
            if audio_codec:
                output_args['acodec'] = audio_codec
            if preset:
                output_args['preset'] = preset
            if crf is not None:
                output_args['crf'] = crf
            
            stream = ffmpeg.output(stream, str(output_path), **output_args)
            stream = ffmpeg.overwrite_output(stream)
            
            # Add additional arguments if provided
            if additional_args:
                for i in range(0, len(additional_args), 2):
                    if i + 1 < len(additional_args):
                        stream = stream.option(additional_args[i], additional_args[i + 1])
                    else:
                        stream = stream.option(additional_args[i])
            
            ffmpeg.run(stream, quiet=True)
        
        # Run with cancellation support
        if cancellation_event:
            # Create a task that can be cancelled
            transcode_task = loop.run_in_executor(None, _transcode)
            
            # Wait for either completion or cancellation
            done, pending = await asyncio.wait(
                [transcode_task, asyncio.create_task(cancellation_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check if cancellation was requested
            if cancellation_event.is_set():
                logger.info(f"Transcoding cancelled for {input_path}")
                raise asyncio.CancelledError("Transcoding cancelled")
            
            # Get the result from the completed transcode task
            await transcode_task
        else:
            await loop.run_in_executor(None, _transcode)
        
        output_path = Path(output_path)
        if not output_path.exists():
            raise TranscodeError(f"Output file was not created: {output_path}")
        
        logger.info(f"Successfully transcoded {input_path} -> {output_path}")
        return output_path
        
    except asyncio.CancelledError:
        logger.info(f"Transcoding cancelled for {input_path}")
        # Clean up partial output file if it exists
        output_path = Path(output_path)
        if output_path.exists():
            try:
                output_path.unlink()
                logger.info(f"Cleaned up partial transcode file: {output_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup partial transcode file: {cleanup_error}")
        raise
    except Exception as e:
        raise TranscodeError(f"Failed to transcode {input_path}: {e}") from e


class StreamingComposer:
    """
    Handles streaming video composition using subprocess for optimal performance.
    """
    
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self._composition_start_time: Optional[float] = None
    
    async def compose_with_overlay(
        self,
        original_path: Union[str, Path],
        output_path: Union[str, Path],
        overlay_x: int,
        overlay_y: int,
        frame_generator: AsyncGenerator[bytes, None],
        total_frames: int,
        original_info: VideoInfo,
        video_codec: str = 'libx264',
        audio_codec: str = 'copy',
        preset: str = 'medium',
        crf: int = 12,
        cancellation_event: Optional[asyncio.Event] = None
    ) -> Path:
        """
        Compose video with streaming overlay frames.
        
        Args:
            original_path: Path to original video
            output_path: Path for output video
            overlay_x: X position for overlay
            overlay_y: Y position for overlay
            frame_generator: Async generator yielding PNG frame bytes
            total_frames: Total number of frames to process
            original_info: Original video information
            video_codec: Video codec for output
            audio_codec: Audio codec for output
            preset: Encoding preset
            crf: Constant rate factor
            cancellation_event: Event to signal cancellation
            
        Returns:
            Path to composed video
            
        Raises:
            CompositionError: If composition fails
            asyncio.CancelledError: If operation is cancelled
        """
        import time
        
        # Check for cancellation before starting
        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Composition cancelled before starting")
        
        self._composition_start_time = time.time()
        
        try:
            # Build ffmpeg command
            cmd = [
                'ffmpeg', '-y',
                # Original video input
                '-i', str(original_path),
                # Overlay frames input (streaming)
                '-f', 'image2pipe',
                '-vcodec', 'png',
                '-r', str(original_info.frame_rate),
                '-i', '-',  # Read from stdin
                # Apply overlay filter
                '-filter_complex', f'[0:v][1:v]overlay={overlay_x}:{overlay_y}:eof_action=pass[v]',
                # Map streams
                '-map', '[v]',
                '-map', '0:a' if original_info.has_audio else '0:v',
                # Output settings
                '-vcodec', video_codec,
                '-acodec', audio_codec,
                '-preset', preset,
                '-crf', str(crf),
                '-pix_fmt', 'yuv420p',
                str(output_path)
            ]
            
            logger.debug(f"Starting streaming composition: {' '.join(cmd)}")
            
            # Start process
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Stream frames with cancellation support
            await self._stream_frames(frame_generator, total_frames, cancellation_event)
            
            # Wait for completion with cancellation support
            if cancellation_event:
                # Create tasks for both process completion and cancellation
                process_task = asyncio.create_task(self.process.communicate())
                cancellation_task = asyncio.create_task(cancellation_event.wait())
                
                done, pending = await asyncio.wait(
                    [process_task, cancellation_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # Check if cancellation was requested
                if cancellation_event.is_set():
                    logger.info("Composition cancelled during processing")
                    await self._cleanup_process()
                    raise asyncio.CancelledError("Composition cancelled")
                
                # Get the result from the completed process task
                stdout, stderr = await process_task
            else:
                stdout, stderr = await self.process.communicate()
            
            if self.process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise CompositionError(f"FFmpeg failed: {error_msg}")
            
            # Verify output
            output_path = Path(output_path)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise CompositionError(f"Output file not created or empty: {output_path}")
            
            duration = time.time() - self._composition_start_time
            size_mb = output_path.stat().st_size / (1024 * 1024)
            
            logger.info(f"Composition completed: {size_mb:.1f}MB in {duration:.1f}s")
            return output_path
            
        except asyncio.CancelledError:
            logger.info("Composition cancelled")
            await self._cleanup_process()
            # Clean up partial output file
            output_path = Path(output_path)
            if output_path.exists():
                try:
                    output_path.unlink()
                    logger.info(f"Cleaned up partial composition file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup partial composition file: {cleanup_error}")
            raise
        except Exception as e:
            await self._cleanup_process()
            raise CompositionError(f"Streaming composition failed: {e}") from e
        finally:
            self.process = None
    
    async def _stream_frames(
        self,
        frame_generator: AsyncGenerator[bytes, None],
        total_frames: int,
        cancellation_event: Optional[asyncio.Event] = None
    ) -> None:
        """Stream frames to ffmpeg process with cancellation support."""
        import time
        
        frame_count = 0
        
        try:
            async for frame_bytes in frame_generator:
                # Check for cancellation during frame streaming
                if cancellation_event and cancellation_event.is_set():
                    logger.info(f"Frame streaming cancelled after {frame_count} frames")
                    raise asyncio.CancelledError("Frame streaming cancelled")
                
                if self.process and self.process.stdin:
                    self.process.stdin.write(frame_bytes)
                    await self.process.stdin.drain()
                
                frame_count += 1
                
                # Log progress
                if total_frames > 100 and frame_count % (total_frames // 10) == 0:
                    self._log_progress(frame_count, total_frames)
            
            # Close stdin
            if self.process and self.process.stdin:
                self.process.stdin.close()
                await self.process.stdin.wait_closed()
            
            logger.info(f"Streamed {frame_count} frames to composition")
            
        except asyncio.CancelledError:
            logger.info(f"Frame streaming cancelled after {frame_count} frames")
            raise
        except Exception as e:
            logger.error(f"Error streaming frames: {e}")
            raise
    
    def _log_progress(self, frame_count: int, total_frames: int) -> None:
        """Log composition progress."""
        import time
        
        if not self._composition_start_time:
            return
        
        progress = (frame_count / total_frames) * 100
        elapsed = time.time() - self._composition_start_time
        estimated_total = elapsed / frame_count * total_frames
        remaining = estimated_total - elapsed
        
        logger.info(
            f"Composition progress: {progress:.1f}% "
            f"({frame_count}/{total_frames} frames, ~{remaining:.0f}s remaining)"
        )
    
    async def _cleanup_process(self) -> None:
        """Clean up ffmpeg process."""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
    
    async def cancel(self) -> None:
        """Cancel ongoing composition."""
        logger.info("Cancelling streaming composition")
        await self._cleanup_process()


async def create_filter_complex_video(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    filter_complex: str,
    input_args: Optional[List[str]] = None,
    output_args: Optional[List[str]] = None
) -> Path:
    """
    Create video with complex filter using subprocess for advanced operations.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        filter_complex: FFmpeg filter complex string
        input_args: Additional input arguments
        output_args: Additional output arguments
        
    Returns:
        Path to output video
        
    Raises:
        FFmpegError: If operation fails
    """
    try:
        cmd = ['ffmpeg', '-y']
        
        # Add input arguments
        if input_args:
            cmd.extend(input_args)
        
        cmd.extend(['-i', str(input_path)])
        
        # Add filter complex
        cmd.extend(['-filter_complex', filter_complex])
        
        # Add output arguments
        if output_args:
            cmd.extend(output_args)
        
        cmd.append(str(output_path))
        
        logger.debug(f"Running filter complex: {' '.join(cmd)}")
        
        # Run process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise FFmpegError(f"Filter complex failed: {error_msg}")
        
        output_path = Path(output_path)
        if not output_path.exists():
            raise FFmpegError(f"Output file not created: {output_path}")
        
        logger.info(f"Filter complex completed: {output_path}")
        return output_path
        
    except Exception as e:
        raise FFmpegError(f"Filter complex operation failed: {e}") from e