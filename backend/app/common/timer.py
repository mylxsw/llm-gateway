"""
Timer Module

Provides request latency statistics, supporting precise measurement of time to first byte and total time.
"""

import time
from typing import Optional


class Timer:
    """
    High-precision Timer
    
    Used to measure various latency metrics during request processing:
    - Time to First Byte (TTFB)
    - Total Time
    
    Uses time.perf_counter() to ensure high precision.
    
    Example:
        timer = Timer()
        timer.start()
        # ... Send request ...
        timer.mark_first_byte()  # Received first byte
        # ... Receive full response ...
        timer.stop()
        print(f"TTFB: {timer.first_byte_delay_ms}ms")
        print(f"Total: {timer.total_time_ms}ms")
    """
    
    def __init__(self):
        """Initialize Timer"""
        self._start_time: Optional[float] = None
        self._first_byte_time: Optional[float] = None
        self._end_time: Optional[float] = None
    
    def start(self) -> "Timer":
        """
        Start timing
        
        Returns:
            Timer: Returns self for chaining
        """
        self._start_time = time.perf_counter()
        self._first_byte_time = None
        self._end_time = None
        return self
    
    def mark_first_byte(self) -> "Timer":
        """
        Mark first byte time
        
        Called when the first byte of the response is received, used to calculate TTFB.
        Subsequent calls are ignored if already marked.
        
        Returns:
            Timer: Returns self for chaining
        """
        if self._first_byte_time is None:
            self._first_byte_time = time.perf_counter()
        return self
    
    def stop(self) -> "Timer":
        """
        Stop timing
        
        Returns:
            Timer: Returns self for chaining
        """
        self._end_time = time.perf_counter()
        # If first byte time not marked, use end time
        if self._first_byte_time is None:
            self._first_byte_time = self._end_time
        return self
    
    @property
    def first_byte_delay_ms(self) -> Optional[int]:
        """
        Get Time to First Byte (ms)
        
        Returns:
            Optional[int]: TTFB, or None if timing not completed
        """
        if self._start_time is None or self._first_byte_time is None:
            return None
        return int((self._first_byte_time - self._start_time) * 1000)
    
    @property
    def total_time_ms(self) -> Optional[int]:
        """
        Get Total Time (ms)
        
        Returns:
            Optional[int]: Total time, or None if timing not completed
        """
        if self._start_time is None or self._end_time is None:
            return None
        return int((self._end_time - self._start_time) * 1000)
    
    def reset(self) -> "Timer":
        """
        Reset Timer
        
        Returns:
            Timer: Returns self for chaining
        """
        self._start_time = None
        self._first_byte_time = None
        self._end_time = None
        return self