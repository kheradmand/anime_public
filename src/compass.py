#!/usr/bin/env python
__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Implementation of Compass algorithm from Net2Text paper (Birkner et al, NSDI'18)
    Based on load_example.py by Ruediger Birkner
"""

import argparse
import networkx as nx
import os
import pickle
import random
import json


class NDBEntry(object):
    def __init__(self, path, destination, prefix, shortest_path, additional_features, traffic_size=1):
        self.path = path
        self.prefix = prefix
        self.destination = destination
        self.shortest_path = shortest_path
        self.additional_features = additional_features

        self.traffic_size = traffic_size

    def get(self, key):
        if key == 'path':
            return tuple(self.path)
        elif key == 'prefix':
            return self.prefix
        elif key == 'destination':
            return self.destination
        elif key == 'egress':
            return self.path[-1]
        elif key == 'ingress':
            return self.path[0]
        elif key == 'shortest_path':
            return self.shortest_path
        elif 'feature_' in key:
            feature_id = int(key.split('_')[1])
            return self.additional_features[feature_id]
        else:
            print 'UNKNOWN FEATURE: %s' % key

    def __str__(self):
        return "{path} - {destination} - {prefix} - {size} - {sp}".format(path=" -> ".join(self.path),
                                                                   destination=self.destination,
                                                                   prefix=self.prefix,
                                                                   size=self.traffic_size,
                                                                    sp=self.shortest_path)

    def __repr__(self):
        return self.__str__()



def compass(paths, features, k = 4, t = 100):
    print "running compass on {} paths with features {}".format(len(paths), str(features))

    import time
    start = time.time()


    count = {}
    for f in features:
        count[f] = {}
        for p in paths:
            v = p.get(f)
            # even if v is None we want to keep it
            if v not in count[f].keys():
                count[f][v] = set()
            count[f][v].add(p)
    S = []
    L = []
    Q = set(features)


    while len(S) < k:
        print "so far S is", S, " Q is ", Q
        best_f = None
        best_v = None
        for f in Q:
            for v in count[f].keys():
                if not v:
                    continue
                if not best_f or len(count[f][v]) > len(count[best_f][best_v]):
                    best_f,best_v = f,v

        if not best_f:
            break

        if not best_v:
            assert False

        print "best feature is", best_f, "best values is", best_v, "with ",len(count[best_f][best_v]), "paths"

        #for p in count[best_f][best_v]:
        #    print p

        L.append((best_f, best_v))
        Q.remove(best_f)

        for worse_v in count[best_f].keys():
            if worse_v != best_v:
                for p in count[best_f][worse_v]:
                    for f in Q:
                        v = p.get(f)
                        # should not remove paths from None value (that is equivalent to wildcard)
                        if v:
                            count[f][v].remove(p)

        if len(L) == t:
            S.append(list(L))
            break

        # check if we can expand the current specification without any changes to the satisfying paths
        removable = set()
        for f in Q:
            for v in count[f].keys():
                if v: #ignore None
                    if count[f][v] == count[best_f][best_v]:
                        print "adding", f,v
                        L.append((f,v))
                        removable.add(f)
                        break
            if len(L) == t:
                S.append(list(L))
                break

        for f in removable:
            Q.remove(f)

        S.append(list(L))

    print "S is ", S

    print ">time", time.time() - start

    return S



def load_example(topo_path, data_path):

    # read data from file
    with open(data_path, 'r') as infile:
        data = pickle.load(infile)

    destination_to_prefix = data['destination_to_prefix']
    prefix_to_destination = data['prefix_to_destination']

    node_to_name = data['node_to_name']
    name_to_node = data['name_to_node']

    # topology
    topo = nx.read_gpickle(topo_path)

    paths = list()
    for path in data['paths']:
        shortest_path = True#len(path[0]) <= len(nx.shortest_path(topo, source=path[0][0], target=path[0][-1]))
        paths.append(NDBEntry(path[0], path[1], path[2], shortest_path, path[4], path[3]))

    return paths, topo, destination_to_prefix, prefix_to_destination, node_to_name, name_to_node


def main(example_path):
    topo_file = "ndb_topo.out"
    data_file = "ndb_dump.out"
    config_file = "config.json"

    topo_path = os.path.join(example_path, topo_file)
    data_path = os.path.join(example_path, data_file)
    config_path = os.path.join(example_path, config_file)

    paths, topo, dest_to_prefix, prefix_to_dest, node_to_name, name_to_node = load_example(topo_path, data_path)

    output = "Successfully read the example files.\n"
    output += "There is a total of {} flows in a topology".format(len(paths))
    #output += "There is a total of {} flows in a topology with {} nodes and {} edges.\n\n".format(len(paths),
    #                                                                                              len(topo.nodes()),
    #                                                                                              len(topo.edges()))
    output += "This is a random flow: {}".format(random.choice(paths))

    print output

    with open(config_path) as f:
        config = json.load(f)

    #compass(paths, config["features"])
    compass(paths, ["ingress", "egress", "destination"])







if __name__ == "__main__":
    #parser = argparse.ArgumentParser()
    #parser.add_argument('path', help='path to the directory containing the example', type=str)
    #parsed_args = parser.parse_args()

    #main(parsed_args.path)
    main("examples/att_na_10")

