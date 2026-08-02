from __future__ import annotations

import math

from .constants import (
    AU_M,
    DAYS_PER_JULIAN_YEAR,
    EARTH_MEAN_DENSITY_G_CM3,
    EARTH_SURFACE_GRAVITY_M_S2,
    SOLAR_EFFECTIVE_TEMPERATURE_K,
    SOLAR_LUMINOSITY_W,
    SOLAR_RADIUS_M,
    STEFAN_BOLTZMANN_W_M2_K4,
)


def stellar_luminosity_solar(radius_solar: float, temperature_k: float) -> float:
    radius_m = radius_solar * SOLAR_RADIUS_M
    luminosity_w = 4.0 * math.pi * radius_m**2 * STEFAN_BOLTZMANN_W_M2_K4 * temperature_k**4
    return luminosity_w / SOLAR_LUMINOSITY_W


def orbital_period_days(semi_major_axis_au: float, stellar_mass_solar: float) -> float:
    if semi_major_axis_au <= 0 or stellar_mass_solar <= 0:
        raise ValueError("semi-major axis and stellar mass must be positive")
    years = math.sqrt(semi_major_axis_au**3 / stellar_mass_solar)
    return years * DAYS_PER_JULIAN_YEAR


def equilibrium_temperature_k(
    stellar_temperature_k: float,
    stellar_radius_solar: float,
    semi_major_axis_au: float,
) -> float:
    if semi_major_axis_au <= 0:
        raise ValueError("semi-major axis must be positive")
    radius_m = stellar_radius_solar * SOLAR_RADIUS_M
    axis_m = semi_major_axis_au * AU_M
    return stellar_temperature_k * math.sqrt(radius_m / axis_m) * (0.25 ** 0.25)


def insolation_earth(stellar_luminosity_solar: float, semi_major_axis_au: float) -> float:
    if semi_major_axis_au <= 0:
        raise ValueError("semi-major axis must be positive")
    return stellar_luminosity_solar / semi_major_axis_au**2


def mass_earth_from_radius_density(radius_earth: float, density_g_cm3: float) -> float:
    return (density_g_cm3 / EARTH_MEAN_DENSITY_G_CM3) * radius_earth**3


def density_g_cm3(mass_earth: float, radius_earth: float) -> float:
    if radius_earth <= 0:
        raise ValueError("radius must be positive")
    return EARTH_MEAN_DENSITY_G_CM3 * mass_earth / radius_earth**3


def surface_gravity_earth(mass_earth: float, radius_earth: float) -> float:
    if radius_earth <= 0:
        raise ValueError("radius must be positive")
    return mass_earth / radius_earth**2


def escape_velocity_km_s(surface_gravity_earth_ratio: float, radius_earth: float) -> float:
    # v = sqrt(2 g r), expressed relative to Earth constants.
    earth_radius_m = 6.371e6
    return math.sqrt(2 * EARTH_SURFACE_GRAVITY_M_S2 * surface_gravity_earth_ratio * earth_radius_m * radius_earth) / 1000


def star_color_temperature_hint(temperature_k: float) -> str:
    if temperature_k < 3700:
        return "warm-red"
    if temperature_k < 5200:
        return "amber"
    if temperature_k < 6000:
        return "sun-white"
    if temperature_k < 7500:
        return "cool-white"
    return "blue-white"


def temperature_relative_to_sun(temperature_k: float) -> float:
    return temperature_k / SOLAR_EFFECTIVE_TEMPERATURE_K
