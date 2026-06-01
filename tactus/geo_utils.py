"""Utilities for simple geographic tasks."""

import numpy as np
import pyproj


class Projstring:
    """Proj4 string class."""

    def __init__(self):
        """Construct proj4 string."""
        self.earth_radius = 6371000.0

    def get_projstring(self, lon0=0.0, lat0=-90.0) -> str:
        """Get proj4 string.

        Args:
            lon0 (float, optional): Central longitude. Defaults to 0.0.
            lat0 (float, optional): Central latitude. Defaults to -90.0.

        Returns:
            str: Proj4 string
        """
        if lat0 == -90.0:
            proj_string = f"+proj=stere +lat_0={lat0!s} +lon_0={lon0!s} +lat_ts={lat0!s}"
        else:
            proj_string = (
                f"+proj=lcc +lat_0={lat0!s} +lon_0={lon0!s} "
                f"+lat_1={lat0!s} +lat_2={lat0!s} "
                f"+units=m +no_defs +R={self.earth_radius!s}"
            )

        return proj_string


class Projection:
    """Projection class."""

    def __init__(self, proj4str):
        """Construct projection.

        Args:
            proj4str (str): Proj4 string
        """
        self.proj4str = proj4str
        self.proj = pyproj.CRS.from_string(proj4str)
        self.wgs84 = pyproj.CRS.from_string("EPSG:4326")

    def geographic2cartessian(self, lon, lat):
        return pyproj.Transformer.from_crs(
            self.proj.wgs84, self.proj, always_xy=True
        ).transform(lon, lat)

    def cartessian2geographic(self, x, y):
        return pyproj.Transformer.from_crs(
            self.proj, self.wgs84, always_xy=True
        ).transform(x, y)

    def check_key(self, key: str, config: dict) -> bool:
        """Check if key is in config.

        Args:
            key (str): Key to check
            config (dict): Configuration

        Returns:
            bool: True if key is in config

        Raises:
            ValueError: If key is not in config
        """
        if key in config:
            return True
        raise ValueError("{} not in dictionary. Check config file".format(key))

    def get_domain_properties(self, domain_spec: dict) -> dict:
        """Get domain properties.

        Args:
            domain_spec (dict): Domain specification

        Returns:
            dict: Domain properties
        """
        self.check_key("lonc", domain_spec)
        self.check_key("latc", domain_spec)
        self.check_key("nlon", domain_spec)
        self.check_key("nlat", domain_spec)
        self.check_key("gsize", domain_spec)

        lonc = domain_spec["lonc"]
        latc = domain_spec["latc"]
        nlon = domain_spec["nlon"]
        nlat = domain_spec["nlat"]
        gsize = domain_spec["gsize"]

        xloncen, xlatcen = pyproj.Transformer.from_crs(
            self.wgs84, self.proj, always_xy=True
        ).transform(lonc, latc)

        x_0 = float(xloncen) - (0.5 * ((float(nlon) - 1.0) * gsize))
        y_0 = float(xlatcen) - (0.5 * ((float(nlat) - 1.0) * gsize))

        xxx = np.empty([nlon])
        yyy = np.empty([nlat])
        for i in range(nlon):
            xxx[i] = x_0 + (float(i) * gsize)
        for j in range(nlat):
            yyy[j] = y_0 + (float(j) * gsize)

        x_v, y_v = np.meshgrid(xxx, yyy)
        lons, lats = pyproj.Transformer.from_crs(
            self.proj, self.wgs84, always_xy=True
        ).transform(x_v, y_v)

        minlat = np.floor(np.min(lats)) - 1
        minlon = np.floor(np.min(lons)) - 1
        maxlat = np.ceil(np.max(lats)) + 1
        maxlon = np.ceil(np.max(lons)) + 1

        minlat = np.max([minlat, -90])
        minlon = np.max([minlon, -180])
        maxlat = np.min([maxlat, 90])
        maxlon = np.min([maxlon, 180])

        return {
            "minlat": minlat,
            "minlon": minlon,
            "maxlat": maxlat,
            "maxlon": maxlon,
        }


class LambertDomain():
    """Domain class."""

    def __init__(self, name, proj, nimax, njmax, xdx, xdy, xloncen, xlatcen,
                 ilone=0, ilate=0):
        """Construct domain.

        Args:
            proj (Projection): Projection object
            nimax (int): Number of grid points in x direction
            njmax (int): Number of grid points in y direction
            xdx (float): Grid spacing in x direction
            xdy (float): Grid spacing in y direction
            xloncen (float): Central longitude in projection coordinates
            xlatcen (float): Central latitude in projection coordinates
            ilone (int, optional): Extension zone in longitude direction. Defaults to 0.
            ilate (int, optional): Extension zone in latitude direction. Defaults to 0.
        """
        self.name = name
        self.nimax = nimax
        self.njmax = njmax
        self.xdx = xdx
        self.xdy = xdy
        self.xloncen = xloncen
        self.xlatcen = xlatcen
        self.proj = proj
        self.inlone = ilone
        self.ilate = ilate

    def get_domain_extension(self) -> dict:
        """Get domain properties.

        Args:
            domain_spec (dict): Domain specification

        Returns:
            dict: Domain properties
        """

        xloncen, xlatcen = self.proj.geographic2cartessian(self.xloncen, self.xlatcen)

        x_0 = float(xloncen) - (0.5 * ((float(self.nimax) - 1.0) * self.xdx))
        y_0 = float(xlatcen) - (0.5 * ((float(self.njmax) - 1.0) * self.xdy))

        xxx = np.empty([self.nimax])
        yyy = np.empty([self.njmax])
        for i in range(self.nimax):
            xxx[i] = x_0 + (float(i) * self.xdy)
        for j in range(self.njmax):
            yyy[j] = y_0 + (float(j) * self.xdy)

        x_v, y_v = np.meshgrid(xxx, yyy)
        lons, lats = self.proj.cartessian2geographic(x_v, y_v)

        minlat = np.floor(np.min(lats)) - 1
        minlon = np.floor(np.min(lons)) - 1
        maxlat = np.ceil(np.max(lats)) + 1
        maxlon = np.ceil(np.max(lons)) + 1

        minlat = np.max([minlat, -90])
        minlon = np.max([minlon, -180])
        maxlat = np.min([maxlat, 90])
        maxlon = np.min([maxlon, 180])

        return {
            "minlat": minlat,
            "minlon": minlon,
            "maxlat": maxlat,
            "maxlon": maxlon,
        }


class LambertDomainFromConfig(LambertDomain):
    """Domain class constructed from config."""

    def __init__(self, config):
        """Construct domain from config.

        Args:
            config (tactus.ParsedConfig): Configuration from which we get the domain data
        """
        name = config["domain.name"]
        lon0 = config["domain.lon0"]
        lat0 = config["domain.lat0"]
        projstr = Projstring().get_projstring(lon0=lon0, lat0=lat0)
        proj = Projection(projstr)
        nimax = config["domain.nimax"]
        njmax = config["domain.njmax"]
        xdx = config["domain.xdx"]
        xdy = config["domain.xdy"]
        xlatcen = config["domain.xlatcen"]
        xloncen = config["domain.xloncen"]
        ilone = config["domain.ilone"]
        ilate = config["domain.ilate"]
        super().__init__(name, proj, nimax, njmax, xdx, xdy, xloncen, xlatcen,
                         ilone=ilone, ilate=ilate)
