from .datatypes import Request, RequestEntry

requests: dict[str, RequestEntry] = {}


def request(req: Request):
    if req.url not in requests:
        requests[req.url] = RequestEntry(1, 1 if req.error else 0, req.ttfb, req.ttlb, req.ttlb)
    else:
        re = requests[req.url]
        with re.lock:
            re.count += 1
            if req.error:
                re.errorcount += 1
            re.sum_ttfb += req.ttfb
            re.sum_ttlb += req.ttlb
            re.max_ttlb = max(re.max_ttlb, req.ttlb)
