from rdkit import Chem
from rdkit.Chem import Descriptors, Draw
from rdkit.Chem import rdMolDescriptors
import json

BIOPESTICIDE_COMPOUNDS = [
    {"name": "Azadirachtin", "smiles": "CC1=C(C(=O)O)C(C)(C)OC1"},
    {"name": "Pyrethrin", "smiles": "CC1=CC(=O)C(C)(C)C1CC=C"},
    {"name": "Rotenone", "smiles": "O=C1OC2CC3=CC=CC=C3OC2C1"},
    {"name": "Neem oil", "smiles": "CCCCCCCC(=O)OCC"},
    {"name": "Limonene", "smiles": "CC1=CCC(=CC1)C(C)=C"},
]

def analyze_compound(compound):
    name = compound["name"]
    smiles = compound["smiles"]
    
    mol = Chem.MolFromSmiles(smiles)
    
    if mol is None:
        return {"name": name, "valid": False}
    
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    
    safe_for_humans = (
        mw < 500 and
        logp < 5 and
        hbd <= 5 and
        hba <= 10
    )
    
    return {
        "name": name,
        "molecular_weight": round(mw, 2),
        "logP": round(logp, 2),
        "h_bond_donors": hbd,
        "h_bond_acceptors": hba,
        "passes_safety_filter": safe_for_humans,
        "valid": True
    }

print("MOLECULAR ANALYSIS — BIOPESTICIDE CANDIDATES")
print("="*55)

results = []
for compound in BIOPESTICIDE_COMPOUNDS:
    result = analyze_compound(compound)
    results.append(result)
    
    if result["valid"]:
        print(f"\nCompound: {result['name']}")
        print(f"  Molecular Weight: {result['molecular_weight']} g/mol")
        print(f"  LogP: {result['logP']}")
        print(f"  H-Bond Donors: {result['h_bond_donors']}")
        print(f"  H-Bond Acceptors: {result['h_bond_acceptors']}")
        print(f"  Passes Safety Filter: {result['passes_safety_filter']}")

with open("molecular_analysis.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*55)
print("Molecular analysis saved to molecular_analysis.json")
