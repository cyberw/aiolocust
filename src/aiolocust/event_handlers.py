requests = {}


def request(url: str, ttfb: float, ttlb: float, success: bool):
    if url not in requests:
        requests[url] = 1, ttfb, ttlb, ttlb
    else:
        count, sum_ttfb, sum_ttlb, max_ttlb = requests[url]
        requests[url] = (
            count + 1,
            sum_ttfb + ttfb,
            sum_ttlb + ttlb,
            max(max_ttlb, ttlb),
        )
