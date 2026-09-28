"""Immutable enterprise population v1. No wall clock, random IDs or production counters."""
from datetime import datetime, time, timedelta
import calendar

CORE_VOLUMES = (36,40,44,48,40,36,44,48,52,44,48,56)
LOW_VOLUMES = (8,9,10,12,8,9,10,12,8,10,12,12)
DOMAINS = {
    'booking': ('booking.booking','clinic_booking'),
    'procedure': ('clinic.procedure.session','clinic_encounter'),
    'billing': ('clinic.billing.invoice','clinic_billing'),
    'insurance': ('clinic.insurance.authorization','clinic_insurance_authorization'),
    'membership': ('membership.contract','clinic_membership'),
    'inventory': ('clinic.treatment.product.usage','clinic_inventory'),
    'wallet': ('clinic.wallet.transaction','clinic_wallet'),
    'incident': ('clinic.incident','clinic_incident_event'),
}
PATIENT_KEYS = ('DEMO-PAT-RET-001','DEMO-PAT-ELDER-001','DEMO-PAT-CHRON-001','DEMO-PAT-FREQ-001')

def month_shift(day, offset):
    n=day.year*12+day.month-1+offset
    year,month=divmod(n,12);month+=1
    return day.replace(year=year,month=month,day=min(day.day,calendar.monthrange(year,month)[1]))

def volume(domain, month):
    return 2 if domain=='incident' else (LOW_VOLUMES if domain in ('insurance','membership') else CORE_VOLUMES)[month-1]

def prefix(domain, month): return f'DEMO-POP-{domain.upper()}-M{month:02d}'

def entries(anchor, domain, month):
    start=max(month_shift(anchor,month-13), anchor-timedelta(days=365))
    stop=month_shift(anchor,month-12)
    n=volume(domain,month); span=(stop-start).days
    result=[]
    for i in range(n):
        day=start+timedelta(days=i*span//n)
        # Each fixed slot is unique within a batch. No mutable availability search.
        hour=10+(i%2)*4
        at=datetime.combine(day,time(hour, (i//2)%3*10))
        result.append(dict(key=f'{prefix(domain,month)}-{i+1:03d}', day=day, at=at,
                           patient=PATIENT_KEYS[i%len(PATIENT_KEYS)], index=i,
                           cancelled=i%7==0, amount=150000+25000*((i+month)%7)))
    return tuple(result)

def batch_specs():
    return tuple((f'population.{domain}.m{month:02d}',domain,month)
                 for month in range(1,13) for domain in DOMAINS)

def reference_keys(anchor, domain, month=0):
    """Exact provenance inventory for reconciliation before any ORM mutation."""
    if domain=='setup':
        return tuple(
            [f'DEMO-POP-SETUP-WH-{i}' for i in range(1,4)]
            + [f'DEMO-POP-SETUP-{tag}-{i}' for i in range(1,4)
               for tag in ('STOCK','SINK','DONOR')]
            + [f'DEMO-POP-SETUP-WALLET-{i}' for i in range(4)]
        )
    keys=[]
    for item in entries(anchor,domain,month):
        key=item['key'];keys.append(key)
        if domain=='procedure':
            keys += [key+'-ENC',key+'-CREATE',key+('-CANCEL' if item['cancelled'] else '-START')]
            if not item['cancelled']:keys.append(key+'-DONE')
        elif domain=='billing':
            keys += [key+'-EVT-INVOICE_CREATED',key+('-EVT-INVOICE_CANCELLED' if item['cancelled'] else '-EVT-INVOICE_CONFIRMED')]
            if not item['cancelled']:keys += [key+'-EVT-INVOICE_POSTED',key+'-MOVE']
        elif domain=='insurance':keys.append(key+'-POLICY')
        elif domain=='membership' and item['cancelled']:keys.append(key+'-EVT-CANCELLED')
        elif domain in ('inventory','wallet') and not item['cancelled']:
            if domain=='inventory':keys.append(key+'-RECEIPT')
            keys.append(key+'-MOVE')
    if len(keys)!=len(set(keys)):raise ValueError(f'Duplicate population reference identity: {domain} / {month}')
    return tuple(keys)











