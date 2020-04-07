from labeling import Labeling, Spec, inf
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