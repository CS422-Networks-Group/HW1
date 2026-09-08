# Assignment 1 Report

## 1 (c) Does distance relate to RTT?

Yes, RTT (especially min RTT) correlates strongly with distance. Close servers (Chicago, Washington, Toronto, <1000 km) had min RTTs of 9-31 ms; far ones (Kediri, Floreal, ~16,000 km) had 210-256 ms.

Max RTT correlates much more weakly with distance, with several notable high outliers in the mid-range of distances, despite their associated min RTTs seeming "normal" relevant to the distance. This likely means that congestion/queuing along the path is more relevant than distance for RTTs. In one of the runs, Auckland (13,165 km) had almost no jitter between max / min RTTs (1.1 ms), while the much closer Winterthur (7,213 km) spiked to 664 ms.

