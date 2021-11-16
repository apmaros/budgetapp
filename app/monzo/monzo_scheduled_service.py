import datetime
from dataclasses import dataclass
from threading import Timer
from typing import Optional

from app.db.influxdb_client import InfluxDbClient, build_influxdb_client
from app.monzo.api_error import ApiError
from app.monzo.monzo_client import MonzoClient
from app.server import app
from app.transaction.transaction_provider import transactions_to_records, build_transaction_with_merchant
from app.util import current_time_sec, _day_to_daytime_str


class MonzoScheduledService(object):
    _DEFAULT_TXS_SINCE_DAYS_AGO = 30
    _TASK_DESCRIPTION = "Synchronise Monzo transactions"

    def __init__(
        self,
        monzo_client: MonzoClient,
        influxdb_client: InfluxDbClient,
        delay_sec: float
    ):
        self.monzo_client = monzo_client
        self.influxdb_client = influxdb_client
        self.delay_sec = delay_sec
        self.refresh_token_delay_sec = monzo_client.get_expiry_sec() / 2
        self.timer = None
        self.is_running = False

    def start(self):
        app.logger.info(f"scheduled: {self._TASK_DESCRIPTION}")
        self.schedule()
        self.is_running = True

    def schedule(self) -> None:
        self.timer = Timer(
            self.delay_sec,
            self._load_and_schedule
        )
        self.timer.start()

    def _load_and_schedule(self):
        app.logger.info(f"start: {self._TASK_DESCRIPTION}")
        try:
            self._load_transactions()
        except ApiError as err:
            app.logger.error(f"Monzo API failed to load transactions due to {err}")
        except Exception as err:
            app.logger.error(f"Failed to load transactions {err}")
        app.logger.info(f"finish: {self._TASK_DESCRIPTION}")
        self.schedule()

    def _load_transactions(self):
        if not self.monzo_client.is_authenticated():
            app.logger.error("Monzo client not authenticated. Authenticate to load transactions")
            return

        app.logger.info(f"Token created at {self.monzo_client.token.created_at_sec}")

        if (
            self.monzo_client.token.created_at_sec + self.refresh_token_delay_sec
            <= current_time_sec()
        ):
            app.logger.info(f"Refreshing token - "
                            f"{self.monzo_client.token.created_at_sec + self.delay_sec} <= {current_time_sec()}")
            self.monzo_client.refresh_token()

        since = datetime.datetime.now() - datetime.timedelta(self._DEFAULT_TXS_SINCE_DAYS_AGO)
        try:
            txs = self.monzo_client.get_transactions(
                since_date=_day_to_daytime_str(since),
                before_date=_day_to_daytime_str(datetime.datetime.now()),
            )
            points = transactions_to_records(list(map(
                lambda tx: build_transaction_with_merchant(tx),
                txs['transactions']
            )))
            app.logger.info(f"transaction_count={len(points)}")
            self.influxdb_client.write_records(points)
        except ApiError as e:
            app.logger.error(f"Failed to load transactions due to ApiError: {e}")
        except RuntimeError as e:
            app.logger.error(f"Failed to load transactions due to error: {e}")


@dataclass
class MonzoScheduledServiceInstance:
    instance: Optional[MonzoScheduledService]

    def is_initialized(self):
        return self.instance is not None


monzo_scheduled_service_instance: MonzoScheduledServiceInstance = MonzoScheduledServiceInstance(None)


def get_scheduled_monzo_service_instance(
    monzo_client: MonzoClient,
    delay_sec: int
):
    if monzo_scheduled_service_instance.is_initialized():
        return monzo_scheduled_service_instance.instance

    service = MonzoScheduledService(
        monzo_client=monzo_client,
        influxdb_client=build_influxdb_client(),
        delay_sec=delay_sec
    )

    monzo_scheduled_service_instance.instance = service

    return monzo_scheduled_service_instance.instance
