import os

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor

resource = Resource.create(
    {
        "service.name": "locust",
        "service.version": "0.0.0",  # __version__
    }
)


def setup_tracer_provider():
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    traces_exporters = {e.strip().lower() for e in os.getenv("OTEL_TRACES_EXPORTER", "none").split(",") if e.strip()}
    for exporter in traces_exporters:
        if exporter == "otlp":
            protocol = (
                os.getenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"))
                .lower()
                .strip()
            )
            try:
                if protocol == "grpc":
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore
                elif protocol == "http/protobuf" or protocol == "http":
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
                else:
                    print(
                        f"Unknown OpenTelemetry otlp traces exporter protocol '{protocol}'. Use 'grpc' or 'http/protobuf'"
                    )
                    continue
            except ImportError:
                print(
                    f"OpenTelemetry otlp exporter for '{protocol}' is not available. Please install the required package: opentelemetry-exporter-otlp-proto-{'grpc' if protocol == 'grpc' else 'http'}"
                )
                continue

            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

        elif exporter == "console":
            tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        elif exporter == "none":
            continue

        else:
            print(f"Unknown traces exporter '{exporter}'. Ignored")


def setup_meter_provider(metric_readers: list[MetricReader]):
    metrics_exporters = {e.strip().lower() for e in os.getenv("OTEL_METRICS_EXPORTER", "none").split(",") if e.strip()}
    for exporter in metrics_exporters:
        if exporter == "otlp":
            protocol = (
                os.getenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "none"))
                .lower()
                .strip()
            )
            try:
                if protocol == "grpc":
                    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # type: ignore
                        OTLPMetricExporter,
                    )
                elif protocol == "http/protobuf" or protocol == "http":
                    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (  # type: ignore
                        OTLPMetricExporter,
                    )
                else:
                    print(
                        f"Unknown OpenTelemetry otlp meter exporter protocol '{protocol}'. Use 'grpc' or 'http/protobuf'"
                    )
                    continue
            except ImportError:
                print(
                    f"OpenTelemetry otlp exporter for '{protocol}' is not available. Please install the required package: opentelemetry-exporter-otlp-proto-{'grpc' if protocol == 'grpc' else 'http'}"
                )
                continue

            metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
            metric_readers.append(metric_reader)

        elif exporter == "prometheus":
            print("Prometheus metrics exporter is not yet implemented!")

        elif exporter == "console":
            metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
            metric_readers.append(metric_reader)

        elif exporter == "none":
            continue

        else:
            print(f"Unknown metrics exporter '{exporter}'. Ignored")

    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=metric_readers))
