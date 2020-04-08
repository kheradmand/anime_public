# Automatic Network Intent Miner (Anime)

Anime is a framework and a prototype tool to infer high-level networking intents by mining the comonality among low-level forwarding behavior.

For a high level overview of Anime you may checkout the following resource:
- Automatic Inference of High-Level Network Intents by Mining Forwarding Patterns (SOSR'20)
    - [paper](http://kheradmand.web.illinois.edu/papers/anime-sosr20.pdf)
    - [slides](http://kheradmand.web.illinois.edu/slides/Anime_SOSR20_final.pdf)
    - [presentation](https://www.youtube.com/watch?v=slDamPr_l8E&feature=youtu.be)


### Using Anime

You first need to encode your fowarding in form of a list of features. For example (dstIP, src, dst). You also need to create a appropriate feature types and their instantiations. You can then pass the the behavior and the features to the clustering algorithm to infer intents. See experiments/hre-cli/hre_cli.py for an example usage of the framework.