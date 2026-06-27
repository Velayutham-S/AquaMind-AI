import difflib
from typing import Optional
from sqlalchemy.orm import Session
from app.logging_config import logger
from app.models import (
    DistrictMaster, TalukMaster, FirkaMaster, VillageMaster,
    AquiferMaster, RiverBasinMaster, WatershedMaster,
    DistrictAssessment, FirkaAssessment, MonitoringData
)

# Hardcoded common Tamil Nadu aliases and Tamil translations
LOCATION_ALIASES = {
    "kovai": "COIMBATORE",
    "nellai": "TIRUNELVELI",
    "trichy": "TIRUCHIRAPPALLI",
    "trichi": "TIRUCHIRAPPALLI",
    "tuticorin": "THOOTHUKUDI",
    "thoothukudi": "THOOTHUKUDI",
    "madras": "CHENNAI",
    "madurai": "MADURAI",
    "chengalpattu": "CHENGALPATTU",
    "karumathampatti": "KARUMATHAMPATTY",
    "karumathampatty": "KARUMATHAMPATTY",
    "kanyakumari": "KANNIYAKUMARI",
    "kanniyakumari": "KANNIYAKUMARI",
    "vellore": "VELLORE",
    "tirupur": "TIRUPPUR",
    "tiruppur": "TIRUPPUR",
    "ponnamaravathy": "PONNAMARAVATHI",
    "tanjore": "THANJAVUR",
    "thanjavur": "THANJAVUR",
    "pondicherry": "PUDUCHERRY",
    "puducherry": "PUDUCHERRY",
    
    # Tamil script aliases
    "சேலம்": "SALEM",
    "சேலம் மாவட்ட": "SALEM",
    "கோவை": "COIMBATORE",
    "சென்னை": "CHENNAI",
    "திருச்சி": "TIRUCHIRAPPALLI",
    "மதுரை": "MADURAI",
    "தஞ்சாவூர்": "THANJAVUR",
    "நெல்லை": "TIRUNELVELI",
    "ஈரோடு": "ERODE",
    "கரூர்": "KARUR"
}

class LocationResolver:
    """Enhanced Location Resolver caching master directories for fuzzy geographical name parsing."""
    
    _cached_districts = set()
    _cached_taluks = set()
    _cached_firkas = set()
    _cached_villages = set()
    _cached_aquifers = set()
    _cached_basins = set()
    _cached_watersheds = set()
    
    _is_seeded = False

    @classmethod
    def seed_cache(cls, db: Session):
        """Seeds location master sets from database to enable high performance fuzzy matching."""
        if cls._is_seeded:
            return
            
        try:
            # Seed Districts
            dists = db.query(DistrictMaster.district_name).distinct().all()
            cls._cached_districts = {d[0].strip().upper() for d in dists if d[0]}
            if not cls._cached_districts:
                # Fallback to assessments table
                dists_fallback = db.query(DistrictAssessment.district).distinct().all()
                cls._cached_districts = {d[0].strip().upper() for d in dists_fallback if d[0]}
                
            # Seed Taluks
            taluks = db.query(TalukMaster.taluk_name).distinct().all()
            cls._cached_taluks = {t[0].strip().upper() for t in taluks if t[0]}
            
            # Seed Firkas
            firkas = db.query(FirkaMaster.firka_name).distinct().all()
            cls._cached_firkas = {f[0].strip().upper() for f in firkas if f[0]}
            if not cls._cached_firkas:
                firkas_fallback = db.query(FirkaAssessment.firka).distinct().all()
                cls._cached_firkas = {f[0].strip().upper() for f in firkas_fallback if f[0]}
                
            # Seed Villages
            villages = db.query(VillageMaster.village_name).distinct().all()
            cls._cached_villages = {v[0].strip().upper() for v in villages if v[0]}
            # Seed Tamil name mappings to aliases
            villages_tamil = db.query(VillageMaster.village_name_tamil, VillageMaster.village_name).filter(VillageMaster.village_name_tamil.isnot(None)).all()
            for vt, vn in villages_tamil:
                if vt and vn:
                    LOCATION_ALIASES[vt.strip().lower()] = vn.strip().upper()
            
            # Seed Aquifers
            aquifers = db.query(AquiferMaster.aquifer_name).distinct().all()
            cls._cached_aquifers = {a[0].strip().upper() for a in aquifers if a[0]}
            
            # Seed River Basins
            basins = db.query(RiverBasinMaster.river_basin_name).distinct().all()
            cls._cached_basins = {b[0].strip().upper() for b in basins if b[0]}
            
            # Seed Watersheds
            watersheds = db.query(WatershedMaster.watershed_name).distinct().all()
            cls._cached_watersheds = {w[0].strip().upper() for w in watersheds if w[0]}
            
            cls._is_seeded = True
            logger.info(
                f"LocationResolver cache seeded. Districts: {len(cls._cached_districts)} | "
                f"Taluks: {len(cls._cached_taluks)} | Firkas: {len(cls._cached_firkas)} | "
                f"Villages: {len(cls._cached_villages)} | Aquifers: {len(cls._cached_aquifers)} | "
                f"Basins: {len(cls._cached_basins)} | Watersheds: {len(cls._cached_watersheds)}"
            )
        except Exception as e:
            logger.error(f"Error seeding LocationResolver: {e}")

    @classmethod
    def resolve_location(cls, db: Session, raw_name: str, threshold: float = 0.8) -> dict:
        """Resolves a raw location string into a validated geographical entity name and type."""
        if not raw_name or not isinstance(raw_name, str):
            return {"resolved": None, "type": None}

        cls.seed_cache(db)
        cleaned = raw_name.strip().lower()
        
        # 1. Alias & Translation Lookup
        if cleaned in LOCATION_ALIASES:
            resolved_name = LOCATION_ALIASES[cleaned]
            return cls._identify_type(resolved_name)
            
        # Normalize casing for lookup
        query_upper = cleaned.upper()
        
        # 2. Exact match check
        exact_type = cls._check_exact(query_upper)
        if exact_type:
            return {"resolved": query_upper, "type": exact_type}
            
        # 3. Fuzzy matches search (by priority/hierarchy)
        categories = [
            ("district", cls._cached_districts),
            ("river_basin", cls._cached_basins),
            ("watershed", cls._cached_watersheds),
            ("aquifer", cls._cached_aquifers),
            ("taluk", cls._cached_taluks),
            ("firka", cls._cached_firkas),
            ("village", cls._cached_villages)
        ]
        
        for loc_type, master_set in categories:
            matches = difflib.get_close_matches(query_upper, list(master_set), n=1, cutoff=threshold)
            if matches:
                return {"resolved": matches[0], "type": loc_type}
                
        # 4. Sub-word fallback matching
        for loc_type, master_set in categories:
            for item in master_set:
                if item in query_upper or query_upper in item:
                    return {"resolved": item, "type": loc_type}
                    
        return {"resolved": None, "type": None}

    @classmethod
    def _check_exact(cls, name_upper: str) -> Optional[str]:
        if name_upper in cls._cached_districts:
            return "district"
        if name_upper in cls._cached_basins:
            return "river_basin"
        if name_upper in cls._cached_watersheds:
            return "watershed"
        if name_upper in cls._cached_aquifers:
            return "aquifer"
        if name_upper in cls._cached_taluks:
            return "taluk"
        if name_upper in cls._cached_firkas:
            return "firka"
        if name_upper in cls._cached_villages:
            return "village"
        return None

    @classmethod
    def _identify_type(cls, name_upper: str) -> dict:
        exact_type = cls._check_exact(name_upper)
        if exact_type:
            return {"resolved": name_upper, "type": exact_type}
        # default fallback type if registered in aliases but missing from masters
        return {"resolved": name_upper, "type": "district"}
