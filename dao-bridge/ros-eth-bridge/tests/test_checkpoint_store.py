import os
import tempfile

from bridge_io.checkpoint_store import CheckpointStore


def test_checkpoint_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ckpt.json")
        ck = CheckpointStore(path)
        # fresh store starts from latest block fallback and zero cursor
        assert ck.next_from_block(100) == 100
        assert ck.last_cursor() == (0, -1)

        ck.update_cursor(10, 2)
        ck.save()

        ck2 = CheckpointStore(path)
        assert ck2.last_cursor() == (10, 2)
        assert ck2.next_from_block(50) == 10
