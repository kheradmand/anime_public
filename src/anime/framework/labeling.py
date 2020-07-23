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

    def top(self):
        assert False

class Feature(object):
    def __init__(self, name, labeling):
        self.name = name
        self.labeling = labeling


class HierarchicalLabeling(Labeling):
    #Assumption: the input is a rooted DAG

    def __init__(self, label_info):
        self.label_info = label_info
        self.predecessors = {}
        self.successors = {}
        self.top_label = None

        for l, info in label_info.items():
            info["children"] = set()

        # find children, find top
        for l,info in label_info.items():
            if len(info["parents"]) == 0:
                assert self.top_label is None
                self.top_label = l

            for p in info["parents"]:
                self.label_info[p]["children"].add(l)

        assert self.top_label is not None



    @classmethod
    def load_from_file(cls, input_file):
        with open(input_file) as f:
            label_info = json.load(f)
            return HierarchicalLabeling(label_info)

    def get_predecessors(self, label):
        if label in self.predecessors:
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

    def get_successors(self, label):
        if label not in self.successors:
            suc = set()

            def add_children(label):
                suc.add(label)
                for c in self.label_info[label]["children"]:
                    add_children(c)

            add_children(label)
            self.successors[label] = suc

        return self.successors[label]

    def visualize_dot(self, outfile, view=True):
        from graphviz import Digraph
        dot = Digraph(comment='Labeling')
        for l in self.label_info.keys():
            dot.node(l, "%s (%d)" % (l, self.label_info[l]["cost"]))
        for l in self.label_info.keys():
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
            # workaround for cases where parent and children have the same cost (although it should not be the case technically)
            elif abs(self.label_info[label]["cost"] - self.label_info[best]["cost"]) < 1e-10 and best in self.get_predecessors(label):
                best = label
        return Spec(self.label_info[best]["cost"], best)

    def meet(self, l1, l2):
        c1 = self.get_successors(l1)
        c2 = self.get_successors(l2)

        inter = c1 & c2

        if len(inter) == 0:
            return None

        best = None
        for label in inter:
            if best is None or self.label_info[label]["cost"] > self.label_info[best]["cost"]:
                best = label

        return Spec(self.label_info[best]["cost"], best)

    def subset(self, l1, l2):
        return l2 in self.get_predecessors(l1)

    def cost(self, l):
        return self.label_info[l]["cost"]

    def cardinality(self, l):
        if "cardinality" in self.label_info[l]:
            return self.label_info[l]["cardinality"]
        else:
            return self.cost(l)

    def top(self):
        return self.top_label


class DValueLabeling(Labeling):
    top_symbol = "*"

    def __init__(self, top_cost, atom_cost = 1, top_card = None):
        self.top_cost = top_cost
        self.atom_cost = atom_cost
        self.top_card = top_card

    def join(self, l1, l2):
        if l2 == DValueLabeling.top_symbol or l2 == DValueLabeling.top_symbol or l1 != l2:
            return Spec(self.top_cost, DValueLabeling.top_symbol)
        else:
            # l1 == l2
            return Spec(self.atom_cost, l1)

    def meet(self, l1, l2):
        if self.subset(l1, l2):
            return Spec(self.cost(l1), l1)
        if self.subset(l2, l1):
            return Spec(self.cost(l2), l2)
        return None

    def cost(self, l):
        if l == DValueLabeling.top_symbol:
            return self.top_cost
        else:
            return self.atom_cost

    def top(self):
        return DValueLabeling.top_symbol

    def subset(self, l1, l2):
        return l1 == l2 or (l1 != DValueLabeling.top_symbol and l2 == DValueLabeling.top_symbol)

    def cardinality(self, l):
        if self.top_card is None:
            return self.top_cost
        else:
            return self.top_card


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

    def meet(self, a, b):
        meet = []
        cost = 1
        for f in range(len(self.features)):
            spec = self.features[f].labeling.meet(a[f],b[f])
            if spec is None:
                return None
            meet.append(spec.value)
            cost *= spec.cost

        return Spec(cost, tuple(meet))

    def cost(self, l):
        ret = 1

        for i in range(len(self.features)):
            ret *= self.features[i].labeling.cost(l[i])

        return ret

    def cost(self, l):
        ret = 1

        for i in range(len(self.features)):
            ret *= self.features[i].labeling.cardinality(l[i])

        return ret

    def subset(self, l1, l2):
        for i in range(len(self.features)):
            if not self.features[i].labeling.subset(l1[i], l2[i]):
                return False
        return True

    def top(self):
        return tuple(f.labeling.top() for f in self.features)



