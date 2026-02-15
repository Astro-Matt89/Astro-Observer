"""
Calibration System

Implements standard astronomical image calibration pipeline:
- Master dark/flat/bias creation
- Light frame calibration
- Cosmetic correction (hot/cold pixels)
"""

import numpy as np
from typing import Optional, List
from .frames import Frame, FrameType, FrameSet


class Calibrator:
    """
    Image calibration engine
    
    Implements the standard calibration equation:
    Calibrated = (Light - Dark - Bias) / Flat
    
    Also handles master frame creation and cosmetic corrections.
    """
    
    def __init__(self):
        """Initialize calibrator"""
        pass
    
    @staticmethod
    def create_master_bias(bias_frames: List[Frame]) -> Optional[Frame]:
        """
        Create master bias frame by median combining
        
        Bias frames capture electronic baseline + read noise.
        Median combining removes cosmic rays and hot pixels.
        
        Args:
            bias_frames: List of bias frames
            
        Returns:
            Master bias frame, or None if no frames
        """
        if not bias_frames:
            return None
        
        # Stack all bias frames
        stack = np.stack([f.data for f in bias_frames], axis=0)
        
        # Median combine (robust to outliers)
        master_data = np.median(stack, axis=0).astype(np.float32)
        
        # Create master frame with metadata from first frame
        master_meta = bias_frames[0].meta
        master_meta.frame_type = FrameType.BIAS
        master_meta.target_name = f"MASTER_BIAS_{len(bias_frames)}x"
        
        master = Frame(master_data, master_meta)
        master.add_calibration_step(f"Master bias from {len(bias_frames)} frames (median)")
        
        return master
    
    @staticmethod
    def create_master_dark(dark_frames: List[Frame], 
                          master_bias: Optional[Frame] = None) -> Optional[Frame]:
        """
        Create master dark frame
        
        Dark frames capture thermal + electronic noise.
        If bias is available, subtract it first (more accurate).
        
        Args:
            dark_frames: List of dark frames
            master_bias: Optional master bias for subtraction
            
        Returns:
            Master dark frame, or None if no frames
        """
        if not dark_frames:
            return None
        
        # Optionally bias-subtract each dark first
        if master_bias is not None:
            darks_corrected = []
            for dark in dark_frames:
                corrected = dark.data - master_bias.data
                darks_corrected.append(corrected)
            stack = np.stack(darks_corrected, axis=0)
        else:
            stack = np.stack([f.data for f in dark_frames], axis=0)
        
        # Median combine
        master_data = np.median(stack, axis=0).astype(np.float32)
        
        # Create master frame
        master_meta = dark_frames[0].meta
        master_meta.frame_type = FrameType.DARK
        master_meta.target_name = f"MASTER_DARK_{len(dark_frames)}x"
        
        master = Frame(master_data, master_meta)
        
        if master_bias is not None:
            master.add_calibration_step(f"Master dark from {len(dark_frames)} frames, bias-subtracted (median)")
        else:
            master.add_calibration_step(f"Master dark from {len(dark_frames)} frames (median)")
        
        return master
    
    @staticmethod
    def create_master_flat(flat_frames: List[Frame],
                          master_dark: Optional[Frame] = None,
                          master_bias: Optional[Frame] = None) -> Optional[Frame]:
        """
        Create master flat frame
        
        Flat frames correct vignetting, dust shadows, pixel response variations.
        Should be dark-subtracted first, then normalized to mean=1.
        
        Args:
            flat_frames: List of flat frames
            master_dark: Optional master dark (same exposure as flats)
            master_bias: Optional master bias
            
        Returns:
            Master flat frame (normalized), or None if no frames
        """
        if not flat_frames:
            return None
        
        # Calibrate each flat
        flats_corrected = []
        for flat in flat_frames:
            corrected = flat.data.copy()
            
            # Subtract dark (if available and matching exposure)
            if master_dark is not None:
                if abs(flat.meta.exposure_s - master_dark.meta.exposure_s) < 0.01:
                    corrected = corrected - master_dark.data
                elif master_bias is not None:
                    # If dark exposure doesn't match, use bias instead
                    corrected = corrected - master_bias.data
            elif master_bias is not None:
                corrected = corrected - master_bias.data
            
            flats_corrected.append(corrected)
        
        stack = np.stack(flats_corrected, axis=0)
        
        # Median combine
        master_data = np.median(stack, axis=0).astype(np.float32)
        
        # Normalize to mean = 1.0 (preserves relative variations)
        mean_val = np.mean(master_data)
        if mean_val > 0:
            master_data = master_data / mean_val
        
        # Clip to avoid division by zero later
        master_data = np.clip(master_data, 0.1, 10.0)
        
        # Create master frame
        master_meta = flat_frames[0].meta
        master_meta.frame_type = FrameType.FLAT
        master_meta.target_name = f"MASTER_FLAT_{len(flat_frames)}x"
        
        master = Frame(master_data, master_meta)
        master.add_calibration_step(f"Master flat from {len(flat_frames)} frames, normalized (median)")
        
        return master
    
    @staticmethod
    def calibrate_light(light: Frame,
                       master_dark: Optional[Frame] = None,
                       master_flat: Optional[Frame] = None,
                       master_bias: Optional[Frame] = None) -> Frame:
        """
        Calibrate light frame using masters
        
        Applies the standard calibration equation:
        Calibrated = (Light - Dark - Bias) / Flat
        
        Args:
            light: Light frame to calibrate
            master_dark: Master dark frame (same exposure)
            master_flat: Master flat frame (normalized)
            master_bias: Master bias frame
            
        Returns:
            Calibrated light frame
        """
        calibrated = light.data.copy()
        calibration_steps = []
        
        # Step 1: Subtract bias
        if master_bias is not None:
            calibrated = calibrated - master_bias.data
            calibration_steps.append("bias subtraction")
        
        # Step 2: Subtract dark
        if master_dark is not None:
            # Check exposure match
            if abs(light.meta.exposure_s - master_dark.meta.exposure_s) < 0.01:
                calibrated = calibrated - master_dark.data
                calibration_steps.append("dark subtraction")
            else:
                # Scale dark to match exposure (simple linear scaling)
                scale = light.meta.exposure_s / master_dark.meta.exposure_s
                calibrated = calibrated - (master_dark.data * scale)
                calibration_steps.append(f"dark subtraction (scaled {scale:.2f}x)")
        
        # Step 3: Divide by flat
        if master_flat is not None:
            calibrated = calibrated / (master_flat.data + 1e-6)
            calibration_steps.append("flat division")
        
        # Clip negative values (shouldn't happen with good calibration)
        calibrated = np.clip(calibrated, 0, None)
        
        # Create calibrated frame
        cal_frame = Frame(calibrated, light.meta)
        
        step_desc = " + ".join(calibration_steps) if calibration_steps else "no calibration"
        cal_frame.add_calibration_step(step_desc)
        
        return cal_frame
    
    @staticmethod
    def cosmetic_correction(frame: Frame, 
                           method: str = "median",
                           kernel_size: int = 3) -> Frame:
        """
        Correct hot/cold pixels and cosmic rays
        
        Args:
            frame: Frame to correct
            method: Correction method ("median" or "mean")
            kernel_size: Size of kernel for replacement (3, 5, 7)
            
        Returns:
            Corrected frame
        """
        from scipy.ndimage import median_filter, uniform_filter
        
        data = frame.data.copy()
        
        # Detect outliers (simple sigma-clipping approach)
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        sigma = 1.4826 * mad  # Robust sigma estimate
        
        # Pixels > 5-sigma are likely defects
        outlier_mask = np.abs(data - median) > (5.0 * sigma)
        
        # Replace outliers with local median/mean
        if method == "median":
            filtered = median_filter(data, size=kernel_size)
        else:
            filtered = uniform_filter(data, size=kernel_size)
        
        corrected = np.where(outlier_mask, filtered, data)
        
        # Create corrected frame
        cor_frame = Frame(corrected, frame.meta)
        n_corrected = np.sum(outlier_mask)
        cor_frame.add_calibration_step(f"Cosmetic correction ({n_corrected} pixels, {method})")
        
        return cor_frame
    
    @staticmethod
    def batch_calibrate_lights(light_frames: List[Frame],
                              master_dark: Optional[Frame] = None,
                              master_flat: Optional[Frame] = None,
                              master_bias: Optional[Frame] = None,
                              apply_cosmetic: bool = True) -> List[Frame]:
        """
        Calibrate multiple light frames
        
        Args:
            light_frames: List of light frames
            master_dark: Master dark
            master_flat: Master flat
            master_bias: Master bias
            apply_cosmetic: Apply cosmetic correction
            
        Returns:
            List of calibrated frames
        """
        calibrated = []
        
        for light in light_frames:
            # Calibrate
            cal = Calibrator.calibrate_light(light, master_dark, master_flat, master_bias)
            
            # Optionally apply cosmetic correction
            if apply_cosmetic:
                cal = Calibrator.cosmetic_correction(cal)
            
            calibrated.append(cal)
        
        return calibrated


class CalibrationLibrary:
    """
    Manages a library of master calibration frames
    
    Organizes masters by exposure time, binning, temperature, etc.
    for easy matching during calibration.
    """
    
    def __init__(self):
        """Initialize library"""
        self.master_biases: List[Frame] = []
        self.master_darks: List[Frame] = []
        self.master_flats: dict[str, List[Frame]] = {}  # Keyed by filter
    
    def add_master_bias(self, master_bias: Frame):
        """Add master bias to library"""
        self.master_biases.append(master_bias)
    
    def add_master_dark(self, master_dark: Frame):
        """Add master dark to library"""
        self.master_darks.append(master_dark)
    
    def add_master_flat(self, master_flat: Frame, filter_name: str):
        """Add master flat to library"""
        if filter_name not in self.master_flats:
            self.master_flats[filter_name] = []
        self.master_flats[filter_name].append(master_flat)
    
    def get_best_bias(self, binning: int = 1) -> Optional[Frame]:
        """
        Find best matching bias frame
        
        Args:
            binning: Binning mode
            
        Returns:
            Best matching bias, or None
        """
        if not self.master_biases:
            return None
        
        # For now, just return most recent
        # TODO: match by binning, temperature
        return self.master_biases[-1]
    
    def get_best_dark(self, exposure_s: float, 
                     temperature_c: Optional[float] = None,
                     tolerance_s: float = 1.0) -> Optional[Frame]:
        """
        Find best matching dark frame
        
        Args:
            exposure_s: Exposure time to match
            temperature_c: Temperature to match (optional)
            tolerance_s: Tolerance for exposure matching
            
        Returns:
            Best matching dark, or None
        """
        if not self.master_darks:
            return None
        
        # Find darks with matching exposure
        candidates = [d for d in self.master_darks 
                     if abs(d.meta.exposure_s - exposure_s) < tolerance_s]
        
        if not candidates:
            return None
        
        # If temperature specified, prefer closest match
        if temperature_c is not None:
            candidates.sort(key=lambda d: abs(d.meta.temperature_c - temperature_c))
        
        return candidates[0]
    
    def get_best_flat(self, filter_name: str) -> Optional[Frame]:
        """
        Find best matching flat frame
        
        Args:
            filter_name: Filter name
            
        Returns:
            Best matching flat, or None
        """
        if filter_name not in self.master_flats:
            return None
        
        if not self.master_flats[filter_name]:
            return None
        
        # Return most recent
        return self.master_flats[filter_name][-1]
    
    def clear(self):
        """Clear all masters from library"""
        self.master_biases.clear()
        self.master_darks.clear()
        self.master_flats.clear()
    
    def __repr__(self) -> str:
        n_flats = sum(len(v) for v in self.master_flats.values())
        return (f"CalibrationLibrary(biases={len(self.master_biases)}, "
                f"darks={len(self.master_darks)}, flats={n_flats})")
