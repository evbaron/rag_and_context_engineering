# Frontier (supercomputer)

## Infobox

- **Active:** Deployment: Sep. 2021 Completion: May 2022
- **Operators:** Oak Ridge National Laboratory and U.S. Department of Energy
- **Location:** Oak Ridge Leadership Computing Facility
- **Power:** 24.6 MW [ 1 ]
- **Operating system:** HPE Cray OS
- **Space:** 680 m 2 (7,300 ft 2 )
- **Speed:** 1.353 exaFLOPS (Rmax) / 2.055 exaFLOPS (Rpeak) [ 1 ]
- **Cost:** US$600 million (est.)
- **Ranking:** TOP500: 2, June 2025
- **Purpose:** Scientific research and development
- **Website:** www.olcf.ornl.gov /frontier /

For other uses, see [Frontier (disambiguation)](/wiki/Frontier_(disambiguation)).

**Hewlett Packard Enterprise Frontier**, or **OLCF-5**, is the world's first [exascale](/wiki/Exascale_computing) [supercomputer](/wiki/Supercomputer). It is hosted at the [Oak Ridge Leadership Computing Facility](/wiki/Oak_Ridge_Leadership_Computing_Facility) (OLCF) in [Tennessee](/wiki/Tennessee), United States, and became operational in 2022. As of November 2024, Frontier is the [third fastest supercomputer in the world](/wiki/TOP500). It is based on the [Cray EX](/wiki/Cray) and is the successor to [Summit](/wiki/Summit_(supercomputer)) (OLCF-4). Frontier achieved an [Rmax](/wiki/LINPACK_benchmarks#HPLinpack) of 1.102 [exaFLOPS](/wiki/FLOPS), which is 1.102 quintillion [floating-point operations](/wiki/Floating-point_operation) per second, using [AMD](/wiki/AMD) [CPUs](/wiki/CPU) and [GPUs](/wiki/GPU).

Measured at 62.86 gigaflops/watt, the smaller **Frontier TDS** (test and development system) topped the [Green500](/wiki/Green500) list for most efficient supercomputer until it was dethroned in efficiency by the [Flatiron Institute](/wiki/Flatiron_Institute)'s Henri supercomputer in November 2022.

Frontier was superseded as the fastest supercomputer in the world by [El Capitan](/wiki/El_Capitan_(supercomputer)) in November 2024.

## Design

Frontier uses 9,472 [AMD Epyc 7713 "Trento"](/wiki/Epyc#Third_generation_Epyc_(Milan)) 64 core 2 GHz CPUs (606,208 cores) and 37,888 [Instinct](/wiki/AMD_Instinct) MI250X GPUs (8,335,360 cores). They can perform [double-precision](/wiki/Double-precision_floating-point_format) operations at the same speed as single precision.

"Trento" is an optimized third-generation [EPYC](/wiki/EPYC) CPU ("Milan"), which is based on the [Zen 3](/wiki/Zen_3) [microarchitecture](/wiki/Microarchitecture).

It occupies 74 19-inch (48 cm) rack cabinets. Each cabinet hosts 64 [blades](/wiki/Blade_server), each consisting of 2 nodes.

Blades are interconnected by HPE Slingshot 64-port switches that provides 12.8 terabits/second of bandwidth. Groups of blades are linked in a dragonfly topology with at most three hops between any two nodes. Cabling is either optical or copper, customized to minimize cable length. Total cabling runs 145 km (90 mi). Frontier is liquid-cooled by 4 350-horsepower pumps, which flow around 6,000 gallons (22,712.47 Liters) of non-pre chilled water through the system each minute, allowing 5x the density of air-cooled architectures.

Each node consists of one CPU, 4 GPUs and 4 terabytes of flash memory. Each GPU has 128 GB of RAM soldered onto it, and each CPU has 512GB of local DDR4 memory. Each GPU has an idle power of about 100 W and a thermal design power (TDP) of about 500 W and 560 W at peak.

Frontier has coherent interconnects between CPUs and GPUs, allowing GPU memory to be accessed coherently by code running on the Epyc CPUs.

Frontier uses an internal 75 TB/s read / 35 TB/s write / 15 billion IOPS flash storage system, along with the 700 PB Orion site-wide [Lustre](/wiki/Lustre_(file_system)) [filesystem](/wiki/File_system).

Frontier consumes around 21 megawatts (MW) (which is equivalent to the power needed for 15,000 single-family homes), compared to its predecessor [Summit](/wiki/Summit_(supercomputer))'s 13 MW.

## History

One of the largest challenges during development was power consumption. Existing information pointed to hundreds of thousands of GPUs being necessary to achieve 1 exaFLOP, with a total power consumption of 150-500 MW. Thus, high efficiency was a primary target of the project.

Oak Ridge partnered with HPE Cray and AMD to build the system at a cost of US$600 million. It began deployment in 2021 and reached full capability in 2022. It clocked 1.1 exaflops Rmax in May 2022, making it the world's fastest supercomputer as measured in the June 2022 edition of the [TOP500](/wiki/TOP500) list, replacing [Fugaku](/wiki/Fugaku_(supercomputer)).

Upon its release, the supercomputer topped the [Green500](/wiki/Green500) list for most efficient supercomputer, measured at 62.68 gigaflops/watt. ORNL Director Thomas Zacharia declared, "Frontier is ushering in a new era of exascale computing to solve the world’s biggest scientific challenges." He added, "This milestone offers just a preview of Frontier’s unmatched capability as a tool for scientific discovery. It is the result of more than a decade of collaboration among the national laboratories, academia and private industry, including DOE's Exascale Computing Project, which is deploying the applications, software technologies, hardware and integration necessary to ensure impact at the exascale."

## See also

- [List of the top supercomputers in the United States](/wiki/List_of_the_top_supercomputers_in_the_United_States)

## References
