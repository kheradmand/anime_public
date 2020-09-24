/*
 * cites-eval.cpp
 *
 *  Created on: Sep 8, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */

#include "cites.h"
#include "Feature.h"
#include "Clustering.h"
#include "Eval.h"
#include "Args.h"
using namespace std;

template <typename Feature, typename Flow, typename FlowDeserializer>
int eval(Feature& flow_feature) {

    device_hierarchy.load_from_file(Args::get().device_file);

    HierarchicalClustering<decltype(flow_feature), Flow> clustering(flow_feature);
    typedef RTreeIndex<decltype(flow_feature), CostLabel<Flow>, std::size_t> IndexT;

    HLabelFactory f{device_hierarchy};
    FlowDeserializer deserializer{flow_feature, f};
    clustering.deserialize(deserializer);

    if (Args::get().xml_k > -1 and not Args::get().aug_xml) {
        clustering.write_xml(Args::get().xml_k, Args::get().xml_depth_limit);
        return 0;
    }

    cout << clustering.get_clusters().size() << endl;


    std::vector<Flow> flows;
    ifstream fin(Args::get().flows_file);
    read_flows(fin, flows);
    fin.close();

    if (Args::get().eval_k > -1 or Args::get().eval_partial_obs) {
        clustering.compute_inc_cluster_info();
        EvalIncremental<decltype(flow_feature), Flow, IndexT> eval(clustering.get_feature(), clustering.get_clusters(), clustering.get_inc_cluster_info(), flows);

        if (Args::get().eval_k > -1) {
            eval.eval(Args::get().eval_k);
        } else {
            eval.eval();
            eval.write_csv();
        }
    } else {
        {
            EvalSummarization<decltype(clustering)> eval(clustering);
            eval.eval();
            eval.write_csv();
        }
        {
            PerClusterEval<decltype(clustering)> eval(clustering);
            eval.eval();
            eval.write_csv();
            if (Args::get().xml_k > -1) {
                eval.write_xml(Args::get().xml_k, Args::get().xml_depth_limit);
            }
        }

        if (Args::get().eval_real_tp) {
             PerClusterEvalPrecise<decltype(clustering),Flow, RTreeIndex<decltype(flow_feature), CostLabel<Flow>, std::size_t>> eval(clustering,flows);
             eval.eval();
             eval.write_csv();
             if (Args::get().write_impr_limit > -1) {
                 eval.write_imprecisions(Args::get().write_impr_limit);
             }
             if (Args::get().xml_k > -1) {
                 eval.write_xml(Args::get().xml_k, Args::get().xml_depth_limit);
             }
        }

    }

    return 0;
}

int main(int argc, char** argv){
    auto exit_code = Args::get().parse_cli(argc, argv);
    if (exit_code != 0)
        return exit_code;


    return eval<decltype(prefix_src_dst_flow_feature), PREFIX_SRC_DST_Flow, PREFIX_SRC_DST_FlowDeserializer>(prefix_src_dst_flow_feature);


}
