SCALE = 10000


def ndvi(ds):
    return (ds.nir - ds.red) / (ds.nir + ds.red)


def evi(ds):
    return 2.5 * (ds.nir - ds.red) / (ds.nir + 6 * ds.red - 7.5 * ds.blue + SCALE)


def gndvi(ds):
    return (ds.nir - ds.green) / (ds.nir + ds.green)


def savi(ds, L: float = 0.5):
    return (1 + L) * (ds.nir - ds.red) / (ds.nir + ds.red + L * SCALE)


def msavi(ds):
    nir = ds.nir
    red = ds.red
    return (2 * nir + SCALE - ((2 * nir + SCALE) ** 2 - 8 * SCALE * (nir - red)) ** 0.5) / (2 * SCALE)


def ndwi(ds):
    return (ds.green - ds.nir) / (ds.green + ds.nir)


def gcvi(ds):
    return (ds.nir / ds.green) - 1


def vari(ds):
    return (ds.green - ds.red) / (ds.green + ds.red - ds.blue)


def ndre(ds):
    return (ds.nir - ds.rededge1) / (ds.nir + ds.rededge1)


def cire(ds):
    return (ds.nir / ds.rededge1) - 1


def ndmi(ds):
    return (ds.nir - ds.swir1) / (ds.nir + ds.swir1)


def mndwi(ds):
    return (ds.green - ds.swir1) / (ds.green + ds.swir1)


def psri(ds):
    return (ds.red - ds.blue) / ds.rededge1


def rendvi(ds):
    return (ds.nir - ds.rededge2) / (ds.nir + ds.rededge2)


register = {
    "ndvi": ndvi,
    "evi": evi,
    "gndvi": gndvi,
    "savi": savi,
    "msavi": msavi,
    "ndwi": ndwi,
    "gcvi": gcvi,
    "vari": vari,
    "ndre": ndre,
    "cire": cire,
    "ndmi": ndmi,
    "mndwi": mndwi,
    "psri": psri,
    "rendvi": rendvi,
}