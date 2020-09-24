/*
 * test.cc
 *
 *  Created on: Aug 25, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */


#include "Feature.h"
#include "Index.h"
#include "Clustering.h"
#include <iostream>
using namespace std;

int main(){
	typedef Range<uint32_t> UI32Range;
	UI32Range r1{10, 20}, r2{30, 40};
	RangeFeature<uint32_t> rangeFeature;

	cout << rangeFeature.join(r1, r2) << endl;

	std::tuple<RangeFeature<uint32_t>, RangeFeature<uint32_t>> doubleRangeFeatureTuple{rangeFeature, rangeFeature};
	typedef Tuple<UI32Range, UI32Range> DoubleRange;
	TupleFeature<decltype(doubleRangeFeatureTuple), DoubleRange> doubleRangeFeature{doubleRangeFeatureTuple};

	DoubleRange d1{r1, r2}, d2{r2, r1};
	auto j = doubleRangeFeature.join(d1, d2);
	cout << j << endl;


	//


	LabelHierarchy device_hierarchy;
	device_hierarchy.load_from_file("labeling.txt");
	device_hierarchy.print_info(std::cout);

	DAGFeature dag_feature{device_hierarchy};

	HLabel s1{"s1", device_hierarchy};
	HLabel s2{"s2", device_hierarchy};
	HLabel f1{"f1", device_hierarchy};

	cout << dag_feature.join(s1, s2) << endl;
	cout << dag_feature.join(s1, f1) << endl;

	//


    RTreeIndex<RangeFeature<uint32_t>, CostLabel<UI32Range>, int> index(rangeFeature);
    index.insert({rangeFeature.cost(r1), r1}, 1);
    index.insert({rangeFeature.cost(r2), r2}, 2);
    index.print_index(cout);

    index.remove_subset({rangeFeature.cost(r2), r1});
    index.print_index(cout);

    const auto knn = index.get_knn_approx({rangeFeature.cost(r2), r1});

    cout << knn[0].object->first << endl;
    cout << knn.size() << endl;


    //

    IPv4PrefixFeature ipPrefixFeature;
    RTreeIndex<IPv4PrefixFeature, CostLabel<IPv4Prefix>, int> ipIndex(ipPrefixFeature);
    for (auto i = 0 ; i < 256; i++){
        ipIndex.insert({1, IPv4Prefix{"192.168.1." + std::to_string(i) + "/32"}}, i);
    }

    ipIndex.print_index(std::cout);

    //

    {
        HLabelFactory f{device_hierarchy};
        cout << "---->" << dag_feature.subset(f.get("User"), f.get("Any")) << endl;


        HierarchicalClustering<decltype(dag_feature), HLabel> clustering(dag_feature);
        std::vector<HLabel> flows = {
                f.get("u1"),
                f.get("u2"),
                f.get("f1"),
                f.get("s1"),
        };

        clustering.cluster(flows);
    }

    //

    {
        typedef Tuple<HLabel, HLabel, HLabel> Flow;
        auto src_mid_dst_features_tuple = make_tuple(dag_feature, dag_feature, dag_feature);
        TupleFeature<decltype(src_mid_dst_features_tuple), Flow> flow_feature(src_mid_dst_features_tuple);

        HLabelFactory f{device_hierarchy};
        std::vector<Flow> flows;
        flows.emplace_back(f.get("u1"), f.get("f1"), f.get("s1"));
        flows.emplace_back(f.get("u2"), f.get("f1"), f.get("s1"));
        flows.emplace_back(f.get("u3"), f.get("f2"), f.get("s1"));
        flows.emplace_back(f.get("u1"), f.get("f1"), f.get("s2"));
        flows.emplace_back(f.get("u2"), f.get("f2"), f.get("s2"));
        flows.emplace_back(f.get("u3"), f.get("f2"), f.get("s2"));

        HierarchicalClustering<decltype(flow_feature), Flow> clustering(flow_feature);
        clustering.cluster(flows);
    }

    //

    {
        typedef Tuple<IPv4Prefix, HLabel, HLabel, HLabel> Flow;
        auto prefix_src_mid_dst_features_tuple = make_tuple(ipPrefixFeature, dag_feature, dag_feature, dag_feature);
        TupleFeature<decltype(prefix_src_mid_dst_features_tuple), Flow> flow_feature(prefix_src_mid_dst_features_tuple);

        HLabelFactory f{device_hierarchy};
        std::vector<Flow> flows;
        flows.emplace_back(IPv4Prefix("10.0.0.2/32"), f.get("u1"), f.get("f1"), f.get("s1"));
        flows.emplace_back(IPv4Prefix("10.0.0.2/32"), f.get("u2"), f.get("f1"), f.get("s1"));
        flows.emplace_back(IPv4Prefix("10.0.0.2/32"), f.get("u3"), f.get("f2"), f.get("s1"));
        flows.emplace_back(IPv4Prefix("10.0.0.3/32"), f.get("u1"), f.get("f1"), f.get("s2"));
        flows.emplace_back(IPv4Prefix("10.0.0.3/32"), f.get("u2"), f.get("f2"), f.get("s2"));
        flows.emplace_back(IPv4Prefix("10.0.0.3/32"), f.get("u3"), f.get("f2"), f.get("s2"));

        HierarchicalClustering<decltype(flow_feature), Flow> clustering(flow_feature);
        clustering.cluster(flows);
    }



}
