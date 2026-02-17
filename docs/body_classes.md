# Solar System Body Classes - Reference Documentation

**Last updated:** Sprint 13b (Feb 2026)  
**Source files:** `universe/space_object.py`, `universe/orbital_body.py`, `universe/minor_bodies.py`

---

## 🔷 Class Hierarchy

```
SpaceObject (base)
    ├── OrbitalBody (Sole, Luna, pianeti principali)
    └── (non-inherited) MinorBody (asteroidi)
                        CometBody (comete)
```

---

## 1. `SpaceObject` (base class)

**File:** `universe/space_object.py`  
**Purpose:** Universal base class for every object in the simulated universe.

### Required Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `uid` | str | Unique identifier (e.g. "M42", "SUN", "CERES") |
| `name` | str | Human-readable name |
| `ra_deg` | float | Right Ascension J2000 (degrees) |
| `dec_deg` | float | Declination J2000 (degrees) |
| `distance_ly` | float | Distance from observer (light-years) |
| `obj_class` | ObjectClass | Enum: STAR, GALAXY, NEBULA, etc. |
| `subtype` | ObjectSubtype | Enum: MAIN_SEQUENCE, SPIRAL, etc. |
| `origin` | ObjectOrigin | REAL or PROCEDURAL |

### Optional Physical Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `mag` | float | 0.0 | Apparent visual magnitude |
| `size_arcmin` | float | 0.0 | Apparent major axis (arcminutes) |
| `size_minor_arcmin` | float | 0.0 | Apparent minor axis (arcminutes, 0=circular) |
| `pa_deg` | float | 0.0 | Position angle (degrees from North) |
| `bv_color` | float | 0.6 | B-V color index (0.6 = Sun-like) |
| `constellation` | str | "" | IAU constellation name |
| `description` | str | "" | Object description |
| `meta` | dict | {} | Flexible metadata dict |

### Properties (computed on demand)

```python
@property
def xyz_ly(self) -> Tuple[float, float, float]:
    """Cartesian position in light-years (origin = Sun/observer)"""

@property
def is_visible_in_chart(self) -> bool:
    """Should this object be visible in the Sky Chart?"""

@property
def angular_size(self) -> Tuple[float, float]:
    """(major_arcmin, minor_arcmin)"""
```

### Methods

```python
def distance_str(self) -> str:
    """Human-readable distance string (e.g. '2.5 Mly', '150 ly')"""
```

---

## 2. `OrbitalBody` (pianeti principali, Sole, Luna)

**File:** `universe/orbital_body.py`  
**Inherits:** `SpaceObject`  
**Purpose:** Solar System body with Keplerian orbital mechanics.

### Specific Attributes (beyond SpaceObject)

| Attribute | Type | Description |
|-----------|------|-------------|
| `orbital_elements` | Optional[OrbitalElements] | J2000 Keplerian elements with secular rates |
| `physical_radius_km` | float | Mean radius in km |
| `albedo` | float | Geometric albedo (0–1) |
| `absolute_mag` | float | H magnitude for planets (unused for Sun) |
| `is_sun` | bool | True only for the Sun |
| `is_moon` | bool | True only for Earth's Moon |
| `parent_body_uid` | str | UID of parent body (for moons) |

### Dynamic Attributes (computed by `update_position()`)  
These are **private** fields updated every frame:

| Attribute | Type | Description |
|-----------|------|-------------|
| `_jd` | float | Last computed Julian Date |
| `_ra_computed` | float | Computed RA (deg, J2000) |
| `_dec_computed` | float | Computed Dec (deg, J2000) |
| `_distance_au` | float | Distance from Earth (AU) |
| `_alt_deg` | float | Altitude above horizon (deg) |
| `_az_deg` | float | Azimuth (deg, N=0, E=90) |
| `_phase_angle` | float | Sun-body-Earth angle (deg) |
| `_apparent_mag` | float | Computed apparent magnitude |

### 🔴 CRITICAL: Position Update Pattern

**You MUST call `update_position()` every frame BEFORE reading any position/magnitude data:**

```python
# Every frame in your render loop:
jd = time_controller.jd
lat = observer.latitude_deg
lon = observer.longitude_deg

body.update_position(jd, lat, lon)

# NOW you can safely read:
ra = body.ra_deg          # Auto-synced from _ra_computed
dec = body.dec_deg        # Auto-synced from _dec_computed
mag = body.apparent_mag   # Property reading _apparent_mag
```

### Key Methods

```python
def update_position(self, jd: float,
                    observer_lat: float = 0.0,
                    observer_lon: float = 0.0) -> None:
    """
    Compute and cache RA/Dec/Alt/Az/distance/magnitude for Julian Date jd.
    observer_lat/lon in degrees (WGS84).
    
    Automatically updates:
      - self.ra_deg, self.dec_deg (SpaceObject fields)
      - All _internal fields (_alt_deg, _distance_au, _apparent_mag, etc.)
    ```

def update_position_datetime(self, dt: datetime,
                             observer_lat: float = 0.0,
                             observer_lon: float = 0.0) -> None:
    """Convenience wrapper accepting datetime instead of JD."""
```

### Properties (read AFTER update_position)

```python
@property
def altitude_deg(self) -> float:
    """Altitude above horizon (degrees). Needs observer lat/lon."

@property
def azimuth_deg(self) -> float:
    """Azimuth (degrees, N=0, E=90)."

@property
def distance_au(self) -> float:
    """Distance from Earth (AU)."

@property
def apparent_mag(self) -> float:
    """Apparent visual magnitude (V band, IAU 2012 for planets)."

@property
def is_above_horizon(self) -> bool:
    """True if altitude_deg > 0."

@property
def phase_fraction(self) -> float:
    """Illuminated fraction 0..1 (0=new, 1=full)."

@property
def apparent_diameter_arcsec(self) -> float:
    """Apparent angular diameter in arcseconds."
```

### Example Usage

```python
from universe.orbital_body import build_solar_system

# Initialize once
solar_bodies = build_solar_system()
sun = next(b for b in solar_bodies if b.is_sun)
moon = next(b for b in solar_bodies if b.is_moon)
planets = [b for b in solar_bodies if not b.is_sun and not b.is_moon]

# Every frame
jd = time_controller.jd
lat = observer.latitude_deg
lon = observer.longitude_deg

sun.update_position(jd, lat, lon)
moon.update_position(jd, lat, lon)
for planet in planets:
    planet.update_position(jd, lat, lon)

# Now read data
print(f"Jupiter: RA={{planet.ra_deg:.2f}}°, Mag={{planet.apparent_mag:.1f}}")
print(f"Apparent diameter: {{planet.apparent_diameter_arcsec:.2f}}\"")
print(f"Phase: {{planet.phase_fraction*100:.0f}}% illuminated")
```

---

## 3. `MinorBody` (asteroidi e pianeti nani)

**File:** `universe/minor_bodies.py`  
**Does NOT inherit from SpaceObject** (standalone dataclass)  
**Purpose:** Asteroids and dwarf planets with MPC orbital elements.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `uid` | str | Unique ID (e.g. "CERES", "VESTA") |
| `name` | str | Asteroid name |
| `mpc_number` | str | MPC catalog number (e.g. "1" for Ceres) |
| `elements` | Optional[MinorBodyElements] | MPC orbital elements |
| `description` | str | Object description |
| `physical_radius_km` | float | Mean radius in km |
| `albedo` | float | Geometric albedo |
| `bv_base` | float | Base B-V color index |

### Dynamic Attributes (computed by `update_position()`)  
| Attribute | Type | Description |
|-----------|------|-------------|
| `_ra_deg` | float | Right Ascension (degrees) |
| `_dec_deg` | float | Declination (degrees) |
| `_alt_deg` | float | Altitude above horizon (degrees) |
| `_az_deg` | float | Azimuth (degrees) |
| `_distance_au` | float | Distance from Earth (AU) |
| `_phase_deg` | float | Phase angle (degrees) |
| `_apparent_mag` | float | Apparent visual magnitude |

### Compatibility Flags

```python
is_sun: bool = False   # Always False (for renderer compatibility)
is_moon: bool = False  # Always False
```

### Properties (read AFTER update_position)

```python
@property
def ra_deg(self) -> float:
    """Right Ascension (degrees)."

@property
def dec_deg(self) -> float:
    """Declination (degrees)."

@property
def altitude_deg(self) -> float:
    """Altitude above horizon (degrees)."

@property
def azimuth_deg(self) -> float:
    """Azimuth (degrees)."

@property
def distance_au(self) -> float:
    """Distance from Earth (AU)."

@property
def apparent_mag(self) -> float:
    """Apparent visual magnitude."

@property
def phase_fraction(self) -> float:
    """Illuminated fraction 0..1."

@property
def mag(self) -> float:
    """Alias for apparent_mag (compatibility)."
```

### Methods

```python
def update_position(self, jd: float,
                    observer_lat: float = 0.0,
                    observer_lon: float = 0.0) -> None:
    """Calcola posizione e magnitudine alla data JD."

def apparent_diameter_arcsec(self) -> float:
    """Apparent angular diameter in arcseconds."""
```

### Example Usage

```python
from universe.minor_bodies import MinorBodyCatalog

# Get default hardcoded bodies (Ceres, Vesta, Pallas, etc.)
catalog = MinorBodyCatalog.get_default_bodies()

# Every frame
for body in catalog:
    body.update_position(jd, lat, lon)
    
    if body.apparent_mag < mag_limit:
        print(f"{body.name}: RA={{body.ra_deg:.2f}}°, Mag={{body.apparent_mag:.1f}}")
```

### MPC Loader (scalable to 600k+ asteroids)

```python
from universe.minor_bodies import MinorBodyCatalog

# Load from MPCORB.DAT file (filter by aperture)
catalog = MinorBodyCatalog.from_mpc_file("MPCORB.DAT", aperture_cm=25.0)
# Returns only asteroids visible with 25cm telescope
```

---

## 4. `CometBody` (comete)

**File:** `universe/minor_bodies.py`  
**Does NOT inherit from SpaceObject** (standalone dataclass)  
**Purpose:** Comets with parabolic/elliptic orbits and tail rendering.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `uid` | str | Unique ID (e.g. "1P", "2P") |
| `name` | str | Comet name (e.g. "1P/Halley") |
| `mpc_id` | str | MPC designation |
| `q_au` | float | Perihelion distance (AU) |
| `e` | float | Eccentricity (0–1 for elliptic, 1+ for parabolic) |
| `i` | float | Inclination (degrees) |
| `omega` | float | Argument of perihelion (degrees) |
| `Om` | float | Longitude of ascending node (degrees) |
| `T_peri_jd` | float | Julian Date of perihelion passage |
| `H0` | float | Absolute magnitude of nucleus (mag at 1 AU) |
| `n_act` | float | Activity exponent (brightness vs. distance) |
| `tail_length_au` | float | ⚠️ **Tail length in AU, NOT km** |
| `nucleus_radius_km` | float | Nucleus radius in km |
| `active` | bool | True if comet is currently active |

### Dynamic Attributes (computed by `update_position()`)  
| Attribute | Type | Description |
|-----------|------|-------------|
| `_ra_deg` | float | Right Ascension (degrees) |
| `_dec_deg` | float | Declination (degrees) |
| `_alt_deg` | float | Altitude above horizon (degrees) |
| `_az_deg` | float | Azimuth (degrees) |
| `_distance_au` | float | Distance from Earth (AU) |
| `_r_sun_au` | float | Distance from Sun (AU) |
| `_apparent_mag` | float | Apparent visual magnitude |
| `_tail_pa_deg` | float | Tail position angle (anti-solar direction) |

### Compatibility Flags

```python
is_sun: bool = False   # Always False
is_moon: bool = False  # Always False
```

### Properties (read AFTER update_position)

```python
@property
def ra_deg(self) -> float:
    """Right Ascension (degrees)."

@property
def dec_deg(self) -> float:
    """Declination (degrees)."

@property
def altitude_deg(self) -> float:
    """Altitude above horizon (degrees)."

@property
def azimuth_deg(self) -> float:
    """Azimuth (degrees)."

@property
def distance_au(self) -> float:
    """Distance from Earth (AU)."

@property
def apparent_mag(self) -> float:
    """Apparent total magnitude (nucleus + coma)."

@property
def tail_pa_deg(self) -> float:
    """Tail position angle (degrees, anti-solar direction)."
```

### Methods

```python
def update_position(self, jd: float,
                    observer_lat: float = 0.0,
                    observer_lon: float = 0.0) -> None:
    """Update position, magnitude, and tail direction."

def _heliocentric_ecliptic(self, jd: float) -> Tuple[float, float, float]:
    """Compute heliocentric ecliptic coordinates (x, y, z) in AU."""
```

### Example Usage

```python
from universe.minor_bodies import CometBody

# Halley's Comet
halley = CometBody(
    uid="1P", name="1P/Halley", mpc_id="1P",
    q_au=0.586, e=0.967, i=162.3,
    omega=111.3, Om=58.4, T_peri_jd=2446470.0,
    H0=4.0, n_act=4.0,
    tail_length_au=2.0,  # ⚠️ in AU, not km!
    nucleus_radius_km=5.5,
    active=True
)

# Every frame
halley.update_position(jd, lat, lon)

print(f"Halley: RA={{halley.ra_deg:.2f}}°, Mag={{halley.apparent_mag:.1f}}")
print(f"Tail PA={{halley.tail_pa_deg:.0f}}° (anti-solar)")
print(f"Distance from Sun: {{halley._r_sun_au:.2f}} AU")
```

---

## ⚠️ Common Mistakes

### 1. ❌ Reading position BEFORE update_position

```python
# WRONG
planet.ra_deg  # ← Stale data from previous frame!
```

```python
# CORRECT
planet.update_position(jd, lat, lon)
planet.ra_deg  # ← Fresh data
```

### 2. ❌ Confusing tail_length units

```python
# WRONG
comet.tail_length_au * 1000  # Thinking it's in km
```

```python
# CORRECT
tail_length_km = comet.tail_length_au * 149597870.7  # AU → km
```

### 3. ❌ Accessing private fields directly

```python
# WRONG (breaks encapsulation)
planet._apparent_mag  # Private field!
```

```python
# CORRECT (use property)
planet.apparent_mag   # Property accessor
```

### 4. ❌ Forgetting observer lat/lon for altitude

```python
# WRONG (defaults to lat=0, lon=0)
planet.update_position(jd)
alt = planet.altitude_deg  # ← Wrong altitude!
```

```python
# CORRECT
planet.update_position(jd, observer.latitude_deg, observer.longitude_deg)
alt = planet.altitude_deg  # ← Correct altitude
```

---

## 🎯 Quick Reference: Which Class?

| Object | Class | File |
|--------|-------|------|
| Sun | `OrbitalBody` | `orbital_body.py` |
| Moon | `OrbitalBody` | `orbital_body.py` |
| Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto | `OrbitalBody` | `orbital_body.py` |
| Ceres, Vesta, Pallas, Juno (asteroids) | `MinorBody` | `minor_bodies.py` |
| 1P/Halley, 2P/Encke (comets) | `CometBody` | `minor_bodies.py` |
| Stars (Sirius, Betelgeuse) | `SpaceObject` | `space_object.py` |
| DSO (M31, M42, NGC7293) | `SpaceObject` | `space_object.py` |

---

**End of Reference Documentation**