__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    based on #PEC Algorithm from our ICNP'19 work
"""


import logging as log


class LatticeNode(object):
    #__slots__ = ["label", "children", "cardinality"]

    def __init__(self, l):
        self.label = l
        self.children = set()
        self.cardinality = None

    def __repr__(self):
        return "%s, %s" % (self.label, self.cardinality)


class MeetSemiLattice(object):
    def __init__(self, feature):
        self.feature = feature
        self.label_to_node = {}
        self.root,new = self.get_node(feature.labeling.top())
        assert new

    def insert(self, l):
        n,new = self.get_node(l)
        if new:
            self.insert_under(n,self.root)
        return n

    def subset(self, l1, l2):
        return self.feature.labeling.subset(l1, l2)

    def meet(self, l1, l2):
        return self.feature.labeling.meet(l1, l2)

    def get_node(self, l):
        new = False
        if l not in self.label_to_node:
            self.label_to_node[l] = LatticeNode(l)
            new = True
        return self.label_to_node[l], new

    def print_tree(self):
        self.print_subtree(self.root)

    def print_subtree(self, n, level = 1):
        print("-"*level, n)
        for c in n.children:
            self.print_subtree(c, level + 1)

    def get_label_subtree(self, l):
        n, new = self.get_node(l)
        assert not new
        return self.get_node_subtree(n)


    def get_cardinality(self, n):
        if n.cardinality is None:
            subtree = self.get_node_subtree(n) - set([n])
            card = self.feature.labeling.cardinality(n.label)
            n.cardinality = card - sum([self.get_cardinality(c) for c in subtree])
            #print "for ", n, "=", card, "-", [self.get_cardinality(c) for c in subtree]

        return n.cardinality

    def compute_all_cardinality(self):
        self.get_cardinality(self.root)

    def get_all_nodes(self):
        return list(self.label_to_node.values())


    def _get_node_subtree(self, n, res):
        res.add(n)
        for c in n.children:
            self._get_node_subtree(c, res)

    def get_node_subtree(self, n):
        res = set()
        self._get_node_subtree(n,res)
        return res

    def insert_under(self, n, r):
        log.debug("Inserting %s under %s", n, r)

        assert(self.subset(n.label, r.label))

        if n.label == r.label:
            log.debug('%s == %s, returning', n, r)
            return


        children = []
        inter_children = []

        for c in r.children:
            if self.subset(n.label, c.label):
                log.debug("%s under child %s", n, c)
                self.insert_under(n, c)
            elif self.subset(c.label, n.label):
                log.debug("child %s under %s", c, n)
                children.append(c)
            else:
                m_label = self.meet(n.label, c.label)
                log.debug("intersection of %s and %s is %s", n, c, m_label)
                if m_label is not None:
                    m_label = m_label.value
                    m, new = self.get_node(m_label)
                    inter_children.append(m)
                    if new:
                        self.insert_under(m, c)

        r.children.add(n)

        # find max children
        for i,ic in enumerate(inter_children):
            for j,c in enumerate(children):
                if self.subset(ic.label, c.label):
                    inter_children[i] = None
                    break

        for i in range(len(inter_children)):
            for j in range(len(inter_children)):
                if i == j or inter_children[i] is None or inter_children[j] is None:
                    continue
                if self.subset(inter_children[j].label, inter_children[i].label):
                    inter_children[j] = None

        for c in children:
            r.children.remove(c)
            n.children.add(c)

        for ic in inter_children:
            if ic:
                if ic in r.children:
                    r.children.remove(ic)
                n.children.add(ic)



import unittest

class TestLattice(unittest.TestCase):
    def test_lattice_insertion_ip(self):
        import netaddr
        from .labeling import Feature
        from .ip_labeling import IPv4PrefixLabeling

        feature = Feature('ip', IPv4PrefixLabeling())

        lattice = MeetSemiLattice(feature)
        lattice.insert(netaddr.IPNetwork('192.168.0.0/32'))
        lattice.insert(netaddr.IPNetwork('192.168.1.0/32'))
        lattice.insert(netaddr.IPNetwork('192.168.1.0/30'))
        self.assertEqual(len(lattice.get_all_nodes()), 4)

        lattice.compute_all_cardinality()
        lattice.print_tree()

        self.assertEqual(lattice.get_cardinality(lattice.root), 2**32 - 1 - 4)

    def test_lattice_insertion_tuple(self):
        from .labeling import *

        feature = Feature('tuple', TupleLabeling(
            [Feature('src',  DValueLabeling(3)), Feature('dst', DValueLabeling(3))]))

        lattice = MeetSemiLattice(feature)
        lattice.insert(('*','X'))
        lattice.insert(('A','*'))

        self.assertEqual(len(lattice.get_all_nodes()), 4)

        lattice.compute_all_cardinality()
        lattice.print_tree()

        self.assertEqual(lattice.get_cardinality(lattice.root),9 - 3 -3 + 1)


