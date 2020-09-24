__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

import ray
import random
from .index import *


@ray.remote
class RTreeIndexShard(RTreeIndex):
    pass

class ParallelRTreeIndex(Index):
    def __init__(self, feature, node_min_size=2, node_max_size=5, processes=1):
        self.feature = feature
        self.node_min_size = node_min_size
        self.node_max_size = node_max_size

        ray.init(num_cpus=processes)
        self.processes = processes
        self.shards = [RTreeIndexShard.remote(feature, node_min_size, node_max_size) for i in range(processes)]
        self.selected_shard = 0


    def get_shard(self):
        ret = self.shards[self.selected_shard]
        self.selected_shard = (self.selected_shard + 1) % self.processes
        return ret

    def insert(self, key, value):
        id = self.get_shard().insert.remote(key, value)
        ray.get(id)

    def remove_subset(self, key):
        remaining_ids = [shard.remove_subset.remote(key) for shard in self.shards]
        covered = 0
        while len(remaining_ids) > 0:
            ready_ids, remaining_ids = ray.wait(remaining_ids)
            covered += sum([ray.get(id) for id in ready_ids])
        return covered


    def print_index(self):
        for i, shard in enumerate(self.shards):
            print("Shard", i)
            ray.get(shard.print_index.remote())


    def get_subsets(self, key):
        remaining_ids = [shard.get_subsets.remote(key) for shard in self.shards]
        ret = []
        while len(remaining_ids) > 0:
            ready_ids, remaining_ids = ray.wait(remaining_ids)
            for id in ready_ids:
                ret += ray.get(id)
        return ret

    def get_knn_approx(self, key, k=2):
        remaining_ids = [shard.get_knn_approx.remote(key, k) for shard in self.shards]
        ret = []
        while len(remaining_ids) > 0:
            ready_ids, remaining_ids = ray.wait(remaining_ids)
            for id in ready_ids:
                ret = sorted(ret + ray.get(id))[:k]
        return ret

    def get_knn_precise(self, key, k=2):
        remaining_ids = [shard.get_knn_precise.remote(key, k) for shard in self.shards]
        ret = []
        while len(remaining_ids) > 0:
            ready_ids, remaining_ids = ray.wait(remaining_ids)
            for id in ready_ids:
                ret = sorted(ret + ray.get(id))[:k]
        return ret





import unittest


class TestIndex(unittest.TestCase):
    def test_parallel_index(self):
        import netaddr
        from .labeling import Feature, Spec
        from .ip_labeling import IPv4PrefixLabeling

        feature = Feature('ip', IPv4PrefixLabeling())

        index = ParallelRTreeIndex(feature, processes=4)
        for i in range(256):
            index.insert(Spec(1, (netaddr.IPNetwork('192.186.1.%d/32' % i))), i)

        index.print_index()


        print(index.get_knn_approx(Spec(1, (netaddr.IPNetwork('192.186.1.0/32')))))
        print(index.get_knn_precise(Spec(1, (netaddr.IPNetwork('192.186.1.0/32')))))

        subsets = index.get_subsets(Spec(1, netaddr.IPNetwork('192.186.1.0/30')))
        print(subsets)
        self.assertEqual(len(subsets), 4)

        cover_dec = index.remove_subset(Spec(1, netaddr.IPNetwork('192.186.1.0/30')))
        print(cover_dec)
        self.assertEqual(cover_dec, 4)

        index.print_index()

        cover_dec = index.remove_subset(Spec(256, netaddr.IPNetwork('192.186.1.0/24')))
        print(cover_dec)
        self.assertEqual(cover_dec, 252)

        index.print_index()
