/*
 * Index.h
 *
 *  Created on: Aug 26, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */

#ifndef INDEX_H_
#define INDEX_H_

#include <vector>
#include <type_traits>
#include <cmath>
#include <queue>
#include "Feature.h"
#include "ctpl_stl.h"

template<typename Key, typename Value>
class Index {
public:
    void insert(const Key& key, const Value& value);
    void get_subsets(const Key& key);
    void remote_subsets(const Key& key);
};


#define KEEP_PARENT

template<typename Key, typename Value>
struct RTreeNode {
    //static_assert(std::is_base_of<CostLabel, Key>::value, "Key must be a CostLabel");
    bool is_leaf = true;
    Key bounding_box;
    std::vector<RTreeNode*> children;
    std::vector<std::pair<Key,Value>> objects;
#ifdef KEEP_PARENT
    RTreeNode* parent = nullptr;
#endif

    RTreeNode(const Key& bounding_box) : bounding_box(bounding_box) {
    }

    std::size_t size() const {
        if (is_leaf)
            return objects.size();
        else
            return children.size();
    }

    const Key& get_bb_at(std::size_t pos) {
        if (is_leaf)
            return objects[pos].first;
        else
            return children[pos]->bounding_box;
    }
};

template<typename Feature, typename Key, typename Value>
class RTreeIndex;

template<typename Feature, typename Key, typename Value>
void  execute_remove_under_subset_parallel(int id, RTreeIndex<Feature, Key, Value>* index, const Key& key, RTreeNode<Key, Value>* node, std::vector<Value>& removed, ctpl::thread_pool& pool, int level, std::set<std::pair<int,RTreeNode<Key, Value>*>>& post_set){
    index->remove_subset_under_parallel(key, node, removed, pool, level, post_set);
}


template<typename Feature, typename Key, typename Value>
class RTreeIndex : public Index<Key, Value> {
    using RTreeNodeT = RTreeNode<Key,Value>;
    using LevelNodeSet = std::set<std::pair<int,RTreeNodeT*>>;
    friend void execute_remove_under_subset_parallel<Feature,Key,Value>(int id, RTreeIndex<Feature, Key, Value>* index, const Key& key, RTreeNode<Key, Value>* node, std::vector<Value>& removed, ctpl::thread_pool& pool, int level, std::set<std::pair<int,RTreeNode<Key, Value>*>>& post_set);
private:
    Feature& feature;
    int node_min_size, node_max_size;
    RTreeNodeT* root;

//    RTreeNodeT* insert_under(const Key& key, const Value& value, RTreeNodeT* node);
//    RTreeNodeT* split_node(RTreeNodeT* node);
public:
    RTreeIndex(Feature& _feature, int _node_min_size = 2, int _node_max_size = 5) :
        feature(_feature),
        node_min_size(_node_min_size),
        node_max_size(_node_max_size) {
                root = new RTreeNodeT{{feature.cost(feature.top()),feature.top()}};
        }

    void insert(const Key& key, const Value& value) {
        auto new_child = insert_under(key, value, root);
        if (new_child) {
            auto new_root = new RTreeNodeT(feature.cjoin(
                    root->bounding_box.label,
                    new_child->bounding_box.label));
            new_root->is_leaf = false;
            new_root->children.emplace_back(root);
            new_root->children.emplace_back(new_child);
            root = new_root;
#ifdef KEEP_PARENT
            set_children_parent(new_root);
#endif
        }
    }

    std::vector<Value> get_subset(const Key& key) {
        std::vector<Value> ret;

        if (root->size() > 0) {
            get_subset_under(key, root, ret);
        }
        return ret;
    }

    std::vector<Value> remove_subset(const Key& key){
        std::vector<Value> ret;

        if (root->size() > 0) {
            remove_subset_under(key, root, ret);
            if (root->size() == 0) {
                root->bounding_box = {feature.cost(feature.top()),feature.top()};
                root->is_leaf = true;
            }
        }

        return ret;
    }

    std::vector<Value> remove_subset_parallel(const Key& key, ctpl::thread_pool& pool){
            std::vector<Value> ret;

            if (root->size() > 0) {
                LevelNodeSet post_set;


                pool.push(execute_remove_under_subset_parallel<Feature,Key,Value>,
                        this, std::ref(key), root, std::ref(ret), std::ref(pool), 0, std::ref(post_set));

                pool.wait();


                // delete empty nodes

                while (not post_set.empty()){
                    int level;
                    RTreeNodeT* node;
                    std::tie(level, node) = *(std::prev(post_set.end()));
                    //const auto [level, node] = *(post_set.end()-1); Eclipse can't handle it
                    post_set.erase(std::prev(post_set.end()));
                    //std::cout << "post processing " << level << " " << node << std::endl;
                    if (node == nullptr) {
                        assert(level == - 1);
                        continue;
                    }
                    assert(node == root or not node->is_leaf);
                    assert(level >= 0);


                    decltype(node->children) remaining_children;
                    for (const auto& c : node->children) {
                       if (c->size() > 0) {
                           remaining_children.emplace_back(c);
                       }
                    }
                    node->children = remaining_children;
                    if (remaining_children.empty()) {
                       if (level == 0) {
                           assert(node == root);
                       } else {
                           assert(node->parent != nullptr);
                           post_set.emplace(level - 1, node->parent);
                       }
                    } else {
                       node->bounding_box = node->get_bb_at(0);
                       for (auto i = 1; i < node->size(); i++) {
                           node->bounding_box = feature.cjoin(node->bounding_box.label, node->get_bb_at(i).label);
                       }
                    }
                }

                if (root->size() == 0) {
                    root->bounding_box = {feature.cost(feature.top()),feature.top()};
                    root->is_leaf = true;
                }
            }

            return ret;
    }



    void print_index(std::ostream& out, int level_limit = 0, int level = 0, RTreeNodeT* node = nullptr) {
        if (level_limit > 0 and level > level_limit)
            return;
        if (not node) {
            print_index(out, level_limit, 0, root);
        } else {
            for (auto i = 0; i < level; i++) { out << "--"; }
            out << " " << node->bounding_box << std::endl;
            if (node->is_leaf){
                for (const auto& o : node->objects) {
                    for (auto i = 0; i < level + 1; i++) { out << "--"; }
                    out << o.first << " " << o.second << std::endl;
                }
            } else {
                for (const auto c : node->children)
                    print_index(out, level_limit, level + 1, c);
            }
        }
    }

    template <typename KeySerializer>
    void serialize(std::istream& out, KeySerializer& serializer) {
        serialize(out, root, serializer);
    }

    template <typename KeyDeserializer>
    void deserialize(std::istream& out, KeyDeserializer& deserializer) {
        deserialize(out, root, deserializer);
    }

    template <typename KeySerializer>
    void serialize(std::ostream& out, RTreeNodeT* node, KeySerializer& serializer) {
        out << node->is_leaf <<  " " << node->size() << " ";
        if (node->is_leaf) {
            for (const auto& o : node->objects) {
                serializer.serialize(o.key);
                out << " ";
            }
            out << "\n";
        } else {
            out << "\n";
            for (const auto& c : node->children) {
                serialize(out, c, serializer);
            }
        }
    }

    template <typename KeyDeserializer>
    void deserialize(std::istream& in, RTreeNodeT* node, KeyDeserializer& deserializer) {
        int n;
        in >> node->is_leaf >> n;
        if (node->is_leaf) {
            for (auto i = 0; i < n; i++){
                const auto key = deserializer(in);
                Value value;
                in >> value;
                node->objects.emplace_back(key, value);
            }
        } else {
            for (auto i = 0; i < n; i++){
                node->children.emplace_back(new RTreeNodeT{{feature.cost(feature.top()),feature.top()}});
                deserialize(in, node->children.back(), deserializer);
            }
        }

        node->bounding_box = node->get_bb_at(0);
        for (auto i = 1; i < n; i++){
            node->bounding_box = feature.cjoin(node->bounding_box, node->get_bb_at(i));
        }
    }

    struct NNEntry {
       Cost dist;
       Key joined;
       RTreeNodeT* node;
       std::optional<std::pair<Key, Value>> object;
       NNEntry(const Cost _dist, const Key& _joined, RTreeNodeT* _node, const decltype(object)& _object) :
           dist(_dist),
           joined(_joined),
           node(_node),
           object(_object) {

       }

    };

    struct NNEntryCmp {
        bool operator()(const NNEntry&a, const NNEntry& b) {
            if (std::abs(a.dist - b.dist) < 1e-10){
                return a.joined.cost > b.joined.cost;
            } else {
                return a.dist > b.dist;
            }
        }
    };


    std::vector<NNEntry> get_knn_approx(const Key& key, int k = 2) {
//        std::cout << "knn for " << key << std::endl;
        std::vector<NNEntry> ret;

        std::priority_queue<NNEntry, std::vector<NNEntry>, NNEntryCmp> pq;

        {
            const auto joined = feature.cjoin(root->bounding_box.label, key.label);
            const auto dist = joined.cost - root->bounding_box.cost - key.cost;
            pq.emplace(dist, joined, root, std::nullopt);
        }

        while (not pq.empty() and ret.size() < k) {
            const auto entry = pq.top();
            pq.pop();

//            std::cout << "entry is dist:" << entry.dist << " joined:" << entry.joined << " ";
//            if (entry.node == nullptr) {
//                std::cout << "object " << entry.object->first << " " << entry.object->second;
//            } else {
//                std::cout << "node " << entry.node->bounding_box;
//            }
//            std::cout << std::endl;

            if (entry.node) {
                for (auto i = 0; i < entry.node->size(); i++){
                    const auto& bb = entry.node->get_bb_at(i);
                    const auto joined = feature.cjoin(bb.label, key.label);
                    const auto dist = joined.cost - bb.cost - key.cost;
                    if (entry.node->is_leaf) {
                        pq.emplace(dist, joined, nullptr, entry.node->objects[i]);
                    } else {
                        pq.emplace(dist, joined, entry.node->children[i], std::nullopt);
                    }
                }
            } else {
                ret.emplace_back(entry);
            }
        }

        return ret;
    }

private:

    //TODO: delete nodes (note that also used in get_subsets)
    void get_values_in_subtree(RTreeNodeT* node, std::vector<Value>& acc) {
        if (node->is_leaf) {
            for (const auto& o : node->objects) {
                acc.emplace_back(o.second);
            }
        } else {
            for (const auto& c : node->children) {
                get_values_in_subtree(c, acc);
            }
        }
    }

    //TODO: delete nodes
    void get_values_in_subtree_parallel(RTreeNodeT* node, std::vector<Value>& acc) {
        if (node->is_leaf) {
            lock.lock();
            for (const auto& o : node->objects) {
                acc.emplace_back(o.second);
            }
            lock.unlock();
        } else {
            for (const auto& c : node->children) {
                get_values_in_subtree_parallel(c, acc);
            }
        }
    }




    std::mutex lock;
    std::vector<std::future<void>> futures;
    void remove_subset_under_parallel(const Key& key, RTreeNodeT* node, std::vector<Value>& removed, ctpl::thread_pool& pool, int level, LevelNodeSet& post_set) {
        if (feature.subset(node->bounding_box.label, key.label)){
            get_values_in_subtree_parallel(node, removed);
            node->children.clear();
            node->objects.clear();
            lock.lock();
            post_set.emplace(level - 1, node->parent);
            lock.unlock();
        } else {
            if (node->is_leaf) {
                decltype(node->objects) remaining_objects;
                for (const auto& o : node->objects){
                    if (not feature.subset(o.first.label, key.label)) {
                        remaining_objects.emplace_back(o);
                    } else {
                        lock.lock();
                        removed.emplace_back(o.second);
                        lock.unlock();
                    }
                }
                node->objects = remaining_objects;
                if (remaining_objects.empty()) {
                    lock.lock();
                    post_set.emplace(level - 1, node->parent);
                    lock.unlock();
                }
            } else {
                decltype(node->children) remaining_children;

                for (const auto& c : node->children){
                    if (feature.meet(c->bounding_box.label, key.label).has_value()) {
                        pool.push(execute_remove_under_subset_parallel<Feature,Key,Value>,
                                this, std::ref(key), c, std::ref(removed), std::ref(pool), level + 1, std::ref(post_set));
                    }
                }
            }

        }

    }

    void remove_subset_under(const Key& key, RTreeNodeT* node, std::vector<Value>& removed) {
        //std::cout << "remove_subset of " << key << "  at node " << node << " " << node->bounding_box << " leaf?" << node->is_leaf << std::endl;

        if (feature.subset(node->bounding_box.label, key.label)){
            get_values_in_subtree(node, removed);
            node->children.clear();
            node->objects.clear();
        } else {
            if (node->is_leaf) {
                decltype(node->objects) remaining_objects;
                for (const auto& o : node->objects){
                    if (not feature.subset(o.first.label, key.label)) {
                        //std::cout << o.first.label << " is NOT a subset of " << key.label << std::endl;
                        remaining_objects.emplace_back(o);
                    } else {
                        //std::cout << o.first.label << " IS a subset of " << key.label << std::endl;
                        removed.emplace_back(o.second);
                    }
                }
                node->objects = remaining_objects;
            } else {
                decltype(node->children) remaining_children;

                for (const auto& c : node->children){
                    if (feature.meet(c->bounding_box.label, key.label).has_value()) {
                        //std::cout << c->bounding_box << " meets " << key.label << std::endl;
                        remove_subset_under(key, c, removed);
                        if (c->size() == 0) {
                            delete c;
                        } else {
                            remaining_children.emplace_back(c);
                        }
                    } else {
                        //std::cout << c->bounding_box << " does NOT meet " << key.label << std::endl;
                        remaining_children.emplace_back(c);
                    }
                }
                node->children = remaining_children;
            }

            if (node != root)
                assert(node->size() > 0);
            // ? TODO
            node->bounding_box = node->get_bb_at(0);
            for (auto i = 1; i < node->size(); i++) {
                node->bounding_box = feature.cjoin(node->bounding_box.label, node->get_bb_at(i).label);
            }

        }

    }

    void get_subset_under(const Key& key, RTreeNodeT* node, std::vector<Value>& acc) {
        //std::cout << "get_subset_under of " << key << "  at node " << node << " " << node->bounding_box << " leaf?" << node->is_leaf << std::endl;

        if (feature.subset(node->bounding_box.label, key.label)){
            get_values_in_subtree(node, acc);
        } else {
            if (node->is_leaf) {
                decltype(node->objects) remaining_objects;
                for (const auto& o : node->objects){
                    if (feature.subset(o.first.label, key.label)) {
                        acc.emplace_back(o.second);
                    }
                }
            } else {
                for (const auto& c : node->children){
                    if (feature.meet(c->bounding_box.label, key.label).has_value()) {
                        get_subset_under(key, c, acc);
                    }
                }
            }
        }
    }

    RTreeNodeT* insert_under(const Key& key, const Value& value, RTreeNodeT* node) {
        //std::cout << "inserting " << key << " " << value << " under " << node << " " << node->bounding_box << " leaf:" << node->is_leaf << " children:" << node->children.size() << " obj"  << node->objects.size() << std::endl;

        node->bounding_box = feature.cjoin(node->bounding_box.label, key.label);

        if (node->is_leaf) {
            node->objects.emplace_back(key, value);
        } else {

            struct Entry {
                Cost diff;
                Key joined;
                std::size_t pos;
            };

            std::optional<Entry> best;

            for (std::size_t i = 0; i < node->children.size(); i++) {
                const auto& c = node->children[i];
                const auto joined = feature.cjoin(c->bounding_box.label, key.label);
                const auto diff = joined.cost - c->bounding_box.cost;

                if (not best.has_value() or diff < best->diff or
                        (std::abs(diff - best->diff) < 1e-10 and joined.cost < best->joined.cost)){
                    best.emplace(Entry{diff, joined, i});
                }
            }

            assert(best.has_value());

            auto new_child = insert_under(key, value, node->children[best.value().pos]);

            if (new_child) {
#ifdef KEEP_PARENT
                new_child->parent = node;
#endif
                node->children.insert(
                        node->children.begin () + best->pos + 1,
                        new_child);
            }
        }

        return split_node(node);
    }

    RTreeNodeT* split_node(RTreeNodeT* node) {
        if (node->size() <= node_max_size) {
            return nullptr;
        } else {
            struct Entry {
                Cost dist;
                std::size_t a;
                std::size_t b;
            };

            const auto n = node->size();
            std::optional<Entry> max_dist;
            for (std::size_t i = 0; i < n; i++){
                for (std::size_t j = i + 1; j < n; j++){
                    const auto join = feature.cjoin(node->get_bb_at(i).label, node->get_bb_at(j).label);
                    if (not max_dist.has_value() or join.cost > max_dist->dist){
                        max_dist.emplace(Entry{join.cost, i, j});
                    }
                }
            }

            assert(max_dist.has_value());
            const auto a = max_dist->a, b = max_dist->b;
            std::vector<RTreeNodeT*> children[2];
            std::vector<std::pair<Key,Value>> objects[2];
            Key bounding_boxes[2] = {node->get_bb_at(a), node->get_bb_at(b)};

            if (node->is_leaf) {
                objects[0].emplace_back(node->objects[a]);
                objects[1].emplace_back(node->objects[b]);
            } else {
                children[0].emplace_back(node->children[a]);
                children[1].emplace_back(node->children[b]);
            }

            auto get_group_size = [&](const auto g) {
                return node->is_leaf ? objects[g].size() : children[g].size();
            };

            //std::cout << "max_dist is between " << node->get_bb_at(a) << " " << node->get_bb_at(b) << std::endl;


            int g;
            //std::cout << "n is " << n << std::endl;
            for (auto i = 0; i < n; i++) {
                if (i == a or i == b){
                    //std::cout << "adding by definition\n";
                    continue;
                } else if ((int)get_group_size(0) <= (int)node_min_size - (int)(n - i - (i < a ? 1 : 0) - (i < b ? 1 : 0))){
                    //std::cout <<  "adding to 0 because of min_size\n";
                    g = 0;
                } else if ((int)get_group_size(1) <= (int)node_min_size - (int)(n - i - (i < a ? 1 : 0) - (i < b ? 1 : 0))){
                    //std::cout << "adding to 1 because of min_size\n";
                    g = 1;
                } else {
                    // 1- smallest increase in area
                    // 2- smallest area
                    // 3- smallest number of entries

                    const Key joined[2] = {
                      feature.cjoin(node->get_bb_at(i).label, bounding_boxes[0].label),
                      feature.cjoin(node->get_bb_at(i).label, bounding_boxes[1].label)
                    };

                    const Cost diff[2] = {
                      joined[0].cost - bounding_boxes[0].cost,
                      joined[1].cost - bounding_boxes[1].cost,
                    };

                    if (std::abs(diff[0] - diff[1]) > 1e-10) {
                      g =  diff[0] < diff[1] ? 0 : 1;
                      //std::cout <<  "adding to" << g << "because of diff\n";
                    } else if (std::abs(joined[0].cost - joined[1].cost) > 1e-10) {
                      g = joined[0].cost < joined[1].cost ? 0 : 1;
                      //std::cout <<  "adding to" << g << "because of cost\n";
                    } else {
                      g = get_group_size(0) < get_group_size(1) ? 0 : 1;
                      //std::cout <<  "adding to" << g << "because of len\n";
                    }
                }

                if (node->is_leaf) {
                    objects[g].emplace_back(node->objects[i]);
                } else {
                    children[g].emplace_back(node->children[i]);
                }
                bounding_boxes[g] = feature.cjoin(bounding_boxes[g].label, node->get_bb_at(i).label);
            }

            {
                const std::size_t size[2] = {
                        node->is_leaf ? objects[0].size() : children[0].size(),
                        node->is_leaf ? objects[1].size() : children[1].size(),
                };
                assert(size[0] >= node_min_size and size[0] <= node_max_size);
                assert(size[1] >= node_min_size and size[1] <= node_max_size);
                assert(size[0] + size[1] == n);
            }

            node->objects = objects[0];
            node->children = children[0];
            node->bounding_box = bounding_boxes[0];

            RTreeNodeT* new_node = new RTreeNodeT(bounding_boxes[1]);
            new_node->objects = objects[1];
            new_node->children = children[1];
            new_node->is_leaf = node->is_leaf;
#ifdef KEEP_PARENT
            set_children_parent(new_node);
#endif

            return new_node;
        }
    }

#ifdef KEEP_PARENT
    inline void set_children_parent(RTreeNodeT* node) {
        for (const auto& c : node->children) {
            c->parent = node;
        }
    }
#endif

};






#endif /* INDEX_H_ */
