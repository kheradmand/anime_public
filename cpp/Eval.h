/*
 * Eval.h
 *
 *  Created on: Sep 7, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */

#ifndef EVAL_H_
#define EVAL_H_


#include "Args.h"
#include "Timer.h"
#include "Feature.h"
#include "ctpl_stl.h"
#include <vector>
#include <fstream>
#include <unordered_set>

template <typename HierarchicalClustering>
class EvalSummarization {
    struct Record {
        int k;
        Cost tp;
        Cost fp_ub;
        Cost fn;
        Record(int _k, Cost _tp, Cost _fp_ub, Cost _fn) : k(_k), tp(_tp), fp_ub(_fp_ub), fn(_fn){}
    };
public:
    std::vector<Record> results;
    HierarchicalClustering& clustering;
    const int n;

    EvalSummarization(HierarchicalClustering& _clustering) : clustering(_clustering), n(_clustering.get_parents().size()) {
        clustering.compute_children();
    }

    void eval() {
        std::cout << "Starting evaluation of summary" << std::endl;
        Timer timer;
        const auto& clusters = clustering.get_clusters();
        const auto& children = clustering.get_children();
        int i = 0;
        int k = 0;
        Cost tp = 0;
        Cost pp_ub = 0;
        while (children[i].empty()){
            k++;
            i++;
            tp += clusters[i].cost;
            pp_ub += clusters[i].cost;
        }

        results.emplace_back(k, tp, pp_ub - tp, 0);

        for (; i < n; i++) {
            for (const auto c : children[i]) {
                k--;
                pp_ub -= clusters[c].cost;
            }
            k++;
            pp_ub += clusters[i].cost;
            results.emplace_back(Record{k, tp, pp_ub - tp, 0});
        }

        std::cout << "Finished evaluation of summary in " << timer << std::endl;
    }

    void write_csv() {
        const auto file = Args::get().out + "/summary_eval.csv";
        std::ofstream fout{file};
        fout << "k,tp,fp,fn\n";
        assert(fout);
        for (const auto& r : results) {
            fout << r.k << "," << r.tp << "," << r.fp_ub << "," << r.fn << "\n";
        }
        fout.close();
    }

};


template <typename HierarchicalClustering>
class PerClusterEval {
public:
    struct Record {
        std::size_t k;
        Cost tp_subtree;
        Cost pp;
    };

    std::vector<Record> results;
    HierarchicalClustering& clustering;
    const int n;
    int n_flows = 0;


    PerClusterEval(HierarchicalClustering& _clustering) : clustering(_clustering), n(_clustering.get_parents().size()) {
       clustering.compute_children();
       const auto& children = clustering.get_children();
       while(children[n_flows].empty()){
           ++n_flows;
       }
    }

    Cost ap = 0;
    void eval() {
        std::cout << "Starting evaluation of summary" << std::endl;
        Timer timer;
        const auto& clusters = clustering.get_clusters();
        const auto& children = clustering.get_children();
        results.reserve(n);

        int k = n_flows;
        for (int i = 0; i < n; i++) {
            Cost tp_subtree = 0;
            if (children[i].empty()){
                tp_subtree = clusters[i].cost;
                ap += clusters[i].cost;
            } else {
                k = k + 1 - (int)children[i].size();
                for (const auto c : children[i]) {
                    tp_subtree += results[c].tp_subtree;
                }
            }
            results.emplace_back(Record{static_cast<std::size_t>(k), tp_subtree, clusters[i].cost});
        }


        std::cout << "Finished evaluation of summary in " << timer << std::endl;
    }


    void write_xml(int k = 1, int depth_limit = -1){
        eval();

       auto aug = [this](std::ostream& out, int c) {
            const auto pr = this->results[c].tp_subtree / this->results[c].pp;
            const auto rc = this->results[c].tp_subtree / this->ap;
            const auto fs = 2 * pr * rc / (pr + rc);
            out << "pr=\"" << pr << "\" rc=\"" << rc << "\" fs=\"" << fs << "\"";
        };
        clustering.write_xml(k, depth_limit, aug, "_aug");
    }

    void write_csv() {
        const auto file = Args::get().out + "/summary_eval_per_cluster.csv";
        std::ofstream fout{file};
        fout << "k,tp_subtree,pp,ap\n";
        assert(fout);
        for (const auto& r : results) {
            fout << r.k << "," << r.tp_subtree << "," << r.pp << "," << ap << "\n";
        }
        fout.close();
    }

};


template <typename HierarchicalClustering, typename Flow, typename Index>
class PerClusterEvalPrecise {
public:
    struct Record {
        std::size_t k;
        Cost tp_all;
        Cost pp;
    };

    std::vector<Record> results;
    HierarchicalClustering& clustering;
    Index index;
    const std::vector<Flow>& flows;
    const int n;
    Cost ap = 0;


    PerClusterEvalPrecise(HierarchicalClustering& _clustering, decltype(flows) _flows)
        : clustering(_clustering), index(_clustering.get_feature()), flows(_flows), n(_clustering.get_parents().size()) {
        clustering.compute_ks();

        auto& feature = clustering.get_feature();
        std::cout << "Begin indexing" << std::endl;
        Timer indexTimer;
        for (auto i = 0; i < flows.size(); i++){
            CostLabel<Flow> cflow{feature.cost(flows[i]), flows[i]};
            ap += cflow.cost;
            index.insert(cflow, i);
        }
        std::cout << "Finished indexing in " <<  indexTimer << std::endl;
    }


    void eval() {
        if (not results.empty()){
            return;
        }
        std::cout << "Starting evaluation of summary" << std::endl;
        Timer timer;
        const auto& clusters = clustering.get_clusters();
        const auto& ks = clustering.get_ks();
        results.reserve(n);


        int l = flows.size();
        for (int i = 0; i < l; i++){
            results.emplace_back(Record{ks[i], clusters[i].cost, clusters[i].cost});
        }

        std::vector<std::future<Cost>> futures;
        ctpl::thread_pool pool(std::thread::hardware_concurrency());

        auto get_tp = [&](int id, int c) {
            const auto subsets = index.get_subset(clusters[c]);
            Cost sum = 0;
            for (const auto c : subsets)
                sum += clusters[c].cost;
            return sum;
        };

        for (int i = l; i < n; i++) {
            futures.emplace_back(pool.push(get_tp, i));
        }

        for (int i = 0; i < futures.size(); i++) {
            results.emplace_back(Record{ks[i+l], futures[i].get(), clusters[i+l].cost});
            if ((i+l) % 10000 == 0){
                std::cout << i+l << std::endl;
            }
        }

        std::cout << "Finished evaluation of summary in " << timer << std::endl;
    }

    void write_xml(int k = 1, int depth_limit = -1){
        eval();

       auto aug = [this](std::ostream& out, int c) {
            const auto pr = this->results[c].tp_all / this->results[c].pp;
            const auto rc = this->results[c].tp_all / this->ap;
            const auto fs = 2 * pr * rc / (pr + rc);
            out << "pr=\"" << pr << "\" rc=\"" << rc << "\" fs=\"" << fs << "\"";
        };
        clustering.write_xml(k, depth_limit, aug, "_aug_precise");
    }


    void write_csv() {
        const auto file = Args::get().out + "/summary_eval_per_cluster_precise.csv";
        std::ofstream fout{file};
        fout << "k,tp_all,pp,ap\n";
        assert(fout);
        for (const auto& r : results) {
            fout <<  r.k << "," << r.tp_all << "," << r.pp << "," << ap << "\n";
        }
        fout.close();
    }

    void write_imprecisions(int k_lb = 1){
        if (results.empty())
            eval();
        clustering.compute_children();
        const auto& clusters = clustering.get_clusters();
//        const auto& children = clustering.get_children();
        std::cout << "Writing imprecisions" << std::endl;
        const auto file = Args::get().out + "/imprecisions-" + std::to_string(k_lb) + ".txt";
        std::ofstream fout{file};
        for (auto i = 0; i < results.size(); i++){
            const auto& r = results[i];
            if (r.k < k_lb)
                break;
            if (r.tp_all < r.pp) {
//                bool should_continue = false;
//                for (const auto c : children[i]){
//                    if (c >= flows.size()){
//                        should_continue = true;
//                        break;
//                    }
//                }
//                if (should_continue)
//                    continue;
                fout << r.k << " " << clusters[i] <<  " tp:" << r.tp_all << " pp:" << r.pp << " pr:" << (r.tp_all/r.pp) << " rc:" << (r.tp_all/ap) << std::endl;

                const auto subsets = index.get_subset(clusters[i]);
                std::vector<Flow> sorted_flows;
                for (const auto f : subsets) {
                    sorted_flows.push_back(flows[f]);
                }

                std::sort(sorted_flows.begin(), sorted_flows.end());

                for (const auto& f : sorted_flows) {
                    fout << "\t" << f << std::endl;
                }

            }
        }
        std::cout << "Finished writing imprecisions" << std::endl;
    }

};




template <typename Feature, typename Label, typename Index>
class EvalIncremental {
public:
    struct Record {
        int k;
        Cost tp;
        Cost pp_ub;
        Cost ap;
    };


    std::vector<Record> results;
    Feature& feature;
    const std::vector<CostLabel<Label>>& clusters;
    const std::vector<IncClusterInfo>& inc_cluster_info;
    const std::vector<Label>& flows;
    std::vector<CostLabel<Label>> cflows;
    Index index;
    Cost ap = 0;



    EvalIncremental(Feature& _feature, const  std::vector<CostLabel<Label>>& _clusters, const std::vector<IncClusterInfo>& _inc_cluster_info, const std::vector<Label>& _flows)  :
        feature(_feature), clusters(_clusters), inc_cluster_info(_inc_cluster_info), flows(_flows), index(_feature) {
        std::cout << "Begin indexing" << std::endl;
        Timer timer;
        for (auto i = 0; i < flows.size(); i++){
            cflows.emplace_back(CostLabel<Label>{feature.cost(flows[i]), flows[i]});
            ap += cflows[i].cost;
            index.insert(cflows[i], i);
        }
        std::cout << "Finished indexing in " <<  timer << std::endl;
    }

    void eval(int k){
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

        struct Record {
            std::size_t c;
            Cost tp;
            Cost pr;
            Cost rc;
            bool operator<(const Record& rhs) const {
                if (std::abs(pr - rhs.pr) < 1e-10) {
                    return rc < rhs.rc;
                } else {
                    return pr < rhs.pr;
                }
            }
        };

        std::set<Record> sorted_records;


        const auto& info = inc_cluster_info[i];
        std::cout << "k: " << info.k << std::endl;
        Cost total_tp = 0;
        Cost total_pp = 0;
        std::unordered_set<std::size_t> covered;
        for (const auto c : k_clusters) {
            total_pp += clusters[c].cost;
            const auto subsets = index.get_subset(clusters[c]);
            Cost tp = 0;
            for (const auto f : subsets) {
                tp += cflows[f].cost;
                if (covered.emplace(f).second) {
                    total_tp += cflows[f].cost;
                }
            }
            sorted_records.emplace(Record{c,tp, (tp / clusters[c].cost), (tp/ ap)});

            //std::cout << c << " " << clusters[c] << " tp:" << tp << " pr:" << (tp / clusters[c].cost) << " rc:" << (tp/ ap) << std::endl;
        }


        for (const auto r : sorted_records) {
            std::cout << r.c << " " << clusters[r.c] << " tp:" << r.tp << " pr:" << r.pr << " rc:" << r.rc << std::endl;

            const auto subsets = index.get_subset(clusters[r.c]);
            std::vector<Label> sorted_flows;

            for (const auto f : subsets) {
                sorted_flows.push_back(flows[f]);
            }

            std::sort(sorted_flows.begin(), sorted_flows.end());

            for (const auto& f : sorted_flows) {
                std::cout << "\t" << f << std::endl;
            }

        }
    }


    void eval() {
        std::cout << "Starting evaluation" << std::endl;
        Timer timer;
        //ctpl::thread_pool pool(std::thread::hardware_concurrency());
        //std::vector<std::future<std::pair<int, Cost>>> futures;

        Cost pp_ub = 0;
        Cost tp = 0;
        std::unordered_set<std::size_t> covered;
        for (auto i = 0; i < inc_cluster_info.size(); i++) {
            const auto& info = inc_cluster_info[i];
            std::cout << "+" << info.add.size() << " -" << info.del.size() << std::endl;
            for (const auto c : info.add)
                pp_ub += clusters[c].cost;
            for (const auto c : info.del)
                pp_ub -= clusters[c].cost;

            //optimization
            if (info.add.size() > 1){
                assert(info.del.empty());
                assert(i == 0);

                for (const auto c : info.add){
                    const auto subsets = index.get_subset(clusters[c]);
                    assert(subsets.size() == 1);
                    const auto f =  *(subsets.begin());
                    tp += cflows[f].cost;
                    assert(covered.emplace(f).second);
                }
                std::cout << std::endl;

                //futures.emplace_back(poo.push())
            } else {
                assert(info.add.size() == 1);
                const auto c = *(info.add.begin());
                const auto subsets = index.get_subset(clusters[c]);
                std::cout << "subsets " << subsets.size() << std::endl;
                for (const auto f : subsets) {
                    if (covered.emplace(f).second){
                        std::cout << "adding to tp " << cflows[f].cost <<  std::endl;
                        tp += cflows[f].cost;
                    }
                }
            }

            results.emplace_back(Record{info.k, tp, pp_ub});


        }
        std::cout << "Finished evaluation of summary in " << timer << std::endl;
    }


    void write_csv() {
        const auto file = Args::get().out + "/inc_eval.csv";
        std::ofstream fout{file};
        fout << "k,tp,pp,ap\n";
        assert(fout);
        for (const auto& r : results) {
            fout <<  r.k << "," << r.tp << "," << r.pp_ub << "," << ap << "\n";
        }
        fout.close();
    }

};


#endif /* EVAL_H_ */
