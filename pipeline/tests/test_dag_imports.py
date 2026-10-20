"""Every DAG file must import cleanly (ARCHITECTURE.md section 13).

Runs inside the Airflow image (`make test-pipeline`), so it uses the real Airflow version.
Example DAGs stay out because Compose sets AIRFLOW__CORE__LOAD_EXAMPLES=False.
"""

from airflow.dag_processing.dagbag import DagBag

DAGS_FOLDER = "/opt/airflow/dags"


def test_dags_import_without_errors():
    dag_bag = DagBag(dag_folder=DAGS_FOLDER)

    assert dag_bag.import_errors == {}
