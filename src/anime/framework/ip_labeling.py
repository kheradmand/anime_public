__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Various labeling designs for IP feature
"""

from labeling import *
import netaddr


class IPv4Prefix(netaddr.IPNetwork):
    pass


class IPv4PrefixLabeling(Labeling):
    def join(self, l1, l2):
        start = min(l1.first, l2.first)
        end = max(l1.last, l2.last)

        b = "{0:032b}".format(start ^ end)

        prefixlen = b.find('1')
        if prefixlen is -1:
            prefixlen = 32

        ip = netaddr.IPAddress(start & (~((1 << (32 - prefixlen)) - 1) & ((1 << 32) - 1)))

        ret = IPv4Prefix(ip)
        ret.prefixlen = prefixlen

        return Spec((1 << (32 - prefixlen)), ret)

    def cost(self, l):
        return len(l)


class IPv4PrefixSetLabeling(Labeling):
    def join(self, l1, l2):
        ret = l1 | l2
        cost = len(ret)

        return Spec(cost, ret)


class IPv4FlatLabeling(Labeling):
    def join(self, l1, l2):
        if l1 != l2:
            ret = '*'
        else:
            ret = l1
        if ret == '*':
            return Spec(2**32, ret)
        else:
            return Spec(netaddr.IPNetwork(ret).size, ret)


class IPv4SmallPrefixSetLabeling(Labeling):
    def __init__(self, limit = 2):
        assert limit > 0
        self.limit = limit

    def join(self, l1, l2):
        print l1, l2
        union = netaddr.IPSet(l1) | l2

        while True:
            union.compact()

            cidrs = []
            for p in union.iter_cidrs():
                cidrs.append(p)

            print "cidrs", cidrs
            if len(cidrs) <= self.limit:
                break

            best = None
            for i in range(len(cidrs) - 1):
                merge = netaddr.spanning_cidr(cidrs[i:i+2])
                if best is None or len(merge) < len(best):
                    print "best updated from",best,"to",merge,"from",cidrs[i:i+2]
                    best = merge
            union = union | best
        print union
        return Spec(len(union), union)

    def subset(self, l1, l2):
        return netaddr.IPSet(l1).issubset(l2)

    def cost(self, l):
        return len(l)

