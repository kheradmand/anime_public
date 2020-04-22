#!/usr/bin/env python
__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"


import argparse
import sys
import random
import logging
sys.path.append('../../src/')
from anime.framework.clustering import *
from anime.framework.hregex import *
from anime.framework.ip_labeling import *
from anime.framework.labeling import *

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

parser = argparse.ArgumentParser()
parser.add_argument('--labeling', '-l', help='path to labeling json file', type=str, default="labeling.json")
parser.add_argument('--clusters', '-c', help='number of cluster', type=int, default=1)
parser.add_argument('--ip', help='paths with ip', type=bool, default=False)
parser.add_argument('--batch', '-b', help='batch size', type=int, default=0)
parser.add_argument("--seed", '-s', help='random seed', type=int, default=10)
parsed_args = parser.parse_args()

random.seed(parsed_args.seed)

print ">clusters", parsed_args.clusters
print ">batch", parsed_args.batch

flows = []

d = 0
for l in sys.stdin:
    path = l.strip().split()
    if len(path) == 0:
        continue
    if parsed_args.ip:
        ip = path[0]
        path = path[1:]
        flows.append([IPv4Prefix(ip), HRegex(path)])
    else:
        flows.append([HRegex(path)])

    d = max(d, len(path))

print "d is", d

device_labeling = HierarchicalLabeling.load_from_file(parsed_args.labeling)
pathFeature = Feature("path", HRegexLabeling(device_labeling, d))
ipFeature = Feature("dst ip", IPv4PrefixLabeling())

if parsed_args.ip:
    flow_labeling = TupleLabeling([ipFeature, pathFeature])
else:
    flow_labeling = TupleLabeling([pathFeature])

clustering = HierarchicalClustering(parsed_args.clusters, parsed_args.batch)
clusters = clustering.cluster(flows, Feature('flow', flow_labeling))

print "final clusters:"
for c in clusters:
    print c






