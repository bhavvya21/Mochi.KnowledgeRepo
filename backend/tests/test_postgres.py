"""Exercise the production vector type and tenant filter against PostgreSQL."""
import os
import uuid
import pytest
from sqlalchemy import select, delete
from mochi.db import database, Workspace, Document, Chunk


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='PostgreSQL integration runs in CI')
def test_pgvector_distance_and_owner_filter():
    engine, factory = database(os.environ['TEST_POSTGRES_URL'])
    owners = ['test-' + str(uuid.uuid4()) for _ in range(2)]
    vector = [1.0] + [0.0] * 383
    try:
        with factory.begin() as db:
            db.add_all([Workspace(id=o) for o in owners])
            db.flush()
            for owner in owners:
                doc = Document(owner=owner, name='Private', collection='Test', type='TXT', pages=[], chars=7)
                db.add(doc)
                db.flush()
                db.add(Chunk(document=doc.id, owner=owner, strategy='structure', page=1, topic='', text='Private', vector=vector))
        with factory() as db:
            rows = db.scalars(select(Chunk).where(Chunk.owner == owners[0]).order_by(Chunk.vector.cosine_distance(vector))).all()
            assert len(rows) == 1 and rows[0].owner == owners[0]
            assert len(rows[0].vector) == 384
    finally:
        with factory.begin() as db:
            db.execute(delete(Chunk).where(Chunk.owner.in_(owners)))
            db.execute(delete(Document).where(Document.owner.in_(owners)))
            db.execute(delete(Workspace).where(Workspace.id.in_(owners)))
        engine.dispose()
