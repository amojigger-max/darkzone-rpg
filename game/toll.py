"""Compatibility for the original Hormuz menu; all authority lives in straits.py."""
from game import straits
TOLL=50
PENALTY=0.0
ROUTE_COUNTRIES=straits.CONTROLS['hormuz'][2]

def is_on():return bool(straits.get('hormuz')['fee'])
def needs_pass(uid):return straits.relevant(uid,'hormuz') and is_on()
def toggle(uid):return straits.set_fee(uid,'hormuz',0 if is_on() else 50),''
def status(uid):return straits.view(uid,'hormuz')
def announce_text():return straits.view(key='hormuz')
def pay(uid):return straits.pay(uid,'hormuz')
def collect(uid):return straits.collect(uid,'hormuz')
def enforce(uid):return None
def daily_announce_needed():return False
