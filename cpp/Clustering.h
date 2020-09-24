/*
 * Clustering.h
 *
 *  Created on: Aug 28, 2020
 *      Author: Ali Kheradmand (kheradm2@illinos.edu)
 */

#ifndef CLUSTERING_H_
#define CLUSTERING_H_

#include "Args.h"
#include "Timer.h"
#include "Feature.h"
#include "Index.h"
#include <vector>
#include <thread>
#include <optional>
#include <fstream>

#include "ctpl_stl.h"

struct IncClusterInfo {
    int k;
    std::vector<std::size_t> add;
    std::vector<std::size_t> del;
};

struct ClusterInfo {
    int k;
    std::vector<std::size_t> clusters;
};


#define IN_SET(member,set) (set.find(member) != set.end())

template <typename Feature, typename Label>
class HierarchicalClustering {
public:
    std::vector<CostLabel<Label>> clusters;
    std::vector<std::size_t> parents;
    std::vector<std::vector<std::size_t>> children;
    Feature& feature;
public:
    HierarchicalClustering(Feature& _feature) : feature(_feature) {

    }

    Cost cost_gain_distance(const CostLabel<Label>& l1, const CostLabel<Label>& l2, const CostLabel<Label>& joined) {
        return joined.cost - l1.cost - l2.cost;
    }


    const std::vector<CostLabel<Label>>& get_clusters(){
        return clusters;
    }

    const std::vector<std::size_t>& get_parents() {
        return parents;
    }

    const std::vector<std::vector<std::size_t>>& get_children() {
        return children;
    }

    Feature& get_feature() {
        return feature;
    }

    void cluster(const std::vector<Label> flows, int k = 1) {
        if (k == 0)
            k = flows.size();

        std::set<std::size_t> remaining_clusters;

        Timer overall_timer;

        for (auto i = 0; i < flows.size(); i++) {
            clusters.emplace_back(feature.cjoin(flows[i],flows[i]));
            parents.emplace_back(i);
            remaining_clusters.insert(i);
        }

        std::cout << "Init done" << std::endl;
        std::cout << "Indexing started" << std::endl;

        Timer timer;
        RTreeIndex<Feature, CostLabel<Label>, std::size_t> index(feature);

        for (auto i = 0; i < flows.size(); i++) {
            index.insert(clusters[i], i);
        }

        std::cout << "Indexing finished in " << timer << std::endl;

        std::ofstream fout{Args::get().out + "/hr_index.txt"};
        index.print_index(fout);
        fout.close();

//        std::ofstream sout{"index.bin"};
//        index.serialize(sout);
//        sout.close();

        auto get_closest_cluster = [&](std::size_t c) -> std::optional<typename decltype(index)::NNEntry>  {
            const auto res = index.get_knn_approx(clusters[c]);
            if (res.size() < 2) {
                assert(res[0].object->second == c);
                return std::nullopt;
            } else if (res[0].object->second == c) {
                return res[1];
            } else {
                std::cout << "Warning: the first item of nearest neighbors for cluster " << c << " " << clusters[c] << " isn't the cluster itself " << res[0].object->first << " " << res[1].object->first << std::endl;
                assert(res[1].object->second == c);
                return res[0];
            }
        };

        struct Entry {
            Cost dist;
            CostLabel<Label> joined;
            std::size_t i;
            std::size_t j;
        };

        struct EntryCmp {
            bool operator()(const Entry&a, const Entry& b) {
                if (std::abs(a.dist - b.dist) < 1e-10){
                    return a.joined.cost > b.joined.cost;
                } else {
                    return a.dist > b.dist;
                }
            }
        };

        std::priority_queue<Entry, std::vector<Entry>, EntryCmp> pq;


        auto recomute_closest = [&](std::size_t c) {
            const auto closest = get_closest_cluster(c);
            assert(closest.has_value());
            const auto dist = cost_gain_distance(clusters[c], closest->object->first, closest->joined);
            pq.emplace(Entry{dist, closest->joined, c, closest->object->second});
        };

        auto recomute_closest_parallel = [&](int id, std::size_t c, std::mutex& lock) {
            const auto closest = get_closest_cluster(c);
            assert(closest.has_value());
            const auto dist = cost_gain_distance(clusters[c], closest->object->first, closest->joined);
            lock.lock();
            pq.emplace(Entry{dist, closest->joined, c, closest->object->second});
            lock.unlock();
        };

        timer.reset();
        std::cout << "Started adding instances for initial clusters" << std::endl;

        if (not Args::get().multithreaded_init) {
            std::cout << "Single threaded" << std::endl;
            for (auto i = 0; i < flows.size(); i++) {
                recomute_closest(i);

                if (i % 10000 == 0)
                    std::cout << i << std::endl;
            }
        } else {
            const auto threads = Args::get().threads == 0 ? std::thread::hardware_concurrency() :  Args::get().threads;
            std::mutex lock;
            ctpl::thread_pool pool(threads);

            std::cout << "Running with " << threads << " threads" << std::endl;

            std::vector<std::future<void>> futures;
            for (auto i = 0; i < flows.size(); i++) {
                futures.emplace_back(pool.push(recomute_closest_parallel, i, std::ref(lock)));
            }
            auto i = 0;
            for (auto& f : futures) {
                i++;
                f.wait();

                if (i % 10000 == 0)
                    std::cout << i << std::endl;
            }
        }


        std::cout << "Finished adding instances for initial clusters in " << timer << std::endl;

        std::optional<ctpl::thread_pool> pool;
        if (Args::get().multithreaded_index_remove)
            pool.emplace(2);

        while (remaining_clusters.size() > k) {
            std::cout << "Number of clusters so far " << remaining_clusters.size() << std::endl;
//#define PER_CLUSTER_TIME
#ifdef PER_CLUSTER_TIME
            std::cout << "--" << remaining_clusters.size() << "," << overall_timer << std::endl;
#endif

            while (true) {
                int recompute = -1;
                const auto& candid = pq.top();
                if (IN_SET(candid.i, remaining_clusters)) {
                    if IN_SET(candid.j, remaining_clusters) {
                        break;
                    } else {
                        recompute = candid.i;
                    }
                } else if (IN_SET(candid.j, remaining_clusters)) {
                    recompute = candid.j;

                }

                pq.pop();

                if (recompute != -1){
                    recomute_closest(recompute);
                }
            }

            assert (not remaining_clusters.empty());

            const auto best = pq.top();
            pq.pop();

            const auto new_cluster_id = clusters.size();

            std::cout << "Final best distance is " << best.dist << " for clusters ";
            std::cout << new_cluster_id << " <- " << best.i << " U " << best.j << std::endl;
            std::cout << best.joined << " <- " << clusters[best.i] << " U " << clusters[best.j] << std::endl;

            clusters.emplace_back(best.joined);
            parents.emplace_back(new_cluster_id);


            const auto subsumed = Args::get().multithreaded_index_remove ?
                    index.remove_subset_parallel(best.joined, *pool) :
                    index.remove_subset(best.joined);

            for (const auto c : subsumed) {
                std::cout << "subsumed " << c << " " << clusters[c] << std::endl;
                parents[c] = new_cluster_id;
                remaining_clusters.erase(remaining_clusters.find(c));
            }

            assert(not IN_SET(best.i, remaining_clusters));
            assert(not IN_SET(best.j, remaining_clusters));

            remaining_clusters.insert(new_cluster_id);
            index.insert(best.joined, new_cluster_id);

            if (remaining_clusters.size() > 1) {
               recomute_closest(new_cluster_id);
            }

            //index.print_index(std::cout);

        }

        std::cout << "Done! " << overall_timer << std::endl;
    }

    template <typename Serializer>
    void serialize(Serializer& serializer) {
        std::cout << "Serializing the clusters" << std::endl;
        Timer timer;

        const auto parents_file = Args::get().out + "/parents.txt";
        const auto clusters_file = Args::get().out + "/clusters.txt";
        std::ofstream p_out{parents_file};
        assert(p_out);
        for (const auto p : parents){
            p_out << p << "\n";
        }
        p_out.close();

        std::ofstream c_out{clusters_file};
        assert(c_out);
        for (const auto& c : clusters){
            serializer.serialize(c_out, c);
            c_out << "\n";
        }
        c_out.close();

        std::cout << "Finished serializing the clusters in " << timer << std::endl;

        if (Args::get().hr_clusters) {
            std::cout << "Writing human readable clusters clusters" << std::endl;
            Timer timer;
            const auto clusters_file = Args::get().out + "/hr_clusters.txt";
            std::ofstream c_out{clusters_file};
            assert(c_out);
            for (const auto& c : clusters){
               c_out << c << "\n";
            }
            c_out.close();
            std::cout << "Finished writing human readable clusters in " << timer << std::endl;

        }
    }

    template <typename Deserializer>
    void deserialize(Deserializer& deserializer) {
        std::cout << "Deserializing the clusters" << std::endl;
        Timer timer;

        const auto parents_file = Args::get().out + "/parents.txt";
        const auto clusters_file = Args::get().out + "/clusters.txt";
        std::ifstream p_in{parents_file};
        int parent;
        while (p_in >> parent) {
            parents.emplace_back(parent);
        }

        std::ifstream c_in{clusters_file};
        for (auto i = 0; i < parents.size(); i++){
            clusters.emplace_back(deserializer.deserialize(c_in).value());
            //std::cout << i << "/" << parents.size() << " " << clusters[i] << std::endl;
        }
        c_in.close();

        std::cout << "Finished deserializing the clusters in " << timer << std::endl;
    }


    void compute_children(){
        if (not children.empty())
            return;
        const int n = parents.size();
        children.resize(n);
        for (auto i = 0; i < n; i++) {
            if (i == parents[i]) {
                assert (i == n - 1);
                continue;
            }
            children[parents[i]].emplace_back(i);
        }
    }

    std::vector<IncClusterInfo> inc_cluster_info;
    void compute_inc_cluster_info(){
        if (not inc_cluster_info.empty())
            return;

        compute_children();
        int k = 0;
        std::size_t i = 0;
        std::vector<std::size_t> add;
        while (children[i].empty()){
            add.emplace_back(i);
            k++;
            i++;
        }
        inc_cluster_info.emplace_back(IncClusterInfo{k, add, {}});


        for (; i < clusters.size(); i++){
            k = k + 1 - (int)children[i].size();
            inc_cluster_info.emplace_back(IncClusterInfo{k, {i}, children[i]});
        }
    }

    const std::vector<IncClusterInfo>& get_inc_cluster_info() {
        return inc_cluster_info;
    }


    std::vector<std::size_t> ks;
    void compute_ks() {
        if (not ks.empty())
            return;

        compute_children();

        int n_flows = 0;
        while (children[n_flows].empty()){
            n_flows++;
        }

        int k = n_flows;
        for (int i = 0; i < clusters.size(); i++){
            if (i < n_flows){
                assert (children[i].empty());
            } else {
                assert (not children[i].empty());
                k = k + 1 - children[i].size();
            }

            ks.emplace_back(k);
        }
    }

    const std::vector<std::size_t>& get_ks(){
        return ks;
    }


    std::vector<std::size_t> get_clusters_at(int k) {
        compute_inc_cluster_info();
        std::set<std::size_t> k_clusters;
        auto i = 0;
        for (; i < inc_cluster_info.size(); i++) {
            const auto& info = inc_cluster_info[i];
            if (k <= info.k) {
                for (const auto c : info.del)
                    k_clusters.erase(c);
                for (const auto c : info.add)
                    k_clusters.emplace(c);
            } else {
                break;
            }
        }
        std::vector<std::size_t> ret;
        for (const auto c : k_clusters)
            ret.emplace_back(c);
        return ret;
    }




    void write_xml_rec(std::ofstream& out, int c, int level, int depth_limit) {
        if (depth_limit > -1 and level > depth_limit)
            return;
        for (auto i = 0; i < level; i++)
            out << "\t";
        out << "<cluster id=\"" << c << "\" value=\"" << clusters[c] << "\" ";
        if (children[c].empty()) {
            out << "/>\n";
        } else {
            out << ">\n";
            for (const auto & child : children[c]) {
                write_xml_rec(out, child, level + 1, depth_limit);
            }
            for (auto i = 0; i < level; i++)
                       out << "\t";
            out << "</cluster>\n";
        }

    }

    template <typename F>
    void write_xml_rec(std::ofstream& out, int c, int level, int depth_limit, F augment) {
        if (depth_limit > -1 and level > depth_limit)
            return;
        for (auto i = 0; i < level; i++)
            out << "\t";
        out << "<cluster id=\"" << c << "\" value=\"" << clusters[c] << "\" ";
        augment(out,c);
        if (children[c].empty()) {
            out << "/>\n";
        } else {
            out << ">\n";
            for (const auto & child : children[c]) {
                write_xml_rec(out, child, level + 1, depth_limit, augment);
            }
            for (auto i = 0; i < level; i++)
                       out << "\t";
            out << "</cluster>\n";
        }

    }

    void write_xml(int k = 1, int depth_limit = -1) {
        std::cout << "Writing XML for k " << k << " with depth limit " << depth_limit << std::endl;
        const auto k_clsuters = get_clusters_at(k);
        std::ofstream fout{Args::get().out + "/clusters-" + std::to_string(k) + (depth_limit == -1 ? "" : "-" + std::to_string(depth_limit)) + ".xml"};
        assert(fout);
        fout << "<all>\n";
        for (const auto c : k_clsuters) {
            write_xml_rec(fout, c, 0, depth_limit);
        }
        fout << "</all>\n";

        fout.close();

        std::cout << "Finished writing XML for k " << k << std::endl;

    }

    template <typename F>
    void write_xml(int k, int depth_limit, F augment, const std::string& extention) {
        std::cout << "Writing XML for k " << k << " with depth limit " << depth_limit << std::endl;
        const auto k_clsuters = get_clusters_at(k);
        std::ofstream fout{Args::get().out + "/clusters-" + std::to_string(k) + (depth_limit == -1 ? "" : "-" + std::to_string(depth_limit)) + extention + ".xml"};
        assert(fout);
        fout << "<all>\n";
        for (const auto c : k_clsuters) {
            write_xml_rec(fout, c, 0, depth_limit, augment);
        }
        fout << "</all>\n";

        fout.close();

        std::cout << "Finished writing XML for k " << k << std::endl;

    }

};



template <typename Feature, typename Label>
class HierarchicalClusteringWithoutIndex : public HierarchicalClustering<Feature, Label> {
public:
    HierarchicalClusteringWithoutIndex(Feature& _feature) : HierarchicalClustering<Feature, Label>(_feature) {

    }
    void cluster(const std::vector<Label> flows, int k = 1) {
        if (k == 0)
            k = flows.size();

        std::set<std::size_t> remaining_clusters;

        Timer overall_timer;

        for (auto i = 0; i < flows.size(); i++) {
            this->clusters.emplace_back(this->feature.cjoin(flows[i],flows[i]));
            this->parents.emplace_back(i);
            remaining_clusters.insert(i);
        }

        std::cout << "Init done" << std::endl;

        Timer timer;


        auto get_closest_cluster = [this, &remaining_clusters](std::size_t c) -> std::optional<typename RTreeIndex<Feature, CostLabel<Label>, std::size_t>::NNEntry>  {

            using NNEntry = typename RTreeIndex<Feature, CostLabel<Label>, std::size_t>::NNEntry;
            std::optional<NNEntry> best;

            for (const auto cc : remaining_clusters){
                if (cc == c)
                    continue;
                const auto joined = this->feature.cjoin(this->clusters[c].label, this->clusters[cc].label);
                const auto dist = joined.cost - this->clusters[cc].cost - this->clusters[c].cost;
                if (not best.has_value()){
                    best.emplace(dist, joined, nullptr, std::pair<CostLabel<Label>, std::size_t>{this->clusters[cc], cc});
                } else if (std::abs(dist - best->dist) < 1e-10 and joined.cost < best->joined.cost){
                    best.emplace(dist, joined, nullptr, std::pair<CostLabel<Label>, std::size_t>{this->clusters[cc], cc});
                } else if (dist < best->dist){
                    best.emplace(dist, joined, nullptr, std::pair<CostLabel<Label>, std::size_t>{this->clusters[cc], cc});
                }
            }
            return best;
        };

        struct Entry {
            Cost dist;
            CostLabel<Label> joined;
            std::size_t i;
            std::size_t j;
        };

        struct EntryCmp {
            bool operator()(const Entry&a, const Entry& b) {
                if (std::abs(a.dist - b.dist) < 1e-10){
                    return a.joined.cost > b.joined.cost;
                } else {
                    return a.dist > b.dist;
                }
            }
        };

        std::priority_queue<Entry, std::vector<Entry>, EntryCmp> pq;


        auto recomute_closest = [&](std::size_t c) {
            const auto closest = get_closest_cluster(c);
            assert(closest.has_value());
            const auto dist = this->cost_gain_distance(this->clusters[c], closest->object->first, closest->joined);
            pq.emplace(Entry{dist, closest->joined, c, closest->object->second});
        };

        auto recomute_closest_parallel = [&](int id, std::size_t c, std::mutex& lock) {
            const auto closest = get_closest_cluster(c);
            assert(closest.has_value());
            const auto dist = this->cost_gain_distance(this->clusters[c], closest->object->first, closest->joined);
            lock.lock();
            pq.emplace(Entry{dist, closest->joined, c, closest->object->second});
            lock.unlock();
        };

        timer.reset();
        std::cout << "Started adding instances for initial clusters" << std::endl;

        if (not Args::get().multithreaded_init) {
            std::cout << "Single threaded" << std::endl;
            for (auto i = 0; i < flows.size(); i++) {
                recomute_closest(i);

                if (i % 10000 == 0)
                    std::cout << i << std::endl;
            }
        } else {
            const auto threads = Args::get().threads == 0 ? std::thread::hardware_concurrency() :  Args::get().threads;
            std::mutex lock;
            ctpl::thread_pool pool(threads);

            std::cout << "Running with " << threads << " threads" << std::endl;

            std::vector<std::future<void>> futures;
            for (auto i = 0; i < flows.size(); i++) {
                futures.emplace_back(pool.push(recomute_closest_parallel, i, std::ref(lock)));
            }
            auto i = 0;
            for (auto& f : futures) {
                i++;
                f.wait();

                if (i % 10000 == 0)
                    std::cout << i << std::endl;
            }
        }


        std::cout << "Finished adding instances for initial clusters in " << timer << std::endl;


        while (remaining_clusters.size() > k) {
            std::cout << "Number of clusters so far " << remaining_clusters.size() << std::endl;
//#define PER_CLUSTER_TIME
#ifdef PER_CLUSTER_TIME
            std::cout << "--" << remaining_clusters.size() << "," << overall_timer << std::endl;
#endif

            while (true) {
                int recompute = -1;
                const auto& candid = pq.top();
                if (IN_SET(candid.i, remaining_clusters)) {
                    if IN_SET(candid.j, remaining_clusters) {
                        break;
                    } else {
                        recompute = candid.i;
                    }
                } else if (IN_SET(candid.j, remaining_clusters)) {
                    recompute = candid.j;

                }

                pq.pop();

                if (recompute != -1){
                    recomute_closest(recompute);
                }
            }

            assert (not remaining_clusters.empty());

            const auto best = pq.top();
            pq.pop();

            const auto new_cluster_id = this->clusters.size();

            std::cout << "Final best distance is " << best.dist << " for clusters ";
            std::cout << new_cluster_id << " <- " << best.i << " U " << best.j << std::endl;
            std::cout << best.joined << " <- " << this->clusters[best.i] << " U " << this->clusters[best.j] << std::endl;

            this->clusters.emplace_back(best.joined);
            this->parents.emplace_back(new_cluster_id);

            std::vector<std::size_t> subsumed;
            for (const auto c : remaining_clusters) {
                if (this->feature.subset(this->clusters[c].label, best.joined.label)){
                    subsumed.emplace_back(c);
                }
            }

            for (const auto c : subsumed) {
                std::cout << "subsumed " << c << " " << this->clusters[c] << std::endl;
                this->parents[c] = new_cluster_id;
                remaining_clusters.erase(remaining_clusters.find(c));
            }

            assert(not IN_SET(best.i, remaining_clusters));
            assert(not IN_SET(best.j, remaining_clusters));

            remaining_clusters.insert(new_cluster_id);
            //index.insert(best.joined, new_cluster_id);

            if (remaining_clusters.size() > 1) {
               recomute_closest(new_cluster_id);
            }

            //index.print_index(std::cout);

        }

        std::cout << "Done! " << overall_timer << std::endl;
    }
};

#endif /* CLUSTERING_H_ */
