__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Various types of labeling
"""

import collections
import json

Spec = collections.namedtuple('Spec', ['cost', 'value'])

class Labeling(object):

    def join(self, l1, l2):
        # return: Spec(cost, joined label)
        assert False

    def join(self,s):
        assert False

    def cost(self, l):
        assert False

    def subset(self, l1, l2):
        # would not work for something like HRegex
        return self.join(l1, l2).value == l2

    def meet(self, l1, l2):
        assert False

    def meet(self, s):
        assert False

    def cardinality(self, l):
        return self.cost(l)

class Feature(object):
    def __init__(self, name, labeling):
        self.name = name
        self.labeling = labeling


class HierarchicalLabeling(Labeling):
    #Assumption: the input is a rooted DAG

    def __init__(self, label_info):
        self.label_info = label_info
        self.predecessors = {}

    @classmethod
    def load_from_file(cls, input_file):
        with open(input_file) as f:
            label_info = json.load(f)
            return HierarchicalLabeling(label_info)

    def get_predecessors(self, label):
        if label in self.predecessors.keys():
            return self.predecessors[label]
        else:
            pred = set()

            def add_parents(label):
                pred.add(label)
                for p in self.label_info[label]["parents"]:
                    add_parents(p)

            add_parents(label)
            self.predecessors[label] = pred

            return pred

    def visualize_dot(self, outfile, view=True):
        from graphviz import Digraph
        dot = Digraph(comment='Labeling')
        for l in self.label_info.iterkeys():
            dot.node(l, "%s (%d)" % (l, self.label_info[l]["cost"]))
        for l in self.label_info.iterkeys():
            for p in self.label_info[l]["parents"]:
                dot.edge(p, l)
        dot.render(outfile, view=view)

    def join(self, l1, l2):
        p1 = self.get_predecessors(l1)
        p2 = self.get_predecessors(l2)

        inter = p1 & p2
        assert len(inter) > 0

        best = None
        for label in inter:
            if best is None or self.label_info[label]["cost"] < self.label_info[best]["cost"]:
                best = label

        return Spec(self.label_info[best]["cost"], best)

    def subset(self, l1, l2):
        return l2 in self.get_predecessors(l1)

    def cost(self, l):
        return self.label_info[l]["cost"]


class DValueLabeling(Labeling):
    top = "*"

    def __init__(self, top_cost, atom_cost = 1):
        self.top_cost = top_cost
        self.atom_cost = atom_cost

    def join(self, l1, l2):
        if l2 == DValueLabeling.top or l2 == DValueLabeling.top or l1 != l2:
            return Spec(self.top_cost, DValueLabeling.top)
        else:
            # l1 == l2
            return Spec(self.atom_cost, l1)

    def cost(self, l):
        if l == DValueLabeling.top:
            return self.top_cost
        else:
            return self.atom_cost


class TupleLabeling(Labeling):
    def __init__(self, features):
        self.features = features

    def join(self, a, b):
        joined = []
        cost = 1
        for f in range(len(self.features)):
            spec = self.features[f].labeling.join(a[f],b[f])
            joined.append(spec.value)
            cost *= spec.cost

        return Spec(cost, tuple(joined))

    def cost(self, l):
        ret = 1

        for i in range(len(self.features)):
            ret *= self.features[i].labeling.cost(l[i])

        return ret

    def subset(self, l1, l2):
        for i in range(len(self.features)):
            if not self.features[i].labeling.subset(l1[i], l2[i]):
                return False
        return True



