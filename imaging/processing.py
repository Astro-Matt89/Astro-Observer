"""
Image Processing System

Post-processing tools for stacked images:
- Histogram stretch (linear, log, asinh, gamma)
- Auto-stretch
- Sharpen (unsharp mask)
- Denoise
- Color combination (RGB, narrowband palettes)
"""

import numpy as np
from typing import Optional, Tuple
from enum import Enum


class StretchMethod(Enum):
    """Histogram stretch method"""
    LINEAR = "LINEAR"
    LOG = "LOG"
    ASINH = "ASINH"
    GAMMA = "GAMMA"
    AUTO = "AUTO"


class ImageProcessor:
    """
    Image processing tools
    
    Provides various post-processing operations for
    enhancing stacked astronomical images.
    """
    
    def __init__(self):
        """Initialize processor"""
        pass
    
    @staticmethod
    def stretch_linear(image: np.ndarray,
                      black_point: float,
                      white_point: float) -> np.ndarray:
        """
        Linear histogram stretch
        
        Maps [black_point, white_point] → [0, 1]
        
        Args:
            image: Input image
            black_point: Lower bound (becomes 0)
            white_point: Upper bound (becomes 1)
            
        Returns:
            Stretched image (0-1 range)
        """
        stretched = (image - black_point) / (white_point - black_point + 1e-9)
        return np.clip(stretched, 0.0, 1.0).astype(np.float32)
    
    @staticmethod
    def stretch_log(image: np.ndarray,
                   black_point: float = 0.0) -> np.ndarray:
        """
        Logarithmic stretch
        
        Good for bringing out faint details while
        compressing bright regions.
        
        Args:
            image: Input image
            black_point: Offset before log
            
        Returns:
            Stretched image
        """
        img_shifted = image - black_point
        img_shifted = np.clip(img_shifted, 1e-6, None)
        
        stretched = np.log1p(img_shifted)
        stretched = stretched / np.max(stretched)
        
        return stretched.astype(np.float32)
    
    @staticmethod
    def stretch_asinh(image: np.ndarray,
                     black_point: float = 0.0,
                     stretch_factor: float = 1.0) -> np.ndarray:
        """
        Inverse hyperbolic sine stretch
        
        Popular in astronomy - similar to log but smoother
        at low values. Good for wide dynamic range.
        
        Args:
            image: Input image
            black_point: Black point
            stretch_factor: Controls aggressiveness (higher = more contrast)
            
        Returns:
            Stretched image
        """
        img_shifted = image - black_point
        img_shifted = np.clip(img_shifted, 0, None)
        
        stretched = np.arcsinh(img_shifted * stretch_factor) / np.arcsinh(stretch_factor)
        stretched = np.clip(stretched, 0, 1)
        
        return stretched.astype(np.float32)
    
    @staticmethod
    def stretch_gamma(image: np.ndarray,
                     black_point: float,
                     white_point: float,
                     gamma: float = 2.2) -> np.ndarray:
        """
        Gamma stretch
        
        Linear stretch followed by gamma correction.
        gamma < 1: brighten midtones
        gamma > 1: darken midtones
        
        Args:
            image: Input image
            black_point: Black point
            white_point: White point
            gamma: Gamma exponent
            
        Returns:
            Stretched image
        """
        # Linear stretch first
        linear = ImageProcessor.stretch_linear(image, black_point, white_point)
        
        # Apply gamma
        stretched = np.power(linear, 1.0 / gamma)
        
        return stretched.astype(np.float32)
    
    @staticmethod
    def auto_stretch(image: np.ndarray,
                    percentile_low: float = 0.1,
                    percentile_high: float = 99.9,
                    method: StretchMethod = StretchMethod.LINEAR) -> np.ndarray:
        """
        Automatic histogram stretch
        
        Computes black/white points from percentiles
        
        Args:
            image: Input image
            percentile_low: Lower percentile for black point
            percentile_high: Upper percentile for white point
            method: Stretch method to use
            
        Returns:
            Auto-stretched image
        """
        black = np.percentile(image, percentile_low)
        white = np.percentile(image, percentile_high)
        
        if method == StretchMethod.LINEAR:
            return ImageProcessor.stretch_linear(image, black, white)
        elif method == StretchMethod.LOG:
            return ImageProcessor.stretch_log(image, black)
        elif method == StretchMethod.ASINH:
            return ImageProcessor.stretch_asinh(image, black, stretch_factor=10.0)
        elif method == StretchMethod.GAMMA:
            return ImageProcessor.stretch_gamma(image, black, white, gamma=2.2)
        else:
            return ImageProcessor.stretch_linear(image, black, white)
    
    @staticmethod
    def stretch(image: np.ndarray,
               method: StretchMethod = StretchMethod.LINEAR,
               black_point: Optional[float] = None,
               white_point: Optional[float] = None,
               gamma: float = 2.2,
               **kwargs) -> np.ndarray:
        """
        General stretch function
        
        Args:
            image: Input image
            method: Stretch method
            black_point: Black point (None for auto)
            white_point: White point (None for auto)
            gamma: Gamma value (for GAMMA method)
            **kwargs: Additional parameters
            
        Returns:
            Stretched image
        """
        if black_point is None or white_point is None:
            # Auto-determine from percentiles
            black_point = np.percentile(image, 0.1)
            white_point = np.percentile(image, 99.9)
        
        if method == StretchMethod.LINEAR:
            return ImageProcessor.stretch_linear(image, black_point, white_point)
        elif method == StretchMethod.LOG:
            return ImageProcessor.stretch_log(image, black_point)
        elif method == StretchMethod.ASINH:
            stretch_factor = kwargs.get('stretch_factor', 10.0)
            return ImageProcessor.stretch_asinh(image, black_point, stretch_factor)
        elif method == StretchMethod.GAMMA:
            return ImageProcessor.stretch_gamma(image, black_point, white_point, gamma)
        elif method == StretchMethod.AUTO:
            return ImageProcessor.auto_stretch(image)
        else:
            return ImageProcessor.stretch_linear(image, black_point, white_point)
    
    @staticmethod
    def sharpen(image: np.ndarray, amount: float = 1.0, radius: float = 1.0) -> np.ndarray:
        """
        Unsharp mask sharpening
        
        Enhances edges and fine details.
        
        Args:
            image: Input image (0-1 range)
            amount: Sharpening strength (0-2, typical: 0.5-1.5)
            radius: Blur radius for mask (pixels)
            
        Returns:
            Sharpened image
        """
        from scipy.ndimage import gaussian_filter
        
        # Create blurred version
        blurred = gaussian_filter(image, sigma=radius)
        
        # Compute unsharp mask
        mask = image - blurred
        
        # Add mask to original
        sharpened = image + amount * mask
        
        return np.clip(sharpened, 0, 1).astype(np.float32)
    
    @staticmethod
    def denoise(image: np.ndarray, sigma: float = 1.0, method: str = "bilateral") -> np.ndarray:
        """
        Denoise image
        
        Args:
            image: Input image
            sigma: Denoising strength
            method: "gaussian", "bilateral", or "median"
            
        Returns:
            Denoised image
        """
        if method == "gaussian":
            from scipy.ndimage import gaussian_filter
            return gaussian_filter(image, sigma=sigma).astype(np.float32)
        
        elif method == "median":
            from scipy.ndimage import median_filter
            kernel_size = int(2 * sigma + 1)
            return median_filter(image, size=kernel_size).astype(np.float32)
        
        elif method == "bilateral":
            # Simplified bilateral filter (edge-preserving)
            from scipy.ndimage import gaussian_filter
            # For simplicity, use Gaussian (true bilateral is more complex)
            return gaussian_filter(image, sigma=sigma).astype(np.float32)
        
        else:
            return image
    
    @staticmethod
    def to_uint8(image: np.ndarray) -> np.ndarray:
        """
        Convert float image to 8-bit unsigned integer
        
        Args:
            image: Float image (0-1 range)
            
        Returns:
            uint8 image
        """
        img_clipped = np.clip(image, 0, 1)
        return (img_clipped * 255).astype(np.uint8)
    
    @staticmethod
    def to_uint16(image: np.ndarray, bit_depth: int = 16) -> np.ndarray:
        """
        Convert float image to 16-bit unsigned integer
        
        Args:
            image: Float image (0-1 range)
            bit_depth: Effective bit depth (12, 14, 16)
            
        Returns:
            uint16 image
        """
        max_val = (1 << bit_depth) - 1
        img_clipped = np.clip(image, 0, 1)
        return (img_clipped * max_val).astype(np.uint16)


class ColorProcessor:
    """
    Color image processing
    
    Handles RGB and narrowband color combination
    """
    
    @staticmethod
    def combine_rgb(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
        """
        Combine R, G, B channels into RGB image
        
        Args:
            r, g, b: Individual channels (0-1 range)
            
        Returns:
            RGB image (H, W, 3)
        """
        # Ensure same shape
        assert r.shape == g.shape == b.shape, "Channels must have same shape"
        
        rgb = np.stack([r, g, b], axis=-1)
        return rgb.astype(np.float32)
    
    @staticmethod
    def combine_narrowband_HOO(ha: np.ndarray, oiii: np.ndarray) -> np.ndarray:
        """
        HOO palette (Ha-OIII-OIII)
        
        Popular narrowband palette:
        R = Ha
        G = OIII
        B = OIII
        
        Gives natural-looking colors with blue/teal OIII regions
        and red Ha regions.
        
        Args:
            ha: H-alpha channel
            oiii: OIII channel
            
        Returns:
            RGB image
        """
        return ColorProcessor.combine_rgb(ha, oiii, oiii)
    
    @staticmethod
    def combine_narrowband_SHO(sii: np.ndarray, ha: np.ndarray, 
                               oiii: np.ndarray) -> np.ndarray:
        """
        SHO palette (Hubble palette)
        
        Famous Hubble Space Telescope palette:
        R = SII
        G = Ha
        B = OIII
        
        Gives dramatic gold/blue appearance.
        
        Args:
            sii: SII channel
            ha: H-alpha channel
            oiii: OIII channel
            
        Returns:
            RGB image
        """
        return ColorProcessor.combine_rgb(sii, ha, oiii)
    
    @staticmethod
    def combine_narrowband_HOS(ha: np.ndarray, oiii: np.ndarray,
                               sii: np.ndarray) -> np.ndarray:
        """
        HOS palette
        
        Alternative palette:
        R = Ha
        G = OIII
        B = SII
        
        Args:
            ha: H-alpha channel
            oiii: OIII channel
            sii: SII channel
            
        Returns:
            RGB image
        """
        return ColorProcessor.combine_rgb(ha, oiii, sii)
    
    @staticmethod
    def apply_color_balance(rgb: np.ndarray,
                           r_scale: float = 1.0,
                           g_scale: float = 1.0,
                           b_scale: float = 1.0) -> np.ndarray:
        """
        Apply color balance adjustment
        
        Args:
            rgb: RGB image
            r_scale, g_scale, b_scale: Channel multipliers
            
        Returns:
            Balanced RGB image
        """
        balanced = rgb.copy()
        balanced[..., 0] *= r_scale
        balanced[..., 1] *= g_scale
        balanced[..., 2] *= b_scale
        
        return np.clip(balanced, 0, 1).astype(np.float32)
    
    @staticmethod
    def apply_saturation(rgb: np.ndarray, saturation: float = 1.0) -> np.ndarray:
        """
        Adjust color saturation
        
        Args:
            rgb: RGB image
            saturation: Saturation multiplier (0=grayscale, 1=original, >1=boosted)
            
        Returns:
            Saturated RGB image
        """
        # Convert to luminance
        luminance = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        luminance = luminance[..., np.newaxis]
        
        # Interpolate between grayscale and color
        result = luminance + saturation * (rgb - luminance)
        
        return np.clip(result, 0, 1).astype(np.float32)


class HistogramAnalyzer:
    """
    Histogram analysis tools
    """
    
    @staticmethod
    def compute_histogram(image: np.ndarray, bins: int = 256) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute image histogram
        
        Args:
            image: Input image
            bins: Number of bins
            
        Returns:
            (counts, bin_edges)
        """
        counts, edges = np.histogram(image.ravel(), bins=bins, range=(0, 1))
        return counts, edges
    
    @staticmethod
    def compute_statistics(image: np.ndarray) -> dict:
        """
        Compute comprehensive image statistics
        
        Args:
            image: Input image
            
        Returns:
            Dictionary with statistics
        """
        return {
            'mean': float(np.mean(image)),
            'median': float(np.median(image)),
            'std': float(np.std(image)),
            'min': float(np.min(image)),
            'max': float(np.max(image)),
            'p01': float(np.percentile(image, 0.1)),
            'p99': float(np.percentile(image, 99.9)),
            'q25': float(np.percentile(image, 25)),
            'q75': float(np.percentile(image, 75)),
        }
    
    @staticmethod
    def estimate_background(image: np.ndarray) -> float:
        """
        Estimate background level (sky background)
        
        Uses median of lower half of histogram
        
        Args:
            image: Input image
            
        Returns:
            Estimated background level
        """
        median = np.median(image)
        # Background is typically in lower half
        lower_half = image[image < median]
        if len(lower_half) > 0:
            return float(np.median(lower_half))
        else:
            return float(median)
    
    @staticmethod
    def estimate_noise(image: np.ndarray) -> float:
        """
        Estimate image noise level
        
        Uses robust MAD (Median Absolute Deviation) estimator
        
        Args:
            image: Input image
            
        Returns:
            Estimated noise (standard deviation)
        """
        median = np.median(image)
        mad = np.median(np.abs(image - median))
        # MAD to sigma conversion factor
        sigma = 1.4826 * mad
        return float(sigma)
