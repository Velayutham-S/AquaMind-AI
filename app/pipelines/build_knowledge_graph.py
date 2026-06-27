import json
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal, init_db
from app.models import (
    DistrictMaster, TalukMaster, FirkaMaster, VillageMaster,
    AquiferMaster, RiverBasinMaster, WatershedMaster, Document
)
from app.logging_config import logger

def main():
    logger.info("Compiling Spatial Knowledge Graph (Dual-Hierarchy)...")
    init_db()
    
    db = SessionLocal()
    data_dir = Config.BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    nodes = []
    edges = []
    
    try:
        # 1. Fetch data from masters
        dists = db.query(DistrictMaster).all()
        taluks = db.query(TalukMaster).all()
        firkas = db.query(FirkaMaster).all()
        villages = db.query(VillageMaster).all()
        aquifers = db.query(AquiferMaster).all()
        basins = db.query(RiverBasinMaster).all()
        watersheds = db.query(WatershedMaster).all()
        docs = db.query(Document).all()
        
        # 2. Add District Nodes
        dist_map = {}
        for d in dists:
            node_id = f"DIS-{d.id:04d}"
            dist_map[d.district_name] = node_id
            nodes.append({
                "id": node_id,
                "name": d.district_name,
                "type": "District"
            })
            
        # 3. Add Taluk Nodes & Edges (Taluk -> District)
        taluk_map = {}
        for t in taluks:
            node_id = f"TAL-{t.id:04d}"
            taluk_map[t.taluk_name] = node_id
            nodes.append({
                "id": node_id,
                "name": t.taluk_name,
                "type": "Taluk"
            })
            # Relationship: Taluk belongs to District
            target_id = dist_map.get(t.district_name)
            if target_id:
                edges.append({
                    "source": node_id,
                    "target": target_id,
                    "type": "belongs_to"
                })

        # 4. Add Firka Nodes & Edges (Firka -> Taluk)
        firka_map = {}
        for f in firkas:
            node_id = f"FIR-{f.id:04d}"
            firka_map[f.firka_name] = node_id
            nodes.append({
                "id": node_id,
                "name": f.firka_name,
                "type": "Firka"
            })
            # Relationship: Firka belongs to Taluk
            target_id = taluk_map.get(f.taluk_name)
            if target_id:
                edges.append({
                    "source": node_id,
                    "target": target_id,
                    "type": "belongs_to"
                })
                
        # 5. Add Hydrological Nodes (Basin, Watershed, Aquifer)
        basin_nodes = []
        for b in basins:
            node_id = f"BAS-{b.id:04d}"
            nodes.append({"id": node_id, "name": b.river_basin_name, "type": "River Basin"})
            basin_nodes.append(node_id)
            
        watershed_nodes = []
        for w in watersheds:
            node_id = f"WAT-{w.id:04d}"
            nodes.append({"id": node_id, "name": w.watershed_name, "type": "Watershed"})
            watershed_nodes.append(node_id)
            
        aquifer_nodes = []
        for aq in aquifers:
            node_id = f"AQU-{aq.id:04d}"
            nodes.append({"id": node_id, "name": aq.aquifer_name, "type": "Aquifer"})
            aquifer_nodes.append(node_id)

        # 6. Add Village Nodes & Edges (Village -> Admin + Hydrological Cross-links)
        for v in villages:
            node_id = v.village_id
            nodes.append({
                "id": node_id,
                "name": v.village_name,
                "type": "Village"
            })
            
            # Edges:
            # - belongs_to -> Firka
            f_id = firka_map.get(v.firka)
            if f_id:
                edges.append({"source": node_id, "target": f_id, "type": "belongs_to"})
            
            # - belongs_to -> Taluk
            t_id = taluk_map.get(v.taluk)
            if t_id:
                edges.append({"source": node_id, "target": t_id, "type": "belongs_to"})
                
            # - belongs_to -> District
            d_id = dist_map.get(v.district)
            if d_id:
                edges.append({"source": node_id, "target": d_id, "type": "belongs_to"})
                
            # - located_in -> Watershed (cyclic mapping mock)
            w_idx = v.id % len(watershed_nodes) if watershed_nodes else 0
            if watershed_nodes:
                edges.append({"source": node_id, "target": watershed_nodes[w_idx], "type": "located_in"})
                
            # - overlies -> Aquifer
            a_idx = v.id % len(aquifer_nodes) if aquifer_nodes else 0
            if aquifer_nodes:
                edges.append({"source": node_id, "target": aquifer_nodes[a_idx], "type": "overlies"})
                
            # - drains_to -> River Basin
            b_idx = v.id % len(basin_nodes) if basin_nodes else 0
            if basin_nodes:
                edges.append({"source": node_id, "target": basin_nodes[b_idx], "type": "drains_to"})

            # - monitoring well link
            well_node_id = f"WEL-{v.village_id.split('-')[-1]}"
            nodes.append({
                "id": well_node_id,
                "name": f"WELL-{v.village_name}",
                "type": "Monitoring Well"
            })
            edges.append({"source": well_node_id, "target": node_id, "type": "monitors"})

        # 7. Add Documents, Policies, and Recommendations Nodes
        policy_nodes = []
        policies = [
            ("Tamil Nadu Groundwater Act 2003", "Policy"),
            ("CGWA Extraction Guidelines 2020", "Policy"),
            ("Tamil Nadu Water Regulation Rules 2024", "Policy")
        ]
        for idx, (p_name, p_type) in enumerate(policies):
            node_id = f"POL-{idx+1:04d}"
            nodes.append({"id": node_id, "name": p_name, "type": "Policy"})
            policy_nodes.append(node_id)
            
        recs = [
            ("Rainwater Harvesting Mandate", "Recommendation"),
            ("Artificial Recharge via Check Dams", "Recommendation"),
            ("Extraction Restriction in Over-exploited blocks", "Recommendation")
        ]
        for idx, (r_name, r_type) in enumerate(recs):
            node_id = f"REC-{idx+1:04d}"
            nodes.append({"id": node_id, "name": r_name, "type": "Recommendation"})
            # Link recommendation to policies
            if policy_nodes:
                edges.append({"source": node_id, "target": policy_nodes[idx % len(policy_nodes)], "type": "implements"})

        for d in docs:
            node_id = f"DOC-{d.id:04d}"
            nodes.append({
                "id": node_id,
                "name": d.title,
                "type": "Assessment Report"
            })
            # Link Document to District if mentioned
            if d.district and d.district.upper() in dist_map:
                edges.append({
                    "source": node_id,
                    "target": dist_map[d.district.upper()],
                    "type": "assesses"
                })

        # Save to knowledge_graph.json
        graph_data = {
            "nodes": nodes,
            "edges": edges
        }
        
        with open(data_dir / "knowledge_graph.json", "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2)
            
        logger.info(f"Successfully compiled Spatial Knowledge Graph with {len(nodes)} nodes and {len(edges)} edges. Saved to: {data_dir / 'knowledge_graph.json'}")
        
    except Exception as e:
        logger.error(f"Error compiling knowledge graph: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    main()
