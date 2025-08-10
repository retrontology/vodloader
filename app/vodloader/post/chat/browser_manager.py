"""
Browser manager for Playwright automation in chat overlay generation.

This module provides a context manager for managing Playwright browser instances
with proper resource cleanup, timeout handling, and error recovery.
"""

import asyncio
import logging
import psutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, Browser, Page, Playwright

logger = logging.getLogger('vodloader.chat_video.browser_manager')


class BrowserManagerError(Exception):
    """Base exception for browser manager errors."""
    pass


class BrowserTimeoutError(BrowserManagerError):
    """Exception raised when browser operations timeout."""
    pass


class BrowserResourceError(BrowserManagerError):
    """Exception raised when browser resource limits are exceeded."""
    pass


class BrowserManager:
    """
    Context manager for Playwright browser lifecycle management.
    
    Provides automatic browser process creation, configuration, cleanup,
    and resource monitoring for chat overlay generation.
    """
    
    # Resource limits
    MAX_MEMORY_MB = 2048  # 2GB memory limit per browser instance
    PAGE_LOAD_TIMEOUT = 30000  # 30 seconds
    BROWSER_OPERATION_TIMEOUT = 60000  # 60 seconds
    
    def __init__(self):
        """Initialize browser manager."""
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._start_time: Optional[float] = None
        self._process_id: Optional[int] = None
        
    async def __aenter__(self) -> Browser:
        """
        Context manager entry - initialize browser.
        
        Returns:
            Configured Playwright browser instance
            
        Raises:
            BrowserManagerError: If browser initialization fails
        """
        try:
            logger.info("Initializing Playwright browser for chat overlay generation")
            self._start_time = time.time()
            
            # Start Playwright
            self._playwright = await async_playwright().start()
            
            # Launch Chromium browser with optimized settings
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--memory-pressure-off',
                    f'--max_old_space_size={self.MAX_MEMORY_MB}',
                ]
            )
            
            # Get browser process ID for monitoring
            if hasattr(self._browser, '_connection') and hasattr(self._browser._connection, '_transport'):
                # Try to get process ID from browser connection
                try:
                    # This is a best-effort attempt to get the process ID
                    # The exact method may vary depending on Playwright version
                    pass
                except Exception:
                    logger.debug("Could not retrieve browser process ID for monitoring")
            
            logger.info(f"Browser initialized successfully in {time.time() - self._start_time:.2f}s")
            return self._browser
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            await self._cleanup()
            raise BrowserManagerError(f"Browser initialization failed: {e}") from e
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - cleanup browser resources.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred  
            exc_tb: Exception traceback if an exception occurred
        """
        if exc_type:
            logger.warning(f"Browser context exiting due to exception: {exc_type.__name__}: {exc_val}")
        
        await self._cleanup()
        
        if self._start_time:
            total_time = time.time() - self._start_time
            logger.info(f"Browser session completed in {total_time:.2f}s")
    
    async def create_chat_page(self, config: Dict[str, Any]) -> Page:
        """
        Create and configure a page for chat rendering.
        
        Args:
            config: Configuration dictionary containing overlay dimensions and settings
            
        Returns:
            Configured Playwright page instance
            
        Raises:
            BrowserManagerError: If page creation fails
            BrowserTimeoutError: If page operations timeout
        """
        if not self._browser:
            raise BrowserManagerError("Browser not initialized - use within context manager")
        
        try:
            logger.debug("Creating new page for chat rendering")
            
            # Create new page with timeout
            page = await asyncio.wait_for(
                self._browser.new_page(),
                timeout=self.BROWSER_OPERATION_TIMEOUT / 1000
            )
            
            # Set page timeouts
            page.set_default_timeout(self.PAGE_LOAD_TIMEOUT)
            page.set_default_navigation_timeout(self.PAGE_LOAD_TIMEOUT)
            
            # Configure viewport based on overlay dimensions
            overlay_width = config.get('overlay_width', 400)
            overlay_height = config.get('overlay_height', 600)
            
            await page.set_viewport_size({
                'width': overlay_width,
                'height': overlay_height
            })
            
            # Set up page for video recording
            await page.add_init_script("""
                // Disable animations for deterministic rendering
                window.matchMedia = () => ({
                    matches: true,
                    addListener: () => {},
                    removeListener: () => {}
                });
                
                // Override requestAnimationFrame for deterministic timing
                let frameId = 0;
                window.requestAnimationFrame = (callback) => {
                    return setTimeout(() => callback(++frameId * 16.67), 0);
                };
                
                // Disable smooth scrolling
                document.documentElement.style.scrollBehavior = 'auto';
                
                // Ensure transparent background
                document.addEventListener('DOMContentLoaded', () => {
                    document.body.style.background = 'transparent';
                    document.documentElement.style.background = 'transparent';
                });
            """)
            
            logger.debug(f"Page created with viewport {overlay_width}x{overlay_height}")
            return page
            
        except asyncio.TimeoutError:
            logger.error("Page creation timed out")
            raise BrowserTimeoutError("Page creation timed out")
        except Exception as e:
            logger.error(f"Failed to create chat page: {e}")
            raise BrowserManagerError(f"Page creation failed: {e}") from e
    
    async def monitor_resources(self) -> Dict[str, Any]:
        """
        Monitor browser resource usage.
        
        Returns:
            Dictionary containing resource usage information
            
        Raises:
            BrowserResourceError: If resource limits are exceeded
        """
        try:
            # Get current process info
            current_process = psutil.Process()
            memory_info = current_process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Check memory limit
            if memory_mb > self.MAX_MEMORY_MB:
                error_msg = f"Browser memory usage ({memory_mb:.1f}MB) exceeds limit ({self.MAX_MEMORY_MB}MB)"
                logger.error(error_msg)
                
                # Log additional context for debugging
                logger.error(f"Browser uptime: {time.time() - self._start_time:.1f}s")
                
                # Attempt emergency cleanup
                try:
                    await self._emergency_cleanup()
                except Exception as cleanup_error:
                    logger.error(f"Emergency cleanup failed: {cleanup_error}")
                
                raise BrowserResourceError(error_msg)
            
            # Get CPU usage
            cpu_percent = current_process.cpu_percent()
            
            # Check for high CPU usage (warning only)
            if cpu_percent > 90:
                logger.warning(f"High browser CPU usage: {cpu_percent:.1f}%")
            
            resource_info = {
                'memory_mb': memory_mb,
                'cpu_percent': cpu_percent,
                'uptime_seconds': time.time() - self._start_time if self._start_time else 0,
                'process_id': current_process.pid
            }
            
            # Log resource usage periodically
            if not hasattr(self, '_last_resource_log'):
                self._last_resource_log = time.time()
                logger.debug(f"Browser resources: {memory_mb:.1f}MB memory, {cpu_percent:.1f}% CPU")
            elif time.time() - self._last_resource_log > 30:  # Log every 30 seconds
                logger.debug(f"Browser resources: {memory_mb:.1f}MB memory, {cpu_percent:.1f}% CPU")
                self._last_resource_log = time.time()
            
            return resource_info
            
        except psutil.NoSuchProcess:
            logger.warning("Browser process no longer exists during resource monitoring")
            return {'memory_mb': 0, 'cpu_percent': 0, 'uptime_seconds': 0, 'process_id': None}
        except BrowserResourceError:
            # Re-raise resource errors
            raise
        except Exception as e:
            logger.warning(f"Could not monitor browser resources: {e}")
            return {'memory_mb': 0, 'cpu_percent': 0, 'uptime_seconds': 0, 'process_id': None}
    
    async def _emergency_cleanup(self) -> None:
        """
        Perform emergency cleanup when resource limits are exceeded.
        
        This method attempts to free resources immediately without
        waiting for normal cleanup procedures.
        """
        logger.warning("Performing emergency browser cleanup due to resource limits")
        
        try:
            if self._browser:
                # Close all pages immediately
                pages = self._browser.contexts
                for context in pages:
                    try:
                        await asyncio.wait_for(context.close(), timeout=2.0)
                    except Exception as e:
                        logger.debug(f"Error closing browser context during emergency cleanup: {e}")
                
                # Force close browser
                try:
                    await asyncio.wait_for(self._browser.close(), timeout=3.0)
                except Exception as e:
                    logger.debug(f"Error closing browser during emergency cleanup: {e}")
                
                self._browser = None
                
        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")
        
        logger.info("Emergency browser cleanup completed")
    
    async def _cleanup(self):
        """Clean up browser resources with comprehensive error handling."""
        cleanup_start_time = time.time()
        cleanup_errors = []
        
        try:
            logger.debug("Starting browser cleanup")
            
            # Close browser with timeout
            if self._browser:
                try:
                    logger.debug("Closing browser instance")
                    await asyncio.wait_for(
                        self._browser.close(),
                        timeout=10.0  # 10 second timeout for cleanup
                    )
                    logger.debug("Browser closed successfully")
                except asyncio.TimeoutError:
                    cleanup_errors.append("Browser close timed out")
                    logger.warning("Browser close timed out, attempting force cleanup")
                    
                    # Attempt to force close by terminating process
                    if self._process_id:
                        try:
                            browser_process = psutil.Process(self._process_id)
                            if browser_process.is_running():
                                browser_process.terminate()
                                logger.debug(f"Terminated browser process {self._process_id}")
                        except Exception as proc_error:
                            cleanup_errors.append(f"Failed to terminate browser process: {proc_error}")
                            
                except Exception as e:
                    cleanup_errors.append(f"Browser close error: {e}")
                    logger.warning(f"Error closing browser: {e}")
                finally:
                    self._browser = None
                
            # Stop Playwright with timeout
            if self._playwright:
                try:
                    logger.debug("Stopping Playwright")
                    await asyncio.wait_for(
                        self._playwright.stop(),
                        timeout=10.0  # 10 second timeout for cleanup
                    )
                    logger.debug("Playwright stopped successfully")
                except asyncio.TimeoutError:
                    cleanup_errors.append("Playwright stop timed out")
                    logger.warning("Playwright stop timed out")
                except Exception as e:
                    cleanup_errors.append(f"Playwright stop error: {e}")
                    logger.warning(f"Error stopping Playwright: {e}")
                finally:
                    self._playwright = None
                
        except Exception as e:
            cleanup_errors.append(f"Unexpected cleanup error: {e}")
            logger.error(f"Unexpected error during browser cleanup: {e}")
        finally:
            # Always reset state regardless of errors
            self._browser = None
            self._playwright = None
            self._process_id = None
            
            cleanup_duration = time.time() - cleanup_start_time
            
            if cleanup_errors:
                logger.warning(
                    f"Browser cleanup completed with errors in {cleanup_duration:.2f}s: "
                    f"{'; '.join(cleanup_errors)}"
                )
            else:
                logger.debug(f"Browser cleanup completed successfully in {cleanup_duration:.2f}s")


@asynccontextmanager
async def browser_context(config: Optional[Dict[str, Any]] = None):
    """
    Async context manager for browser operations.
    
    Args:
        config: Optional configuration for browser setup
        
    Yields:
        Tuple of (browser, page) ready for chat rendering
        
    Example:
        async with browser_context({'overlay_width': 400, 'overlay_height': 600}) as (browser, page):
            # Use browser and page for chat rendering
            pass
    """
    config = config or {}
    
    async with BrowserManager() as browser:
        manager = BrowserManager()
        manager._browser = browser  # Share the browser instance
        
        page = await manager.create_chat_page(config)
        try:
            yield browser, page
        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")