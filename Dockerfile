FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=pip_ca \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY --chmod=644 invoices.py pdf.py server.py serve.py ./
COPY --chmod=755 static ./static
COPY --chmod=755 fonts ./fonts
RUN useradd -u 10001 -m sprig && mkdir /data && chown sprig /data
USER 10001
EXPOSE 8126
CMD ["python", "serve.py"]
