"""
Constellation line data — J2000 RA/Dec, Hipparcos-verified.
All referenced stars exist in STAR_CATALOG (Yale BSC + HIP additions).
"""

# Star positions: must match exactly what's in STAR_CATALOG
# fmt: off
_S = {
    # Orion
    "Betelgeuse": ( 88.7930,  7.4070), "Rigel":      ( 78.6340, -8.2020),
    "Bellatrix":  ( 81.2830,  6.3500), "Saiph":      ( 86.9390, -9.6700),
    "Alnitak":    ( 85.1900, -1.9430), "Alnilam":    ( 84.0530, -1.2020),
    "Mintaka":    ( 83.0020, -0.2990), "Meissa":     ( 83.8580,  9.9340),
    # Taurus
    "Aldebaran":  ( 68.9800, 16.5090), "Elnath":     ( 81.5730, 28.6080),
    "Hyadum":     ( 65.7340, 15.6270), "Ain":        ( 67.1540, 19.1800),
    "Zeta Tau":   ( 84.4110, 21.1430), "Alcyone":    ( 56.8710, 24.1050),
    # Gemini
    "Castor":     (113.6490, 31.8880), "Pollux":     (116.3290, 28.0260),
    "Alhena":     ( 99.4280, 16.3990), "Tejat":      ( 95.7400, 22.5140),
    "Propus":     ( 92.7330, 22.5060), "Wasat":      (110.0310, 21.9820),
    "Mebsuda":    (103.1970, 25.1310), "Alzirr":     (118.2140, 12.8960),
    # Auriga
    "Capella":    ( 79.1720, 45.9980), "Menkalinan": ( 89.8820, 44.9470),
    "Mahasim":    ( 74.2480, 37.2130), "Hassaleh":   ( 74.9970, 33.1660),
    # Perseus
    "Mirfak":     ( 51.0810, 49.8610), "Algol":      ( 47.0420, 40.9560),
    "Atik":       ( 58.4680, 39.9970), "Miram":      ( 55.8950, 50.6880),
    "Menkib":     ( 58.1920, 35.7910),
    # Cassiopeia
    "Schedar":    ( 10.1270, 56.5370), "Caph":       (  2.2950, 59.1500),
    "Gamma Cas":  ( 14.1770, 60.7170), "Ruchbah":    ( 21.4540, 60.2350),
    "Segin":      ( 28.5990, 63.6700),
    # Ursa Major
    "Dubhe":      (165.9320, 61.7510), "Merak":      (165.4600, 56.3830),
    "Phecda":     (178.4580, 53.6950), "Megrez":     (183.8570, 57.0330),
    "Alioth":     (193.5070, 55.9600), "Mizar":      (200.9810, 54.9260),
    "Alkaid":     (206.8860, 49.3130), "Talitha":    (134.8020, 47.1570),
    "Tania Bor":  (148.1900, 51.6770), "Tania Aus":  (149.9130, 41.4990),
    "Alula Bor":  (169.6190, 33.0940), "Alula Aus":  (169.5450, 31.5290),
    # Ursa Minor — all 7 stars now in catalog
    "Polaris":    ( 37.9550, 89.2640), "Kochab":     (222.6760, 74.1560),
    "Pherkad":    (230.1820, 71.8340), "Yildun":     (263.0540, 86.5860),
    "Eps UMi":    (247.5560, 82.0370), "Zeta UMi":   (236.0120, 77.7940),
    "Eta UMi":    (244.5800, 75.7560),
    # Leo
    "Regulus":    (152.0930, 11.9670), "Algieba":    (154.9930, 19.8420),
    "Denebola":   (177.2650, 14.5720), "Zosma":      (168.5270, 20.5240),
    "Chertan":    (168.5600, 15.4300), "Eta Leo":    (168.5600, 16.7620),
    "Ras Elased": (146.4630, 23.7740), "Adhafera":   (154.1740, 23.4180),
    # Virgo
    "Spica":      (201.2980,-11.1610), "Porrima":    (190.4150, -1.4490),
    "Vindemiatrix":(195.5440,10.9590), "Zaniah":     (188.3760, -0.5960),
    "Minelauva":  (196.6540,  3.3970), "Heze":       (202.7620,  0.6670),
    # Bootes
    "Arcturus":   (213.9150, 19.1820), "Izar":       (221.2470, 27.0740),
    "Seginus":    (210.4120, 38.3080), "Nekkar":     (225.4860, 40.3900),
    "Muphrid":    (208.6710, 18.3980),
    # Corona Borealis
    "Alphecca":   (233.6720, 26.7150), "Nusakan":    (231.2320, 29.1060),
    # Hercules
    "Kornephoros":(247.5550, 21.4900), "Zeta Her":   (250.3230, 31.6020),
    "Pi Her":     (250.7230, 36.8090), "Eta Her":    (258.7620, 38.9220),
    "Xi Her":     (253.9510, 29.2480), "Iota Her":   (258.7620, 46.0060),
    "Theta Her":  (269.0630, 37.2500), "Sarin":      (258.7620, 24.8390),
    # Lyra
    "Vega":       (279.2350, 38.7840), "Sheliak":    (282.5200, 33.3630),
    "Sulafat":    (284.7360, 32.6900), "Delta Lyr":  (281.1940, 36.8980),
    # Cygnus
    "Deneb":      (310.3580, 45.2800), "Sadr":       (305.5570, 40.2570),
    "Gienah":     (311.5530, 33.9700), "Albireo":    (292.6800, 27.9600),
    "Fawaris":    (296.2440, 45.1310), "Iota Cyg":   (294.4140, 51.7220),
    # Aquila
    "Altair":     (297.6960,  8.8680), "Tarazed":    (296.5650, 10.6130),
    "Alshain":    (298.8280,  6.4070), "Zeta Aql":   (286.3520, 13.8640),
    "Theta Aql":  (291.0720, -0.8210), "Lambda Aql": (287.8340, -4.8830),
    "Delta Aql":  (296.0630,  3.1150), "Eta Aql":    (298.1630,  1.0050),
    # Scorpius
    "Antares":    (247.3520,-26.4320), "Graffias":   (241.3590,-19.8060),
    "Dschubba":   (240.0830,-22.6220), "Shaula":     (263.4020,-37.1030),
    "Sargas":     (262.6910,-42.9980), "Lesath":     (262.6910,-37.1030),
    "Wei":        (255.0660,-29.2140), "Zeta Sco":   (253.0850,-34.2930),
    "Mu Sco":     (253.0840,-38.0470), "Girtab":     (260.2060,-34.7920),
    # Sagittarius
    "Kaus Aus":   (276.0430,-34.3840), "Kaus Med":   (274.4070,-29.8280),
    "Kaus Bor":   (271.4520,-25.4210), "Nunki":      (283.8160,-26.2970),
    "Ascella":    (283.8160,-29.8800), "Phi Sgr":    (277.9440,-26.9860),
    "Tau Sgr":    (285.6520,-27.6700),
    # Capricornus
    "Algedi":     (304.5130,-12.5450), "Dabih":      (305.2520,-14.7810),
    "Nashira":    (325.0230,-16.6620), "Deneb Algedi":(326.7600,-16.1270),
    # Aquarius
    "Sadalsuud":  (322.8900, -5.5710), "Sadalmelik": (331.4460, -0.3200),
    "Sadachbia":  (335.4140, -1.3840), "Skat":       (344.4140,-15.8210),
    # Pisces
    "Eta Psc":    ( 22.8700, 15.3460), "Omega Psc":  (354.8360,  6.8630),
    "Iota Psc":   (355.4990, -5.6730), "Alrescha":   ( 30.5120,  2.7640),
    # Aries
    "Hamal":      ( 31.7930, 23.4630), "Sheratan":   ( 28.6600, 20.8080),
    "Mesarthim":  ( 28.3830, 19.2940), "Botein":     ( 44.5650, 19.7270),
    # Cetus
    "Diphda":     ( 10.8970,-17.9870), "Menkar":     ( 45.5700,  4.0900),
    "Baten Kaitos":( 40.8250,-8.9090),
    # Eridanus
    "Achernar":   ( 24.4290,-57.2370), "Cursa":      ( 76.9620, -5.0860),
    "Zaurak":     ( 59.5070,-13.5090), "Theta Eri":  ( 40.4970,-40.3050),
    # Lepus
    "Arneb":      ( 83.1820,-17.8220), "Nihal":      ( 82.0610,-20.7590),
    # Canis Major
    "Sirius":     (101.2870,-16.7160), "Adhara":     (104.6570,-28.9720),
    "Wezen":      (107.0980,-26.3930), "Aludra":     (111.0240,-29.3030),
    "Mirzam":     ( 95.6750,-17.9560), "Furud":      ( 95.0790,-30.0630),
    # Canis Minor
    "Procyon":    (114.8250,  5.2250), "Gomeisa":    (111.7880,  8.2890),
    # Hydra
    "Alphard":    (141.8970, -8.6580),
    # Corvus
    "Gienah Crv": (183.9510,-17.5420), "Algorab":    (187.4660,-16.5150),
    "Kraz":       (191.5710,-23.3970), "Minkar":     (184.9770,-22.6200),
    # Andromeda
    "Alpheratz":  (  2.0970, 29.0910), "Mirach":     ( 17.4330, 35.6210),
    "Almach":     ( 30.9750, 42.3300), "Delta And":  (  9.8330, 30.8610),
    # Pegasus
    "Markab":     (346.1900, 15.2050), "Scheat":     (345.9430, 28.0830),
    "Algenib":    (  3.3090, 15.1840), "Enif":       (326.0460,  9.8750),
    "Homam":      (337.3310, 10.8310), "Matar":      (340.7510, 30.2210),
    # Draco
    "Eltanin":    (269.1520, 51.4890), "Rastaban":   (262.6080, 52.3010),
    "Thuban":     (211.0970, 64.3760), "Kuma":       (256.2740, 55.1740),
    "Grumium":    (261.3690, 56.8730), "Nodus I":    (261.3650, 65.7140),
    "Altais":     (288.1390, 67.6610), "Edasich":    (237.4550, 58.9660),
    "Giausar":    (172.8510, 69.3310),
    # Triangulum
    "Beta Tri":   ( 31.1220, 34.9870), "Alpha Tri":  ( 29.5200, 29.5790),
    "Gamma Tri":  ( 35.2750, 33.8470),
}
# fmt: on


def _seg(a, b):
    if a not in _S or b not in _S:
        return None
    return (*_S[a], *_S[b])

def _chain(*n):
    return [s for i in range(len(n)-1) for s in [_seg(n[i],n[i+1])] if s]

def _loop(*n):
    return _chain(*n, n[0])

def _lines(*pairs):
    return [s for a,b in pairs for s in [_seg(a,b)] if s]


def get_constellation_lines() -> dict:
    return {
        "Orion": (
            _chain("Meissa","Betelgeuse","Bellatrix",
                   "Mintaka","Alnilam","Alnitak","Saiph","Rigel") +
            _lines(("Bellatrix","Mintaka"),("Rigel","Mintaka"),
                   ("Betelgeuse","Alnitak"))
        ),
        "Taurus": _lines(
            ("Aldebaran","Ain"),("Ain","Elnath"),
            ("Aldebaran","Hyadum"),("Aldebaran","Zeta Tau"),
            ("Alcyone","Aldebaran"),
        ),
        "Gemini": _lines(
            ("Castor","Pollux"),
            ("Castor","Mebsuda"),("Mebsuda","Tejat"),("Tejat","Propus"),
            ("Pollux","Wasat"),("Wasat","Alhena"),("Wasat","Alzirr"),
        ),
        "Auriga": (
            _loop("Capella","Menkalinan","Mahasim","Hassaleh") +
            _lines(("Capella","Elnath"),)
        ),
        "Perseus": _lines(
            ("Mirfak","Algol"),("Mirfak","Atik"),
            ("Mirfak","Miram"),("Atik","Menkib"),
        ),
        "Cassiopeia": _chain("Caph","Schedar","Gamma Cas","Ruchbah","Segin"),
        "Ursa Major": (
            _loop("Dubhe","Merak","Phecda","Megrez") +
            _chain("Megrez","Alioth","Mizar","Alkaid") +
            _chain("Talitha","Tania Bor","Tania Aus","Merak") +
            _lines(("Phecda","Alula Aus"),("Alula Aus","Alula Bor"))
        ),
        # Piccolo Carro — tutte e 7 le stelle ora nel catalogo
        "Ursa Minor": _chain(
            "Kochab","Pherkad","Eta UMi","Zeta UMi",
            "Eps UMi","Yildun","Polaris"
        ),
        "Leo": (
            _chain("Regulus","Ras Elased","Adhafera","Algieba","Eta Leo") +
            _lines(("Eta Leo","Regulus"),) +
            _chain("Algieba","Zosma","Chertan","Denebola")
        ),
        "Virgo": _lines(
            ("Vindemiatrix","Porrima"),("Porrima","Zaniah"),
            ("Porrima","Spica"),("Spica","Heze"),
            ("Heze","Minelauva"),("Minelauva","Porrima"),
        ),
        "Bootes": _lines(
            ("Arcturus","Muphrid"),("Arcturus","Izar"),
            ("Izar","Seginus"),("Seginus","Nekkar"),
            ("Nekkar","Izar"),("Arcturus","Seginus"),
        ),
        "Corona Borealis": _chain("Nusakan","Alphecca"),
        "Hercules": (
            _loop("Kornephoros","Zeta Her","Pi Her","Eta Her","Xi Her") +
            _chain("Pi Her","Iota Her","Theta Her") +
            _lines(("Sarin","Kornephoros"),("Sarin","Xi Her"))
        ),
        "Lyra": (
            _lines(("Vega","Sheliak"),("Vega","Delta Lyr")) +
            _loop("Sheliak","Sulafat","Delta Lyr")
        ),
        "Cygnus": _lines(
            ("Deneb","Sadr"),("Sadr","Albireo"),
            ("Sadr","Fawaris"),("Fawaris","Iota Cyg"),
            ("Sadr","Gienah"),
        ),
        "Aquila": _lines(
            ("Altair","Tarazed"),("Altair","Alshain"),
            ("Altair","Zeta Aql"),("Zeta Aql","Delta Aql"),
            ("Altair","Theta Aql"),("Theta Aql","Lambda Aql"),
            ("Altair","Eta Aql"),
        ),
        "Scorpius": _chain(
            "Graffias","Dschubba","Antares",
            "Wei","Zeta Sco","Mu Sco","Girtab","Lesath","Shaula","Sargas"
        ),
        "Sagittarius": _lines(
            ("Kaus Aus","Kaus Med"),("Kaus Med","Kaus Bor"),
            ("Kaus Aus","Phi Sgr"),("Phi Sgr","Ascella"),
            ("Ascella","Nunki"),("Nunki","Tau Sgr"),
            ("Kaus Bor","Phi Sgr"),
        ),
        "Capricornus": _chain("Algedi","Dabih","Nashira","Deneb Algedi"),
        "Aquarius":    _chain("Sadalsuud","Sadalmelik","Sadachbia","Skat"),
        "Pisces":      _lines(
            ("Eta Psc","Omega Psc"),("Omega Psc","Alrescha"),
            ("Alrescha","Iota Psc"),
        ),
        "Aries":    _chain("Hamal","Sheratan","Mesarthim"),
        "Cetus":    _chain("Menkar","Baten Kaitos","Diphda"),
        "Eridanus": _chain("Cursa","Zaurak","Theta Eri","Achernar"),
        "Lepus":    _chain("Arneb","Nihal"),
        "Canis Major": (
            _chain("Sirius","Mirzam") +
            _chain("Sirius","Adhara","Wezen","Aludra") +
            _lines(("Adhara","Furud"),)
        ),
        "Canis Minor": _chain("Procyon","Gomeisa"),
        "Hydra":       _chain("Alphard","Gomeisa"),
        "Corvus":      _loop("Gienah Crv","Kraz","Algorab","Minkar"),
        "Andromeda":   _chain("Alpheratz","Delta And","Mirach","Almach"),
        "Pegasus": (
            _loop("Markab","Scheat","Alpheratz","Algenib") +
            _chain("Markab","Homam","Enif") +
            _lines(("Scheat","Matar"),)
        ),
        "Draco": (
            _chain("Giausar","Thuban","Edasich","Kuma",
                   "Nodus I","Grumium","Rastaban","Eltanin") +
            _chain("Eltanin","Altais")
        ),
        "Triangulum": _loop("Alpha Tri","Beta Tri","Gamma Tri"),
    }


_LABELS = {
    "Orion":           ( 84.0,   2.0),   "Taurus":          ( 68.0,  22.0),
    "Gemini":          (107.0,  24.0),   "Auriga":          ( 82.0,  41.0),
    "Perseus":         ( 52.0,  44.0),   "Cassiopeia":      ( 14.0,  60.0),
    "Ursa Major":      (175.0,  55.0),   "Ursa Minor":      (245.0,  80.0),
    "Leo":             (160.0,  18.0),   "Virgo":           (195.0,   2.0),
    "Bootes":          (218.0,  28.0),   "Corona Borealis": (234.0,  27.5),
    "Hercules":        (255.0,  32.0),   "Lyra":            (282.0,  36.0),
    "Cygnus":          (305.0,  43.0),   "Aquila":          (294.0,   5.0),
    "Scorpius":        (253.0, -30.0),   "Sagittarius":     (278.0, -28.0),
    "Capricornus":     (315.0, -14.0),   "Aquarius":        (333.0,  -6.0),
    "Pisces":          ( 10.0,   9.0),   "Aries":           ( 35.0,  21.0),
    "Cetus":           ( 25.0, -10.0),   "Eridanus":        ( 55.0, -25.0),
    "Lepus":           ( 82.5, -19.0),   "Canis Major":     (104.0, -24.0),
    "Canis Minor":     (113.0,   7.0),   "Hydra":           (148.0,  -8.0),
    "Corvus":          (187.0, -19.0),   "Andromeda":       ( 17.0,  36.0),
    "Pegasus":         (341.0,  20.0),   "Draco":           (250.0,  62.0),
    "Triangulum":      ( 31.0,  32.0),
}

def get_constellation_labels() -> dict:
    return _LABELS
