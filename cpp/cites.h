/*
 * cites.h
 *
 *  Created on: Sep 12, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */

#ifndef CITES_H_
#define CITES_H_

#include <vector>
#include "Feature.h"
#include "Timer.h"

LabelHierarchy device_hierarchy;
DAGFeature dag_feature{device_hierarchy};

template <typename Flow>
void read_flows(std::istream& in, std::vector<Flow>& flows) {
    HLabelFactory f{device_hierarchy};
    Timer timer;

    std::cout << "Reading flows" << std::endl;

    while (read_one_flow(in, f, flows)) {
        //if (flows.size() > 100)
        //    break;

        //cout << flows.back() << endl;
    }

    std::cout << "Finished reading " << flows.size() << " flows in " << timer << std::endl;
}


//===================

IPv4PrefixFeature ipPrefixFeature;
typedef Tuple<IPv4Prefix, HLabel, HLabel> PREFIX_SRC_DST_Flow;
auto prefix_src_dst_features_tuple = std::make_tuple(ipPrefixFeature, dag_feature, dag_feature);
TupleFeature<decltype(prefix_src_dst_features_tuple), PREFIX_SRC_DST_Flow> prefix_src_dst_flow_feature(prefix_src_dst_features_tuple);

bool operator<(const PREFIX_SRC_DST_Flow& lhs, const PREFIX_SRC_DST_Flow& rhs) {
    if (std::get<0>(lhs) == std::get<0>(rhs)) {
        if (std::get<1>(lhs) == std::get<1>(rhs)){
            return std::get<2>(lhs) < std::get<2>(rhs);
        } else {
            return std::get<1>(lhs) < std::get<1>(rhs);
        }
    } else {
        return std::get<0>(lhs) < std::get<0>(rhs);
    }
}

struct PREFIX_SRC_DST_FlowSerializer{
    void serialize(std::ostream& out, const CostLabel<PREFIX_SRC_DST_Flow>& cflow){
        const auto& flow = cflow.label;
        out << " " << std::get<0>(flow) << " " << std::get<1>(flow).id << " " <<  std::get<2>(flow).id;
    }
};

struct PREFIX_SRC_DST_FlowDeserializer {
   using Flow = PREFIX_SRC_DST_Flow;
   using Feature = decltype(prefix_src_dst_flow_feature);
   Feature& feature;
   HLabelFactory& f;

   PREFIX_SRC_DST_FlowDeserializer(Feature& _feature, HLabelFactory& _f) : feature(_feature), f(_f) {}
   std::optional<CostLabel<Flow>> deserialize(std::istream& in){
       std::string prefix_str;
       int src_id, dst_id;
       in >> prefix_str >> src_id >> dst_id;
       Flow flow{IPv4Prefix(prefix_str), f.get(src_id), f.get(dst_id)};
       return CostLabel<Flow>{feature.cost(flow), flow};
   }
};

bool read_one_flow(std::istream& in, HLabelFactory& f, std::vector<PREFIX_SRC_DST_Flow>& flows) {
    std::string prefix_str;
    int src_id, dst_id;

    if (not (in >> prefix_str))
        return false;

    in >> src_id >> dst_id;

    flows.emplace_back(IPv4Prefix(prefix_str), f.get(src_id), f.get(dst_id));

    return true;
}

//======================


IPRangeFeature ipRangeFeature;
typedef Tuple<IPRange, HLabel, HLabel> RANGE_SRC_DST_Flow;
auto range_src_dst_features_tuple = std::make_tuple(ipRangeFeature, dag_feature, dag_feature);
TupleFeature<decltype(range_src_dst_features_tuple), RANGE_SRC_DST_Flow> range_src_dst_flow_feature(range_src_dst_features_tuple);

bool operator<(const RANGE_SRC_DST_Flow& lhs, const RANGE_SRC_DST_Flow& rhs) {
    if (std::get<0>(lhs) == std::get<0>(rhs)) {
        if (std::get<1>(lhs) == std::get<1>(rhs)){
            return std::get<2>(lhs) < std::get<2>(rhs);
        } else {
            return std::get<1>(lhs) < std::get<1>(rhs);
        }
    } else {
        return std::get<0>(lhs) < std::get<0>(rhs);
    }
}

struct RANGE_SRC_DST_FlowSerializer{
    void serialize(std::ostream& out, const CostLabel<RANGE_SRC_DST_Flow>& cflow){
        const auto& flow = cflow.label;
        out << " " << std::get<0>(flow).begin << " " << std::get<0>(flow).end << " " << std::get<1>(flow).id << " " <<  std::get<2>(flow).id;
    }
};


struct RANGE_SRC_DST_FlowDeserializer {
   using Flow = RANGE_SRC_DST_Flow;
   using Feature = decltype(range_src_dst_flow_feature);
   Feature& feature;
   HLabelFactory& f;

   RANGE_SRC_DST_FlowDeserializer(Feature& _feature, HLabelFactory& _f) : feature(_feature), f(_f) {}
   std::optional<CostLabel<Flow>> deserialize(std::istream& in){
       uint32_t begin, end;
       int src_id, dst_id;
       in >> begin >> end >> src_id >> dst_id;
       Flow flow{IPRange(begin, end), f.get(src_id), f.get(dst_id)};
       return CostLabel<Flow>{feature.cost(flow), flow};
   }
};

bool read_one_flow(std::istream& in, HLabelFactory& f, std::vector<RANGE_SRC_DST_Flow>& flows) {
    std::string prefix_str;
    int src_id, dst_id;

    if (not (in >> prefix_str))
        return false;

    in >> src_id >> dst_id;

    flows.emplace_back(IPRange(prefix_str), f.get(src_id), f.get(dst_id));

    return true;
}


//========


#endif /* CITES_H_ */
