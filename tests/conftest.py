import logging
import pylibmc
import pytest

from anom import (
    Adapter, Key, Query, adapters, get_adapter, set_adapter,
    put_multi, delete_multi, set_default_namespace, set_namespace,
)
from anom.testing import Emulator
from concurrent import futures
from contextlib import contextmanager

from .models import Person, Mutant, Cat, Human, Eagle

logging.basicConfig(level=logging.DEBUG)


@contextmanager
def push_adapter(adapter):
    old_adapter = get_adapter()
    yield set_adapter(adapter)
    set_adapter(old_adapter)


@pytest.fixture(scope="session")
def emulator():
    emulator = Emulator()
    emulator.start(inject=True)
    yield
    emulator.stop()


@pytest.fixture(scope="session")
def memcache_client():
    client = pylibmc.Client(["127.0.0.1"], binary=True, behaviors={"cas": True})
    yield client
    client.flush_all()


@pytest.fixture(autouse=True)
def noop_adapter():
    with push_adapter(Adapter()) as adapter:
        yield adapter


@pytest.fixture(scope="session")
def datastore_adapter_instance(emulator):
    # This fixture exists to memoize the DS adapter instance to make
    # initial test setup much cheaper.
    return adapters.DatastoreAdapter(project="fake-project-name")


@pytest.fixture
def datastore_adapter(datastore_adapter_instance):
    with push_adapter(datastore_adapter_instance) as adapter:
        yield adapter
        Query().delete()


@pytest.fixture()
def memcache_adapter(datastore_adapter, memcache_client):
    with push_adapter(adapters.MemcacheAdapter(memcache_client, datastore_adapter)) as adapter:
        yield adapter


@pytest.fixture(params=[None, "namespace"])
def default_namespace(request):
    namespace = getattr(request, "param", None)
    yield set_default_namespace(namespace)
    set_default_namespace(None)
    set_namespace(None)


@pytest.fixture(params=["datastore_adapter", "memcache_adapter"])
def adapter(request, default_namespace):
    return request.getfixturevalue(request.param)


@pytest.fixture()
def person(adapter):
    person = Person(
        email="john.smith@example.com",
        first_name="John",
        last_name="Smith"
    )
    person.put()
    yield person
    person.delete()


@pytest.fixture()
def person_in_ns(adapter):
    person = Person(
        email="namespaced@example.com",
        first_name="Namespaced",
        last_name="Person"
    )
    person.key = Key(Person, namespace="a-namespace")
    person.put()
    yield person
    person.delete()


@pytest.fixture()
def person_with_ancestor(person):
    child = Person(
        email="child@example.com",
        first_name="Child",
        last_name="Person",
    )
    child.key = Key(Person, parent=person.key, namespace=person.key.namespace)
    child.put()
    yield child
    child.delete()


@pytest.fixture
def people(adapter):
    people = put_multi([
        Person(
            key=Key(Person, i), email=f"{i}@example.com", first_name="Person", last_name=str(i)
        ) for i in range(1, 21)
    ])

    yield people

    delete_multi([person.key for person in people])


@pytest.fixture()
def mutant(adapter):
    mutant = Mutant(email="charles@xavier.edu", first_name="Charles", last_name="Xavier")
    mutant.power = "telepathy"
    mutant.put()
    yield mutant
    mutant.delete()


@pytest.fixture
def cat(adapter):
    cat = Cat(name="Volgar the Destoryer").put()
    yield cat
    cat.delete()


@pytest.fixture
def human(adapter):
    human = Human(name="Steve").put()
    yield human
    human.delete()


@pytest.fixture
def eagle(adapter):
    eagle = Eagle().put()
    yield eagle
    eagle.delete()


@pytest.fixture
def executor():
    with futures.ThreadPoolExecutor() as executor:
        yield executor
