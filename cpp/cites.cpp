/*
 * cites.cpp
 *
 *  Created on: Sep 1, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */


#include <iostream>
#include <fstream>
#include <filesystem>
#include "cites.h"
#include "Timer.h"
#include "Feature.h"
#include "Clustering.h"
#include "Args.h"
using namespace std;


template <typename Feature, typename Flow, typename FlowSerializer>
int infer(Feature& flow_feature){
    if (std::filesystem::exists(Args::get().out)){
        if (not std::filesystem::is_empty(Args::get().out)){
            if (not Args::get().override) {
                std::cout << "The output folder is not empty and override flag is not set" << std::endl;
                return 1;
            } else {
                std::cout << "The output folder is not empty. Cleaning up" << std::endl;
                std::filesystem::remove_all(Args::get().out);
            }
        }
    }

    std::filesystem::create_directories(Args::get().out);

    device_hierarchy.load_from_file(Args::get().device_file);


    std::vector<Flow> flows;
    ifstream fin(Args::get().flows_file);
    read_flows(fin, flows);
    fin.close();

    cout << "Starting to cluster" << endl;

    if (Args::get().index) {
        HierarchicalClustering<Feature, Flow> clustering(flow_feature);
        clustering.cluster(flows);

        FlowSerializer flow_serializer;
        clustering.serialize(flow_serializer);
    } else {
        HierarchicalClusteringWithoutIndex<Feature, Flow> clustering(flow_feature);
        clustering.cluster(flows);

        FlowSerializer flow_serializer;
        clustering.serialize(flow_serializer);
    }

    return 0;

}

int main(int argc, char** argv){
    auto exit_code = Args::get().parse_cli(argc, argv);
    if (exit_code != 0)
        return exit_code;


    return infer<decltype(prefix_src_dst_flow_feature), PREFIX_SRC_DST_Flow, PREFIX_SRC_DST_FlowSerializer>(prefix_src_dst_flow_feature);

}
