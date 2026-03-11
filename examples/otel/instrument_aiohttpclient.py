# In aiolocust, you instrument libraries just like you would in any other application.
#
# Combine this with standard OTel env vars for exporter configuration, for example:
#
# OTEL_TRACES_EXPORTER=console aiolocust instrument_aiohttpclient.py
# or
# OTEL_METRIC_EXPORT_INTERVAL=1000 OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://ingest.us1.signalfx.com/v2/trace/otlp" OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="https://ingest.us1.signalfx.com/v2/datapoint/otlp" OTEL_EXPORTER_OTLP_HEADERS="X-SF-TOKEN=..." OTEL_EXPORTER_OTLP_METRICS_PROTOCOL="http" OTEL_METRIC_EXPORT_INTERVAL=500 aiolocust instrument_aiohttpclient.py

# Note: autoinstrumentation appears to be not 100% stable on Windows, occasionally saying:
# SystemError: <class 'BoundFunctionWrapper'> returned a result with an exception set
# https://github.com/cyberw/aiolocust/actions/runs/22975875471/job/66704198296#step:5:1373

from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

AioHttpClientInstrumentor().instrument()


async def run(user):
    async with user.client.get("http://localhost:8080/") as resp:
        pass
