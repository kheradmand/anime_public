__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Various clustering algorithms
"""


import math
import time
import random
import heapq
import logging
import pickle

class Clustering(object):
    pass

plot = False


class GreedyCostBasedClustering(Clustering):
    def __init__(self, cluster_count=1, batch_size=0):
        self.cluster_count = cluster_count
        self.batch_size = batch_size

        self.clusters = []
        self.parents = []
        self.stats = []

    def cluster(self, flows, feature, callback=None):
        flow_labeling = feature.labeling

        batch_size = self.batch_size
        if batch_size == 0:
            batch_size = len(flows)

        self.clusters = [flow_labeling.join(flow, flow) for flow in flows]
        self.parents = range(len(self.clusters))

        logging.debug("Initial clusters added")

        heap = []
        overall_cost = sum([c.cost for c in self.clusters])

        start = time.time()

        # initial distances
        for i in range(len(self.clusters)):
            logging.debug("Adding distances for cluster %s", i)

            if len(self.clusters) - i <= batch_size:
                batch = range(i + 1, len(self.clusters))
            else:
                batch = [random.randint(i+1,len(self.clusters)-1) for x in range(batch_size)]

            for j in batch:
                spec = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
                delta = spec.cost - self.clusters[i].cost - self.clusters[j].cost
                heapq.heappush(heap, (delta, spec, (i, j)))

        remaining_clusters = set(range(len(flows)))

        self.stats = []
        self.stats.append((len(remaining_clusters), overall_cost, time.time() - start))
        logging.debug(self.stats[-1])

        if callback:
            callback(self, remaining_clusters)

        while len(remaining_clusters) > self.cluster_count:
            logging.debug("Number of clusters so far %s", len(remaining_clusters))

            best = None
            while True:
                candidate = heapq.heappop(heap)

                #print candidate
                if candidate[2][0] in remaining_clusters and candidate[2][1] in remaining_clusters:
                    best = candidate
                    break

            assert best is not None

            new_cluster_id = len(self.clusters)
            best_clusters_to_merge = best[2]
            best_new_cluster = best[1]
            best_delta = best[0]
            logging.debug("Final best delta is %s %s with cluster id %s by merging %s %s %s",
                         best_delta, best_new_cluster, new_cluster_id, best_clusters_to_merge,
                         self.clusters[best_clusters_to_merge[0]], self.clusters[best_clusters_to_merge[1]])

            overall_cost += best_delta

            self.clusters.append(best_new_cluster)
            remaining_clusters -= set([best_clusters_to_merge[0], best_clusters_to_merge[1]])

            self.parents.append(new_cluster_id)
            self.parents[best_clusters_to_merge[0]] = new_cluster_id
            self.parents[best_clusters_to_merge[1]] = new_cluster_id


            cost_sanity_check = self.clusters[new_cluster_id].cost

            while True:
                subsumed = set()

                # choosing the batch to go through
                if len(remaining_clusters) <= batch_size:
                    # just go through everything
                    batch = remaining_clusters
                else:
                    # sample a random batch
                    batch = set()

                    # choosing the more efficient way of sampling:
                    if (float(len(self.clusters)) / len(remaining_clusters)) * batch_size < len(remaining_clusters):
                        while len(batch) < batch_size:
                            r = random.randint(0,len(self.clusters)-1)
                            if r in remaining_clusters:
                                batch.add(r)
                    else:
                        batch = set(random.sample(remaining_clusters, batch_size))

                # now going through the batch
                for c in batch:
                    if flow_labeling.subset(self.clusters[c].value, self.clusters[new_cluster_id].value):
                        subsumed.add(c)
                        print new_cluster_id, self.clusters[new_cluster_id].value, "subsuming ", c, ":", self.clusters[c]
                        overall_cost -= self.clusters[c].cost
                    else:
                        cost_sanity_check += self.clusters[c].cost
                        spec = flow_labeling.join(self.clusters[c].value, self.clusters[new_cluster_id].value)

                        delta = spec.cost - self.clusters[c].cost - self.clusters[new_cluster_id].cost
                        heapq.heappush(heap, (delta, spec, (c, new_cluster_id)))

                # remove subsumed clusters
                remaining_clusters -= subsumed
                for c in subsumed:
                    self.parents[c] = new_cluster_id

                if batch_size >= len(remaining_clusters) + len(subsumed) or len(subsumed) < len(batch):
                    break
                else:
                    logging.warning("All batch subsumed, using new batch")

            remaining_clusters.add(new_cluster_id)

            if batch_size == len(flows):
                pass
                #assert(cost_sanity_check - overall_cost < 1e-10)

            self.stats.append((len(remaining_clusters), overall_cost, time.time() - start))
            logging.debug("Cumulative cost is %s", overall_cost)
            logging.debug(self.stats[-1])

            if callback:
                callback(self, remaining_clusters)

        # clustering is done
        logging.info("Clustering is finished")
        logging.info(">time %s", str(time.time()-start))

        # self.store_stats_csv()
        if plot:
            self.plot_stats(sum((x.cost for x in self.clusters[:len(flows)])))

        return [self.clusters[c] for c in remaining_clusters]

    def plot_stats(self, tp):
        if plot:
            import matplotlib.pyplot as plt
            #plt.plot([x[0] for x in res], [x[1] for x in res])
            #plt.plot([x[0] for x in res], [math.log(x[1]) for x in res], '--bo')
            plt.plot([x[0] for x in self.stats], [float(tp) / x[1] for x in self.stats], '--bo')
            plt.title("cost")
            plt.show()

            plt.plot([x[0] for x in self.stats], [x[2] for x in self.stats], '--bo')
            plt.title("time")
            plt.show()

    def store_stats_csv(self, dir="./"):
        with open(dir + "/stats.csv",'w') as f:
            f.write("k,score,time\n")
            for r in self.stats:
                f.write(",".join(map(str, list(r)))+"\n")

    def store_internals_pk(self, dir="./", stats=True, clusters=True, parents=True):
        if clusters:
            logging.info("Started saving clusters")
            with open(dir + "/clusters.pk", 'w') as f:
                pickle.dump(self.clusters, f)
            logging.info("Finished saving clusters")

        if parents:
            with open(dir + "/parents.pk", 'w') as f:
                pickle.dump(self.parents, f)

        if stats:
            with open(dir + "/stats.pk", 'w') as f:
                pickle.dump(self.stats, f)

    def store_cluster_hierarchy_xml(self, dir="./"):
        children = [[] for c in range(len(self.clusters))]
        roots = []
        for c, p in enumerate(self.parents):
            if c == p:
                roots.append(c)
            else:
                children[p].append(c)

        def writeXML(f, n):
            f.write("<cluster id=\"%d\" value=\"%s\">\n" % (n, self.clusters[n]))
            for c in children[n]:
                writeXML(f, c)
            f.write("</cluster>\n")

        with open(dir + "cluster_hierarchy.xml", 'w') as f:
            for n in roots:
                writeXML(f, n)




# depricated
class MDSClustering(Clustering):
    def __init__(self, cluster_count):
        self.cluster_count = cluster_count

    def cluster(self, flows, features):
        from sklearn.manifold import MDS
        from sklearn.cluster import KMeans

        flow_labeling = FlowLabeling(features)

        import time
        start = time.time()
        dist = [[flow_labeling.join(f1,f2).cost for f2 in flows] for f1 in flows]

        import matplotlib.pyplot as plt
        print dist
        plt.imshow(dist, zorder=2, cmap='Blues', interpolation='nearest')
        plt.colorbar()
        plt.show()


        model = MDS(n_components=2, dissimilarity='precomputed', random_state=2)
        out = model.fit_transform(dist)

        clusters = KMeans(n_clusters=self.cluster_count, random_state=0).fit(dist)


        cls = {}
        for i,c in enumerate(clusters.labels_):
            if c not in cls.keys():
                cls[c] = [i]
            else:
                cls[c] += [i]

        for k,v in cls.iteritems():
            spec = flow_labeling.join(flows[v[0]], flows[v[0]])
            #print "-", spec, flows[v[0]]
            for i in range(1,len(v)):
                spec = flow_labeling.join(spec.value, flows[v[i]])
                #print "-", spec, flows[v[i]]
            print "------",spec


        plt.scatter(out[:, 0], out[:, 1], c=clusters.labels_)
        plt.xlim(right=200)
        for i,f in enumerate(flows):
            plt.annotate(str(f),[out[i,0],out[i,1]], fontsize=5)

        plt.show()