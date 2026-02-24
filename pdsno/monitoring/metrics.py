"""
Prometheus metrics for PDSNO.
"""

from prometheus_client import Counter, Histogram, start_http_server

_metrics_started = False

rest_requests_total = Counter(
    "pdsno_rest_requests_total",
    "Total REST requests",
    ["method", "path", "status"]
)

rest_request_latency_seconds = Histogram(
    "pdsno_rest_request_latency_seconds",
    "REST request latency in seconds",
    ["method", "path"]
)

rest_errors_total = Counter(
    "pdsno_rest_errors_total",
    "Total REST errors",
    ["method", "path", "error_type"]
)


def start_metrics_server(port: int = 9090, addr: str = "0.0.0.0"):
    """Start Prometheus metrics server if not already running."""
    global _metrics_started

    if _metrics_started:
        return

    start_http_server(port, addr=addr)
    _metrics_started = True


def track_rest_request(method: str, path: str, status: str):
    """Track REST request count by method, path, and status."""
    rest_requests_total.labels(method=method, path=path, status=status).inc()


def track_rest_latency(method: str, path: str, duration_seconds: float):
    """Track REST request latency."""
    rest_request_latency_seconds.labels(method=method, path=path).observe(duration_seconds)


def track_rest_error(method: str, path: str, error_type: str):
    """Track REST errors by type."""
    rest_errors_total.labels(method=method, path=path, error_type=error_type).inc()
