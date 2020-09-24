/*
 * Argument.h
 *
 *  Created on: Sep 4, 2020
 *      Author: ali
 */

#ifndef ARGS_H_
#define ARGS_H_

#include "CLI11.hpp"

class Args {
private:
    static Args* _instance;
public:
    static Args& get() {
        if (not _instance)
            _instance = new Args();
        return *_instance;
    }


    std::string device_file = "in/cites-ip-src-dst/icyt-nondrop/devices.txt";
    std::string flows_file = "in/cites-ip-src-dst/icyt-nondrop/flows.txt";

    bool multithreaded_init = true;
    bool multithreaded_index_remove = false;
    int threads = 0;

    std::string out = "tmp/";
    bool hr_clusters = true;
    bool override = false;


    bool eval_real_tp = false;
    bool eval_partial_obs = false;

    int eval_k = -1;
    int xml_k = -1;
    int xml_depth_limit = -1;
    bool aug_xml = false;

    int write_impr_limit = -1;

    bool index = true;


    int parse_cli(int argc, char** argv) {
        CLI::App app{"CITES"};

        app.add_option("--devices", device_file, "Device file");
        app.add_option("--flows", flows_file, "Flows file");
        app.add_option("--threads", threads, "Number of threads in init phase");
        app.add_option("--out", out, "Out folder");

        app.add_flag("!--no-parallel-init", multithreaded_init, "No parallel init");
        app.add_flag("--parallel-index-remove", multithreaded_index_remove, "Parallel index remove");
        app.add_flag("!--no-hr-cluster", hr_clusters, "No Human readable clusters");
        app.add_flag("!--no-index", index, "Do not use index during clustering");
        app.add_flag("--override", override, "Override");
        app.add_flag("--aug-xml", aug_xml, "Augmented XML");

        app.add_flag("--eval-real-tp", eval_real_tp, "Evaluate real true positive in per cluster evaluation");

        app.add_flag("--eval-partial-obs", eval_partial_obs, "Evaluate partial observation rather than summarization");

        app.add_option("--eval-k", eval_k, "Evaluate the clusters of a single k");
        app.add_option("--xml-k", xml_k, "Write clusters in XML format with clusters at k as root");
        app.add_option("--xml-depth-limit", xml_depth_limit, "XML depth limit");

        app.add_option("--write-impr-limit", write_impr_limit, "Lower bound for writing imprecise (i.e precision < 1) clusters");



        CLI11_PARSE(app, argc, argv);

        return 0;
    }

};


Args* Args::_instance = nullptr;

#endif /* ARGS_H_ */
