"""Single source of truth for the turn-based campaign rules and the Persian guide."""
from dataclasses import dataclass

@dataclass(frozen=True)
class WarMode:
    label: str
    warning: int
    minimum: int
    maximum: int
    min_rounds: int
    captures: bool
    colony: bool

MODES = {
    'border': WarMode('درگیری مرزی', 15*60, 6*3600, 48*3600, 6, True, False),
    'limited': WarMode('عملیات محدود', 30*60, 12*3600, 72*3600, 8, False, False),
    'siege': WarMode('محاصرهٔ شهرها', 30*60, 24*3600, 120*3600, 10, True, False),
    'total': WarMode('جنگ فراگیر', 60*60, 48*3600, 168*3600, 12, True, True),
}
STRIKE_COOLDOWN = 300
COUNTRY_COOLDOWN = 180
MISSILE_FLIGHT = 30
MAX_SHOTS = 5
AMMO_CAP = 50
RESUPPLY_QTY = 10
RESUPPLY_COST = 300
RESUPPLY_COOLDOWN = 1800
CITY_MIN_ROUNDS = 8
CITY_MIN_SIEGE = 6 * 3600
CITY_MAX_PRESSURE = 14
CAPITAL_HOLD = 6 * 3600
TRUCE_TIME = 12 * 3600
BUILD_TIME = 3600
REPAIR_COOLDOWN = 600
REPAIR_POINTS = 20

MISSILE_SALVO = 3
MISSILES_PER_HOUR = 6
MISSILES_PER_WAR = 20

FUEL_PER_SHOT={'زمینی':1,'توپخانه':1,'پهپادی':1,'موشکی':2,'هوایی':2,'چندمنظوره':2,'دریایی':2,'آبی‌خاکی':3}
