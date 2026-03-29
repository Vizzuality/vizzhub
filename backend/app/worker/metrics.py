"""Worker metrics for Prometheus."""

from prometheus_client import Counter, Histogram

arq_jobs_total = Counter(
    "arq_jobs_total",
    "ARQ jobs completed",
)

arq_job_duration_seconds = Histogram(
    "arq_job_duration_seconds",
    "ARQ job duration",
)
