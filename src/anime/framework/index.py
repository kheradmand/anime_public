__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Various indexing techniques
"""

from labeling import Spec


class Index(object):
    def insert(self, key, value):
        assert False

    def get_subsets(self, key):
        assert False


class RtreeIndexNode:
    def __init__(self, bounding_box):
        self.is_leaf = True
        self.bounding_box = bounding_box
        self.objects = []

        self.covered = 0


class RTreeIndex(Index):
    def __init__(self, feature, node_min_size=4, node_max_size=10):
        self.feature = feature
        top = feature.labeling.top()
        self.root = RtreeIndexNode(Spec(feature.labeling.cost(top), top))
        self.node_min_size = node_min_size
        self.node_max_size = node_max_size

    def insert(self, key, value):
        new_child = self._insert(key, value, self.root)
        if new_child:
            new_root = RtreeIndexNode(self.feature.labeling.join(self.root.bounding_box.value, new_child.bounding_box.value))
            new_root.is_leaf = False
            new_root.objects = [self.root, new_child]
            new_root.covered = self.root.covered + new_child.covered
            self.root = new_root

    def remove_subset(self, key):
        original_covered = self.root.covered
        self._remove_subset(key, self.root)
        if self.root.covered == 0:
            top = self.feature.labeling.top()
            self.root.bounding_box = Spec(self.feature.labeling.cost(top), top)
            self.root.is_leaf =  True
        return original_covered - self.root.covered

    def _remove_subset(self, key, n):
        if self.feature.labeling.subset(n.bounding_box.value, key.value):
            n.covered = 0
            n.objects = []
        else:
            if n.is_leaf:
                for i in range(len(n.objects)):
                    if self.feature.labeling.subset(RTreeIndex.leaf_obj_get_bb(n.objects[i]).value, key.value):
                        n.covered -= RTreeIndex.leaf_obj_get_bb(n.objects[i]).cost
                        n.objects[i] = None
                n.objects = filter(lambda x: x is not None, n.objects)
            else:
                for i in range(len(n.objects)):
                    if self.feature.labeling.meet(RTreeIndex.internal_obj_get_bb(n.objects[i]).value, key.value):
                        n.covered -= n.objects[i].covered
                        self._remove_subset(key, n.objects[i])
                        n.covered += n.objects[i].covered
                n.objects = filter(lambda o: o.covered > 0, n.objects)

            assert len(n.objects) > 0


            if n.is_leaf:
                get_bb = RTreeIndex.leaf_obj_get_bb
            else:
                get_bb = RTreeIndex.internal_obj_get_bb

            n.bounding_box = get_bb(n.objects[0])
            for o in n.objects[1:]:
                n.bounding_box = self.feature.labeling.join(n.bounding_box.value, get_bb(o).value)


    def split_node(self, n):
        if n.is_leaf:
            get_bb = RTreeIndex.leaf_obj_get_bb
        else:
            get_bb = RTreeIndex.internal_obj_get_bb
        if len(n.objects) <= self.node_max_size:
            return None
        else:
            l = len(n.objects)
            max_dist = None
            for i in range(l):
                for j in range(i+1, l):
                    spec = self.feature.labeling.join(get_bb(n.objects[i]).value, get_bb(n.objects[j]).value)
                    if max_dist is None or spec.cost > max_dist[0]:
                        max_dist = (spec.cost, (i,j))

            assert max_dist is not None
            # print "max_dist is ", max_dist

            a, b = max_dist[1]
            groups = [[n.objects[a]],[n.objects[b]]]
            bounding_boxes = [get_bb(n.objects[a]), get_bb(n.objects[b])]
            covered = [get_bb(n.objects[a]).cost, get_bb(n.objects[b]).cost] if n.is_leaf\
                else [n.objects[a].covered, n.objects[b].covered]

            for i in range(l):
                # print i,
                if i == a or i == b:
                    # print "adding by definition"
                    continue
                elif len(groups[0]) <= self.node_min_size - (l - i - (1 if i < a else 0) - (1 if i < b else 0)):
                    # print "adding to 0 because of min_size"
                    g = 0
                elif len(groups[1]) <= self.node_min_size - (l - i - (1 if i < a else 0) - (1 if i < b else 0)):
                    # print "adding to 1 because of min_size"
                    g = 1
                else:
                    # 1- smallest increase in area
                    # 2- smallest area
                    # 3- smallest number of entries
                    # print get_bb(n.objects[i]),  bounding_boxes[0],  bounding_boxes[1]
                    spec1 = self.feature.labeling.join(get_bb(n.objects[i]).value, bounding_boxes[0].value)
                    spec2 = self.feature.labeling.join(get_bb(n.objects[i]).value, bounding_boxes[1].value)

                    diff1 = spec1.cost - bounding_boxes[0].cost
                    diff2 = spec2.cost - bounding_boxes[1].cost

                    if abs(diff1 - diff2) > 1e-10:
                        g = 0 if diff1 < diff2 else 1
                        # print "adding to %s because of diff" % g
                    elif abs(spec1.cost - spec2.cost) > 1e-10:
                        g = 0 if spec1.cost < spec2.cost else 1
                        # print "adding to %s because of cost" % g
                    else:
                        g = 0 if len(groups[0]) < len(groups[1]) else 1
                        # print "adding to %s because of len" % g

                o = n.objects[i]
                groups[g].append(o)
                bounding_boxes[g] = self.feature.labeling.join(bounding_boxes[g].value, get_bb(o).value)
                covered[g] += get_bb(o).cost if n.is_leaf else o.covered

            # print "new_sets"
            # print groups[0], bounding_boxes[0]
            # print groups[1], bounding_boxes[1]
            # print len(groups[0]), len(groups[1])
            assert self.node_min_size <= len(groups[0]) <= self.node_max_size
            assert self.node_min_size <= len(groups[1]) <= self.node_max_size

            n.objects = groups[0]
            n.bounding_box = bounding_boxes[0]
            n.covered = covered[0]

            np = RtreeIndexNode(bounding_boxes[1])
            np.is_leaf = n.is_leaf
            np.objects = groups[1]
            np.covered = covered[1]

            return np

    def print_index(self, n=None, level=0, level_limit=0):
        if 0 < level_limit < level:
            return
        if n is None:
            self.print_index(self.root, level_limit=level_limit)
        else:
            print '--' * level, n.bounding_box, n.covered
            if not n.is_leaf:
                for o in n.objects:
                    self.print_index(o, level+1, level_limit)
            else:
                for o in n.objects:
                    print '--' * (level+1), o

    @staticmethod
    def leaf_obj_get_bb(obj):
        return obj[0]

    @staticmethod
    def internal_obj_get_bb(obj):
        return obj.bounding_box

    def _insert(self, key, value, n):
        n.bounding_box = self.feature.labeling.join(n.bounding_box.value, key.value)
        n.covered += key.cost # assumption: no overlap between entries

        if n.is_leaf:
            n.objects.append((key,value)) # assumption: key is unique
            return self.split_node(n)
        else:
            l = len(n.objects)
            best = None
            for i in range(l):
                spec = self.feature.labeling.join(n.objects[i].bounding_box.value, key.value)
                diff = spec.cost - n.objects[i].bounding_box.cost
                if best is None or diff < best[0] or (diff - best[0] < 1e-10 and spec.cost < best[1].cost):
                    best = (diff, spec, i)

            assert best is not None
            # print "best is", best

            new_child = self._insert(key, value, n.objects[best[2]])

            if new_child:
                n.objects.insert(best[2] + 1, new_child)

            return self.split_node(n)


    def get_all_nodes(self):
        acc = []
        self._get_all_nodes(self.root, acc)
        return acc

    def _get_all_nodes(self, n, acc):
        acc.append(n)
        if not n.is_leaf:
            for o in n.objects:
                self._get_all_nodes(o, acc)



    def get_subsets(self, key):
        acc = []
        self._get_subsets(key, self.root, acc)
        return acc

    def _get_subsets(self, key, n, acc):
        # print "in get_subset for", key, n.bounding_box
        if n.is_leaf:
            for o in n.objects:
                if self.feature.labeling.subset(RTreeIndex.leaf_obj_get_bb(o).value, key.value):
                    acc.append(o)
        else:
            for o in n.objects:
                if self.feature.labeling.meet(RTreeIndex.internal_obj_get_bb(o).value, key.value):
                    self._get_subsets(key, o, acc)


    # def compute_node_cover_cost(self, n =None):
    #     if n is None:
    #         self.compute_node_cover_cost(self.root)
    #     else:
    #         if n.is_leaf:
    #             n.covered = sum(RTreeIndex.leaf_obj_get_bb(c).cost for c in n.objects)
    #         else:
    #             n.covered = sum(self.compute_node_cover_cost(c) for c in n.objects)
    #
    #         return n.covered

    def get_cover(self, key):
        return self._get_cover(key, self.root)

    def _get_cover(self, key, n):
        if self.feature.labeling.subset(n.bounding_box.value, key.value):
            ret = n.covered
        else:
            ret = 0
            if n.is_leaf:
                for o in n.objects:
                    # assumption: each leaf object is either subset or not overlapping
                    if self.feature.labeling.subset(RTreeIndex.leaf_obj_get_bb(o).value, key.value):
                        ret += RTreeIndex.leaf_obj_get_bb(o).cost
            else:
                for o in n.objects:
                    if self.feature.labeling.subset(RTreeIndex.internal_obj_get_bb(o).value, key.value):
                        ret += o.cover_cost
                    elif self.feature.labeling.meet(RTreeIndex.internal_obj_get_bb(o).value, key.value):
                        ret += self._get_cover(key, o)
        return ret


    def get_all_bounding_boxes(self):
        acc = []
        self._get_all_bounding_boxes(self.root, acc)
        return acc

    def _get_all_bounding_boxes(self, n, acc):
        acc.append(n.bounding_box)
        if n.is_leaf:
            for o in n.objects:
                acc.append(RTreeIndex.leaf_obj_get_bb(o))
        else:
            for o in n.objects:
                self._get_all_bounding_boxes(o, acc)





import unittest


class TestIndex(unittest.TestCase):
    def test_index(self):
        import netaddr
        from labeling import Feature, Spec
        from ip_labeling import IPv4PrefixLabeling

        feature = Feature('ip', IPv4PrefixLabeling())

        index = RTreeIndex(feature)
        for i in range(256):
            index.insert(Spec(1, (netaddr.IPNetwork('192.186.1.%d/32' % i))), i)

        index.print_index()

        subsets = index.get_subsets(Spec(1, netaddr.IPNetwork('192.186.1.0/30')))
        print subsets
        self.assertEqual(len(subsets), 4)

        cover_dec = index.remove_subset(Spec(1, netaddr.IPNetwork('192.186.1.0/30')))
        print cover_dec
        self.assertEqual(cover_dec, 4)

        index.print_index()

        cover_dec = index.remove_subset(Spec(256, netaddr.IPNetwork('192.186.1.0/24')))
        print cover_dec
        self.assertEqual(cover_dec, 252)

        index.print_index()
