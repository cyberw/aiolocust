import logging
import os
import socket
import sys
from importlib.metadata import version

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogRecordExporter
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    ConsoleMetricExporter,
    InMemoryMetricReader,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from rich.console import Console
from rich.logging import RichHandler

from aiolocust import config

HISTOGRAM_BOUNDARIES = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]

reader: InMemoryMetricReader = None  # type: ignore


def configure_telemetry():
    global reader
    if reader:
        return
    resource = Resource.create(
        {
            "service.name": "locust",
            "service.version": version("aiolocust"),
            "host.name": socket.gethostname(),
            "filename": config.filename,
            "profile": config.profile or "",
        }
    )
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    setup_logging(getattr(logging, config.log_level.value.upper()), logger_provider)
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    reader = InMemoryMetricReader(
        preferred_temporality={
            Histogram: AggregationTemporality.DELTA,
        }
    )
    setup_trace_exporters(tracer_provider)
    setup_meter_provider([reader], resource)


def setup_logging(level: int, logger_provider: LoggerProvider):
    otel_handler = LoggingHandler(level=level, logger_provider=logger_provider)
    # avoid double-handling logs emitted by the OTEL handler itself
    # otel_handler.addFilter(lambda record: record.name != "opentelemetry.sdk._logs.export.LoggingHandler")

    logs_exporters = {e.strip().lower() for e in os.getenv("OTEL_LOGS_EXPORTER", "otlp").split(",") if e.strip()}
    for exporter in logs_exporters:
        if exporter == "otlp":
            protocol = (
                os.getenv("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"))
                .lower()
                .strip()
            )
            try:
                if protocol == "grpc":
                    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter  # type: ignore
                elif protocol == "http/protobuf" or protocol == "http":
                    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter  # type: ignore
                else:
                    print(
                        f"Unknown OpenTelemetry otlp logs exporter protocol '{protocol}'. Use 'grpc' or 'http/protobuf'"
                    )
                    continue
            except ImportError:
                if (
                    level == logging.INFO
                    and os.getenv("OTEL_LOGS_EXPORTER", "")
                    or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "")
                ):
                    print(
                        f"setup_logging: OpenTelemetry otlp exporter for '{protocol}' is not available. Please install the required package: opentelemetry-exporter-otlp-proto-{'grpc' if protocol == 'grpc' else 'http'}",
                    )
                continue

            otlp_exporter = OTLPLogExporter()
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))
        elif exporter == "console":
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(ConsoleLogRecordExporter(), schedule_delay_millis=100)
            )

        elif exporter == "none":
            continue

        else:
            print(f"Unknown logs exporter '{exporter}'. Ignored")

    # Use RichHandler only when stderr is a TTY (interactive) to avoid double-formatting.
    if sys.stderr.isatty():
        logging.basicConfig(
            handlers=[otel_handler, RichHandler(level, console=Console(stderr=True))],
            datefmt="[%X]",
            level=level,
            format="%(message)s",
        )
    else:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s/%(name)s: %(message)s"))
        logging.basicConfig(
            handlers=[otel_handler, stream_handler],
            datefmt="[%X]",
            level=level,
            format="%(message)s",
        )


def setup_trace_exporters(tracer_provider: TracerProvider):
    logger = logging.getLogger(__name__)
    traces_exporters = {e.strip().lower() for e in os.getenv("OTEL_TRACES_EXPORTER", "otlp").split(",") if e.strip()}
    for exporter in traces_exporters:
        if exporter == "otlp":
            protocol = (
                os.getenv(
                    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
                )
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
                level = logging.INFO if os.getenv("OTEL_TRACES_EXPORTER", "") else logging.DEBUG
                logger.log(
                    level,
                    f"setup_trace_exporters: OpenTelemetry otlp exporter for '{protocol}' is not available. Please install the required package: opentelemetry-exporter-otlp-proto-{'grpc' if protocol == 'grpc' else 'http'}",
                )
                continue

            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

        elif exporter == "console":
            tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        elif exporter == "none":
            continue

        else:
            print(f"Unknown traces exporter '{exporter}'. Ignored")


def setup_meter_provider(metric_readers: list[MetricReader], resource):
    readers_from_env = get_metric_exporters()
    metrics.set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=metric_readers + readers_from_env,
            views=[
                View(
                    instrument_type=Histogram,
                    aggregation=ExplicitBucketHistogramAggregation(boundaries=HISTOGRAM_BOUNDARIES),
                )
            ],
        )
    )


def get_metric_exporters() -> list[MetricReader]:
    metric_readers: list[MetricReader] = []
    metrics_exporters = {e.strip().lower() for e in os.getenv("OTEL_METRICS_EXPORTER", "otlp").split(",") if e.strip()}
    logger = logging.getLogger(__name__)
    for exporter in metrics_exporters:
        if exporter == "otlp":
            protocol = (
                os.getenv(
                    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
                )
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
                    logging.warning(
                        f"Unknown OpenTelemetry otlp meter exporter protocol '{protocol}'. Use 'grpc' or 'http/protobuf'"
                    )
                    continue
            except ImportError:
                logger.log(
                    logging.INFO if os.getenv("OTEL_METRICS_EXPORTER", "") else logging.DEBUG,
                    f"setup_meter_provider: OpenTelemetry otlp exporter for '{protocol}' is not available. Please install the required package: opentelemetry-exporter-otlp-proto-{'grpc' if protocol == 'grpc' else 'http'}",
                )
                continue
            metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
            metric_readers.append(metric_reader)

        elif exporter == "prometheus":
            logger.warning("Prometheus metrics exporter is not yet implemented!")

        elif exporter == "console":
            metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
            metric_readers.append(metric_reader)

        elif exporter == "none":
            logger.debug("Metric exporter explicitly set to 'none', metrics will not be exported")

        else:
            logger.warning(f"Unknown metrics exporter '{exporter}'. Ignored")

    if not metrics_exporters:
        logger.debug("No metrics exporter configured,")

    return metric_readers
