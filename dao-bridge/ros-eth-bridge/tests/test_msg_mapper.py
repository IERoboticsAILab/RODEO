import types
import sys

# Provide stub ros_eth_msgs.msg with minimal message classes
stub_module = types.SimpleNamespace()

class _Base:
    def __eq__(self, other):
        return self.__dict__ == getattr(other, "__dict__", {})

class ServiceInfo(_Base):
    def __init__(self):
        self.id = 0; self.name = ""; self.description = ""; self.category = ""
        self.service_type = ""; self.price_wei = ""; self.creator = ""
        self.active = False; self.provider_type = 0; self.busy = False

class TaskInfo(_Base):
    def __init__(self):
        self.id = 0; self.description = ""; self.category = ""
        self.task_type = ""; self.creator = ""; self.executor = ""
        self.reward_wei = ""; self.status = 0; self.active = False
        self.proof_uri = ""; self.verified = False

stub_module.ServiceInfo = ServiceInfo
stub_module.TaskInfo = TaskInfo

sys.modules["ros_eth_msgs"] = types.SimpleNamespace(msg=stub_module)
sys.modules["ros_eth_msgs.msg"] = stub_module

from ros.msg_mapper import pack_service, pack_task
from core.contracts import Service, Task


def test_pack_service():
    s = Service(id=1, name="n", description="d", category="c", service_type="t",
                price_wei="10", creator="0x1", active=True, provider_type=2, busy=False)
    msg = pack_service(s)
    assert msg.id == 1
    assert msg.name == "n"
    assert msg.provider_type == 2
    assert msg.busy is False


def test_pack_task():
    t = Task(id=5, description="desc", category="cat", task_type="type",
             creator="0xC", executor="0xE", reward_wei="42",
             status=3, active=True, proof_uri="ipfs://x", verified=True)
    msg = pack_task(t)
    assert msg.id == 5
    assert msg.executor == "0xE"
    assert msg.verified is True
