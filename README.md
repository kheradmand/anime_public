# Automatic Network Intent Miner (Anime)

Anime is a framework and a prototype tool to infer high-level networking intents by mining the comonality among low-level forwarding behavior.

You can checkout the following resource for more information about the work:
- Automatic Inference of High-Level Network Intents by Mining Forwarding Patterns (SOSR'20)
    - [paper](http://kheradmand.web.illinois.edu/papers/anime-sosr20.pdf)
    - [slides](http://kheradmand.web.illinois.edu/slides/Anime_SOSR20_final.pdf)
    - [presentation](https://www.youtube.com/watch?v=slDamPr_l8E&feature=youtu.be)
    
You may also learn about the latest developments, including optimizations and use of the tool for anomaly detection through the following technical report:
- A Framework for Mining High-Level Intents from Low-Level Network Behavior
    - [working draft](http://kheradmand.web.illinois.edu/papers/Anime-working-draft-Oct2-2020.pdf)


### Using Anime

You first need to encode your forwarding behavior in form of a list of features. For example (dstIP, src, dst). You also need to create appropriate feature types (called labeling in the code) and their instantiations. You can then pass the the behavior and the features to the clustering algorithm to infer intents. Checkout [experiments/hre-cli/hre_cli.py](experiments/hre-cli/hre_cli.py) for an example usage of the framework. Anime is also being reimplemented in C++. Checkout [cpp/cites.cpp](cpp/cites.cpp) for an example. 
