from unittest import TestCase

from adsepra import SepClient

from sepdpc import repository


class Test(TestCase):
    def test_from_server(self):
        client = SepClient(host='http://localhost:9999', user='merlin', token='Basic bWVybGluOg')
        repo = repository.from_server(client)
        assert len(repo.domains) > 0
        assert len(repo.products) > 0

    def test_from_local(self):
        repo_path = '/localrepo'
        repo = repository.from_local(repo_path)
        assert len(repo.domains) == 4
        assert len(repo.products) == 4
