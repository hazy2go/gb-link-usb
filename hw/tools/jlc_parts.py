#!/usr/bin/env python3
"""Look up LCSC part numbers on JLCPCB's assembly parts library (the same endpoint the JLC website uses).
Prints library type (base = basic part, no feeder fee; expand = extended), stock, package, MPN, description.
Usage: jlc_parts.py C25804 [C14663 ...]   or import lookup()."""
import json, sys, time, urllib.request

URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'


def lookup(lcsc):
    body = json.dumps({'keyword': lcsc, 'currentPage': 1, 'pageSize': 10}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
            d = json.loads(urllib.request.urlopen(req, timeout=20).read())
            for c in (d.get('data') or {}).get('componentPageInfo', {}).get('list') or []:
                if c.get('componentCode') == lcsc:
                    return dict(lcsc=lcsc, library=c.get('componentLibraryType'), stock=c.get('stockCount'),
                                package=c.get('componentSpecificationEn'), mpn=c.get('componentModelEn'),
                                mfr=c.get('componentBrandEn'), desc=c.get('describe') or c.get('erpComponentName'),
                                price=(c.get('componentPrices') or [{}])[0].get('productPrice'))
            return dict(lcsc=lcsc, library=None, stock=0, package=None, mpn=None, mfr=None, desc='NOT FOUND', price=None)
        except Exception as e:
            time.sleep(2)
    return dict(lcsc=lcsc, library=None, stock=None, package=None, mpn=None, mfr=None, desc=f'LOOKUP FAILED', price=None)


if __name__ == '__main__':
    for c in sys.argv[1:]:
        r = lookup(c)
        print(f"{c:10} {str(r['library']):7} stock {str(r['stock']):>9}  {str(r['package']):14} {str(r['mpn'])[:24]:24} {str(r['desc'])[:70]}")
