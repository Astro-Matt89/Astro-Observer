## Golden Rules

1. ... 
2. ... 
3. ... 
4. ... 
5. ... 
6. ... 

### 7. Mixed Object Types in UI — Defensive Attribute Access

When displaying or interacting with mixed object types (stars, DSO, planets, asteroids, comets):

**Pattern for inconsistent attributes:**

```python
# ✅ ALWAYS use hasattr before accessing uncertain attributes
if hasattr(obj, 'attribute_name'):
    value = (obj.attribute_name() if callable(obj.attribute_name) 
             else obj.attribute_name)
else:
    value = fallback_default

# ✅ NEVER assume all objects have the same interface
# ❌ WRONG: obj.apparent_diameter_arcsec (crashes on CometBody)
# ✅ RIGHT: hasattr check first
```

**Common inconsistent attributes:**
- `apparent_diameter_arcsec` — property on OrbitalBody, method on MinorBody, absent on CometBody
- `obj_class` — present on SpaceObject (Enum), absent on solar system bodies
- `constellation` — present on DSO, absent on solar system bodies
- `size_arcmin` — present on DSO, absent on solar system bodies

**Reference:** See `docs/api/body_classes.md` for complete API documentation.

**Why this matters:** Sprint 13b discovered 4 AttributeError/TypeError bugs caused by assuming uniform interfaces. Defensive checks add <0.01ms overhead but prevent all crashes.