FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/astock_quant

COPY docker/ashare-smallcap-quant/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY astock_quant /app/astock_quant
COPY monitor/notifiers /app/monitor/notifiers
COPY deliverables/smallcap_strategy.json /app/bundle_deliverables/smallcap_strategy.json
COPY docker/ashare-smallcap-quant/run.sh /app/run.sh
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
