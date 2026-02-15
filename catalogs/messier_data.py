"""
Complete Messier Catalog Data

All 110 Messier objects with accurate astronomical data:
- Coordinates (J2000)
- Visual magnitude
- Angular size
- Distance
- Constellation
- Description
"""

# Format: (id, name, ra_deg, dec_deg, dso_type_value, mag, size_arcmin, distance_ly, constellation, description)
MESSIER_DATA = [
    # M1 - Crab Nebula
    (1, "Crab Nebula", 83.8221, 22.0145, "SNR", 8.4, 7.0, 6500, "Taurus",
     "Supernova remnant from explosion observed in 1054 AD. Contains a pulsar rotating 30 times per second."),
    
    # M2
    (2, "NGC 7089", 323.3625, -0.8233, "GC", 6.5, 16.0, 37500, "Aquarius",
     "One of the largest and richest globular clusters in the sky."),
    
    # M3
    (3, "NGC 5272", 205.5483, 28.3775, "GC", 6.2, 18.0, 33900, "Canes Venatici",
     "One of the finest globular clusters in the northern sky, containing around 500,000 stars."),
    
    # M4
    (4, "NGC 6121", 245.8967, -26.5258, "GC", 5.9, 36.0, 7200, "Scorpius",
     "Nearest globular cluster to Earth. Contains a pulsar and many white dwarfs."),
    
    # M5
    (5, "NGC 5904", 229.6383, 2.0811, "GC", 5.7, 23.0, 24500, "Serpens",
     "One of the oldest globular clusters, estimated at 13 billion years old."),
    
    # M6 - Butterfly Cluster
    (6, "Butterfly Cluster", 265.0817, -32.2167, "OC", 4.2, 25.0, 1600, "Scorpius",
     "Open cluster whose shape resembles a butterfly. Contains about 80 stars."),
    
    # M7 - Ptolemy Cluster
    (7, "Ptolemy Cluster", 268.4600, -34.8367, "OC", 3.3, 80.0, 980, "Scorpius",
     "One of the most prominent open clusters, mentioned by Ptolemy in 130 AD."),
    
    # M8 - Lagoon Nebula
    (8, "Lagoon Nebula", 270.9208, -24.3833, "HII", 6.0, 90.0, 5200, "Sagittarius",
     "Bright emission nebula with active star formation. Contains the young cluster NGC 6530."),
    
    # M9
    (9, "NGC 6333", 259.7958, -18.5158, "GC", 8.4, 12.0, 25800, "Ophiuchus",
     "Globular cluster located close to the galactic center, heavily obscured by dust."),
    
    # M10
    (10, "NGC 6254", 254.2875, -4.1006, "GC", 6.6, 20.0, 14300, "Ophiuchus",
     "Bright globular cluster with a dense, bright core."),
    
    # M11 - Wild Duck Cluster
    (11, "Wild Duck Cluster", 282.7667, -6.2667, "OC", 6.3, 14.0, 6200, "Scutum",
     "Rich open cluster resembling a flight of wild ducks. Contains about 2900 stars."),
    
    # M12
    (12, "NGC 6218", 251.8083, -1.9486, "GC", 7.7, 16.0, 16000, "Ophiuchus",
     "Loose globular cluster, one of the less concentrated Messier globulars."),
    
    # M13 - Hercules Cluster
    (13, "Hercules Cluster", 250.4229, 36.4614, "GC", 5.8, 20.0, 25100, "Hercules",
     "The Great Globular Cluster in Hercules. Contains several hundred thousand stars."),
    
    # M14
    (14, "NGC 6402", 264.4000, -3.2458, "GC", 8.3, 12.0, 30300, "Ophiuchus",
     "Rich globular cluster containing around 150,000 stars."),
    
    # M15
    (15, "NGC 7078", 322.4929, 12.1672, "GC", 6.4, 18.0, 33600, "Pegasus",
     "One of the densest globular clusters, possibly containing an intermediate-mass black hole."),
    
    # M16 - Eagle Nebula
    (16, "Eagle Nebula", 274.7000, -13.8000, "HII", 6.4, 35.0, 7000, "Serpens",
     "Famous for the 'Pillars of Creation' - towering columns of gas and dust imaged by Hubble."),
    
    # M17 - Omega Nebula
    (17, "Omega Nebula", 275.1958, -16.1758, "HII", 6.0, 46.0, 5500, "Sagittarius",
     "Also known as Swan Nebula. Bright emission nebula with active star formation."),
    
    # M18
    (18, "NGC 6613", 274.7250, -17.1333, "OC", 7.5, 9.0, 4900, "Sagittarius",
     "Sparse open cluster embedded in the Milky Way."),
    
    # M19
    (19, "NGC 6273", 255.6583, -26.2683, "GC", 7.5, 17.0, 28000, "Ophiuchus",
     "Slightly elliptical globular cluster, one of the most oblate known."),
    
    # M20 - Trifid Nebula
    (20, "Trifid Nebula", 270.6167, -23.0333, "HII", 6.3, 28.0, 5200, "Sagittarius",
     "Unusual nebula showing emission, reflection, and dark nebula all in one object."),
    
    # M21
    (21, "NGC 6531", 271.0917, -22.4833, "OC", 6.5, 13.0, 4250, "Sagittarius",
     "Young open cluster near the Trifid Nebula, containing about 57 stars."),
    
    # M22
    (22, "NGC 6656", 279.0996, -23.9047, "GC", 5.1, 32.0, 10400, "Sagittarius",
     "One of the brightest globular clusters visible from Earth, containing 70,000+ stars."),
    
    # M23
    (23, "NGC 6494", 269.2333, -19.0167, "OC", 6.9, 27.0, 2150, "Sagittarius",
     "Rich open cluster containing about 150 stars."),
    
    # M24 - Sagittarius Star Cloud
    (24, "Sagittarius Star Cloud", 274.5000, -18.5500, "OC", 4.5, 90.0, 10000, "Sagittarius",
     "Actually a window through the Milky Way revealing distant stars. Not a true cluster."),
    
    # M25
    (25, "IC 4725", 277.0000, -19.2500, "OC", 6.5, 40.0, 2000, "Sagittarius",
     "Open cluster containing a Cepheid variable star, U Sagittarii."),
    
    # M26
    (26, "NGC 6694", 281.3667, -9.3833, "OC", 8.0, 15.0, 5000, "Scutum",
     "Open cluster with a noticeable central condensation."),
    
    # M27 - Dumbbell Nebula
    (27, "Dumbbell Nebula", 299.9017, 22.7211, "PN", 7.5, 8.0, 1360, "Vulpecula",
     "First planetary nebula to be discovered by Messier in 1764. One of the brightest planetaries."),
    
    # M28
    (28, "NGC 6626", 277.8833, -24.8692, "GC", 7.7, 11.0, 17900, "Sagittarius",
     "Globular cluster that was one of the first found to contain a millisecond pulsar."),
    
    # M29
    (29, "NGC 6913", 309.0000, 38.5333, "OC", 7.1, 7.0, 4000, "Cygnus",
     "Small but relatively rich open cluster in the Milky Way."),
    
    # M30
    (30, "NGC 7099", 325.0925, -23.1800, "GC", 7.7, 12.0, 28000, "Capricornus",
     "Globular cluster that has undergone core collapse."),
    
    # M31 - Andromeda Galaxy
    (31, "Andromeda Galaxy", 10.6847, 41.2692, "SG", 3.4, 178.0, 2537000, "Andromeda",
     "The nearest spiral galaxy to the Milky Way. Contains ~1 trillion stars. Visible to naked eye."),
    
    # M32
    (32, "NGC 221", 10.6742, 40.8658, "EG", 8.9, 8.0, 2490000, "Andromeda",
     "Compact elliptical galaxy, satellite of M31. Contains very old stars."),
    
    # M33 - Triangulum Galaxy
    (33, "Triangulum Galaxy", 23.4621, 30.6603, "SG", 5.7, 70.0, 2730000, "Triangulum",
     "Third-largest galaxy in the Local Group. Barely visible to naked eye under dark skies."),
    
    # M34
    (34, "NGC 1039", 40.5292, 42.7194, "OC", 5.5, 35.0, 1500, "Perseus",
     "Open cluster containing about 100 stars, easily resolved with binoculars."),
    
    # M35
    (35, "NGC 2168", 92.3000, 24.3333, "OC", 5.3, 28.0, 2800, "Gemini",
     "Large, rich open cluster. In background lies older, more distant cluster NGC 2158."),
    
    # M36
    (36, "NGC 1960", 84.0750, 34.1333, "OC", 6.3, 12.0, 4100, "Auriga",
     "One of three prominent Messier clusters in Auriga, containing about 60 stars."),
    
    # M37
    (37, "NGC 2099", 88.0583, 32.5500, "OC", 6.2, 24.0, 4500, "Auriga",
     "Richest of the three Auriga Messier clusters, containing about 150 stars."),
    
    # M38
    (38, "NGC 1912", 82.1833, 35.8333, "OC", 7.4, 21.0, 4200, "Auriga",
     "Open cluster that appears to form a cross or oblique cross pattern."),
    
    # M39
    (39, "NGC 7092", 323.8583, 48.4333, "OC", 4.6, 32.0, 825, "Cygnus",
     "Loose open cluster of about 30 stars, one of the nearest to Earth."),
    
    # M40 - Winnecke 4
    (40, "Winnecke 4", 185.5833, 58.0833, "OC", 8.4, 1.0, 510, "Ursa Major",
     "Actually a double star, not a deep-sky object. Messier's 'mistake'."),
    
    # M41
    (41, "NGC 2287", 101.5000, -20.7500, "OC", 4.5, 38.0, 2300, "Canis Major",
     "Bright open cluster south of Sirius, containing about 100 stars."),
    
    # M42 - Orion Nebula
    (42, "Orion Nebula", 83.8221, -5.3911, "HII", 4.0, 85.0, 1344, "Orion",
     "The closest region of massive star formation. Visible to naked eye. Contains the Trapezium cluster."),
    
    # M43
    (43, "De Mairan's Nebula", 83.8583, -5.2667, "HII", 9.0, 20.0, 1600, "Orion",
     "Small nebula separated from M42 by a dark lane. Part of the Orion Molecular Cloud."),
    
    # M44 - Beehive Cluster
    (44, "Beehive Cluster", 130.0583, 19.6667, "OC", 3.7, 95.0, 577, "Cancer",
     "One of the nearest open clusters. Known since antiquity as Praesepe."),
    
    # M45 - Pleiades
    (45, "Pleiades", 56.8500, 24.1167, "OC", 1.6, 110.0, 444, "Taurus",
     "The most famous star cluster. Contains blue-white stars about 100 million years old."),
    
    # M46
    (46, "NGC 2437", 115.4167, -14.8167, "OC", 6.0, 27.0, 5400, "Puppis",
     "Rich open cluster with a planetary nebula (NGC 2438) apparently superimposed on it."),
    
    # M47
    (47, "NGC 2422", 114.1500, -14.4833, "OC", 4.4, 30.0, 1600, "Puppis",
     "Loose, bright open cluster containing about 50 stars."),
    
    # M48
    (48, "NGC 2548", 123.4167, -5.7500, "OC", 5.5, 54.0, 1500, "Hydra",
     "Large open cluster containing about 80 stars spread over a large area."),
    
    # M49
    (49, "NGC 4472", 187.4446, 7.9997, "EG", 8.4, 10.0, 55900000, "Virgo",
     "Brightest galaxy in the Virgo Cluster. Giant elliptical containing trillions of stars."),
    
    # M50
    (50, "NGC 2323", 105.7000, -8.3333, "OC", 6.3, 16.0, 3200, "Monoceros",
     "Rich open cluster with a noticeable red star near its center."),
    
    # M51 - Whirlpool Galaxy
    (51, "Whirlpool Galaxy", 202.4696, 47.1952, "SG", 8.4, 11.0, 23160000, "Canes Venatici",
     "Classic face-on spiral galaxy interacting with smaller companion NGC 5195."),
    
    # M52
    (52, "NGC 7654", 351.1667, 61.5833, "OC", 7.3, 13.0, 5000, "Cassiopeia",
     "Rich open cluster partially obscured by dust."),
    
    # M53
    (53, "NGC 5024", 198.2300, 18.1683, "GC", 7.7, 13.0, 58000, "Coma Berenices",
     "One of the more remote Messier globular clusters, near the north galactic pole."),
    
    # M54
    (54, "NGC 6715", 283.7642, -30.4794, "GC", 8.4, 12.0, 87400, "Sagittarius",
     "Remote globular cluster that is actually the nucleus of the Sagittarius Dwarf Galaxy."),
    
    # M55
    (55, "NGC 6809", 294.9975, -30.9642, "GC", 7.4, 19.0, 17300, "Sagittarius",
     "Loose, large globular cluster often described as looking like a globular on the verge of dissolving."),
    
    # M56
    (56, "NGC 6779", 289.1483, 30.1847, "GC", 8.4, 8.8, 32900, "Lyra",
     "Globular cluster between Lyra and Cygnus."),
    
    # M57 - Ring Nebula
    (57, "Ring Nebula", 283.3963, 33.0297, "PN", 8.8, 1.5, 2300, "Lyra",
     "Classic planetary nebula, the expelled outer layers of a dying star. Easily shows ring shape."),
    
    # M58
    (58, "NGC 4579", 189.4317, 11.8181, "SG", 10.5, 6.0, 62000000, "Virgo",
     "Brightest barred spiral galaxy in the Virgo Cluster."),
    
    # M59
    (59, "NGC 4621", 190.5083, 11.6464, "EG", 10.6, 5.0, 60000000, "Virgo",
     "Elliptical galaxy in the core of the Virgo Cluster."),
    
    # M60
    (60, "NGC 4649", 190.9167, 11.5528, "EG", 9.8, 7.0, 54000000, "Virgo",
     "Giant elliptical galaxy near the center of the Virgo Cluster. Contains a massive black hole."),
    
    # M61
    (61, "NGC 4303", 185.4788, 4.4742, "SG", 9.7, 6.0, 52500000, "Virgo",
     "One of the largest galaxies in the Virgo Cluster, with active star formation."),
    
    # M62
    (62, "NGC 6266", 255.3033, -30.1139, "GC", 7.4, 15.0, 22500, "Ophiuchus",
     "Highly asymmetric globular cluster due to proximity to galactic center."),
    
    # M63 - Sunflower Galaxy
    (63, "Sunflower Galaxy", 198.9554, 42.0294, "SG", 8.6, 12.0, 37000000, "Canes Venatici",
     "Spiral galaxy with a distinctive appearance resembling a sunflower."),
    
    # M64 - Black Eye Galaxy
    (64, "Black Eye Galaxy", 194.1821, 21.6828, "SG", 9.4, 10.0, 24000000, "Coma Berenices",
     "Distinctive galaxy with a dark dust lane in front of its bright nucleus."),
    
    # M65
    (65, "NGC 3623", 169.7333, 13.0919, "SG", 10.2, 10.0, 35000000, "Leo",
     "Part of the Leo Triplet of galaxies along with M66 and NGC 3628."),
    
    # M66
    (66, "NGC 3627", 170.0625, 12.9911, "SG", 9.7, 9.0, 36000000, "Leo",
     "Largest of the Leo Triplet. Shows distorted spiral arms due to gravitational interactions."),
    
    # M67
    (67, "NGC 2682", 132.8250, 11.8167, "OC", 6.1, 25.0, 2700, "Cancer",
     "One of the oldest known open clusters, estimated at 3.2-5 billion years old."),
    
    # M68
    (68, "NGC 4590", 189.8667, -26.7444, "GC", 8.3, 12.0, 33600, "Hydra",
     "Globular cluster located in the southern sky."),
    
    # M69
    (69, "NGC 6637", 277.8458, -32.3481, "GC", 8.3, 10.0, 29700, "Sagittarius",
     "Globular cluster near the galactic center."),
    
    # M70
    (70, "NGC 6681", 280.8025, -32.2928, "GC", 9.1, 8.0, 29400, "Sagittarius",
     "Globular cluster similar to and near M69."),
    
    # M71
    (71, "NGC 6838", 298.4375, 18.7792, "GC", 8.4, 7.2, 13000, "Sagitta",
     "Borderline globular/open cluster. Not as concentrated as typical globulars."),
    
    # M72
    (72, "NGC 6981", 313.3650, -12.5369, "GC", 9.4, 6.6, 55400, "Aquarius",
     "Relatively distant globular cluster, difficult to resolve into individual stars."),
    
    # M73
    (73, "NGC 6994", 314.7483, -12.6333, "OC", 9.0, 2.8, 2000, "Aquarius",
     "A small asterism of four stars, another of Messier's controversial entries."),
    
    # M74 - Phantom Galaxy
    (74, "Phantom Galaxy", 24.1742, 15.7836, "SG", 10.0, 10.0, 32000000, "Pisces",
     "Classic face-on spiral, considered one of the most difficult Messier objects to see."),
    
    # M75
    (75, "NGC 6864", 301.5200, -21.9211, "GC", 8.6, 6.8, 67500, "Sagittarius",
     "One of the most remote and highly concentrated Messier globular clusters."),
    
    # M76 - Little Dumbbell Nebula
    (76, "Little Dumbbell Nebula", 25.5792, 51.5756, "PN", 10.1, 2.7, 2500, "Perseus",
     "Faint planetary nebula, one of the most difficult Messier objects."),
    
    # M77
    (77, "NGC 1068", 40.6700, -0.0133, "SG", 9.7, 7.0, 47000000, "Cetus",
     "Seyfert galaxy with an active galactic nucleus. One of the nearest AGN to Earth."),
    
    # M78
    (78, "NGC 2068", 86.6875, 0.0667, "RN", 8.0, 8.0, 1600, "Orion",
     "Brightest diffuse reflection nebula in the sky, part of the Orion Molecular Cloud."),
    
    # M79
    (79, "NGC 1904", 81.0458, -24.5239, "GC", 8.6, 10.0, 41000, "Lepus",
     "Globular cluster in the winter sky, possibly captured from the Canis Major Dwarf Galaxy."),
    
    # M80
    (80, "NGC 6093", 244.2600, -22.9758, "GC", 7.9, 10.0, 32600, "Scorpius",
     "One of the densest globular clusters in the Milky Way. Site of a nova in 1860."),
    
    # M81 - Bode's Galaxy
    (81, "Bode's Galaxy", 148.8882, 69.0653, "SG", 6.9, 27.0, 11800000, "Ursa Major",
     "Grand spiral galaxy, one of the brightest in the northern sky."),
    
    # M82 - Cigar Galaxy
    (82, "Cigar Galaxy", 148.9696, 69.6797, "IG", 8.4, 11.0, 11400000, "Ursa Major",
     "Starburst galaxy interacting with M81. Shows spectacular jets of gas from its center."),
    
    # M83 - Southern Pinwheel
    (83, "Southern Pinwheel", 204.2538, -29.8658, "SG", 7.5, 13.0, 15000000, "Hydra",
     "Barred spiral galaxy with a very high rate of supernova occurrence."),
    
    # M84
    (84, "NGC 4374", 186.2658, 12.8869, "EG", 10.1, 6.5, 60000000, "Virgo",
     "Giant elliptical galaxy near the center of the Virgo Cluster."),
    
    # M85
    (85, "NGC 4382", 186.3508, 18.1911, "EG", 9.2, 7.0, 60000000, "Coma Berenices",
     "Northernmost member of the Virgo Cluster in Messier's catalog."),
    
    # M86
    (86, "NGC 4406", 186.5500, 12.9464, "EG", 9.8, 9.0, 60000000, "Virgo",
     "Elliptical galaxy moving toward us, one of the few blueshifted galaxies."),
    
    # M87 - Virgo A
    (87, "Virgo A", 187.7059, 12.3911, "EG", 9.6, 7.0, 53490000, "Virgo",
     "Giant elliptical galaxy with a famous relativistic jet. First galaxy to have its black hole imaged."),
    
    # M88
    (88, "NGC 4501", 188.0025, 14.4203, "SG", 10.4, 7.0, 63000000, "Coma Berenices",
     "One of the brightest spiral galaxies in the Virgo Cluster."),
    
    # M89
    (89, "NGC 4552", 188.9167, 12.5564, "EG", 10.7, 4.0, 53000000, "Virgo",
     "Nearly perfectly round elliptical galaxy in the Virgo Cluster."),
    
    # M90
    (90, "NGC 4569", 189.2083, 13.1628, "SG", 10.3, 10.0, 58700000, "Virgo",
     "Spiral galaxy moving toward us. One of the few non-cosmological blueshifts."),
    
    # M91
    (91, "NGC 4548", 188.8583, 14.4958, "SG", 11.0, 5.0, 63000000, "Coma Berenices",
     "Barred spiral galaxy, was Messier's 'missing object' for many years."),
    
    # M92
    (92, "NGC 6341", 259.2800, 43.1367, "GC", 6.5, 14.0, 26700, "Hercules",
     "Fine globular cluster often overlooked because of its proximity to the famous M13."),
    
    # M93
    (93, "NGC 2447", 116.1000, -23.8500, "OC", 6.0, 22.0, 3600, "Puppis",
     "Open cluster with a butterfly or arrowhead shape."),
    
    # M94
    (94, "NGC 4736", 192.7208, 41.1206, "SG", 9.0, 11.0, 16000000, "Canes Venatici",
     "Spiral galaxy with a very bright core and a faint outer ring structure."),
    
    # M95
    (95, "NGC 3351", 160.9900, 11.7033, "SG", 10.5, 7.0, 38000000, "Leo",
     "Barred spiral galaxy, member of the Leo I group."),
    
    # M96
    (96, "NGC 3368", 161.6908, 11.8200, "SG", 10.1, 8.0, 38000000, "Leo",
     "Brightest galaxy in the Leo I group."),
    
    # M97 - Owl Nebula
    (97, "Owl Nebula", 168.6950, 55.0186, "PN", 9.9, 3.4, 2030, "Ursa Major",
     "Planetary nebula with two dark 'eye' holes giving it an owl-like appearance."),
    
    # M98
    (98, "NGC 4192", 183.4517, 14.9003, "SG", 10.9, 10.0, 44400000, "Coma Berenices",
     "Nearly edge-on spiral galaxy, one of the brighter members of the Virgo Cluster."),
    
    # M99
    (99, "NGC 4254", 184.7067, 14.4164, "SG", 10.4, 5.0, 55000000, "Coma Berenices",
     "Nearly face-on spiral galaxy showing asymmetric arms due to interactions."),
    
    # M100
    (100, "NGC 4321", 185.7287, 15.8222, "SG", 10.1, 7.0, 55000000, "Coma Berenices",
     "Grand design spiral galaxy with two prominent spiral arms."),
    
    # M101 - Pinwheel Galaxy
    (101, "Pinwheel Galaxy", 210.8025, 54.3492, "SG", 7.9, 29.0, 20900000, "Ursa Major",
     "Large face-on spiral galaxy with asymmetric arms and many HII regions."),
    
    # M102 (disputed - likely NGC 5866)
    (102, "NGC 5866", 226.6233, 55.7658, "EG", 10.7, 5.0, 44000000, "Draco",
     "Lenticular galaxy seen edge-on. Identity disputed - may be duplicate of M101."),
    
    # M103
    (103, "NGC 581", 23.3417, 60.6500, "OC", 7.4, 6.0, 8500, "Cassiopeia",
     "Small but bright open cluster in the Milky Way."),
    
    # M104 - Sombrero Galaxy
    (104, "Sombrero Galaxy", 189.9976, -11.6231, "SG", 8.0, 9.0, 31100000, "Virgo",
     "Distinctive galaxy with a prominent dust lane and large central bulge."),
    
    # M105
    (105, "NGC 3379", 161.9575, 12.5817, "EG", 10.2, 5.0, 38000000, "Leo",
     "Prototypical elliptical galaxy, member of the Leo I group."),
    
    # M106
    (106, "NGC 4258", 184.7400, 47.3039, "SG", 9.1, 19.0, 23700000, "Canes Venatici",
     "Spiral galaxy with anomalous arms that are jets of hot gas."),
    
    # M107
    (107, "NGC 6171", 248.1325, -13.0539, "GC", 8.9, 13.0, 21000, "Ophiuchus",
     "Loose globular cluster, one of the last objects added to the Messier catalog."),
    
    # M108
    (108, "NGC 3556", 167.8792, 55.6739, "SG", 10.7, 8.0, 46000000, "Ursa Major",
     "Nearly edge-on barred spiral galaxy near M97."),
    
    # M109
    (109, "NGC 3992", 179.3992, 53.3744, "SG", 10.6, 7.5, 55000000, "Ursa Major",
     "Barred spiral galaxy in Ursa Major."),
    
    # M110
    (110, "NGC 205", 10.0917, 41.6853, "EG", 8.9, 22.0, 2690000, "Andromeda",
     "Satellite galaxy of M31, a dwarf elliptical. Contains young blue stars unusually for ellipticals."),
]
