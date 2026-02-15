"""
Stacking System

Implements frame alignment and stacking algorithms:
- Mean stacking (simple average)
- Median stacking (robust to outliers)
- Sigma-clipped mean (reject outliers, then average)
- Simple star-based alignment
"""

import numpy as np
from enum import Enum
from typing import List, Optional, Tuple
from .frames import Frame
from scipy.ndimage import shift as scipy_shift


class StackMethod(Enum):
    """Stacking method"""
    MEAN = "MEAN"
    MEDIAN = "MEDIAN"
    SIGMA_CLIP = "SIGMA_CLIP"


class StackingEngine:
    """
    Frame stacking engine
    
    Handles alignment and combining multiple frames to improve SNR.
    """
    
    def __init__(self):
        """Initialize stacking engine"""
        pass
    
    @staticmethod
    def stack_mean(frames: List[Frame]) -> np.ndarray:
        """
        Simple mean stacking (average)
        
        SNR improvement: √N
        Fast but sensitive to outliers (cosmic rays, satellites)
        
        Args:
            frames: List of frames to stack
            
        Returns:
            Stacked image
        """
        if not frames:
            raise ValueError("No frames to stack")
        
        stack = np.stack([f.data for f in frames], axis=0)
        result = np.mean(stack, axis=0).astype(np.float32)
        
        return result
    
    @staticmethod
    def stack_median(frames: List[Frame]) -> np.ndarray:
        """
        Median stacking
        
        SNR improvement: √(π/2 · N) ≈ 0.886√N
        Robust to outliers but slightly less SNR than mean
        
        Args:
            frames: List of frames to stack
            
        Returns:
            Stacked image
        """
        if not frames:
            raise ValueError("No frames to stack")
        
        stack = np.stack([f.data for f in frames], axis=0)
        result = np.median(stack, axis=0).astype(np.float32)
        
        return result
    
    @staticmethod
    def stack_sigma_clip(frames: List[Frame],
                        sigma_low: float = 3.0,
                        sigma_high: float = 3.0,
                        iterations: int = 1) -> np.ndarray:
        """
        Sigma-clipped mean stacking
        
        Best of both worlds: rejects outliers, then averages
        SNR improvement: ≈ √N (after rejection)
        
        Args:
            frames: List of frames to stack
            sigma_low: Lower sigma threshold for rejection
            sigma_high: Upper sigma threshold for rejection
            iterations: Number of clipping iterations
            
        Returns:
            Stacked image
        """
        if not frames:
            raise ValueError("No frames to stack")
        
        stack = np.stack([f.data for f in frames], axis=0)
        n_frames = len(frames)
        
        # Start with all pixels valid
        mask = np.ones_like(stack, dtype=bool)
        
        for _ in range(iterations):
            # Compute mean and std of non-masked pixels
            masked_stack = np.ma.array(stack, mask=~mask)
            mean = np.ma.mean(masked_stack, axis=0)
            std = np.ma.std(masked_stack, axis=0)
            
            # Update mask: reject pixels outside sigma range
            for i in range(n_frames):
                low_outlier = stack[i] < (mean - sigma_low * std)
                high_outlier = stack[i] > (mean + sigma_high * std)
                mask[i] = mask[i] & ~low_outlier & ~high_outlier
        
        # Final mean of non-rejected pixels
        masked_stack = np.ma.array(stack, mask=~mask)
        result = np.ma.mean(masked_stack, axis=0).filled(0).astype(np.float32)
        
        return result
    
    @staticmethod
    def stack(frames: List[Frame], method: StackMethod = StackMethod.MEAN) -> np.ndarray:
        """
        Stack frames using specified method
        
        Args:
            frames: List of frames
            method: Stacking method
            
        Returns:
            Stacked image
        """
        if method == StackMethod.MEAN:
            return StackingEngine.stack_mean(frames)
        elif method == StackMethod.MEDIAN:
            return StackingEngine.stack_median(frames)
        elif method == StackMethod.SIGMA_CLIP:
            return StackingEngine.stack_sigma_clip(frames)
        else:
            raise ValueError(f"Unknown stacking method: {method}")
    
    @staticmethod
    def estimate_shifts(frames: List[Frame], 
                       reference_idx: int = 0,
                       region_size: int = 256) -> List[Tuple[float, float]]:
        """
        Estimate frame shifts using cross-correlation
        
        Simple implementation: uses central region of each frame
        to compute relative shift using phase correlation.
        
        Args:
            frames: List of frames
            reference_idx: Index of reference frame
            region_size: Size of region for correlation
            
        Returns:
            List of (dx, dy) shifts for each frame
        """
        if not frames:
            return []
        
        reference = frames[reference_idx].data
        h, w = reference.shape
        
        # Extract central region from reference
        cy, cx = h // 2, w // 2
        r = region_size // 2
        ref_region = reference[cy-r:cy+r, cx-r:cx+r]
        
        shifts = []
        
        for frame in frames:
            if frame is frames[reference_idx]:
                shifts.append((0.0, 0.0))
                continue
            
            # Extract central region from this frame
            frame_region = frame.data[cy-r:cy+r, cx-r:cx+r]
            
            # Compute cross-correlation using FFT
            # (simplified version - production code would use phase correlation)
            from scipy.signal import correlate2d
            
            correlation = correlate2d(ref_region, frame_region, mode='same')
            
            # Find peak
            peak_y, peak_x = np.unravel_index(np.argmax(correlation), correlation.shape)
            
            # Convert to shift (relative to center)
            dy = peak_y - r
            dx = peak_x - r
            
            shifts.append((float(dx), float(dy)))
        
        return shifts
    
    @staticmethod
    def align_frames(frames: List[Frame],
                    reference_idx: int = 0,
                    subpixel: bool = False) -> List[Frame]:
        """
        Align frames to reference using shift
        
        This is a simplified alignment. Production code would use
        star pattern matching (triangle algorithm) for robustness.
        
        Args:
            frames: List of frames to align
            reference_idx: Index of reference frame
            subpixel: Use subpixel interpolation (slower but more accurate)
            
        Returns:
            List of aligned frames
        """
        if not frames:
            return []
        
        # Estimate shifts
        shifts = StackingEngine.estimate_shifts(frames, reference_idx)
        
        aligned = []
        
        for frame, (dx, dy) in zip(frames, shifts):
            if abs(dx) < 0.1 and abs(dy) < 0.1:
                # No shift needed
                aligned.append(frame)
                continue
            
            # Apply shift
            if subpixel:
                # Use scipy's shift with interpolation
                shifted_data = scipy_shift(frame.data, shift=(dy, dx), 
                                          order=1, mode='constant', cval=0)
            else:
                # Integer pixel shift (fast)
                shifted_data = np.roll(np.roll(frame.data, int(dy), axis=0), 
                                      int(dx), axis=1)
            
            # Create aligned frame
            aligned_frame = Frame(shifted_data, frame.meta)
            aligned_frame.add_calibration_step(f"Aligned (dx={dx:.2f}, dy={dy:.2f})")
            aligned.append(aligned_frame)
        
        return aligned
    
    @staticmethod
    def compute_snr_improvement(n_frames: int, method: StackMethod) -> float:
        """
        Compute theoretical SNR improvement factor
        
        Args:
            n_frames: Number of frames
            method: Stacking method
            
        Returns:
            SNR improvement factor (e.g., 3.16 for 10 frames mean stack)
        """
        if n_frames <= 0:
            return 1.0
        
        if method == StackMethod.MEAN:
            return np.sqrt(n_frames)
        elif method == StackMethod.MEDIAN:
            # Median is slightly less efficient
            return np.sqrt(np.pi / 2.0 * n_frames)
        elif method == StackMethod.SIGMA_CLIP:
            # Assume ~5% rejection, slight loss of efficiency
            return np.sqrt(n_frames * 0.95)
        else:
            return np.sqrt(n_frames)
    
    @staticmethod
    def estimate_final_snr(frames: List[Frame], method: StackMethod) -> float:
        """
        Estimate final SNR after stacking
        
        Assumes average SNR of input frames is representative
        
        Args:
            frames: Input frames
            method: Stacking method
            
        Returns:
            Estimated final SNR
        """
        if not frames:
            return 0.0
        
        # Get SNRs from frames (if available)
        snrs = [f.meta.snr for f in frames if f.meta.snr is not None]
        
        if not snrs:
            # Estimate SNR from signal/noise
            # SNR ≈ mean / std (rough approximation)
            mean_signal = np.mean([f.meta.mean_adu for f in frames])
            mean_noise = np.mean([f.meta.std_adu for f in frames])
            if mean_noise > 0:
                base_snr = mean_signal / mean_noise
            else:
                base_snr = 10.0  # Default
        else:
            base_snr = np.mean(snrs)
        
        improvement = StackingEngine.compute_snr_improvement(len(frames), method)
        
        return base_snr * improvement


class AdvancedAligner:
    """
    Advanced alignment using star pattern matching
    
    More robust than simple cross-correlation, works even with
    rotation, scale changes, and large shifts.
    
    This is a placeholder for future implementation of triangle
    algorithm or similar star-matching techniques.
    """
    
    def __init__(self):
        """Initialize advanced aligner"""
        self.max_stars = 100  # Limit for performance
    
    def detect_stars(self, image: np.ndarray, 
                    threshold_sigma: float = 5.0) -> List[Tuple[float, float]]:
        """
        Detect bright stars in image
        
        Args:
            image: Input image
            threshold_sigma: Detection threshold in sigma units
            
        Returns:
            List of (x, y) star positions
        """
        # Simple star detection using local maxima
        from scipy.ndimage import maximum_filter
        
        # Find local maxima
        local_max = maximum_filter(image, size=5)
        maxima = (image == local_max)
        
        # Threshold
        median = np.median(image)
        mad = np.median(np.abs(image - median))
        sigma = 1.4826 * mad
        threshold = median + threshold_sigma * sigma
        
        stars = maxima & (image > threshold)
        
        # Get positions
        ys, xs = np.where(stars)
        
        # Sort by brightness and limit
        brightnesses = image[ys, xs]
        indices = np.argsort(brightnesses)[::-1][:self.max_stars]
        
        positions = [(float(xs[i]), float(ys[i])) for i in indices]
        
        return positions
    
    def match_stars(self, stars1: List[Tuple[float, float]],
                   stars2: List[Tuple[float, float]],
                   tolerance: float = 2.0) -> List[Tuple[int, int]]:
        """
        Match stars between two lists
        
        This is a placeholder - production code would use triangle
        matching for robustness.
        
        Args:
            stars1: Stars in first image
            stars2: Stars in second image
            tolerance: Matching tolerance in pixels
            
        Returns:
            List of (idx1, idx2) matched pairs
        """
        # Simple nearest-neighbor matching
        # TODO: Implement triangle algorithm for robustness
        
        matches = []
        
        for i, (x1, y1) in enumerate(stars1):
            best_j = None
            best_dist = float('inf')
            
            for j, (x2, y2) in enumerate(stars2):
                dist = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)
                if dist < best_dist and dist < tolerance:
                    best_dist = dist
                    best_j = j
            
            if best_j is not None:
                matches.append((i, best_j))
        
        return matches
    
    def compute_transform(self, 
                         matches: List[Tuple[int, int]],
                         stars1: List[Tuple[float, float]],
                         stars2: List[Tuple[float, float]]) -> Optional[np.ndarray]:
        """
        Compute transformation matrix from matched stars
        
        Args:
            matches: List of matched star indices
            stars1: Stars in first image
            stars2: Stars in second image
            
        Returns:
            3x3 transformation matrix (affine), or None if not enough matches
        """
        if len(matches) < 3:
            return None
        
        # Extract matched positions
        pts1 = np.array([stars1[i] for i, _ in matches])
        pts2 = np.array([stars2[j] for _, j in matches])
        
        # Compute simple translation (could be extended to full affine)
        translation = np.mean(pts2 - pts1, axis=0)
        
        # Create affine matrix (translation only for now)
        matrix = np.eye(3)
        matrix[0, 2] = translation[0]
        matrix[1, 2] = translation[1]
        
        return matrix
