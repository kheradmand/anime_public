__author__ = "Ali Kheradmand"
__email__ =  "kheradm2@illinois.edu"

"""
    Various clustering algorithms
"""


import math
import time
import random
import heapq

class Clustering(object):
    pass

plot = False
class GreedyCostBasedClustering(Clustering):
    def __init__(self, cluster_count):
        self.cluster_count = cluster_count
        self.clusters = []
        self.parents = []

    def cluster(self, flows, feature, b = 1000, callback = None):
        flow_labeling = feature.labeling

        if b == 0:
            b = len(flows)

        self.clusters = [flow_labeling.join(flow, flow) for flow in flows]
        self.parents = range(len(self.clusters))
        print "added initial clusters"
        heap = []
        overall_cost = sum([c.cost for c in self.clusters])

        start = time.time()

        for i in range(len(self.clusters)):
            print i
            if len(self.clusters) - i <= b:
                batch = range(i + 1, len(self.clusters))
            else:
                batch = [random.randint(i+1,len(self.clusters)-1) for x in range(b)]

            for j in batch:
                spec = flow_labeling.join(self.clusters[i].value, self.clusters[j].value)
                delta = spec.cost - self.clusters[i].cost - self.clusters[j].cost
                heapq.heappush(heap, (delta, spec, (i, j)))

        remaining_clusters = set(range(len(flows)))

        res = []
        res.append((len(remaining_clusters), overall_cost, time.time() - start))
        print "--->", res[-1]

        if callback:
            callback(self, remaining_clusters)

        while len(remaining_clusters) > self.cluster_count:
            print "number of clusters so far", len(remaining_clusters)

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
            print "final best delta is ", best_delta, best_new_cluster, \
                  "with cluster id ", new_cluster_id, " by merging ", \
                  best_clusters_to_merge, \
                  self.clusters[best_clusters_to_merge[0]], self.clusters[best_clusters_to_merge[1]]

            overall_cost += best_delta

            self.clusters.append(best_new_cluster)
            remaining_clusters -= set([best_clusters_to_merge[0], best_clusters_to_merge[1]])

            self.parents.append(new_cluster_id)
            self.parents[best_clusters_to_merge[0]] = new_cluster_id
            self.parents[best_clusters_to_merge[1]] = new_cluster_id


            cost_sanity_check = self.clusters[new_cluster_id].cost

            while True:
                subsumed = set()
                if len(remaining_clusters) <= b:
                    # just go through everything
                    batch = remaining_clusters
                else:
                    # sample a random batch
                    batch = set()

                    # choosing the more efficient way of sampling:
                    if (float(len(self.clusters)) / len(remaining_clusters)) * b < len(remaining_clusters):
                        while len(batch) < b:
                            r = random.randint(0,len(self.clusters)-1)
                            if r in remaining_clusters:
                                batch.add(r)
                    else:
                        batch = set(random.sample(remaining_clusters, b))
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

                remaining_clusters -= subsumed
                for c in subsumed:
                    self.parents[c] = new_cluster_id
                if b >= len(remaining_clusters) + len(subsumed) or len(subsumed) < len(batch):
                    break
                else:
                    print "all batch subsumed, using new batch"
            remaining_clusters.add(new_cluster_id)

            if b == len(flows):
                pass
                #assert(cost_sanity_check - overall_cost < 1e-10)
            print "cumulative cost is", overall_cost
            res.append((len(remaining_clusters), overall_cost, time.time()-start))
            print "--->", res[-1]

            if callback:
                callback(self, remaining_clusters)

        print "final clusters"
        for c in remaining_clusters:
            print self.clusters[c]

        print ">time", time.time()-start

        with open("result.csv",'w') as f:
            f.write("k,score,time\n")
            for r in res:
                f.write(",".join(map(str, list(r)))+"\n")

        if plot:
            import matplotlib.pyplot as plt
            #plt.plot([x[0] for x in res], [x[1] for x in res])
            #plt.plot([x[0] for x in res], [math.log(x[1]) for x in res], '--bo')
            plt.plot([x[0] for x in res], [float(len(flows)) / x[1] for x in res], '--bo')
            plt.title("cost")
            plt.show()

            plt.plot([x[0] for x in res], [x[2] for x in res], '--bo')
            plt.title("time")
            plt.show()


        return [self.clusters[c] for c in remaining_clusters]



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