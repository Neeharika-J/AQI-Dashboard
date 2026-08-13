feature_groups = {
            "parks": {
                "tags": {
                    "leisure": [
                        "park",
                        "garden",
                        "nature_reserve",
                        "recreation_ground",
                        "playground"
                    ],

                    "landuse": [
                        "forest",
                        "meadow",
                        "grass",
                        "recreation_ground",
                        "orchard",
                        "vineyard"
                    ],

                    "natural": [
                        "wood",
                        "grassland",
                        "scrub",
                        "heath",
                        "wetland"
                    ],

                    "boundary": [
                        "national_park",
                        "protected_area"
                    ],

                    "amenity": [
                        "grave_yard"
                    ]
                },
                "color": "green",
                "geometry": "Polygon"
            },

            "highways": {
                "tags": {
                    "highway": True
                },
                "color": "yellow",
                "geometry": "LineString"
            },

            "industries": {
                "tags": {
                    "landuse": [
                        "industrial",
                        "construction",
                        "brownfield",
                        "depot",
                        "railway",
                        "quarry",
                        "port",
                        "commercial"
                    ],

                    "industrial": [
                        "factory",
                        "cement_works",
                        "steelworks",
                        "brickworks",
                        "chemical_plant",
                        "refinery",
                        "warehouse",
                        "plant",
                        "mill"
                    ],

                    "man_made": [
                        "works",
                        "wastewater_plant",
                        "pipeline",
                        "chimney",
                        "storage_tank",
                        "silo"
                    ],

                    "power": [
                        "plant",
                        "generator",
                        "substation"
                    ],

                    "building": [
                        "industrial",
                        "factory",
                        "warehouse",
                        "yes"
                    ],

                    "aeroway": [
                        "hangar"
                    ],

                    "railway": [
                        "yard",
                        "depot"
                    ]
                },
                "color": "blue",
                "geometry": "Polygon"
            }
        }