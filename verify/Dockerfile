FROM python:3.12-slim

WORKDIR /verify
COPY verify.py .

ENV API_URL=http://api:8000 \
    WEB_URL=http://web:80 \
    WEB_CHECK=1

CMD ["python", "verify.py"]
