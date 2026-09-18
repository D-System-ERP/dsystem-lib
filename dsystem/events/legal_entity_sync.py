from sqlalchemy.ext.asyncio import async_sessionmaker

from dsystem.events.replica_sync import ReplicaSync, run_replica_consumer
from dsystem.models.legal_entity_replica import LEGAL_ENTITY_REPLICA_FIELDS, LegalEntityReplica

legal_entity_sync = ReplicaSync(LegalEntityReplica, LEGAL_ENTITY_REPLICA_FIELDS, soft_delete=True)

HANDLERS = legal_entity_sync.handlers("legal_entity")


async def start_legal_entity_sync_consumer(rabbitmq_url: str, session_factory: async_sessionmaker, service_name: str):
    return await run_replica_consumer(rabbitmq_url, session_factory, f"{service_name}-legal-entity-sync", HANDLERS)
