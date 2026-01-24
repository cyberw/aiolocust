from .datatypes import Request, RequestEntry
from .util import Counter

requests: dict[str, RequestEntry] = {}


def request(req: Request):
    if req.url not in requests:
        requests[req.url] = RequestEntry(
            Counter(1), Counter(1 if req.error else 0), req.ttfb, req.ttlb, req.ttlb
        )
    else:
        re = requests[req.url]
        re.count.inc()
        if req.error:
            re.errorcount.inc()
        re.sum_ttfb += req.ttfb
        re.sum_ttlb += req.ttlb
        re.max_ttlb = max(re.max_ttlb, req.ttlb)
