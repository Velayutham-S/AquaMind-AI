import folium
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.agents.state import AgentState
from app.models import MonitoringData, DistrictAssessment
from app.logging_config import logger

class GISAgent:
    @staticmethod
    def get_district_coordinates(db: Session, district_name: str) -> tuple:
        """Helper to get average latitude/longitude of stations in a district."""
        res = db.query(
            MonitoringData.latitude, 
            MonitoringData.longitude
        ).filter(
            MonitoringData.district == district_name.upper(),
            MonitoringData.latitude.isnot(None),
            MonitoringData.longitude.isnot(None)
        ).all()
        
        if res:
            lats = [r[0] for r in res]
            lons = [r[1] for r in res]
            return sum(lats) / len(lats), sum(lons) / len(lons)
            
        # Hardcoded fallback centroids for major TN districts
        centroids = {
            "ARIYALUR": (11.1379, 79.0743),
            "COIMBATORE": (11.0168, 76.9558),
            "CUDDALORE": (11.7480, 79.7714),
            "DHARMAPURI": (12.1211, 78.1582),
            "DINDIGUL": (10.3673, 77.9803),
            "ERODE": (11.3410, 77.7172),
            "KANCHEEPURAM": (12.8342, 79.7036),
            "KANNIYAKUMARI": (8.0883, 77.5385),
            "KARUR": (10.9601, 78.0766),
            "MADURAI": (9.9252, 78.1198),
            "NAGAPATTINAM": (10.7672, 79.8444),
            "NAMAKKAL": (11.2189, 78.1674),
            "SALEM": (11.6643, 78.1460),
            "THANJAVUR": (10.7870, 79.1378),
            "TIRUNELVELI": (8.7139, 77.7567),
            "TIRUPPUR": (11.1085, 77.3411),
            "VELLORE": (12.9165, 79.1325),
            "VIRUDHUNAGAR": (9.5680, 77.9624),
            "CHENNAI": (13.0827, 80.2707)
        }
        return centroids.get(district_name.upper(), (11.1271, 78.6569)) # Default state centroid

    @staticmethod
    def process(state: AgentState) -> dict:
        """GIS node that compiles interactive Folium maps of Tamil Nadu groundwater stress markers."""
        loc = state.get("resolved_location")
        loc_type = state.get("resolved_location_type")
        
        logger.info(f"GISAgent executing map rendering for: {loc}")
        
        db = SessionLocal()
        
        # Center map
        center_lat, center_lon = 11.1271, 78.6569
        zoom_level = 7
        
        if loc and loc_type == "district":
            center_lat, center_lon = GISAgent.get_district_coordinates(db, loc)
            zoom_level = 9
            
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, control_scale=True)
        
        # Draw district-wide markers or state-wide choropleth markers
        try:
            # Fetch latest district assessment data to color markers
            latest_recs = db.query(DistrictAssessment)\
                .filter(DistrictAssessment.year == "2024-2025")\
                .all()
                
            for r in latest_recs:
                d_lat, d_lon = GISAgent.get_district_coordinates(db, r.district)
                stage = r.stage_of_extraction or 0.0
                cat = r.category or "Safe"
                
                # Colors based on Category
                color = "green"
                if cat == "Semi-Critical":
                    color = "orange" # Or yellow
                elif cat == "Critical":
                    color = "darkorange"
                elif cat == "Over-Exploited":
                    color = "red"
                    
                popup_text = (
                    f"<b>District:</b> {r.district.title()}<br>"
                    f"<b>Stage:</b> {stage:.1f}%<br>"
                    f"<b>Category:</b> {cat}<br>"
                    f"<b>Extractable:</b> {r.annual_extractable:.1f} ham<br>"
                    f"<b>Total Recharge:</b> {r.total_recharge:.1f} ham"
                )
                
                folium.CircleMarker(
                    location=[d_lat, d_lon],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.6,
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(m)
                
            # If the query was about a specific station, add detailed marker
            if loc and loc_type == "village":
                stations = db.query(MonitoringData)\
                    .filter(MonitoringData.station == loc.upper(), MonitoringData.latitude.isnot(None))\
                    .first()
                if stations:
                    folium.Marker(
                        location=[stations.latitude, stations.longitude],
                        icon=folium.Icon(color="blue", icon="info-sign"),
                        popup=f"Monitoring Station: {stations.station.title()}<br>District: {stations.district.title()}"
                    ).add_to(m)
                    
        except Exception as e:
            logger.error(f"GISAgent folium rendering error: {e}")
        finally:
            db.close()
            
        map_html = m._repr_html_()
        
        history = list(state.get("routing_history", []))
        history.append("gis")
        
        # Determine next node in routing list
        routing_plan = ["report", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break

        return {
            "map_html": map_html,
            "routing_history": history,
            "current_node": next_node
        }
