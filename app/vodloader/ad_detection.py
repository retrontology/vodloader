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
    
    def analyze_video_segments(self, video_path: Path) -> List[VideoSegment]:
        """
        Analyze video file and extract segments with different properties.
        
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
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed: {e}")
            raise
        
        return self._parse_frame_data(result.stdout)
    
    def _parse_frame_data(self, frame_data: str) -> List[VideoSegment]:
        """Parse ffprobe frame data into video segments."""
        lines = frame_data.strip().split('\n')
        segments = []
        current_segment_frames = []
        
        prev_width = prev_height = None
        
        for line in lines:
            try:
                parts = line.strip().split(',')
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
                current_segment_frames = []
            
            current_segment_frames.append((timestamp, width, height))
            prev_width, prev_height = width, height
        
        # Add final segment
        if current_segment_frames:
            segment = self._create_segment_from_frames(current_segment_frames)
            if segment and segment.duration >= self.min_segment_duration:
                segments.append(segment)
        
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
    
    def remove_ads(self, input_path: Path, output_path: Path) -> Tuple[Path, StreamProperties]:
        """
        Remove ads from a video file and return the cleaned version.
        
        Args:
            input_path: Path to input video with ads
            output_path: Path for output video without ads
            
        Returns:
            Tuple of (output_path, main_stream_properties)
        """
        logger.info(f"Removing ads from {input_path}")
        
        # Detect ad segments
        content_segments, ad_segments, main_properties = self.detect_ads(input_path)
        
        if not ad_segments:
            logger.info("No ads detected, copying original file")
            # Just copy the file if no ads found
            import shutil
            shutil.copy2(input_path, output_path)
            return output_path, main_properties
        
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
        
        # Run ffmpeg to create ad-free video
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-c:a", "aac",
            "-y", str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Successfully created ad-free video: {output_path}")
            return output_path, main_properties
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed: {e}")
            raise