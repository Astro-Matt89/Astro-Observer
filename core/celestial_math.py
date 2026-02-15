"""
Celestial Mathematics

Coordinate conversions and projections for the sky chart:
- RA/Dec (J2000) <-> Altitude/Azimuth (geocentric)
- Stereographic projection for sky chart rendering
- Time calculations (LST, JD)
"""

import math
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Observer:
    """Observer location"""
    latitude_deg: float   # Positive = North
    longitude_deg: float  # Positive = East
    elevation_m: float = 0.0
    
    def __post_init__(self):
        self.lat_rad = math.radians(self.latitude_deg)
        self.lon_rad = math.radians(self.longitude_deg)


# Default observer: Parma, Italy
PARMA_OBSERVER = Observer(latitude_deg=44.801, longitude_deg=10.328)


def julian_date(dt: datetime) -> float:
    """
    Calculate Julian Date from datetime
    
    Args:
        dt: datetime (UTC)
    
    Returns:
        Julian Date
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    y = dt.year
    m = dt.month
    d = dt.day
    h = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    
    if m <= 2:
        y -= 1
        m += 12
    
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + h / 24.0 + B - 1524.5
    return jd


def greenwich_sidereal_time(jd: float) -> float:
    """
    Calculate Greenwich Mean Sidereal Time in degrees
    
    Args:
        jd: Julian Date
    
    Returns:
        GMST in degrees [0, 360)
    """
    T = (jd - 2451545.0) / 36525.0
    theta = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + \
            T * T * (0.000387933 - T / 38710000.0)
    return theta % 360.0


def local_sidereal_time(jd: float, longitude_deg: float) -> float:
    """
    Calculate Local Sidereal Time in degrees
    
    Args:
        jd: Julian Date
        longitude_deg: Observer longitude (positive East)
    
    Returns:
        LST in degrees [0, 360)
    """
    gmst = greenwich_sidereal_time(jd)
    lst = (gmst + longitude_deg) % 360.0
    return lst


def radec_to_altaz(ra_deg: float, dec_deg: float,
                   lst_deg: float, lat_deg: float) -> Tuple[float, float]:
    """
    Convert RA/Dec to Altitude/Azimuth
    
    Args:
        ra_deg: Right Ascension in degrees
        dec_deg: Declination in degrees
        lst_deg: Local Sidereal Time in degrees
        lat_deg: Observer latitude in degrees
    
    Returns:
        (altitude_deg, azimuth_deg) - alt in [-90, 90], az in [0, 360)
    """
    # Hour angle
    ha = math.radians((lst_deg - ra_deg) % 360.0)
    dec = math.radians(dec_deg)
    lat = math.radians(lat_deg)
    
    # Altitude
    sin_alt = math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(ha)
    alt = math.asin(max(-1.0, min(1.0, sin_alt)))
    
    # Azimuth
    cos_az = (math.sin(dec) - math.sin(alt) * math.sin(lat)) / (math.cos(alt) * math.cos(lat))
    cos_az = max(-1.0, min(1.0, cos_az))
    az = math.acos(cos_az)
    
    if math.sin(ha) > 0:
        az = 2 * math.pi - az
    
    return math.degrees(alt), math.degrees(az)


def altaz_to_radec(alt_deg: float, az_deg: float,
                   lst_deg: float, lat_deg: float) -> Tuple[float, float]:
    """
    Convert Altitude/Azimuth to RA/Dec (inverse of radec_to_altaz)
    
    Returns:
        (ra_deg, dec_deg)
    """
    alt = math.radians(alt_deg)
    az  = math.radians(az_deg)
    lat = math.radians(lat_deg)
    
    sin_dec = math.sin(alt) * math.sin(lat) + math.cos(alt) * math.cos(lat) * math.cos(az)
    dec = math.asin(max(-1.0, min(1.0, sin_dec)))
    
    cos_ha = (math.sin(alt) - math.sin(dec) * math.sin(lat)) / (math.cos(dec) * math.cos(lat))
    cos_ha = max(-1.0, min(1.0, cos_ha))
    ha = math.acos(cos_ha)
    
    if math.sin(az) > 0:
        ha = 2 * math.pi - ha
    
    ra = (lst_deg - math.degrees(ha)) % 360.0
    return ra, math.degrees(dec)


class SkyProjection:
    """
    Stereographic sky chart projection.
    
    Projects RA/Dec coordinates onto a 2D plane centered on
    a given RA/Dec center point.
    
    Uses an equatorial (RA/Dec) projection - north up, east left
    (as seen in a standard star atlas).
    """
    
    def __init__(self, center_ra: float, center_dec: float,
                 scale_deg_per_px: float, width: int, height: int):
        """
        Args:
            center_ra: RA of chart center (degrees)
            center_dec: Dec of chart center (degrees)
            scale_deg_per_px: Sky degrees per screen pixel
            width, height: Screen dimensions
        """
        self.center_ra  = center_ra
        self.center_dec = center_dec
        self.scale      = scale_deg_per_px
        self.width      = width
        self.height     = height
        
        self.cx = width  // 2
        self.cy = height // 2
        
        # Precompute
        self._cos_dec0 = math.cos(math.radians(center_dec))
        self._sin_dec0 = math.sin(math.radians(center_dec))
    
    def project(self, ra_deg: float, dec_deg: float) -> Optional[Tuple[int, int]]:
        """
        Project RA/Dec to screen (x, y).
        Returns None if point is behind the sphere.
        """
        ra  = math.radians(ra_deg)
        dec = math.radians(dec_deg)
        ra0 = math.radians(self.center_ra)
        
        cos_dec  = math.cos(dec)
        sin_dec  = math.sin(dec)
        cos_dra  = math.cos(ra - ra0)
        
        # Stereographic projection - guard against antipodal points
        denom = 1.0 + self._sin_dec0 * sin_dec + self._cos_dec0 * cos_dec * cos_dra
        if abs(denom) < 1e-10 or denom <= 0:
            return None
        k = 2.0 / denom
        
        x_proj = k * cos_dec * math.sin(ra - ra0)
        y_proj = k * (self._cos_dec0 * sin_dec - self._sin_dec0 * cos_dec * cos_dra)
        
        # Convert to screen pixels (note: RA increases to the left)
        px = self.cx - int(x_proj / math.radians(self.scale))
        py = self.cy - int(y_proj / math.radians(self.scale))
        
        return px, py
    
    def unproject(self, px: int, py: int) -> Tuple[float, float]:
        """
        Convert screen (x, y) back to RA/Dec.
        
        Returns:
            (ra_deg, dec_deg)
        """
        # Convert pixels to projection units
        x = -(px - self.cx) * math.radians(self.scale)
        y = -(py - self.cy) * math.radians(self.scale)
        
        rho = math.sqrt(x * x + y * y)
        
        if rho < 1e-10:
            return self.center_ra, self.center_dec
        
        c = 2.0 * math.atan2(rho, 2.0)
        
        sin_c = math.sin(c)
        cos_c = math.cos(c)
        
        lat = math.asin(cos_c * self._sin_dec0 + (y * sin_c * self._cos_dec0 / rho))
        lon = math.radians(self.center_ra) + math.atan2(
            x * sin_c,
            rho * self._cos_dec0 * cos_c - y * self._sin_dec0 * sin_c
        )
        
        return math.degrees(lon) % 360.0, math.degrees(lat)
    
    def is_on_screen(self, px: int, py: int, margin: int = 10) -> bool:
        """Check if pixel coordinates are on screen"""
        return (-margin <= px <= self.width + margin and
                -margin <= py <= self.height + margin)
    
    def zoom(self, factor: float):
        """Zoom in/out"""
        self.scale = max(0.01, min(90.0, self.scale * factor))
        self._cos_dec0 = math.cos(math.radians(self.center_dec))
        self._sin_dec0 = math.sin(math.radians(self.center_dec))
    
    def pan(self, delta_ra_deg: float, delta_dec_deg: float):
        """Pan the view"""
        self.center_ra = (self.center_ra + delta_ra_deg) % 360.0
        self.center_dec = max(-90.0, min(90.0, self.center_dec + delta_dec_deg))
        self._cos_dec0 = math.cos(math.radians(self.center_dec))
        self._sin_dec0 = math.sin(math.radians(self.center_dec))
    
    @property
    def fov_deg(self) -> float:
        """Current field of view in degrees"""
        return self.scale * min(self.width, self.height)


class AltAzProjection:
    """
    Perspective (gnomonic) projection centred on a look direction (az, alt).

    This is the mathematically correct projection for a "camera looking at
    the sky": straight lines stay straight, and — crucially — the horizon
    (alt = 0°) is always a perfectly horizontal straight line on screen,
    regardless of where you are looking.

    Coordinate system
    -----------------
    - Screen centre  = (center_az, center_alt)
    - Screen +X      = right  (increasing az when looking along the meridian)
    - Screen +Y      = down   (decreasing alt)
    - FOV is the full *vertical* field of view in degrees.

    Limits
    ------
    Points more than ~85° from the look direction are not projected
    (gnomonic distortion becomes extreme near 90°).
    """

    def __init__(self, center_az: float, center_alt: float,
                 fov_deg: float, width: int, height: int):
        self.center_az  = float(center_az)   % 360.0
        self.center_alt = max(-89.9, min(89.9, float(center_alt)))
        self.fov_deg    = max(2.0, min(170.0, float(fov_deg)))
        self.width      = width
        self.height     = height
        self.cx         = width  // 2
        self.cy         = height // 2

    @property
    def scale(self) -> float:
        """Degrees per pixel (based on vertical FOV)"""
        return self.fov_deg / self.height

    def _focal_length(self) -> float:
        """Focal length in pixels for the perspective projection"""
        return self.height / (2.0 * math.tan(math.radians(self.fov_deg / 2.0)))

    def _use_stereo(self) -> bool:
        """Use stereographic projection for wide FOV (>= 100°)"""
        return self.fov_deg >= 100.0

    def project(self, alt_deg: float, az_deg: float) -> Optional[Tuple[int, int]]:
        """
        Project (alt, az) → screen (x, y).
        Uses perspective for FOV < 100°, stereographic for wider views.
        """
        # Convert both points to unit vectors  (East, North, Up)
        def to_vec(alt, az):
            a = math.radians(alt); z = math.radians(az)
            return (math.cos(a)*math.sin(z), math.cos(a)*math.cos(z), math.sin(a))

        lx, ly, lz = to_vec(self.center_alt, self.center_az)
        px_, py_, pz_ = to_vec(alt_deg, az_deg)
        dot = lx*px_ + ly*py_ + lz*pz_

        # Build camera axes (right, up, forward)
        fx, fy, fz = lx, ly, lz
        wx, wy, wz = 0.0, 0.0, 1.0   # world up
        rx = fy*wz - fz*wy; ry = fz*wx - fx*wz; rz = fx*wy - fy*wx
        r_len = math.sqrt(rx*rx + ry*ry + rz*rz)
        if r_len < 1e-9:              # looking straight up/down
            wx, wy, wz = 0.0, 1.0, 0.0
            rx = fy*wz - fz*wy; ry = fz*wx - fx*wz; rz = fx*wy - fy*wx
            r_len = math.sqrt(rx*rx + ry*ry + rz*rz)
        rx /= r_len; ry /= r_len; rz /= r_len
        ux = ry*fz - rz*fy; uy = rz*fx - rx*fz; uz = rx*fy - ry*fx

        # Component along camera axes
        xc = px_*rx + py_*ry + pz_*rz   # right
        yc = px_*ux + py_*uy + pz_*uz   # up

        if self._use_stereo():
            # Stereographic projection — handles full hemisphere cleanly
            # dot = cos(angle_from_forward)
            # Points behind: dot <= 0 → skip
            if dot <= 0:
                return None
            # Stereographic scale: project onto plane tangent at forward
            # xp = xc / (1 + dot), yp = yc / (1 + dot)  [unit sphere]
            k = self.height / (2.0 * math.tan(math.radians(self.fov_deg / 4.0)))
            denom = 1.0 + dot
            if denom < 1e-9:
                return None
            sx = self.cx + int(k * xc / denom)
            sy = self.cy - int(k * yc / denom)
        else:
            # Perspective (gnomonic) — accurate for narrow FOV
            if dot <= 0.01:
                return None
            f = self._focal_length()
            sx = self.cx + int(f * xc / dot)
            sy = self.cy - int(f * yc / dot)

        return sx, sy

    def unproject(self, sx: int, sy: int) -> Tuple[float, float]:
        """Screen pixel → (alt_deg, az_deg)"""
        def to_vec(alt, az):
            a = math.radians(alt); z = math.radians(az)
            return (math.cos(a)*math.sin(z), math.cos(a)*math.cos(z), math.sin(a))

        fx, fy, fz = to_vec(self.center_alt, self.center_az)
        wx, wy, wz = 0.0, 0.0, 1.0
        rx = fy*wz-fz*wy; ry = fz*wx-fx*wz; rz = fx*wy-fy*wx
        r_len = math.sqrt(rx*rx+ry*ry+rz*rz)
        if r_len < 1e-9:
            wx, wy, wz = 0.0, 1.0, 0.0
            rx = fy*wz-fz*wy; ry = fz*wx-fx*wz; rz = fx*wy-fy*wx
            r_len = math.sqrt(rx*rx+ry*ry+rz*rz)
        rx /= r_len; ry /= r_len; rz /= r_len
        ux = ry*fz-rz*fy; uy = rz*fx-rx*fz; uz = rx*fy-ry*fx

        if self._use_stereo():
            k = self.height / (2.0 * math.tan(math.radians(self.fov_deg / 4.0)))
            if k < 1e-9: return self.center_alt, self.center_az
            xc = (sx - self.cx) / k
            yc = -(sy - self.cy) / k
            # Inverse stereographic
            r2 = xc*xc + yc*yc
            denom = 1.0 + r2 / 4.0   # note: stereo formula uses r²/4 for unit sphere
            # Actually for our formula: dot = (2 - r²) / (2 + r²)  won't work here
            # Use the direct inverse: given xc/(1+dot)=xc_proj, need to find dot
            # Let t = xc_proj, s = yc_proj → t²+s² = (xc²+yc²)/(1+dot)²
            # The world vector is: forward*(1+dot)/2 + right*xc/2 + up*yc/2  (normalised)
            # Simpler: reconstruct ray = forward + right*xc + up*yc, normalise
            wvx = fx + xc*rx + yc*ux
            wvy = fy + xc*ry + yc*uy
            wvz = fz + xc*rz + yc*uz
        else:
            f = self._focal_length()
            if f < 1e-9: return self.center_alt, self.center_az
            xc = (sx - self.cx) / f
            yc = -(sy - self.cy) / f
            wvx = fx + xc*rx + yc*ux
            wvy = fy + xc*ry + yc*uy
            wvz = fz + xc*rz + yc*uz

        w_len = math.sqrt(wvx*wvx + wvy*wvy + wvz*wvz)
        if w_len < 1e-9: return self.center_alt, self.center_az
        wvx /= w_len; wvy /= w_len; wvz /= w_len

        alt = math.degrees(math.asin(max(-1.0, min(1.0, wvz))))
        az  = math.degrees(math.atan2(wvx, wvy)) % 360.0
        return alt, az

    def pixel_to_ray_array(self, xs: 'np.ndarray', ys: 'np.ndarray') -> 'np.ndarray':
        """
        Vectorized unproject: (N,) pixel arrays → (N, 3) unit ray vectors.
        Ray vectors in local horizontal frame: (East, North, Up).
        """
        import numpy as np

        def to_vec(alt, az):
            a = math.radians(alt); z = math.radians(az)
            return np.array([math.cos(a)*math.sin(z),
                             math.cos(a)*math.cos(z),
                             math.sin(a)], dtype=np.float32)

        fwd   = to_vec(self.center_alt, self.center_az)
        up_w  = np.array([0., 0., 1.], dtype=np.float32)
        right = np.cross(fwd, up_w)
        r_len = np.linalg.norm(right)
        if r_len < 1e-9:
            up_w  = np.array([0., 1., 0.], dtype=np.float32)
            right = np.cross(fwd, up_w)
            r_len = np.linalg.norm(right)
        right /= r_len
        up = np.cross(right, fwd)

        dx = (xs - self.cx).astype(np.float32)
        dy = -(ys - self.cy).astype(np.float32)

        if self._use_stereo():
            k  = self.height / (2.0 * math.tan(math.radians(self.fov_deg / 4.0)))
            xc = dx / k;  yc = dy / k
        else:
            f  = self._focal_length()
            xc = dx / f;  yc = dy / f

        rays  = (fwd[np.newaxis, :]
                 + xc[:, np.newaxis] * right[np.newaxis, :]
                 + yc[:, np.newaxis] * up[np.newaxis, :])
        norms = np.linalg.norm(rays, axis=1, keepdims=True)
        norms = np.where(norms < 1e-9, 1.0, norms)
        return (rays / norms).astype(np.float32)

    def is_on_screen(self, px: int, py: int, margin: int = 10) -> bool:
        return (-margin <= px <= self.width  + margin and
                -margin <= py <= self.height + margin)

    def zoom(self, factor: float):
        self.fov_deg = max(2.0, min(115.0, self.fov_deg * factor))

    def pan(self, delta_az: float, delta_alt: float):
        self.center_az  = (self.center_az  + delta_az)  % 360.0
        self.center_alt = max(-89.0, min(89.0, self.center_alt + delta_alt))


# ---------------------------------------------------------------------------
# Allsky threshold — zoom out past this FOV triggers allsky mode
# ---------------------------------------------------------------------------
ALLSKY_FOV_THRESHOLD = 120.0


class OrthographicProjection:
    """
    Orthographic projection for allsky view.

    The entire visible hemisphere maps onto a circle:
      centre = zenith, edge = horizon (alt = 0)
      North = top, East = right

    Pan/drag are DISABLED. Only zoom-in exits back to normal mode.
    """

    ALLSKY_RADIUS_FRAC = 0.44

    def __init__(self, width: int, height: int):
        self.center_az  = 0.0
        self.center_alt = 90.0
        self.fov_deg    = 181.0   # sentinel: > ALLSKY_FOV_THRESHOLD
        self._resize(width, height)

    def _resize(self, W: int, H: int):
        self.width  = W
        self.height = H
        self.cx     = W // 2
        self.cy     = H // 2
        self.radius = min(W, H) * self.ALLSKY_RADIUS_FRAC

    def project(self, alt_deg: float, az_deg: float):
        if alt_deg < -0.5:
            return None
        alt = math.radians(max(0.0, alt_deg))
        az  = math.radians(az_deg)
        r   = math.cos(alt) * self.radius
        x   = int(self.cx + r * math.sin(az))
        y   = int(self.cy - r * math.cos(az))
        return x, y

    def unproject(self, sx: int, sy: int):
        dx  = float(sx - self.cx)
        dy  = -float(sy - self.cy)
        r   = math.sqrt(dx*dx + dy*dy)
        if r > self.radius + 1:
            return -90.0, 0.0
        cos_alt = min(1.0, r / self.radius)
        alt_deg = math.degrees(math.acos(cos_alt))
        az_deg  = math.degrees(math.atan2(dx, dy)) % 360.0
        return alt_deg, az_deg

    def pixel_to_ray_array(self, xs, ys):
        import numpy as np
        dx  = (xs - self.cx).astype(np.float32)
        dy  = -(ys - self.cy).astype(np.float32)
        r   = np.sqrt(dx*dx + dy*dy)
        outside = r > self.radius
        cos_alt = np.clip(r / self.radius, 0.0, 1.0)
        sin_alt = np.sqrt(np.maximum(0.0, 1.0 - cos_alt**2))
        az_rad  = np.arctan2(dx, dy)
        east    = np.where(outside, 0.0, sin_alt * np.sin(az_rad)).astype(np.float32)
        north   = np.where(outside, 0.0, sin_alt * np.cos(az_rad)).astype(np.float32)
        up      = np.where(outside, -1.0, cos_alt).astype(np.float32)
        return np.stack([east, north, up], axis=1)

    def is_on_screen(self, px: int, py: int, margin: int = 10) -> bool:
        return (-margin <= px <= self.width + margin and
                -margin <= py <= self.height + margin)

    def zoom(self, factor: float):
        pass   # handled externally

    def pan(self, *_):
        pass   # locked

    def _use_stereo(self) -> bool:
        return False


def bv_to_rgb(bv: float) -> Tuple[int, int, int]:
    """Convert B-V color index to RGB for star rendering."""
    bv = max(-0.4, min(2.0, bv))
    if bv < 0.0:
        r, g, b = 155 + int(bv * -100), 155 + int(bv * -100), 255
    elif bv < 0.4:
        t = bv / 0.4
        r = int(155 + t * 100); g = int(155 + t * 55); b = 255
    elif bv < 0.8:
        t = (bv - 0.4) / 0.4
        r = 255; g = int(210 - t * 10); b = int(255 - t * 255)
    elif bv < 1.4:
        t = (bv - 0.8) / 0.6
        r = 255; g = int(200 - t * 60); b = int(max(0, 50 - t * 50))
    else:
        t = min(1.0, (bv - 1.4) / 0.6)
        r = 255; g = int(140 - t * 60); b = 0
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def magnitude_to_radius(mag: float, scale: float = 1.0) -> int:
    """
    Convert star magnitude to pixel radius.
    
    Scale: brighter stars (mag < 0) → larger radius
           fainter stars (mag > 6) → minimum 1.5 pixels for visibility
    """
    # Base formula: magnitude 0 = 5 pixels, magnitude 6 = 1 pixel
    r = max(1.5, (6.0 - mag) * scale * 0.8)
    return int(min(10, r))  # Cap at 10 pixels for very bright stars
