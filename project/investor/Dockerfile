FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# SDK T-Invest лежит в GitLab Package Registry TBank — в PyPI его нет.
# Сертификат внутреннего хоста выпущен корпоративным CA, которого нет в образе,
# поэтому доверяем хосту явно (--trusted-host).
# Внутренний реестр подключается как ДОПОЛНИТЕЛЬНЫЙ индекс: зависимости SDK
# (grpcio, protobuf, requests и т.д.) ставятся из PyPI как обычно.
ARG TINVEST_INDEX_URL=https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
ARG TINVEST_TRUSTED_HOST=opensource.tbank.ru

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir \
        --extra-index-url "${TINVEST_INDEX_URL}" \
        --trusted-host "${TINVEST_TRUSTED_HOST}" \
        "t-tech-investments>=1.51,<2"

# сервису нужны источник данных, HTTP-слой и аналитика (signals/ + util/)
COPY market ./market
COPY service ./service
COPY signals ./signals
COPY indicators ./indicators
COPY util ./util

EXPOSE 8100
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8100"]
