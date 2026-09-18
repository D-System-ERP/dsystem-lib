from sqlalchemy.ext.asyncio import async_sessionmaker

from dsystem.events.replica_sync import ReplicaSync, run_replica_consumer
from dsystem.models.partner_replica import PARTNER_REPLICA_FIELDS, PartnerReplica

partner_sync = ReplicaSync(PartnerReplica, PARTNER_REPLICA_FIELDS, soft_delete=True)

HANDLERS = partner_sync.handlers("partner")


async def start_partner_sync_consumer(rabbitmq_url: str, session_factory: async_sessionmaker, service_name: str):
    return await run_replica_consumer(rabbitmq_url, session_factory, f"{service_name}-partner-sync", HANDLERS)
