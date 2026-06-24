import sys
import os
import xgboost as xgb
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def inspect_trees():
    model_path = PROJECT_ROOT / "src" / "ml" / "gatekeeper_v1.model"
    if not model_path.exists():
        print("Model file does not exist!")
        return
        
    model = xgb.Booster()
    model.load_model(str(model_path))
    
    # Dump trees
    trees = model.get_dump()
    print(f"Total Trees in Model: {len(trees)}")
    
    if len(trees) == 0:
        print("Model has NO trees!")
        return
        
    print("\n--- FIRST 3 TREES DUMP ---")
    for i, tree in enumerate(trees[:3]):
        print(f"Tree {i}:")
        print(tree)
        print("-" * 40)

if __name__ == "__main__":
    inspect_trees()
