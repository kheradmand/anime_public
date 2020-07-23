__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

import unittest
from .ip_labeling import *
from .labeling import *
from .hregex import *


class TestAnime(unittest.TestCase):
    def test_ipv4_prefix_labeling(self):
        self.assertEqual(
            IPv4PrefixLabeling.join(IPv4Prefix("192.168.1.0/32"), IPv4Prefix("192.168.1.0/32")),
            Spec(1, IPv4Prefix("192.168.1.0/32")))

        self.assertEqual(
            IPv4PrefixLabeling.join(IPv4Prefix("192.168.1.0/32"), IPv4Prefix("192.168.1.1/32")),
            Spec(2, IPv4Prefix("192.168.1.0/31")))

        self.assertEqual(
            IPv4PrefixLabeling.join(IPv4Prefix("192.168.1.0/32"), IPv4Prefix("0.168.1.1/32")),
            Spec(2**32, IPv4Prefix("0.0.0.0/0")))

    def test_dvalue_labeling(self):
        labeling = DValueLabeling(10, 1)
        for l1,l2 in [("tcp", "udp"), (1000,2000)]:
            self.assertEqual(labeling.join(l1, l2), Spec(10, DValueLabeling.top))
            self.assertEqual(labeling.join(l1, DValueLabeling.top), Spec(10, DValueLabeling.top))
            self.assertEqual(labeling.join(l1, l1), Spec(1, l1))

    label_info = {
        "s1": {"cost": 1, "parents": {"Server"}},
        "s2": {"cost": 1, "parents": {"Server"}},
        "u1": {"cost": 1, "parents": {"User"}},
        "u2": {"cost": 1, "parents": {"User"}},
        "Server": {"cost": 2, "parents": {"Any"}},
        "User": {"cost": 2, "parents": {"Any"}},
        "Any": {"cost": 4, "parents": {}},
    }

    def test_hierarchical_labeling(self):

        labeling = HierarchicalLabeling(TestAnime.label_info)

        self.assertEqual(labeling.join("s1", "s2"), Spec(2, "Server"))
        self.assertEqual(labeling.join("u1", "u2"), Spec(2, "User"))
        self.assertEqual(labeling.join("s1", "Server"), Spec(2, "Server"))
        self.assertEqual(labeling.join("s1", "User"), Spec(4, "Any"))
        self.assertEqual(labeling.join("s1", "u2"), Spec(4, "Any"))

    def test_hregex_labeling(self):
        labeling = HRegexLabeling(HierarchicalLabeling(TestAnime.label_info))

        self.assertEqual(labeling.join(HRegex(["u1", "s1"]), HRegex(["u1", "s2"])), Spec(6, HRegex(["u1", "Server"])))
        self.assertEqual(labeling.join(HRegex(["u1", "s1"]), HRegex(["u2", "s1"])), Spec(6, HRegex(["User", "s1"])))
        self.assertEqual(labeling.join(HRegex(["u1", "s1"]), HRegex(["u2", "s2"])), Spec(8, HRegex(["User", "Server"])))
        self.assertEqual(labeling.join(HRegex(["u1", "s1"]), HRegex(["u1", "s2+"])), Spec(6, HRegex(["u1", "Server+"])))
        self.assertEqual(labeling.join(HRegex(["u1", "s1"]), HRegex(["s1", "u1"])), Spec(16, HRegex(["Any+"])))

    def test_sequential_inference_dval(self):
        inference = SequentialInference(DValueLabeling(10, 1))

        self.assertEqual(inference.infer(["tcp","tcp","tcp","tcp"]), Spec(1, "tcp"))
        self.assertEqual(inference.infer(["tcp", "tcp", "tcp", "udp"]), Spec(10, DValueLabeling.top))

    def test_sequential_inference_ipv4prefix(self):
        inference = SequentialInference(IPv4PrefixLabeling)

        self.assertEqual(inference.infer(
            [IPv4Prefix("192.168.0.0/32"), IPv4Prefix("192.168.0.1/32"), IPv4Prefix("192.168.0.2/32")]),
            Spec(4, IPv4Prefix("192.168.0.0/30")))

    def test_sequential_inference_hregex(self):
        inference = SequentialInference(HRegexLabeling(HierarchicalLabeling(TestAnime.label_info)))

        self.assertEqual(
            inference.infer([HRegex(["u1", "s1"]), HRegex(["u1", "s2"]), HRegex(["u2", "s1"])]).value,
            HRegex(["User", "Server"]))

    def test_regression_1(self):
        labeling = HRegexLabeling(HierarchicalLabeling(TestAnime.label_info))

        self.assertEqual(labeling.join(HRegex(["s1", "u1"]), HRegex(["s1", "u1"])), Spec(4, HRegex(["s1", "u1"])))


class Inference(object):
    def __init__(self, labeling):
        self.labeling = labeling


class SequentialInference(Inference):
    def infer(self, values):
        spec = None
        for v in values:
            if not spec:
                spec = self.labeling.join(v, v)
            else:
                spec = self.labeling.join(spec.value, v)
        return spec