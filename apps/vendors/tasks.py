from celery import shared_task

from .agents import execute_agent_run


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def execute_intelligent_agent_run(self, run_id):
    return execute_agent_run(run_id).pk


@shared_task
def release_expired_stock_reservations():
    from .cart_services import release_expired_reservations
    return release_expired_reservations()
