"""
Deep Sky Objects Catalog
Gestione di nebulose, galassie, ammassi e altri oggetti estesi
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import numpy as np
from typing import Optional

class DSOType(Enum):
    """Tipi di Deep Sky Objects"""
    # Nebulose
    HII_REGION = "HII"           # Nebulose a emissione (H-alpha)
    REFLECTION = "RN"            # Nebulose a riflessione
    PLANETARY = "PN"             # Nebulose planetarie
    SNR = "SNR"                  # Supernova remnants
    DARK = "DN"                  # Nebulose oscure
    
    # Galassie
    SPIRAL = "SG"                # Galassie spirali
    ELLIPTICAL = "EG"            # Galassie ellittiche
    IRREGULAR = "IG"             # Galassie irregolari
    LENTICULAR = "LG"            # Galassie lenticolari
    
    # Ammassi
    OPEN_CLUSTER = "OC"          # Ammassi aperti
    GLOBULAR_CLUSTER = "GC"      # Ammassi globulari
    
    # Altri
    GALAXY_CLUSTER = "GCL"       # Ammassi di galassie
    QUASAR = "Q"                 # Quasar

@dataclass
class DeepSkyObject:
    """Oggetto deep sky completo"""
    # Identificazione
    id: int
    name: str
    catalog: str                 # "M", "NGC", "IC", "Sh2", ecc.
    catalog_num: int
    
    # Posizione
    ra_deg: float
    dec_deg: float
    
    # Proprietà fisiche
    dso_type: DSOType
    mag: float                   # Magnitudine integrata
    surface_brightness: float    # mag/arcmin^2
    size_arcmin: float          # Dimensione maggiore
    size_minor_arcmin: float    # Dimensione minore (0 se circolare)
    pa_deg: float               # Position angle (gradi da Nord)
    
    # Proprietà aggiuntive
    distance_ly: Optional[float] = None
    redshift: Optional[float] = None
    
    # Rendering
    color_index: float = 0.0    # B-V per stelle, altro per DSO
    is_procedural: bool = False # True se generato proceduralmente
    
    def angular_size(self) -> tuple[float, float]:
        """Restituisce (size_major, size_minor) in arcmin"""
        return (self.size_arcmin, self.size_minor_arcmin if self.size_minor_arcmin > 0 else self.size_arcmin)
    
    def is_visible(self, fov_deg: float, limiting_mag: float) -> bool:
        """Verifica se l'oggetto è visibile date le condizioni"""
        # Troppo debole?
        if self.mag > limiting_mag + 2:  # +2 per oggetti estesi
            return False
        
        # Troppo piccolo rispetto al FOV?
        if self.size_arcmin < fov_deg * 60 * 0.002:  # < 0.2% del FOV
            return False
        
        return True

class DSOCatalog:
    """Gestisce il catalogo di oggetti deep sky"""
    
    def __init__(self):
        self.objects: dict[int, DeepSkyObject] = {}
        self._by_type: dict[DSOType, list[int]] = {}
        self._messier: dict[int, int] = {}  # M number -> object id
        self._ngc: dict[int, int] = {}      # NGC number -> object id
        
    def add_object(self, obj: DeepSkyObject):
        """Aggiunge un oggetto al catalogo"""
        self.objects[obj.id] = obj
        
        # Indicizza per tipo
        if obj.dso_type not in self._by_type:
            self._by_type[obj.dso_type] = []
        self._by_type[obj.dso_type].append(obj.id)
        
        # Indicizza per catalogo
        if obj.catalog == "M":
            self._messier[obj.catalog_num] = obj.id
        elif obj.catalog == "NGC":
            self._ngc[obj.catalog_num] = obj.id
    
    def get_by_id(self, obj_id: int) -> Optional[DeepSkyObject]:
        """Recupera un oggetto per ID"""
        return self.objects.get(obj_id)
    
    def get_messier(self, m_num: int) -> Optional[DeepSkyObject]:
        """Recupera un oggetto Messier per numero"""
        obj_id = self._messier.get(m_num)
        return self.objects.get(obj_id) if obj_id else None
    
    def get_ngc(self, ngc_num: int) -> Optional[DeepSkyObject]:
        """Recupera un oggetto NGC per numero"""
        obj_id = self._ngc.get(ngc_num)
        return self.objects.get(obj_id) if obj_id else None
    
    def query_region(self, ra_min: float, ra_max: float, 
                     dec_min: float, dec_max: float,
                     mag_limit: float = 15.0,
                     fov_deg: float = 120.0) -> list[DeepSkyObject]:
        """Query oggetti in una regione di cielo"""
        results = []
        
        for obj in self.objects.values():
            # Check magnitudine
            if obj.mag > mag_limit:
                continue
            
            # Check visibilità
            if not obj.is_visible(fov_deg, mag_limit):
                continue
            
            # Check coordinate
            ra, dec = obj.ra_deg, obj.dec_deg
            
            # Gestione wrap-around per RA
            if ra_max < ra_min:  # Caso attraverso 0°
                if not ((ra >= ra_min or ra <= ra_max) and dec_min <= dec <= dec_max):
                    continue
            else:
                if not (ra_min <= ra <= ra_max and dec_min <= dec <= dec_max):
                    continue
            
            results.append(obj)
        
        return results
    
    def get_by_type(self, dso_type: DSOType) -> list[DeepSkyObject]:
        """Recupera tutti gli oggetti di un tipo"""
        obj_ids = self._by_type.get(dso_type, [])
        return [self.objects[oid] for oid in obj_ids]

def load_messier_catalog() -> DSOCatalog:
    """
    Carica il catalogo Messier completo (110 oggetti)
    """
    from .messier_data import MESSIER_DATA
    
    # Map type strings to DSOType enum
    type_map = {
        "HII": DSOType.HII_REGION,
        "RN":  DSOType.REFLECTION,
        "PN":  DSOType.PLANETARY,
        "SNR": DSOType.SNR,
        "DN":  DSOType.DARK,
        "SG":  DSOType.SPIRAL,
        "EG":  DSOType.ELLIPTICAL,
        "IG":  DSOType.IRREGULAR,
        "LG":  DSOType.LENTICULAR,
        "OC":  DSOType.OPEN_CLUSTER,
        "GC":  DSOType.GLOBULAR_CLUSTER,
    }
    
    catalog = DSOCatalog()
    
    for entry in MESSIER_DATA:
        m_num, name, ra, dec, type_str, mag, size, dist, constellation, desc = entry
        
        dso_type = type_map.get(type_str, DSOType.HII_REGION)
        
        obj = DeepSkyObject(
            id=m_num,
            name=name,
            catalog="M",
            catalog_num=m_num,
            ra_deg=ra,
            dec_deg=dec,
            dso_type=dso_type,
            mag=mag,
            surface_brightness=mag + 3.0,   # Approssimazione
            size_arcmin=size,
            size_minor_arcmin=size * 0.7,    # Approssimazione
            pa_deg=0.0,
            distance_ly=float(dist),
            color_index=0.0,
        )
        # Aggiungi constellation e description come attributi extra
        obj.constellation = constellation
        obj.description = desc
        
        catalog.add_object(obj)
    
    return catalog

def load_ngc_catalog(filepath: str = None) -> DSOCatalog:
    """
    Carica una selezione dei più importanti oggetti NGC (100 oggetti)
    """
    from .ngc_data import NGC_DATA
    
    type_map = {
        "HII": DSOType.HII_REGION,
        "RN":  DSOType.REFLECTION,
        "PN":  DSOType.PLANETARY,
        "SNR": DSOType.SNR,
        "DN":  DSOType.DARK,
        "SG":  DSOType.SPIRAL,
        "EG":  DSOType.ELLIPTICAL,
        "IG":  DSOType.IRREGULAR,
        "LG":  DSOType.LENTICULAR,
        "OC":  DSOType.OPEN_CLUSTER,
        "GC":  DSOType.GLOBULAR_CLUSTER,
    }
    
    catalog = DSOCatalog()
    
    for entry in NGC_DATA:
        ngc_num, name, ra, dec, type_str, mag, size, dist, constellation, desc = entry
        
        dso_type = type_map.get(type_str, DSOType.HII_REGION)
        
        # Usa ID alto per NGC (10000 + ngc_num) per evitare collisioni con Messier
        obj = DeepSkyObject(
            id=10000 + ngc_num,
            name=name,
            catalog="NGC",
            catalog_num=ngc_num,
            ra_deg=ra,
            dec_deg=dec,
            dso_type=dso_type,
            mag=mag,
            surface_brightness=mag + 3.0,
            size_arcmin=size,
            size_minor_arcmin=size * 0.7,
            pa_deg=0.0,
            distance_ly=float(dist),
            color_index=0.0,
        )
        obj.constellation = constellation
        obj.description = desc
        
        catalog.add_object(obj)
    
    return catalog


def load_combined_catalog() -> DSOCatalog:
    """
    Carica il catalogo combinato Messier + NGC (110 + 100 oggetti)
    """
    messier = load_messier_catalog()
    ngc = load_ngc_catalog()
    
    # Merge: aggiungi tutti NGC nel catalogo Messier
    for obj in ngc.objects.values():
        messier.add_object(obj)
    
    return messier
