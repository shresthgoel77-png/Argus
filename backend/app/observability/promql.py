ERROR_RATE_QUERY = 'sum(rate(http_requests_total{{job="{service}",status=~"5.."}}[{window}])) / sum(rate(http_requests_total{{job="{service}"}}[{window}]))'
LATENCY_P95_QUERY = 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{job="{service}"}}[{window}])) by (le)) * 1000'
WEBHOOK_FAILURE_QUERY = 'sum(rate(webhook_failures_total{{job="{service}"}}[{window}])) / sum(rate(http_requests_total{{job="{service}",endpoint="/webhook/payment-event"}}[{window}]))'
