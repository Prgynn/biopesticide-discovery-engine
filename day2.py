def search_pest(pest_name, crop_name):
    print(f"Searching for: {pest_name}")
    print(f"Affecting crop: {crop_name}")
    return f"Found data on {pest_name} affecting {crop_name}"

result = search_pest("aphids", "mustard")
print(result)

pest_data = {
    "name": "aphids",
    "crop": "mustard",
    "damage_type": "sucks sap from leaves",
    "season": "winter",
    "known_biopesticides": ["neem oil", "pyrethrin"]
}

print(pest_data["name"])
print(pest_data["known_biopesticides"])