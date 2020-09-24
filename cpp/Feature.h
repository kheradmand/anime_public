/*
 * Feature.h
 *
 *  Created on: Aug 14, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */

#ifndef FEATURE_H_
#define FEATURE_H_

#include <cassert>
#include <algorithm>
#include <iterator>
#include <utility>
#include <unordered_map>
#include <iostream>
#include <cstdint>
#include <optional>
#include <vector>
#include <set>
#include <fstream>
#include <sstream>
#include <exception>

typedef double Cost;

template <typename Label>
struct CostLabel {
    Cost cost;
    Label label;
};

template <typename Label>
std::ostream& operator<<(std::ostream& out, const CostLabel<Label>& l) {
    out << "{" << l.cost << "," << l.label << "}";
    return out;
}


template <typename Label>
class Feature {
public:
    Label join(const Label& l1, const Label& l2){
        throw std::runtime_error{"Not implemented"};
    }

    std::optional<Label> meet(const Label& l1, const Label& l2){
        throw std::runtime_error{"Not implemented"};
    }

    Cost cost(const Label& l){
        throw std::runtime_error{"Not implemented"};
    }

    Label top(){
        throw std::runtime_error{"Not implemented"};
    }

    CostLabel<Label> cjoin(const Label& l1, const Label& l2){ \
        throw std::runtime_error{"Not implemented"};
    }

#define DEFAULT_CJOIN(LABEL) \
    CostLabel<LABEL> cjoin(const LABEL& l1, const LABEL& l2){ \
        const auto& joined = join(l1, l2); \
        return CostLabel<LABEL>{cost(joined), joined}; \
    }


#define DEFAULT_SUBSET(LABEL) \
    bool subset(const LABEL& l1, const LABEL& l2){ \
        const auto& joined = join(l1, l2); \
        return joined == l2; \
    }

    // Can't have virtual + template
//    Label cardinality(const Label& l) {
//        return cost(l);
//    }
//
//    CostLabel<Label> cjoin(const Label& l1, const Label& l2){
//        const auto& joined = join(l1, l2);
//        return CostLabel<Label>{cost(joined), joined};
//    }
};

typedef int LabelId;
class DAGFeature;



namespace std
{
    template<>
    struct hash<std::pair<int,int>> {
        std::size_t operator()(std::pair<int,int> const& t) const noexcept
        {
            const auto h1 = std::hash<int>{}(t.first);
            const auto h2 = std::hash<int>{}(t.second);
            return h1 ^ (h2 << 1);
        }
    };
}



thread_local std::unordered_map<int, const std::set<int>> successors_cache, predecessors_cache;
thread_local std::unordered_map<std::pair<int, int>, int> join_cache, meet_cache;
class LabelHierarchy {
public:
    struct LabelInfo {
        std::vector<int> parents;
        std::vector<int> children;
        Cost cost;
    };

    void add_label_info(const std::string& label, const LabelInfo& info) {
        assert(label_to_id.find(label) == label_to_id.end());
        const auto id = label_info.size();
        label_to_id[label] = id;
        id_to_label.push_back(label);
        label_info[id] = info;
    }

    void finalize_label_info() {
        assert(not finalized);

        for (const auto& [l, info] : label_info) {
            if (info.parents.empty()){
                assert(top_id == -1);
                top_id = l;
            }

            for (const auto p : info.parents) {
                label_info[p].children.push_back(l);
            }
        }

        assert(top_id != -1);

        finalized = true;
    }

    void load_from_file(const std::string& file) {
        std::ifstream fin(file);
        assert(fin);

        std::string line_str;
        while (std::getline(fin, line_str)){

            // Format of each line : label cost parents
            // Assumption: the entry for the parents of each label comes before the entry for that label

            std::stringstream line{line_str};
            std::string label;
            LabelInfo info;

            line >> label >> info.cost;
            std::vector<std::string> parents{
                std::istream_iterator<std::string>(line),
                std::istream_iterator<std::string>()};

            std::transform(parents.begin(), parents.end(),
                    std::back_inserter(info.parents),
                    [this](const auto& l) {return name_to_id(l);});

            add_label_info(label, info);
        }

        finalize_label_info();
    }

    int join(int l1, int l2) {

        const auto lookup = join_cache.find({l1,l2});
        if (lookup != join_cache.end())
            return lookup->second;

        auto p1 = get_predecessors(l1);
        auto p2 = get_predecessors(l2);

        std::vector<int> inter;
        std::set_intersection(p1.begin(), p1.end(), p2.begin(), p2.end(), std::back_inserter(inter));

        assert(inter.size() > 0);

        int best = -1;
        for (const auto l : inter) {
            if (best == -1 or cost(l) < cost(best)) {
                best = l;
            } else if (std::abs(cost(best) - cost(l)) < 1e-10) {
                // Workaround for cases where parent and children have the same cost
                // (although it should not be the case technically)
                const auto p_l = get_predecessors(l);
                if (p_l.find(best) != p_l.end()){
                    best = l;
                }
            }
        }

        assert(best != -1);

        //std::cout << "join of " << id_to_name(l1) << " " << id_to_name(l2)  << " is " << id_to_name(best) << " with cost " << cost(best) << std::endl;

        join_cache[{l1,l2}] = best;

        return best;
    }


    int meet(int l1, int l2) {
        const auto lookup = meet_cache.find({l1,l2});
        if (lookup != meet_cache.end())
            return lookup->second;

        auto s1 = get_successors(l1);
        auto s2 = get_successors(l2);

        std::vector<int> inter;
        std::set_intersection(s1.begin(), s1.end(), s2.begin(), s2.end(), std::back_inserter(inter));

        int best = -1;
        for (const auto l : inter) {
            if (best == -1 or cost(l) > cost(best)) {
                best = l;
            } else if (std::abs(cost(best) - cost(l)) < 1e-10) {
                // Workaround for cases where parent and children have the same cost
                // (although it should not be the case technically)
                const auto s_l = get_successors(l);
                if (s_l.find(best) != s_l.end()){
                    best = l;
                }
            }
        }

        //std::cout << "meet of " << id_to_name(l1) << " and " << id_to_name(l2) << " is " << (best == -1 ? "none" : id_to_name(best)) << std::endl;

        meet_cache[{l1,l2}] = best;

        return best;
    }

    int top() {
        return top_id;
    }

    Cost cost(int l) {
        return label_info[l].cost;
    }

    //Cost cardinality(int l);

    std::string id_to_name(const int id) const {
        return id_to_label[id];
    }

    int name_to_id(const std::string& name) const {
        return label_to_id.at(name);
    }

    std::set<int> get_predecessors(int l) {
        const auto lookup = predecessors_cache.find(l);
        if (lookup != predecessors_cache.end())
            return lookup->second;

        std::set<int> ret;
        add_parents(l, ret);

        predecessors_cache.emplace(l, ret);
        return ret;
    }

    std::set<int> get_successors(int l) {
        const auto lookup = successors_cache.find(l);
        if (lookup != successors_cache.end())
            return lookup->second;

        std::set<int> ret;
        add_children(l, ret);

        successors_cache.emplace(l, ret);
        return ret;
    }


    void print_info(std::ostream& out) {
        for (const auto& [l, info] : label_info) {
            out << id_to_name(l) << "(" << l << ") " << info.cost << " ";
            for (const auto& p : info.parents)
                out << id_to_name(p) << "(" << p << ") ";
            out << " -- ";
            for (const auto& c : info.children)
                out << id_to_name(c) << "(" << c << ") ";
            out << std::endl;
        }
    }

private:
    std::unordered_map<LabelId, LabelInfo> label_info;
    std::vector<std::string> id_to_label;
    std::unordered_map<std::string, int> label_to_id;
//    std::unordered_map<int, const std::set<int>> successors_cache, predecessors_cache;
//    std::unordered_map<std::pair<int, int>, int> join_cache, meet_cache;
    int top_id = -1;
    bool finalized = false;

    void add_parents(int l, std::set<int>& acc) {
        acc.insert(l);
        for (const auto& p : label_info[l].parents) {
            add_parents(p, acc);
        }
    }

    void add_children(int l, std::set<int>& acc) {
        acc.insert(l);
        for (const auto& c : label_info[l].children) {
            add_children(c, acc);
        }
    }
};

struct HLabel {
    HLabel(const int _id, const LabelHierarchy& _hierarchy):
        id(_id),
        hierarchy(_hierarchy){}
    HLabel(const std::string& name, const LabelHierarchy& _hierarchy):
        id(_hierarchy.name_to_id(name)),
        hierarchy(_hierarchy){}

    HLabel& operator=(const HLabel& l) {
        assert(&hierarchy == &l.hierarchy);
        id = l.id;
        return *this;
    }

    int id;
    const LabelHierarchy& hierarchy;
};

bool operator<(const HLabel& lhs, const HLabel& rhs) {
    assert(&lhs.hierarchy == &rhs.hierarchy);
    //return lhs.id < rhs.id;
    return  lhs.hierarchy.id_to_name(lhs.id) < rhs.hierarchy.id_to_name(rhs.id);
}

struct HLabelFactory {
    const LabelHierarchy& hierarchy;
    HLabelFactory(const LabelHierarchy& _hierarchy) : hierarchy(_hierarchy) {}
    HLabel get(const std::string& name) {
        return HLabel{name, hierarchy};
    }
    HLabel get(const int id) {
        return HLabel{id, hierarchy};
    }
};

inline bool operator==(const HLabel& lhs, const HLabel& rhs) {
    assert(&lhs.hierarchy == &rhs.hierarchy);
    return lhs.id == rhs.id;
}

std::ostream& operator<<(std::ostream& out, const HLabel& l){
    out << l.hierarchy.id_to_name(l.id);
    return out;
}

class DAGFeature : public Feature<HLabel> {
public:
    DAGFeature(LabelHierarchy& _hierarchy): hierarchy(_hierarchy){}

    HLabel join(const HLabel& l1, const HLabel& l2){
        return HLabel(hierarchy.join(l1.id, l2.id), hierarchy);
    }

    std::optional<HLabel> meet(const HLabel& l1, const HLabel& l2){
        const auto ret = hierarchy.meet(l1.id, l2.id);
        return ret != -1 ? std::optional<HLabel>{HLabel{ret, hierarchy}} :  std::nullopt;
    }

    Cost cost(const HLabel& l){
        return hierarchy.cost(l.id);
    }

//    Cost cardinality(const HLabel& l){
//        return hierarchy.cardinality(l.id);
//    }

    HLabel top(){
        return HLabel(hierarchy.top(), hierarchy);
    }

    DEFAULT_CJOIN(HLabel)
    DEFAULT_SUBSET(HLabel)

private:
    LabelHierarchy& hierarchy;
};


struct IPv4Prefix {
    uint32_t address;
    uint8_t len;
    IPv4Prefix(const std::string& prefix_str) {
        std::stringstream prefix(prefix_str);
        uint32_t octet[4], _len;
        char c;
        prefix >> octet[3] >> c;
        assert(c == '.');
        prefix >> octet[2] >> c;
        assert(c == '.');
        prefix >> octet[1] >> c;
        assert(c == '.');
        prefix >> octet[0] >> c;
        assert(c == '/');
        prefix >> _len;
        len = _len;
        address = (octet[3]<<24) | (octet[2]<<16) | (octet[1]<<8) | (octet[0]);
    }
    IPv4Prefix(const uint32_t _address = 0, const uint8_t _len = 0) :
        address(_address),
        len(_len) {}
    uint32_t begin() const {
        return address;
    }

    uint32_t end() const {
        return uint64_t(address) + network_size() - 1 ;
    }

    uint64_t network_size() const {
        return 1UL << (32 - len);
    }
};

std::ostream& operator<<(std::ostream& out, const IPv4Prefix& l){
    auto address = l.address;
    auto mask = (1U << 8) - 1;
    const auto octet0 = address & mask;
    address = address >> 8;
    const auto octet1 = address & mask;
    address = address >> 8;
    const auto octet2 = address & mask;
    address = address >> 8;
    const auto octet3 = address & mask;
    out << octet3 << "." << octet2 << "." << octet1 << "." << octet0;
    out << "/" << uint32_t(l.len);
    return out;
}

inline bool operator==(const IPv4Prefix& lhs, const IPv4Prefix& rhs) {
    return lhs.address == rhs.address and lhs.len == rhs.len;
}

inline bool operator<(const IPv4Prefix& lhs, const IPv4Prefix& rhs) {
    if (lhs.address == rhs.address)
        return lhs.len < rhs.len;
    else
        return lhs.address < rhs.address;
}

class IPv4PrefixFeature : public Feature<IPv4Prefix> {
public:
    IPv4Prefix join(const IPv4Prefix& l1, const IPv4Prefix& l2){
        const auto len = std::min(std::min(l1.len, l2.len),
                l1.address == l2.address ? uint8_t(32) : uint8_t(__builtin_clz(l1.address ^ l2.address)));
        if (len == 0) {
            return {0, 0};
        }
        const auto mask = ~((uint32_t(1)<<(32 - len)) - 1);
        //std::cout << "join of " << l1 << " and " << l2 << " is " << IPv4Prefix{l1.address & mask, len}  << std::endl;
        return {l1.address & mask, len};
    }

    std::optional<IPv4Prefix> meet(const IPv4Prefix& l1, const IPv4Prefix& l2){
        if (l1.begin() > l2.end() or l2.begin() > l1.end())
            return std::nullopt;
        else
            return l1.len < l2.len ? std::optional<IPv4Prefix>{l2} : std::optional<IPv4Prefix>{l1};
    }

    Cost cost(const IPv4Prefix& l){
        return l.network_size();
    }

    IPv4Prefix top(){
        return IPv4Prefix();
    }

    DEFAULT_CJOIN(IPv4Prefix)
    DEFAULT_SUBSET(IPv4Prefix)
};


// Inclusive range
template<typename T>
struct Range{
    T begin;
    T end;
};

template<typename T>
inline bool operator==(const  Range<T>& lhs, const  Range<T>& rhs) {
    return lhs.begin == rhs.begin and lhs.end == rhs.end;
}

template<typename T>
inline bool operator<(const  Range<T>& lhs, const  Range<T>& rhs) {
    if (lhs.begin == rhs.begin)
        return lhs.end < rhs.end;
    else
        return lhs.begin < rhs.begin;
}

template<typename T>
std::ostream& operator<<(std::ostream& out, const Range<T>& r){
    out << "[" << r.begin << ", " << r.end << "]";
    return out;
}

template<typename T>
class RangeFeature : public Feature<Range<T>> {
public:
    Range<T> join(const Range<T>& l1, const Range<T>& l2){
        return {std::min(l1.begin, l2.begin), std::max(l1.end, l2.end)};
    }

    std::optional<Range<T>> meet(const Range<T>& l1, const Range<T>& l2){
        if (l1.end < l2.begin or l2.end < l1.begin)
            return std::nullopt;
        else
            return Range<T>{std::max(l1.begin, l2.begin), std::min(l1.end, l2.end)};
    }

    Cost cost(const Range<T>& l){
        return l.end - l.begin + 1ULL;
    }

    Range<T> top(){
        return {std::numeric_limits<T>::min(), std::numeric_limits<T>::max()};
    }

    DEFAULT_CJOIN(Range<T>)
    DEFAULT_SUBSET(Range<T>)
};

//
//struct IPRange : Range<uint32_t> {
//    IPRange(const std::string& prefix) {
//        IPv4Prefix temp(prefix);
//        begin = temp.begin();
//        end = temp.end();
//    }
//    IPRange(const Range<uint32_t>& r) : Range<uint32_t>(r) {
//
//    }
//};
//
//class IPRangeFeature : public RangeFeature<uint32_t> {
//
//};

struct IPRange{
    uint32_t begin;
    uint32_t end;
    IPRange(const std::string& prefix) {
        IPv4Prefix temp(prefix);
        begin = temp.begin();
        end = temp.end();
        assert(begin <= end);
    }
    IPRange(const uint32_t _begin, const uint32_t _end) : begin(_begin), end(_end) {
    }
};


inline bool operator==(const  IPRange& lhs, const  IPRange& rhs) {
    return lhs.begin == rhs.begin and lhs.end == rhs.end;
}

inline bool operator<(const  IPRange& lhs, const  IPRange& rhs) {
    if (lhs.begin == rhs.begin)
        return lhs.end < rhs.end;
    else
        return lhs.begin < rhs.begin;
}

std::ostream& operator<<(std::ostream& out, const IPRange& r){
    out << "[" << IPv4Prefix{r.begin,32} << ", " << IPv4Prefix{r.end,32} << "]";
    return out;
}

class IPRangeFeature : public Feature<IPRange> {
public:
    IPRange join(const IPRange& l1, const IPRange& l2){
        return {std::min(l1.begin, l2.begin), std::max(l1.end, l2.end)};
    }

    std::optional<IPRange> meet(const IPRange& l1, const IPRange& l2){
        if (l1.end < l2.begin or l2.end < l1.begin)
            return std::nullopt;
        else
            return IPRange{std::max(l1.begin, l2.begin), std::min(l1.end, l2.end)};
    }

    Cost cost(const IPRange& l){
        return l.end - l.begin + 1ULL;
    }

    IPRange top(){
        return {std::numeric_limits<uint32_t>::min(), std::numeric_limits<uint32_t>::max()};
    }

    DEFAULT_CJOIN(IPRange)
    DEFAULT_SUBSET(IPRange)
};


template<typename ...Args>
using Tuple = std::tuple<Args...>;

template<typename ...Args>
std::ostream& operator<<(std::ostream& out, const Tuple<Args...>& t){
    out << "[";
    std::apply([&out](auto&&... x) {((out << x << ","), ...);}, t);
    out << "]";
    return out;
}

template<typename Types, typename ...Args>
class TupleFeature {};


template<typename ...Types, typename ...Args>
class TupleFeature<std::tuple<Types...>, Tuple<Args...>> : public Feature<Tuple<Args...>> {
public:
    std::tuple<Types...>& features;

    TupleFeature(std::tuple<Types...>& _features) : features(_features) { }

    Tuple<Args...> join(const Tuple<Args...>& l1, const Tuple<Args...>& l2) {
        auto out = std::apply([&](auto&&... x){
            return std::apply([&](auto&&... y){
                return std::apply([&](auto&&... f){
                    return std::make_tuple(f.join(x,y) ...);
                }, features);
            }, l1);
        }, l2);
        return out;
    }

    std::optional<Tuple<Args...>> meet(const Tuple<Args...>& l1, const Tuple<Args...>& l2){

        auto out = std::apply([&](auto&&... x){
            return std::apply([&](auto&&... y){
                return std::apply([&](auto&&... f){
                    return std::make_tuple(f.meet(x,y) ...);
                }, features);
            }, l1);
        }, l2);

        auto non_empty = std::apply([](auto&&... x) {
            return (x.has_value() and ...);
        } , out);

        if (not non_empty)
            return std::nullopt;

        auto ret = std::optional<Tuple<Args...>>(
                std::apply([](auto ...x) {
                    return std::make_tuple(x.value() ...);
                } , out));

        return ret;
    }


    Cost cost(const Tuple<Args...>& l){
        return std::apply([&](auto&&... x) {
            return std::apply([&](auto&&... f) {
                return (f.cost(x) * ...);
            }, features);
        }, l);
    }

    Tuple<Args...> top(){
        return std::apply([&](auto&&... f) {
            return std::make_tuple(f.top() ...);
        }, features);
    }

    DEFAULT_CJOIN(Tuple<Args...>)
    DEFAULT_SUBSET(Tuple<Args...>)
};





#endif /* FEATURE_H_ */
