#!/usr/bin/env python3
"""Search JLCPCB's assembly parts library (the endpoint the JLC website uses) by keyword or LCSC number.
Prints LCSC code, library (base = basic part, no feeder fee; expand = extended), stock, package, MPN, price.
Usage: jlc_search.py "SN74LVC1T45DBVR" [more keywords ...]
Adapted from ~/wifi-game-boy-cartridge/hw/rev-b/tools/jlc_parts.py."""
import json, sys, time, urllib.request

URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'


def search(keyword, n=6):
    body = json.dumps({'keyword': keyword, 'currentPage': 1, 'pageSize': n}).encode()
    for _ in range(3):
        try:
            req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
            d = json.loads(urllib.request.urlopen(req, timeout=20).read())
            out = []
            for c in (d.get('data') or {}).get('componentPageInfo', {}).get('list') or []:
                out.append(dict(lcsc=c.get('componentCode'), library=c.get('componentLibraryType'), stock=c.get('stockCount'),
                                package=c.get('componentSpecificationEn'), mpn=c.get('componentModelEn'),
                                price=(c.get('componentPrices') or [{}])[0].get('productPrice'),
                                desc=c.get('describe') or ''))
            return out
        except Exception:
            time.sleep(2)
    return None


if __name__ == '__main__':
    for kw in sys.argv[1:]:
        res = search(kw)
        print(f'== {kw}')
        if res is None:
            print('   lookup failed'); continue
        for r in res:
            print(f"   {r['lcsc']:10} {str(r['library']):7} stock {str(r['stock']):>8}  {str(r['package'])[:12]:12} {str(r['mpn'])[:26]:26} ${r['price']}")
