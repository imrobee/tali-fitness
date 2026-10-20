FROM apache/airflow:3.3.2

# Installing "apache-airflow==<same version>" alongside our extras stops pip from
# upgrading or downgrading Airflow itself (pattern from the official image docs).
COPY requirements-dev.txt /requirements-dev.txt
RUN pip install --no-cache-dir "apache-airflow==3.3.2" -r /requirements-dev.txt

COPY start_airflow.sh /opt/airflow/start_airflow.sh
