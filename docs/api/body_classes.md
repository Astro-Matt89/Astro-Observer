# API Documentation for SpaceObject, OrbitalBody, MinorBody, and CometBody Classes

## SpaceObject Class

### Attributes
- `name` (string): The name of the space object.
- `mass` (float): The mass of the space object in kilograms.
- `diameter` (float): The diameter of the space object in kilometers.

### Methods
- `get_info()`: Returns a string containing the name and mass of the space object.
  
### Inconsistencies Warnings
- Ensure that mass is a non-negative value, as negative mass is not physically meaningful.

### Defensive Patterns
- Use type checking to ensure `mass` and `diameter` are numbers.

### Usage Example
```python
space_object = SpaceObject(name='Mars', mass=6.39e23, diameter=6779)
print(space_object.get_info())  # Output: Mars, 6.39e23 kg
```

---

## OrbitalBody Class

### Attributes
- `orbital_period` (float): The time it takes to complete one orbit in Earth days.
- `semi_major_axis` (float): The average distance from the sun in kilometers.

### Methods
- `calculate_gravity()`: Calculates the gravitational pull of the body.

### Inconsistencies Warnings
- Make sure `orbital_period` is positive and greater than zero.

### Defensive Patterns
- Validate that `semi_major_axis` is greater than zero.

### Usage Example
```python
orbital_body = OrbitalBody(name='Earth', mass=5.97e24, orbital_period=365.25)
print(orbital_body.calculate_gravity())  # Output: 9.81 m/s²
```

---

## MinorBody Class

### Attributes
- `composition` (string): The main components of the body (e.g., rock, ice).

### Methods
- `get_composition()`: Returns the composition of the minor body.

### Inconsistencies Warnings
- Be aware that some minor bodies may have complex compositions which are not easily quantifiable.

### Defensive Patterns
- Check that `composition` is a valid string and not an empty value.

### Usage Example
```python
minor_body = MinorBody(name='Ceres', mass=9.1e20, composition='ice and rock')
print(minor_body.get_composition())  # Output: ice and rock
```

---

## CometBody Class

### Attributes
- `tail_length` (float): The length of the comet's tail in kilometers.

### Methods
- `show_tail()`: Displays information about the comet's tail.

### Inconsistencies Warnings
- Tail length may vary significantly during the comet's orbit, ensure it is measured at the correct time.

### Defensive Patterns
- Validate that `tail_length` is positive when set.

### Usage Example
```python
comet_body = CometBody(name='Halley', mass=2.2e14, tail_length=100000)
print(comet_body.show_tail())  # Output: Tail length: 100000 km
```