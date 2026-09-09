# Assignment 1 Report

*AI Acknowledgement*: We used Claude in this assignment to assist with code reviews, merge conflicts, as well as generating code on the function level.

## 1 (c) Does distance relate to RTT?

Yes, RTT (especially min RTT) correlates strongly with distance. Close servers (Chicago, Washington, Toronto, <1000 km) had min RTTs of 9-31 ms; far ones (Kediri, Floreal, ~16,000 km) had 210-256 ms. Max RTT correlates much more weakly with distance, with several notable high outliers in the mid-range of distances, despite their associated min RTTs seeming "normal" relevant to the distance. This likely means that congestion/queuing along the path is more relevant than distance for RTTs. In one of the runs, Auckland (13,165 km) had almost no jitter between max / min RTTs (1.1 ms), while the much closer Winterthur (7,213 km) spiked to 664 ms.

## 2 (d) Explain your observations from these plots. How does hop count relate to RTT?

Hop count and RTT loosely correlate. Our shortest path (185.152.67.2, 15 hops) had the lowest RTT (61 ms) and our longest (105.235.237.2 and 103.146.200.98, 21-22 hops) had the highest (241-252 ms), but two destinations tied at 19 hops still differed by ~40 ms. The stacked bar chart shows most hops (local network, ISP) each add <10 ms, and total RTT is impacted most by one or two long-haul hops. For example, on the path to 103.146.200.98, hops 1-10 add ~15 ms combined, but the next hop alone adds 183 ms. So RTT depends more on where the slow backbone/transit hops are than on how many hops there are total.

