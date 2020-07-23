__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Code for efficient evaluation of inferred intents
"""

import os

from anime.framework.labeling import *
from anime.framework.ip_labeling import *
from anime.framework.clustering import *
from anime.framework.hregex import *
from anime.framework.lattice import *
from anime.framework.index import *

"""
    Assumption: the coverage of each k is a subset of the coverage of next k
"""


class IncrementalAtomCoverMapGenerator(object):
    def __init__(self, args, clusters, feature):
        self.args = args
        self.clusters = clusters
        self.feature = feature
        self.create_lattice()
        self.lattice.print_tree()

    def create_lattice(self):
        filename = "/meet_semilattice.pk"
        if os.path.exists(self.args.out + filename):
            with open(self.args.out + filename) as f:
                self.lattice = pickle.load(f)
                return

        self.lattice = MeetSemiLattice(self.feature)

        print("creating meet semi-lattice from clusters")
        for c in self.clusters:
            self.lattice.insert(c.value)

        print("computing cardinality")
        self.lattice.compute_all_cardinality()

        print("finished creating lattice")
        print("input size was", len(self.clusters), "output size is", len(self.lattice.get_all_nodes()))

        with open(self.args.out + filename, 'w') as f:
            pickle.dump(self.lattice, f)

    def get_accepted(self, new_intents):
        ret = set()
        for i in new_intents:
            ret = ret | self.lattice.get_label_subtree(self.clusters[i].value)
        return ret

    def get_cover_map(self, intent_info):
        # filename = "/atom_cover_map.pk"
        # if os.path.exists(args.out + filename):
        #     with open(args.out + filename) as f:
        #         cover_map = pickle.load(f)
        #     return cover_map

        covered = set()
        cover_map = {}

        for info in intent_info:
            k = info.k
            print("k", k)
            new_intents = info.added
            print("new_intents", new_intents)
            new_accepted = self.get_accepted(new_intents) - covered
            print("new_accepted", new_accepted, len(new_accepted))
            covered |= new_accepted
            print("covered", len(covered))
            cover_map[k] = new_accepted

        # with open(args.out + filename, 'w') as f:
        #     pickle.dump(cover_map, f)

        return cover_map

    def evaluate(self, intent_info):
        cover_map = self.get_cover_map(intent_info)

        res = {}
        covered = 0

        for info in intent_info:
            k = info.k
            new_covered = sum([self.lattice.get_cardinality(n) for n in cover_map[k]])
            covered += new_covered
            res[k] = {"predicted_positive": covered}
            print(k, res[k])

        return res


class IncrementalCoverMapGenerator(object):
    def __init__(self, name, flows, clusters, feature, use_index=True):
        self.name = name
        self.flows = flows
        self.clusters = clusters
        self.feature = feature
        self.use_index = use_index
        self.index_sanity_check = False

        if self.use_index:
            import time
            start_time = time.time()
            print("Indexing flows")
            self.index = RTreeIndex(self.feature, 2, 10)
            for f in range(len(self.flows)):
                key = self.feature.labeling.join(self.flows[f], self.flows[f])
                self.index.insert(key, f)
            print("Finished indexing flows in ", time.time() - start_time)

    def get_new_accepted(self, new_intents, remaining):
        if self.use_index and self.index_sanity_check:
            return self._get_new_accepted_with_sanity_check(new_intents, remaining)

        ret = []
        if self.use_index:
            for i in new_intents:
                new = [x for _, x in self.index.get_subsets(self.clusters[i])]
                ret += new
                # note than len(ret) can be indeed zero
                self.index.remove_subset(self.clusters[i])
        else:
            for f in remaining:
                accepted = False
                for i in new_intents:
                    if self.feature.labeling.subset(self.flows[f], self.clusters[i].value):
                        accepted = True
                        break
                # print "checking", f, self.flows[f], accepted
                if accepted:
                    ret.append(f)
        return ret


    def _get_new_accepted_with_sanity_check(self, new_intents, remaining):
        ret1 = []
        ret2 = []

        for i in new_intents:
            new = [x for _,x in self.index.get_subsets(self.clusters[i])]
            ret1 += new
            self.index.remove_subset(self.clusters[i])

        for f in remaining:
            accepted = False
            for i in new_intents:
                if self.feature.labeling.subset(self.flows[f], self.clusters[i].value):
                    accepted = True
                    break
            if accepted:
                ret2.append(f)

        assert set(ret1) == set(ret2)
        return ret1

    def get_cover_map(self, intent_info, args):
        filename = "/%s_cover_map.pk" % self.name
        if os.path.exists(args.out + filename):
            with open(args.out + filename) as f:
                cover_map = pickle.load(f)
            return cover_map


        remaining = set(range(len(self.flows)))
        cover_map = {}

        for info in intent_info:
            k = info.k
            print("k", k)
            new_intents = info.added
            print("new_intents", new_intents)
            new_accepted = self.get_new_accepted(new_intents, remaining)
            remaining -= set(new_accepted)
            print("new_accepted", new_accepted, len(new_accepted))
            print("remaining len", len(remaining))
            cover_map[k] = new_accepted


        with open(args.out + filename, 'w') as f:
            pickle.dump(cover_map, f)

        return cover_map

class IncrementalCostBasedEvaluator(object):
    def __init__(self, flows, clusters, feature):
        self.cover_map_gen = IncrementalCoverMapGenerator("positive", flows, clusters, feature)
        self.flows = flows
        self.clusters = clusters
        self.feature = feature


    def evaluate(self, intent_info, args):
        cover_map = self.cover_map_gen.get_cover_map(intent_info, args)

        tp = 0
        res = {}
        original_cost = 0
        card_sum = 0

        for info in intent_info:
            k = info.k
            tp += sum([self.feature.labeling.cardinality(self.flows[f]) for f in cover_map[k]])
            original_cost += \
                sum([self.clusters[c].cost for c in info.added]) - sum([self.clusters[c].cost for c in info.removed])
            card_sum += sum([self.feature.labeling.cardinality(self.clusters[c].value) for c in info.added]) - \
                        sum([self.feature.labeling.cardinality(self.clusters[c].value) for c in info.removed])
            res[k] = {"tp": tp, "cost": original_cost, "cardinality_sum": card_sum}
            print(k, res[k])

        return res


class IncrementalSampleBasedEvaluator(object):
    def __init__(self, p_flows, n_flows, clusters, feature):
        self.p_cover_map_gen = IncrementalCoverMapGenerator("positive", p_flows, clusters, feature)
        self.n_cover_map_gen = IncrementalCoverMapGenerator("negative", n_flows, clusters, feature)
        self.p_flows = p_flows
        self.n_flows = n_flows
        self.clusters = clusters
        self.feature = feature


    def evaluate(self, intent_info, args):
        p_cover_map = self.p_cover_map_gen.get_cover_map(intent_info, args)
        n_cover_map = self.n_cover_map_gen.get_cover_map(intent_info, args)

        tp = 0
        fp = 0
        tn = sum([self.feature.labeling.cardinality(f) for f in self.n_flows])
        fn = sum([self.feature.labeling.cardinality(f) for f in self.p_flows])

        res = {}

        uncovered_negative = set(range(len(self.n_flows)))

        for info in intent_info:
            k = info.k
            p_new_covered = sum([self.feature.labeling.cardinality(self.p_flows[f]) for f in p_cover_map[k]])
            n_new_covered = sum([self.feature.labeling.cardinality(self.n_flows[f]) for f in n_cover_map[k]])
            tp += p_new_covered
            fp += n_new_covered
            tn -= n_new_covered
            fn -= p_new_covered

            res[k] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn}
            print(k, res[k])

        return res

