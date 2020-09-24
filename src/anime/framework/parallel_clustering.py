__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    (work in progress) Various parallel clustering algorithms
"""


import math
import time
import random
import heapq
import logging
import pickle
import sys
from multiprocessing import Pool
import ray

from .actor_pool import *
from .clustering import *
from .index import *
from .ip_labeling import *
from .labeling import *


@ray.remote
class ClustersShard(object):
    def __init__(self, feature, start_index, clusters, closest_clusters_bucket_size, max_shard_size):
        self.start_index = start_index
        self.clusters = clusters
        self.feature = feature
        self.closets_clusters = [[]] * len(clusters)
        self.closets_clusters_bucket_size = closest_clusters_bucket_size
        self.max_shard_size = max_shard_size

    def add_cluster(self, cluster):
        assert len(self.clusters) < self.max_shard_size
        self.clusters.append(cluster)
        self.closets_clusters.append([])

    def get_global_index(self, index):
        return index + self.start_index

    def compute_closest_clusters(self, c_index, cluster, check_subsumption=False, update_other=True):
        subsumed = []
        batch = range(self.clusters)
        closets_clusters = []
        for local_index in batch:
                global_index = self.get_global_index(local_index)
                if check_subsumption and feature.labeling.subset(self.clusters[local_index].value, cluster.value):
                    subsumed.append(self.global_index(local_index))
                    logging.info("%s %s subsuming %s : %s", c_index, cluster, global_index, self.clusters[local_index])
                    #overall_cost -= self.clusters[c].cost
                else:
                    spec = feature.labeling.join(cluster.value, self.clusters[local_index].value)
                    distance = self.distance_measure(cluster, self.clusters[local_index], spec)

                    closest_clusters = sorted(closest_clusters + [(distance, spec, (c_index, global_index))]) \
                        [:self.closest_clusters_bucket_size]

                    if update_other:
                        self.closest_clusters[local_index] = \
                            sorted(self.closest_clusters[local_index] + [(distance, spec, (global_index, c_index))]) \
                            [:self.closest_clusters_bucket_size]

        return closets_clusters, subsumed

    def update_closest_clusters(self, closest_clusters):
        self.closets_clusters()

    def get_closest_cluster(c, recompute_if_empty=False):
        assert c in remaining_clusters
        while len(self.closest_clusters[c]) > 0:
            if self.closest_clusters[c][0][2][1] in remaining_clusters:
                return self.closest_clusters[c][0]
            else:
                self.closest_clusters[c] = self.closest_clusters[c][1:]

        if recompute_if_empty and len(self.closest_clusters[c]) == 0:
            update_closest_clusters(c, get_batch() - set([c]), check_subsumption=False, update_other=False)
            self.closest_clusters_recomputations.append(len(remaining_clusters))
            return get_closest_cluster(c)
        else:
            return None


class ShardManager(object):
    def __init__(self, feature, flows):
        pass

    def update_closest_clusters(self, c, check_subsumption=False, update_other=True):
        pass

    def get_closest_cluster(self, c):
        pass

    def add_cluster(self, c):
        pass



# if __name__ == "__main__":
#     from .labeling import *
#     import netaddr
#     ray.init()
#     feature = Feature('tuple', TupleLabeling(
#         [Feature('src', DValueLabeling(3)), Feature('dst', DValueLabeling(3))]))
#
#     s1 = ClustersShard.remote(feature, 0, [(netaddr.IPNetwork('192.168.1.0/24'), 'A')])
#     s2 = ClustersShard.remote(feature, 1, [(netaddr.IPNetwork('192.168.0.0/24'), 'B')])


@ray.remote
class IndexLookupWorker(object):
    def __init__(self, index_id):
        logging.basicConfig(format='%(asctime)s-%(process)d-%(processName)s-%(levelname)s: %(message)s', level=logging.DEBUG)
        logging.info("Getting the index")
        start = time.time()
        logging.info(index_id)
        self.index = index_id
        logging.info("Finished getting the index in %s seconds", time.time() - start)

    def get_closest_cluster(self, c, cluster):
        res = self.index.get_knn_approx(cluster)
        # res = index.get_knn_precise(self.clusters[c])
        if len(res) < 2:
            assert res[0][2][1] == c
            return c, None
        elif res[0][2][1] == c:
            return c, res[1][2][1]
        else:
            logging.warning("The first item of nearest neighbors isn't the cluster itself %s", res)
            assert res[1][2][1] == c
            return c, res[0][2][1]


# class MP(object):
#     index = None
#
#     @staticmethod
#     def get_closets_cluster(c, cluster):
#         res = MP.index.get_knn_approx(cluster)
#         # res = index.get_knn_precise(self.clusters[c])
#         if len(res) < 2:
#             assert res[0][2][1] == c
#             return c, None
#         elif res[0][2][1] == c:
#             return c, res[1][2][1]
#         else:
#             logging.warning("The first item of nearest neighbors isn't the cluster itself %s", res)
#             assert res[1][2][1] == c
#             return c, res[0][2][1]
mp_index = None
def mp_get_closets_cluster(c_cluster):
    c, cluster = c_cluster
    res = mp_index.get_knn_approx(cluster)
    # res = index.get_knn_precise(self.clusters[c])
    if len(res) < 2:
        assert res[0][2][1] == c
        return c, None
    elif res[0][2][1] == c:
        return c, res[1][2][1]
    else:
        logging.warning("The first item of nearest neighbors isn't the cluster itself %s", res)
        assert res[1][2][1] == c
        return c, res[0][2][1]

class ParallelHierarchicalClusteringWithIndex(HierarchicalClustering):

    def cluster(self, flows, feature, callback=None, processes=4):
        flow_labeling = feature.labeling

        batch_size = self.batch_size
        if batch_size == 0:
            batch_size = len(flows)

        self.clusters = [flow_labeling.join(flow, flow) for flow in flows]
        self.parents = list(range(len(self.clusters)))
        self.closest_clusters = [[]] * len(self.clusters)

        logging.info("Initial clusters added")

        heap = []
        overall_cost = sum([c.cost for c in self.clusters])

        start = time.time()

        remaining_clusters = set(range(len(flows)))

        index = RTreeIndex(feature)

        logging.info("Indexing flows")

        for i in range(len(self.clusters)):
            index.insert(self.clusters[i], i)

        logging.info("Finished indexing flows in %s seconds", time.time() - start)


        # for i in range(len(self.clusters)):
        #     logging.info("Adding distances for cluster %s", i)
        #
        #     j = get_closest_cluster(i)
        #     joined = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
        #     dist = cost_gain_distance(self.clusters[i], self.clusters[j], joined)
        #     heapq.heappush(heap, (dist, joined, (i, j)))


        # ray.init(num_cpus=processes)
        #
        # timer_start = time.time()
        # logging.info("Putting index in the object store")
        # index_id = ray.put(index)
        # logging.info("Finished putting index in the object store in %s seconds", time.time() - timer_start)
        #
        # timer_start = time.time()
        # logging.info("Initializing workers")
        # workers = [IndexLookupWorker.remote(index_id) for i in range(processes)]
        # pool = ActorPool(workers)
        # logging.info("Finished initializing workers in %s seconds", time.time() - timer_start)
        #
        # timer_start = time.time()
        # ctr = 0
        # timer_start = time.time()
        # for i in range(len(self.clusters)):
        #     pool.submit(lambda a,c: a.get_closest_cluster.remote(c, self.clusters[c]), i)
        # while pool.has_next():
        #     ctr += 1
        #     i, j = pool.get_next_unordered()
        #     logging.info("Adding distances for cluster %s (%s)", i, ctr)
        #     joined = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
        #     dist = cost_gain_distance(self.clusters[i], self.clusters[j], joined)
        #     heapq.heappush(heap, (dist, joined, (i, j)))
        # logging.info("Finished adding closest clusters for initial clusters in %s seconds", time.time() - timer_start)
        #
        # ray.shutdown()

        timer_start = time.time()
        global mp_index
        mp_index = index
        pool = Pool(4)
        it = pool.imap_unordered(mp_get_closets_cluster, [(c,self.clusters[c]) for c in range(len(self.clusters))])
        ctr = 0
        for i,j in it:
            ctr += 1
            logging.info("Adding distances for cluster %s (%s)", i, ctr)
            joined = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
            dist = cost_gain_distance(self.clusters[i], self.clusters[j], joined)
            heapq.heappush(heap, (dist, joined, (i, j)))
        pool.close()
        logging.info("Finished adding closest clusters for initial clusters in %s seconds",
                         time.time() - timer_start)


        def get_closest_cluster(c):
            res = index.get_knn_approx(self.clusters[c])
            #res = index.get_knn_precise(self.clusters[c])

            if len(res) < 2:
                assert res[0][2][1] == c
                return None
            elif res[0][2][1] == c:
                return res[1][2][1]
            else:
                logging.warning("The first item of nearest neighbors isn't the cluster itself %s", res)
                assert res[1][2][1] == c
                return res[0][2][1]

            # assert res[0][2][1] == c
            # return None if len(res) < 2 else res[1][2][1]

        self.stats.append((len(remaining_clusters), overall_cost, time.time() - start))
        logging.info(self.stats[-1])

        self.intents.append(IncrementalIntentInfo(len(remaining_clusters), list(remaining_clusters), []))
        if callback:
            callback(self, remaining_clusters)

        while len(remaining_clusters) > self.cluster_count:
            logging.info("Number of clusters so far %s", len(remaining_clusters))

            removed = []

            best = None
            while True:

                candidate = heapq.heappop(heap)
                c_1, c_2 = candidate[2]

                if c_1 in remaining_clusters:
                    if c_2 in remaining_clusters:
                        best = candidate
                        break
                    else:
                        j = get_closest_cluster(c_1)
                        joined = flow_labeling.join(self.clusters[c_1].value, self.clusters[j].value)
                        dist = cost_gain_distance(self.clusters[c_1], self.clusters[j], joined)
                        heapq.heappush(heap, (dist, joined, (c_1, j)))
                else:
                    if c_2 in remaining_clusters:
                        j = get_closest_cluster(c_2)
                        joined = flow_labeling.join(self.clusters[c_2].value, self.clusters[j].value)
                        dist = cost_gain_distance(self.clusters[c_2], self.clusters[j], joined)
                        heapq.heappush(heap, (dist, joined, (c_2, j)))

            assert best is not None

            new_cluster_id = len(self.clusters)
            best_clusters_to_merge = best[2]
            best_new_cluster = best[1]
            best_distance = best[0]
            logging.info("Final best distance is %s %s with cluster id %s by merging %s %s %s",
                         best_distance, best_new_cluster, new_cluster_id, best_clusters_to_merge,
                         self.clusters[best_clusters_to_merge[0]], self.clusters[best_clusters_to_merge[1]])

            overall_cost += best_distance

            self.clusters.append(best_new_cluster)
            remaining_clusters -= set([best_clusters_to_merge[0], best_clusters_to_merge[1]])
            # removed += best_clusters_to_merge # will automatically happen when removing subsumed clusters


            self.closest_clusters.append([])

            self.parents.append(new_cluster_id)
            # self.parents[best_clusters_to_merge[0]] = new_cluster_id
            # self.parents[best_clusters_to_merge[1]] = new_cluster_id

            cost_sanity_check = self.clusters[new_cluster_id].cost

            subsumed = index.get_subsets(best_new_cluster)
            subsumed = [x[1] for x in subsumed]
            index.remove_subset(best_new_cluster)

            # remove subsumed clusters
            overall_cost -= sum([self.clusters[c].cost for c in subsumed])
            removed += subsumed
            remaining_clusters -= set(subsumed)

            for c in subsumed:
                logging.info("subsumed %s", self.clusters[c])
                self.parents[c] = new_cluster_id

            min_dist = None

            remaining_clusters.add(new_cluster_id)

            index.insert(best_new_cluster, new_cluster_id)

            if len(remaining_clusters) > 1:
                j = get_closest_cluster(new_cluster_id)
                joined = flow_labeling.join(self.clusters[new_cluster_id].value, self.clusters[j].value)
                dist = cost_gain_distance(self.clusters[new_cluster_id], self.clusters[j], joined)
                heapq.heappush(heap, (dist, joined, (new_cluster_id, j)))

            self.stats.append((len(remaining_clusters), overall_cost, time.time() - start))
            logging.info("Cumulative cost is %s", overall_cost)
            logging.info(self.stats[-1])

            self.intents.append(IncrementalIntentInfo(len(remaining_clusters), [new_cluster_id], removed))
            if callback:
                callback(self, remaining_clusters)

        # clustering is done
        logging.info("Clustering is finished")
        logging.info(">time %s", str(time.time() - start))
        logging.info(">recounts %s", len(self.closest_clusters_recomputations))
        # self.store_stats_csv()
        if plot:
            self.plot_stats(sum((x.cost for x in self.clusters[:len(flows)])))

        return [self.clusters[c] for c in remaining_clusters]











































            #
    # def update_closest_clusters(i, check_subsumption=False, update_other=True):
    #     subsumed = []
    #     for j in batch:
    #         if check_subsumption and flow_labeling.subset(self.clusters[j].value, self.clusters[i].value):
    #             subsumed.append(j)
    #             logging.info("%s %s subsuming %s : %s", i, self.clusters[i].value, j, self.clusters[j])
    #             #overall_cost -= self.clusters[c].cost
    #         else:
    #             spec = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
    #             distance = self.distance_measure(self.clusters[i], self.clusters[j], spec)
    #
    #             self.closest_clusters[i] = sorted(self.closest_clusters[i] + [(distance, spec, (i, j))]) \
    #                 [:self.closest_clusters_bucket_size]
    #
    #             if update_other:
    #                 self.closest_clusters[j] = sorted(self.closest_clusters[j] + [(distance, spec, (j, i))]) \
    #                     [:self.closest_clusters_bucket_size]


# class ParallelHierarchicalClustering(Clustering):
#     def __init__(self, cluster_count=1, batch_size=0, distance_measure=cost_gain_distance,
#                  closest_clusters_bucket_size=3):
#         self.cluster_count = cluster_count
#         self.batch_size = batch_size
#         self.distance_measure = distance_measure
#         self.closest_clusters_bucket_size = closest_clusters_bucket_size
#
#         self.clusters = []
#         self.parents = []
#         self.stats = []
#
#         # optimization: keep only a few closets clusters per cluster rather than distance to all clusters,
#         # recompute the rest only when necessary
#         self.closest_clusters = []
#
#         # places where recount happened
#         self.closest_clusters_recomputations = []
#
#     def cluster(self, flows, feature, callback=None):
#         flow_labeling = feature.labeling
#
#         batch_size = self.batch_size
#         if batch_size == 0:
#             batch_size = len(flows)
#
#         self.clusters = [flow_labeling.join(flow, flow) for flow in flows]
#         self.parents = range(len(self.clusters))
#         self.closest_clusters = [[]] * len(self.clusters)
#
#         logging.info("Initial clusters added")
#
#         heap = []
#         overall_cost = sum([c.cost for c in self.clusters])
#
#         start = time.time()
#
#         def update_closest_clusters(i, batch, check_subsumption=False, update_other=True):
#             subsumed = []
#             for j in batch:
#                 if check_subsumption and flow_labeling.subset(self.clusters[j].value, self.clusters[i].value):
#                     subsumed.append(j)
#                     logging.info("%s %s subsuming %s : %s", i, self.clusters[i].value, j, self.clusters[j])
#                     #overall_cost -= self.clusters[c].cost
#                 else:
#                     spec = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
#                     distance = self.distance_measure(self.clusters[i], self.clusters[j], spec)
#
#                     self.closest_clusters[i] = sorted(self.closest_clusters[i] + [(distance, spec, (i, j))]) \
#                         [:self.closest_clusters_bucket_size]
#
#                     if update_other:
#                         self.closest_clusters[j] = sorted(self.closest_clusters[j] + [(distance, spec, (j, i))]) \
#                             [:self.closest_clusters_bucket_size]
#
#             return subsumed
#
#         def get_batch():
#             if len(remaining_clusters) <= batch_size:
#                 # just go through everything
#                 batch = remaining_clusters
#             else:
#                 # sample a random batch
#                 batch = set()
#
#                 # choosing the more efficient way of sampling:
#                 if (float(len(self.clusters)) / len(remaining_clusters)) * batch_size < len(remaining_clusters):
#                     while len(batch) < batch_size:
#                         r = random.randint(0, len(self.clusters) - 1)
#                         if r in remaining_clusters:
#                             batch.add(r)
#                 else:
#                     batch = set(random.sample(remaining_clusters, batch_size))
#
#             return batch
#
#         def get_closest_cluster(c, recompute_if_empty=False):
#             assert c in remaining_clusters
#             while len(self.closest_clusters[c]) > 0:
#                 if self.closest_clusters[c][0][2][1] in remaining_clusters:
#                     return self.closest_clusters[c][0]
#                 else:
#                     self.closest_clusters[c] = self.closest_clusters[c][1:]
#
#             if recompute_if_empty and len(self.closest_clusters[c]) == 0:
#                 update_closest_clusters(c, get_batch() - set([c]), check_subsumption=False, update_other=False)
#                 self.closest_clusters_recomputations.append(len(remaining_clusters))
#                 return get_closest_cluster(c)
#             else:
#                 return None
#
#             # all closes clusters consumed
#
#
#
#         remaining_clusters = set(range(len(flows)))
#
#         # initial distances
#         for i in range(len(self.clusters)):
#             logging.info("Adding distances for cluster %s", i)
#
#             if len(self.clusters) - i <= batch_size:
#                 batch = range(i + 1, len(self.clusters))
#             else:
#                 batch = [random.randint(i+1,len(self.clusters)-1) for x in range(batch_size)]
#
#             update_closest_clusters(i, batch)
#             min_dist = get_closest_cluster(i)
#             if min_dist:
#                 heapq.heappush(heap, min_dist)
#
#
#         self.stats = []
#         self.stats.append((len(remaining_clusters), overall_cost, time.time() - start))
#         logging.info(self.stats[-1])
#
#         if callback:
#             callback(self, remaining_clusters)
#
#         while len(remaining_clusters) > self.cluster_count:
#             logging.info("Number of clusters so far %s", len(remaining_clusters))
#
#             best = None
#             while True:
#
#                 candidate = heapq.heappop(heap)
#                 c_1, c_2 = candidate[2]
#
#                 if c_1 in remaining_clusters:
#                     if c_2 in remaining_clusters:
#                         best = candidate
#                         break
#                     else:
#                         min_dist = get_closest_cluster(c_1, recompute_if_empty=True)
#                         if min_dist:
#                             heapq.heappush(heap, min_dist)
#                 else:
#                     if c_2 in remaining_clusters:
#                         min_dist = get_closest_cluster(c_2, recompute_if_empty=True)
#                         if min_dist:
#                             heapq.heappush(heap, min_dist)
#
#             assert best is not None
#
#             new_cluster_id = len(self.clusters)
#             best_clusters_to_merge = best[2]
#             best_new_cluster = best[1]
#             best_distance = best[0]
#             logging.info("Final best distance is %s %s with cluster id %s by merging %s %s %s",
#                          best_distance, best_new_cluster, new_cluster_id, best_clusters_to_merge,
#                          self.clusters[best_clusters_to_merge[0]], self.clusters[best_clusters_to_merge[1]])
#
#             overall_cost += best_distance
#
#             self.clusters.append(best_new_cluster)
#             remaining_clusters -= set([best_clusters_to_merge[0], best_clusters_to_merge[1]])
#
#             self.closest_clusters.append([])
#
#             self.parents.append(new_cluster_id)
#             self.parents[best_clusters_to_merge[0]] = new_cluster_id
#             self.parents[best_clusters_to_merge[1]] = new_cluster_id
#
#             cost_sanity_check = self.clusters[new_cluster_id].cost
#
#             min_dist = None
#             while True:
#                 # choosing the batch to go through
#                 batch = get_batch()
#
#                 # now going through the batch
#                 subsumed = update_closest_clusters(new_cluster_id, batch, check_subsumption=True, update_other=True)
#
#                 # remove subsumed clusters
#                 overall_cost -= sum([self.clusters[c].cost for c in subsumed])
#                 remaining_clusters -= set(subsumed)
#
#                 for c in subsumed:
#                     self.parents[c] = new_cluster_id
#
#                 if batch_size >= len(remaining_clusters) + len(subsumed) or len(subsumed) < len(batch):
#                     break
#                 else:
#                     # no problem in case of computing closets clusters,
#                     # there will be no duplicates because that function is called again for a new batch
#                     # only if the previous batch is completely subsumed
#                     logging.warning("All batch subsumed, using new batch")
#
#             remaining_clusters.add(new_cluster_id)
#
#             min_dist = get_closest_cluster(new_cluster_id)
#             if min_dist:
#                 heapq.heappush(heap, min_dist)
#
#             if batch_size == len(flows):
#                 pass
#                 #assert(cost_sanity_check - overall_cost < 1e-10)
#
#             self.stats.append((len(remaining_clusters), overall_cost, time.time() - start))
#             logging.info("Cumulative cost is %s", overall_cost)
#             logging.info(self.stats[-1])
#
#             if callback:
#                 callback(self, remaining_clusters)
#
#         # clustering is done
#         logging.info("Clustering is finished")
#         logging.info(">time %s", str(time.time()-start))
#         logging.info(">recounts %s", len(self.closest_clusters_recomputations))
#         # self.store_stats_csv()
#         if plot:
#             self.plot_stats(sum((x.cost for x in self.clusters[:len(flows)])))
#
#         return [self.clusters[c] for c in remaining_clusters]
#
#     def plot_stats(self, tp):
#         if plot:
#             import matplotlib.pyplot as plt
#             #plt.plot([x[0] for x in res], [x[1] for x in res])
#             #plt.plot([x[0] for x in res], [math.log(x[1]) for x in res], '--bo')
#             plt.plot([x[0] for x in self.stats], [float(tp) / x[1] for x in self.stats], '--bo')
#             plt.title("cost")
#             plt.show()
#
#             plt.plot([x[0] for x in self.stats], [x[2] for x in self.stats], '--bo')
#             plt.title("time")
#             plt.show()
#
#     def store_stats_csv(self, dir="./"):
#         with open(dir + "/stats.csv",'w') as f:
#             f.write("k,score,time\n")
#             for r in self.stats:
#                 f.write(",".join(map(str, list(r)))+"\n")
#
#     def store_internals_pk(self, dir="./", stats=True, clusters=True, parents=True):
#         if clusters:
#             logging.info("Started saving clusters")
#             with open(dir + "/clusters.pk", 'w') as f:
#                 pickle.dump(self.clusters, f)
#             logging.info("Finished saving clusters")
#
#         if parents:
#             with open(dir + "/parents.pk", 'w') as f:
#                 pickle.dump(self.parents, f)
#
#         if stats:
#             with open(dir + "/stats.pk", 'w') as f:
#                 pickle.dump(self.stats, f)
#
#         if stats:
#             with open(dir + "/recounts.pk", 'w') as f:
#                 pickle.dump(self.closest_clusters_recomputations, f)
#
#     def store_cluster_hierarchy_xml(self, dir="./"):
#         children = [[] for c in range(len(self.clusters))]
#         roots = []
#         for c, p in enumerate(self.parents):
#             if c == p:
#                 roots.append(c)
#             else:
#                 children[p].append(c)
#
#         def write_xml(f, n):
#             f.write("<cluster id=\"%d\" value=\"%s\">\n" % (n, self.clusters[n]))
#             for c in children[n]:
#                 write_xml(f, c)
#             f.write("</cluster>\n")
#
#         with open(dir + "/cluster_hierarchy.xml", 'w') as f:
#             for n in roots:
#                 write_xml(f, n)


