from heapq import *
from labeling import Labeling, Spec, inf


class HRegexElement(object):
    # __slots__ = ["label", "multiple"]

    def __init__(self, label, multiple):
        self.label = label
        self.multiple = multiple

    def __eq__(self, other):
        return self.label == other.label and self.multiple == other.multiple

    def __str__(self):
        return self.label + ("+" if self.multiple else "")


class HRegex(object):
    def __init__(self, path):
        if not isinstance(path[0], HRegexElement):
            #print path
            # not a regex already, make it one
            self.regex = [(HRegexElement(h, False) if h[-1] != "+" else (HRegexElement(h[:-1], True))) for h in path]
        else:
            # a regex already, do nothing
            self.regex = path

    def __eq__(self, other):
        return self.regex == other.regex

    def __repr__(self):
        return "(" + " ".join(map(str, self.regex)) + ")"

    def __len__(self):
        return len(self.regex)


class HRegexLabeling(Labeling):
    def __init__(self, labeling, d = 1):
        self.labeling = labeling
        self.d = d

    def join(self, l1, l2):
        #print l1, l2

        class Entry(object):
            __slots__ = ["cost", "parent"]

            def __init__(self):
                self.cost = inf
                self.parent = None

        N = min(len(l1), len(l2))
        assert(N > 0)

        l1_min_cost, l2_min_cost = [1], [1]
        for i in range(len(l1)):
            l1_min_cost += [l1_min_cost[-1] * self.labeling.label_info[l1.regex[i].label]["cost"]]
        for i in range(len(l2)):
            l2_min_cost += [l2_min_cost[-1] * self.labeling.label_info[l2.regex[i].label]["cost"]]
        # print l1_min_cost
        # print l2_min_cost



        # optimization: Graph search instead of dp
        closed = {}
        # node (n,i,j,i_m,j_m,l_m,l)
        # q entry (heuristic cost, node, parent, actual cost)
        labels = self.labeling.get_predecessors(l1.regex[0].label) & self.labeling.get_predecessors(l2.regex[0].label)
        q = [(self.labeling.label_info[l]['cost'], (-1, 1, 1, 0, 0, 0, l), None, self.labeling.label_info[l]['cost']) for l in labels]
        # using negative n so that bigger n's with same score are prioritized
        heapify(q)
        closed = {}
        best = None
        while q:
            est, node, parent, cost = heappop(q)
            if node in closed.keys():
                continue
            closed[node] = (cost, parent)
            #print "at", "{} ({})".format(est,cost), node, parent
            n, i, j, i_m, j_m, l_m, l = node

            assert -n <= N

            if i > len(l1) and j > len(l2):
                assert cost == est
                #print "!!!"
                if best is None:
                    best = node
                else:
                    c_best = closed[best][0]
                    n_best = best[0]
                    if -n > -n_best and cost ** (-1.0/n) < c_best ** (-1.0/n_best):
                        best = node

                if -n < N:
                    continue

                node = best
                best_cost, parent = closed[node]
                #print "best is {} ({}) {} {}".format(best_cost, best_cost ** (-1.0/node[0]), node, parent)

                ret = []
                c = 0
                while node is not None:
                    #print "--", cost, node
                    _, _, _, i_m, j_m, l_m, l = node
                    c += 1

                    if l_m == 0 and parent is None or parent[0] != node[0]:
                        m = c > 2 or i_m or j_m
                        #print "adding next label", l, c > 2, i_m, j_m,"=>", m
                        ret.append(HRegexElement(l, m))
                        c = 0

                    node = parent
                    if node:
                        cost, parent = closed[node]

                ret.reverse()
                ret = Spec((best_cost**(-1.0/best[0]))**self.d, HRegex(ret))
                #print ret
                return ret

            else:


                def impossible(n, i, j, i_m, j_m, l_m, l):
                    a_i = l1.regex[i - 1] if i <= len(l1) else None
                    b_j = l2.regex[j - 1] if j <= len(l2) else None

                    if i_m == 1:
                        if i > len(l1) or not a_i.multiple:
                            return True
                    if j_m == 1:
                        if j > len(l2) or not b_j.multiple:
                            return True
                    if l_m == 0:
                        # characters must be left to match in both l1 and l2
                        if i > len(l1) or j > len(l2):
                            return True
                    return False

                # optimization A*
                def heuristic(node):
                    return 1
                    # n, i, j, i_m, j_m, l_m, l = node
                    # # if impossible(n, i, j, i_m, j_m, l_m, l):
                    # #    return inf for some reason this make things much slower!
                    # ii = (i - 1) if i > 0 and i_m else i
                    # jj = (j - 1) if j > 0 and j_m else j
                    # return l1_min_cost[ii] + l2_min_cost[jj]

                def update(nei, add_c):
                    if nei not in closed.keys():
                        g = cost * add_c
                        h = heuristic(nei)
                        heappush(q, (g * h, nei, node, g))
                        #print "  pushed", g * h,nei,node,g

                if impossible(n, i, j, i_m, j_m, l_m, l):
                    continue

                a_i = l1.regex[i - 1] if i <= len(l1) else None
                b_j = l2.regex[j - 1] if j <= len(l2) else None

                assert(i <= len(l1) or i_m == 0)
                assert(j <= len(l2) or j_m == 0)

                # if any of l_m,i_m,j_m is true, then we can ignore that
                if i_m == 1 and self.labeling.cost(a_i.label, l) < inf:
                    update((n, i + 1, j, 0, j_m, l_m, l), 1)
                if j_m == 1 and self.labeling.cost(b_j.label, l) < inf:
                    update((n, i, j + 1, i_m, 0, l_m, l), 1)
                if l_m == 1 and -n < N:
                    # optimization
                    # if j_m == 0 and i_m == 0 and i > 0 and j > 0:
                    #    labels = set(self.labeling.get_predecessors(a_i.label)) & set(self.labeling.get_predecessors(b_j.label))
                    # else:
                    #    labels = self.labeling.label_info.keys()
                    if i > len(l1):
                        l1s = set(self.labeling.label_info.keys())
                    else:
                        l1s = self.labeling.get_predecessors(a_i.label)
                        if i_m and i < len(l1):
                            l1s = l1s | self.labeling.get_predecessors(l1.regex[i].label)
                    if j > len(l2):
                        l2s = set(self.labeling.label_info.keys())
                    else:
                        l2s = self.labeling.get_predecessors(b_j.label)
                        if j_m and j < len(l2):
                            l2s = l2s | self.labeling.get_predecessors(l2.regex[j].label)
                    labels = l1s & l2s

                    for ll in labels:
                        update((-(-n + 1), i, j, i_m, j_m, 0, ll), self.labeling.cost(ll,ll))

                # also possibility of character matching
                if l_m == 0 and self.labeling.cost(a_i.label, l) < inf and self.labeling.cost(b_j.label, l) < inf:
                    # must match both
                    ii, ii_m = (i, 1) if a_i.multiple else (i + 1, 0)
                    jj, jj_m = (j, 1) if b_j.multiple else (j + 1, 0)
                    update((n, ii, jj, ii_m, jj_m, 1, l), 1)
                else:
                    # can match only one
                    # with a_i
                    if i <= len(l1) and self.labeling.cost(a_i.label, l) < inf:
                        ii, ii_m = (i, 1) if a_i.multiple else (i + 1, 0)
                        update((n, ii, j, ii_m, j_m, 1, l), 1)
                    # with b_j
                    if j <= len(l2) and self.labeling.cost(b_j.label, l) < inf:
                        jj, jj_m = (j, 1) if b_j.multiple else (j + 1, 0)
                        update((n, i, jj, i_m, jj_m, 1, l), 1)

        assert False


