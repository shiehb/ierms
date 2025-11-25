REGION_1 = {
    "Ilocos Norte": {
        "1st District": [
            "Bacarra","Bangui","Burgos","City of Laoag","Pagudpud","Pasuquin","Piddig","San Nicolas","Sarrat","Vintar"
        ],
        "2nd District": [
            "Adams","Banna (Espiritu)","Batac City","Carasi","Currimao","Dingras","Dumalneg","Marcos","Nueva Era","Paoay","Pinili","Solsona"
        ],
    },
    "Ilocos Sur": {
        "1st District": [
            "Cabugao","Magsingal","San Juan","Santo Domingo","Sinait","Vigan City"
        ],
        "2nd District": [
            "Alilem","Banayoyo","Bantay","Burgos","Candon City","Caoayan","Cervantes","Galimuyod","Lidlidda","Nagbukel","Narvacan","Quirino","Salcedo","San Emilio","San Esteban","San Ildefonso","San Vicente","Santa","Santa Catalina","Santa Cruz","Santa Lucia","Santa Maria","Santiago","Sigay","Sugpon","Suyo","Tagudin"
        ],
    },
    "La Union": {
        "1st District": [
            "Bacnotan","Balaoan","Bangar","Luna","San Fernando City (Capital)","San Gabriel","Santol","Sudipen"
        ],
        "2nd District": [
            "Agoo","Aringay","Bagulin","Bauang","Burgos","Caba","Naguilian","Pugo","Rosario","San Juan","Santo Tomas","Tubao"
        ],
    },
    "Pangasinan": {
        "1st District": ["Alaminos City","Agno","Anda","Bani","Bolinao","Dasol","Infanta"],
        "2nd District": ["Bugallon","Labrador","Lingayen (Capital)","Mabini","Mangatarem","Sual"],
        "3rd District": ["Bayambang","Calasiao","Malasiqui","Mapandan","Santa Barbara"],
        "4th District": ["Dagupan City","Mangaldan","Manaoag","San Fabian"],
        "5th District": ["Basista","Bautista","Binalonan","Laoac","Pozorrubio","San Carlos City","San Manuel","Tayug","Umingan","Urbiztondo","Villasis"],
        "6th District": ["Asingan","Balungao","Natividad","Rosales","San Quintin","Sta. Maria","Urdaneta City"],
    },
}

def get_district_by_city(province: str, city: str) -> str | None:
    # Try exact match first
    province_map = REGION_1.get(province)
    
    # If no exact match, try case-insensitive match
    if not province_map:
        for prov_key in REGION_1.keys():
            if prov_key.lower() == province.lower():
                province_map = REGION_1[prov_key]
                break
    
    if not province_map:
        return None
    
    # Clean the input city name
    clean_city = city.strip()
    
    for district, cities in province_map.items():
        # Direct match first (case-insensitive)
        for city_in_list in cities:
            if clean_city.lower() == city_in_list.lower():
                return district
        
        # Try fuzzy matching for common variations
        for city_in_list in cities:
            # Remove common suffixes and compare base names
            base_city = city_in_list.replace(' City', '').replace(' (Capital)', '').strip()
            base_input = clean_city.replace(' City', '').replace(' (Capital)', '').strip()
            
            if base_city.lower() == base_input.lower():
                return district
            
            # Handle special cases like "San Fernando City" vs "San Fernando City (Capital)"
            # More robust matching for partial matches
            if (base_city.lower() in base_input.lower() or 
                base_input.lower() in base_city.lower() or
                base_city.lower().replace(' ', '') == base_input.lower().replace(' ', '')):
                return district
    
    return None

def list_districts(province: str | None = None):
    if province:
        return [{"province": province, "district": d, "cities": c} for d, c in REGION_1.get(province, {}).items()]
    data = []
    for prov, mapping in REGION_1.items():
        for d, c in mapping.items():
            data.append({"province": prov, "district": d, "cities": c})
    return data


