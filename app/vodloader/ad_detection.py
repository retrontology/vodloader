"""
Ad detection and removal for Twitch VODs.

This module provides functionality to detect and remove advertisement segments
from Twitch streams based on video property changes (resolution, FPS).
"""

import subprocess
import json
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger('vodloader.ad_detection')


@dataclass
class VideoSegment:
    """Represents a segment of video with consistent properties."""
    start_time: float
    end_time: float
    width: int
    height: int
    fps: float
    duration: float
    
    @property
    def resolution(self) -> Tuple[int, int]:
        return (self.width, self.height)
    
    def __post_init__(self):
        if self.duration is None:
            self.duration = self.end_time - self.start_time


@dataclass
class StreamProperties:
    """Main stream properties used to identify content vs ads."""
    width: int
    height: int
    fps: float
    resolution: Tuple[int, int]
    
    def __post_init__(self):
        self.resolution = (self.width, self.height)


class AdDetector:
    """Detects and removes advertisement segments from video streams."""
    
    def __init__(self, fps_tolerance: float = 2.0, min_segment_duration: float = 1.0):
        """
        Initialize the ad detector.
        
        Args:
            fps_tolerance: Maximum FPS difference to consider segments the same
            min_segment_duration: Minimum duration for a segment to be considered valid
        """
        self.fps_tolerance = fps_tolerance
        self.min_segment_duration = min_segment_duration
    
    def get_video_info(self, video_path: Path) -> Dict:
        """
        Get basic video information without processing all frames.
        Useful for quick checks before full analysis.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dict with basic video information
        """
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json",
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            if not data.get('streams'):
                raise ValueError("No video stream found")
            
            stream = data['streams'][0]
            
            # Parse frame rate
            fps_str = stream.get('r_frame_rate', '0/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if float(den) != 0 else 0
            else:
                fps = float(fps_str)
            
            return {
                'width': int(stream.get('width', 0)),
                'height': int(stream.get('height', 0)),
                'fps': round(fps, 3),
                'duration': float(stream.get('duration', 0))
            }
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to get video info: {e}")
            raise
    
    def analyze_video_segments(self, video_path: Path) -> List[VideoSegment]:
        """
        Analyze video file and extract segments with different properties.
        Uses streaming approach to avoid loading all frame data into memory.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            List of VideoSegment objects
        """
        logger.info(f"Analyzing video segments for {video_path}")
        
        # Use ffprobe to get frame-level information
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "frame=best_effort_timestamp_time,width,height",
            "-of", "csv=p=0",
            str(video_path)
        ]
        
        try:
            # Use Popen for streaming processing instead of run()
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return self._parse_frame_data_streaming(process.stdout)
        except Exception as e:
            logger.error(f"ffprobe failed: {e}")
            raise
    
    def _parse_frame_data_streaming(self, stdout) -> List[VideoSegment]:
        """Parse ffprobe frame data into video segments using streaming approach."""
        segments = []
        current_segment_frames = []
        prev_width = prev_height = None
        
        try:
            for line in stdout:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    parts = line.split(',')
                    if len(parts) != 3:
                        continue
                        
                    timestamp = float(parts[0])
                    width = int(parts[1])
                    height = int(parts[2])
                    
                except (ValueError, IndexError):
                    logger.warning(f"Skipping malformed frame data: {line}")
                    continue
                
                # Start new segment if properties changed
                if prev_width is not None and (width != prev_width or height != prev_height):
                    if current_segment_frames:
                        segment = self._create_segment_from_frames(current_segment_frames)
                        if segment and segment.duration >= self.min_segment_duration:
                            segments.append(segment)
                        # Clear frames to free memory
                        current_segment_frames = []
                
                current_segment_frames.append((timestamp, width, height))
                prev_width, prev_height = width, height
            
            # Add final segment
            if current_segment_frames:
                segment = self._create_segment_from_frames(current_segment_frames)
                if segment and segment.duration >= self.min_segment_duration:
                    segments.append(segment)
        
        finally:
            # Ensure the subprocess is properly closed
            stdout.close()
        
        logger.info(f"Found {len(segments)} video segments")
        return segments
    
    def _create_segment_from_frames(self, frames: List[Tuple[float, int, int]]) -> Optional[VideoSegment]:
        """Create a VideoSegment from a list of frame data."""
        if len(frames) < 2:
            return None
        
        start_time = frames[0][0]
        end_time = frames[-1][0]
        width = frames[0][1]
        height = frames[0][2]
        
        # Calculate FPS from frame timestamps
        duration = end_time - start_time
        fps = (len(frames) - 1) / duration if duration > 0 else 0
        
        return VideoSegment(
            start_time=start_time,
            end_time=end_time,
            width=width,
            height=height,
            fps=round(fps, 3),
            duration=duration
        )
    
    def identify_main_stream_properties(self, segments: List[VideoSegment]) -> StreamProperties:
        """
        Identify the main stream properties based on segment analysis.
        
        The main stream is typically the most common resolution/fps combination
        and usually has the longest total duration.
        """
        if not segments:
            raise ValueError("No segments provided")
        
        # Count occurrences of each property combination
        property_stats = {}
        
        for segment in segments:
            key = (segment.width, segment.height, round(segment.fps))
            if key not in property_stats:
                property_stats[key] = {
                    'count': 0,
                    'total_duration': 0,
                    'segments': []
                }
            
            property_stats[key]['count'] += 1
            property_stats[key]['total_duration'] += segment.duration
            property_stats[key]['segments'].append(segment)
        
        # Find the property combination with the longest total duration
        main_properties = max(
            property_stats.items(),
            key=lambda x: x[1]['total_duration']
        )
        
        width, height, fps = main_properties[0]
        
        logger.info(f"Identified main stream properties: {width}x{height} @ {fps}fps "
                   f"(total duration: {main_properties[1]['total_duration']:.1f}s)")
        
        return StreamProperties(width=width, height=height, fps=fps, resolution=(width, height))
    
    def classify_segments(self, segments: List[VideoSegment], 
                         main_properties: StreamProperties) -> Tuple[List[VideoSegment], List[VideoSegment]]:
        """
        Classify segments as content or ads based on main stream properties.
        
        Returns:
            Tuple of (content_segments, ad_segments)
        """
        content_segments = []
        ad_segments = []
        
        for segment in segments:
            is_main_stream = (
                segment.width == main_properties.width and
                segment.height == main_properties.height and
                abs(segment.fps - main_properties.fps) <= self.fps_tolerance
            )
            
            if is_main_stream:
                content_segments.append(segment)
            else:
                ad_segments.append(segment)
        
        logger.info(f"Classified {len(content_segments)} content segments and {len(ad_segments)} ad segments")
        return content_segments, ad_segments
    
    def detect_ads(self, video_path: Path) -> Tuple[List[VideoSegment], List[VideoSegment], StreamProperties]:
        """
        Complete ad detection pipeline.
        
        Returns:
            Tuple of (content_segments, ad_segments, main_properties)
        """
        segments = self.analyze_video_segments(video_path)
        main_properties = self.identify_main_stream_properties(segments)
        content_segments, ad_segments = self.classify_segments(segments, main_properties)
        
        return content_segments, ad_segments, main_properties
    
    def remove_ads(self, input_path: Path, output_path: Path) -> Optional[Tuple[Path, StreamProperties]]:
        """
        Remove ads from a video file and return the cleaned version.
        Uses streaming approach to minimize memory usage.
        
        Args:
            input_path: Path to input video with ads
            output_path: Path for output video without ads
            
        Returns:
            Tuple of (output_path, main_stream_properties) if ads were found and removed,
            None if no ads were detected (caller should use original file)
        """
        logger.info(f"Removing ads from {input_path}")
        
        # Detect ad segments
        content_segments, ad_segments, main_properties = self.detect_ads(input_path)
        
        if not ad_segments:
            logger.info("No ads detected, returning None")
            return None
        
        # Use streaming approach for large numbers of segments
        if len(content_segments) > 50:
            logger.info(f"Large number of segments ({len(content_segments)}), using streaming approach")
            return self._remove_ads_streaming(input_path, output_path, content_segments, main_properties)
        
        # Create ffmpeg filter for content segments
        filter_parts = []
        for i, segment in enumerate(content_segments):
            filter_parts.append(f"[0:v]trim=start={segment.start_time}:end={segment.end_time},setpts=PTS-STARTPTS[v{i}]")
            filter_parts.append(f"[0:a]atrim=start={segment.start_time}:end={segment.end_time},asetpts=PTS-STARTPTS[a{i}]")
        
        # Concatenate all segments
        video_inputs = "".join(f"[v{i}]" for i in range(len(content_segments)))
        audio_inputs = "".join(f"[a{i}]" for i in range(len(content_segments)))
        filter_parts.append(f"{video_inputs}concat=n={len(content_segments)}:v=1:a=0[outv]")
        filter_parts.append(f"{audio_inputs}concat=n={len(content_segments)}:v=0:a=1[outa]")
        
        filter_complex = ";".join(filter_parts)
        
        # Run ffmpeg to create ad-free video with streaming output
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "fast",  # Faster encoding
            "-c:a", "aac", "-movflags", "+faststart",  # Optimize for streaming
            "-y", str(output_path)
        ]
        
        try:
            # Use streaming approach for ffmpeg as well
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"ffmpeg failed with return code {process.returncode}")
                logger.error(f"stderr: {stderr.decode()}")
                raise subprocess.CalledProcessError(process.returncode, cmd)
                
            logger.info(f"Successfully created ad-free video: {output_path}")
            return output_path, main_properties
        except Exception as e:
            logger.error(f"ffmpeg failed: {e}")
            raise
    
    def _remove_ads_streaming(self, input_path: Path, output_path: Path, 
                             content_segments: List[VideoSegment], 
                             main_properties: StreamProperties) -> Tuple[Path, StreamProperties]:
        """
        Remove ads using a streaming approach for videos with many segments.
        Processes segments in batches to avoid command line length limits.
        """
        logger.info("Using streaming approach for ad removal")
        
        # Process segments in batches to avoid command line limits
        batch_size = 20
        temp_files = []
        
        try:
            # Create temporary files for each batch
            for i in range(0, len(content_segments), batch_size):
                batch = content_segments[i:i + batch_size]
                temp_file = output_path.parent / f"temp_batch_{i//batch_size}.mp4"
                temp_files.append(temp_file)
                
                # Create filter for this batch
                filter_parts = []
                for j, segment in enumerate(batch):
                    filter_parts.append(f"[0:v]trim=start={segment.start_time}:end={segment.end_time},setpts=PTS-STARTPTS[v{j}]")
                    filter_parts.append(f"[0:a]atrim=start={segment.start_time}:end={segment.end_time},asetpts=PTS-STARTPTS[a{j}]")
                
                # Concatenate batch segments
                video_inputs = "".join(f"[v{j}]" for j in range(len(batch)))
                audio_inputs = "".join(f"[a{j}]" for j in range(len(batch)))
                filter_parts.append(f"{video_inputs}concat=n={len(batch)}:v=1:a=0[outv]")
                filter_parts.append(f"{audio_inputs}concat=n={len(batch)}:v=0:a=1[outa]")
                
                filter_complex = ";".join(filter_parts)
                
                # Process this batch
                cmd = [
                    "ffmpeg", "-i", str(input_path),
                    "-filter_complex", filter_complex,
                    "-map", "[outv]", "-map", "[outa]",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-y", str(temp_file)
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"Processed batch {i//batch_size + 1}/{(len(content_segments) + batch_size - 1)//batch_size}")
            
            # Concatenate all batch files
            if len(temp_files) == 1:
                # Only one batch, just rename
                temp_files[0].rename(output_path)
            else:
                # Multiple batches, concatenate them
                concat_list = output_path.parent / "concat_list.txt"
                with open(concat_list, 'w') as f:
                    for temp_file in temp_files:
                        f.write(f"file '{temp_file.name}'\n")
                
                cmd = [
                    "ffmpeg", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list),
                    "-c", "copy", "-y", str(output_path)
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                concat_list.unlink()
            
            logger.info(f"Successfully created ad-free video using streaming approach: {output_path}")
            return output_path, main_properties
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()