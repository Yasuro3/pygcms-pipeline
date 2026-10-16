# Sulfur-containing / sulfurization-associated class (S)

PyGCMS Pipeline v1.3.2 / ClassificationModelVersion 2.1.0 adds a separate **S** application-layer class. The purpose is to prevent sulfur-bearing pyrolysis products from being merged into the N-containing/protein/microbial **P** class and to permit a separate sulfur-product fraction to be evaluated in strongly reducing, anoxic or sulfidic samples.

## What enters S

Name-based rules include thiophene and alkylthiophenes, benzothiophene and alkylbenzothiophenes, dibenzothiophenes, thiols/mercaptans, sulfides/disulfides/polysulfides, thiazoles/benzothiazoles, isothiocyanates/thiocyanates, sulfoxides and sulfones. Formula-only candidates containing sulfur also fall back to S at low confidence. N+S compounds remain S for sulfur accounting but are flagged as mixed N/S.

## Interpretation

S is an **operational compositional/process-associated class**, not a confirmed source apportionment. Sulfur-containing pyrolysis products can reflect organically bound sulfur and early-diagenetic sulfurization; alkylthiophenes have been used in studies of sulfur uptake during sulfate reduction. Laboratory experiments also show that sulfurized carbohydrates yield alkylthiophenes on flash pyrolysis. However, alkylthiophenes can also form during pyrolysis when elemental sulfur reacts with unsaturated lipids. Therefore S alone must not be interpreted as proof of anoxia, sulfate reduction, or in-situ sulfurization.

For environmental interpretation, combine the S fraction with independent evidence where available (for example porewater sulfide/sulfate, Fe speciation, total/organic sulfur, redox conditions, mineralogy, and depth trends).

## Core literature provenance

- Sinninghe Damsté et al. (1989), *Geochimica et Cosmochimica Acta* 53, 873–889. DOI 10.1016/0016-7037(89)90032-X.
- Eglinton et al. (1992), *Geochimica et Cosmochimica Acta* 56, 1545–1560. DOI 10.1016/0016-7037(92)90224-7.
- Lückge et al. (2002), *Organic Geochemistry* 33, 477–488. DOI 10.1016/S0146-6380(01)00171-1.
- Kok et al. (2000), *Geochimica et Cosmochimica Acta* 64, 2689–2699. DOI 10.1016/S0016-7037(00)00382-3.
- van Dongen et al. (2003), *Organic Geochemistry* 34, 1129–1144. DOI 10.1016/S0146-6380(03)00060-3.
- Saiz-Jimenez (1995), *Organic Geochemistry* 23, 81–85. DOI 10.1016/0146-6380(94)00102-7.
- Eglinton et al. (1990), *Fuel* 69, 1394–1404. DOI 10.1016/0016-2361(90)90121-6.

The machine-readable citations and sulfur rules are archived in `provenance/literature_sources.csv` and `provenance/literature_classification_rules.csv`.
